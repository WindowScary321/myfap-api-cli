import base64
import hashlib
import math
import re
import secrets
import time
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

import jwt
import requests


ID_TOKEN_CLOCK_SKEW = 30.0


class OAuthError(Exception):
    def __init__(self, message, code="oauth", status_code=None):
        super().__init__(message)
        self.code = code
        self.status_code = status_code


class OIDCClient:
    def __init__(self, session, timeout=None, issuer=None, client_id=None, redirect_uri=None):
        self.session = session
        self.timeout = timeout if timeout is not None else 10
        self.issuer = issuer
        self.client_id = client_id
        self.redirect_uri = redirect_uri
        self._metadata = None
        self._used_states = set()
        self._used_codes = set()
        try:
            parsed = self._split_url(issuer)
            if parsed.scheme != "https" or not parsed.hostname or parsed.username is not None or parsed.password is not None or parsed.query or parsed.fragment:
                raise ValueError
            self._origin = (parsed.hostname, parsed.port or 443)
            self._redirect = self._split_url(redirect_uri)
            if not self._redirect.scheme or self._redirect.query or self._redirect.fragment or self._redirect.username is not None or self._redirect.password is not None:
                raise ValueError
        except (TypeError, ValueError):
            raise OAuthError("Cấu hình FEID hoặc URI callback không hợp lệ.", code="configuration") from None

    @staticmethod
    def _split_url(url):
        if not isinstance(url, str) or not url or any(character.isspace() or ord(character) < 32 for character in url) or "\\" in url:
            raise ValueError
        return urlsplit(url)

    def _trusted_endpoint(self, value):
        parsed = self._split_url(value)
        if parsed.scheme != "https" or (parsed.hostname, parsed.port or 443) != self._origin or parsed.username is not None or parsed.password is not None or parsed.fragment:
            raise ValueError
        return value

    def _get_json(self, url, code):
        try:
            result = self.session.get(url, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException:
            raise OAuthError("Không kết nối được FEID. Hãy thử lại sau.", code="network") from None
        if result.status_code != 200:
            raise OAuthError(f"FEID trả về HTTP {result.status_code}. Hãy thử lại sau.", code=code, status_code=result.status_code)
        try:
            data = result.json()
        except ValueError:
            raise OAuthError("FEID trả về JSON không hợp lệ.", code=code) from None
        if not isinstance(data, dict):
            raise OAuthError("FEID trả về dữ liệu không hợp lệ.", code=code)
        return data

    def discover(self):
        if self._metadata is not None:
            return self._metadata
        data = self._get_json(self.issuer.rstrip("/") + "/.well-known/openid-configuration", "discovery")
        try:
            if data.get("issuer") != self.issuer:
                raise ValueError
            for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
                self._trusted_endpoint(data[field])
            algorithms = data["id_token_signing_alg_values_supported"]
            if not isinstance(algorithms, list) or "RS256" not in algorithms:
                raise ValueError
            methods = data.get("code_challenge_methods_supported", ["S256"])
            if not isinstance(methods, list) or "S256" not in methods:
                raise ValueError
        except (KeyError, TypeError, ValueError):
            raise OAuthError("Metadata FEID không khớp cấu hình tin cậy hoặc không hỗ trợ RS256/PKCE S256.", code="discovery") from None
        self._metadata = data
        return data

    def begin_login(self):
        metadata = self.discover()
        verifier = secrets.token_urlsafe(48)
        challenge = base64.urlsafe_b64encode(hashlib.sha256(verifier.encode("ascii")).digest()).decode("ascii").rstrip("=")
        state, nonce = secrets.token_urlsafe(32), secrets.token_urlsafe(32)
        parameters = {
            "client_id": self.client_id, "redirect_uri": self.redirect_uri, "response_type": "code",
            "scope": "openid profile offline_access identity-service", "code_challenge": challenge,
            "code_challenge_method": "S256", "state": state, "nonce": nonce, "prompt": "login",
        }
        endpoint = urlsplit(metadata["authorization_endpoint"])
        try:
            existing = parse_qsl(endpoint.query, keep_blank_values=True, strict_parsing=True) if endpoint.query else []
            if any(key in parameters for key, _ in existing):
                raise ValueError
        except ValueError:
            raise OAuthError("Endpoint đăng nhập FEID có tham số không hợp lệ.", code="discovery") from None
        url = urlunsplit(endpoint._replace(query=urlencode(existing + list(parameters.items()))))
        return {"url": url, "code_verifier": verifier, "code_challenge": challenge, "state": state, "nonce": nonce}

    def parse_callback(self, url, attempt):
        try:
            parsed = self._split_url(url)
        except (TypeError, ValueError):
            raise OAuthError("URI callback FEID không hợp lệ.", code="callback") from None
        if parsed.scheme != self._redirect.scheme:
            return None
        if (parsed.netloc, parsed.path) != (self._redirect.netloc, self._redirect.path) or parsed.fragment:
            raise OAuthError("URI callback FEID không khớp cấu hình.", code="callback")
        try:
            if re.search(r"%(?![0-9a-fA-F]{2})", parsed.query):
                raise ValueError
            pairs = parse_qsl(parsed.query, keep_blank_values=True, strict_parsing=True, encoding="utf-8", errors="strict")
            parameters = dict(pairs)
            if len(parameters) != len(pairs):
                raise ValueError
            state = parameters.get("state", "")
            expected = attempt.get("state", "")
            if not state or not expected or not secrets.compare_digest(state.encode(), expected.encode()):
                raise ValueError
            if state in self._used_states:
                raise ValueError
            if "error" in parameters:
                if "code" in parameters or not parameters["error"]:
                    raise ValueError
                if parameters["error"] == "access_denied":
                    self._used_states.add(state)
                    raise OAuthError("Đăng nhập đã bị hủy.", code="access_denied")
                raise OAuthError("FEID từ chối đăng nhập. Hãy thử lại.", code="callback")
            code = parameters.get("code")
            if not code or code in self._used_codes:
                raise ValueError
            self._used_states.add(state)
            self._used_codes.add(code)
            return code
        except (TypeError, ValueError, UnicodeError, AttributeError):
            raise OAuthError("Callback FEID thiếu code hoặc có state/tham số không hợp lệ.", code="callback") from None

    def request_token(self, form):
        endpoint = self.discover()["token_endpoint"]
        try:
            result = self.session.post(endpoint, data=form, timeout=self.timeout, allow_redirects=False)
        except requests.RequestException:
            raise OAuthError("Không kết nối được FEID để lấy token. Hãy thử lại sau.", code="network") from None
        try:
            data = result.json()
        except ValueError:
            raise OAuthError("FEID trả về JSON token không hợp lệ.", code="token_response", status_code=result.status_code) from None
        if result.status_code != 200 or (isinstance(data, dict) and "error" in data):
            code = data.get("error") if isinstance(data, dict) else None
            if not isinstance(code, str) or code not in {"invalid_grant", "invalid_client", "invalid_request", "unauthorized_client", "unsupported_grant_type", "invalid_scope"}:
                code = "token_response"
            raise OAuthError(f"FEID không cấp token (HTTP {result.status_code}). Hãy thử lại hoặc đăng nhập lại.", code=code, status_code=result.status_code)
        if not isinstance(data, dict) or not isinstance(data.get("access_token"), str) or not data["access_token"].strip():
            raise OAuthError("FEID không trả về access token hợp lệ.", code="token_response")
        if "refresh_token" in data and (not isinstance(data["refresh_token"], str) or not data["refresh_token"].strip()):
            raise OAuthError("FEID trả về refresh token không hợp lệ.", code="token_response")
        return data

    def validate_tokens(self, response, nonce, expected_subject=None, refresh=False):
        if not isinstance(response, dict):
            raise OAuthError("FEID trả về token không hợp lệ.", code="token_response")
        if "token_type" in response and (not isinstance(response["token_type"], str) or response["token_type"].lower() != "bearer"):
            raise OAuthError("FEID trả về loại token không được hỗ trợ.", code="token_response")
        token = response.get("id_token")
        if "id_token" not in response and refresh:
            return None
        if not isinstance(token, str) or not token:
            raise OAuthError("FEID không trả về ID token để xác minh đăng nhập.", code="id_token")
        try:
            header = jwt.get_unverified_header(token)
            kid = header.get("kid")
            if header.get("alg") != "RS256" or not isinstance(kid, str) or not kid or any(name in header for name in ("jku", "jwk", "x5u", "crit")):
                raise ValueError
            jwks = self._get_json(self.discover()["jwks_uri"], "jwks")
            keys = jwks.get("keys")
            if not isinstance(keys, list):
                raise ValueError
            candidates = [key for key in keys if isinstance(key, dict) and key.get("kid") == kid]
            if len(candidates) != 1:
                raise ValueError
            key = candidates[0]
            if key.get("kty") != "RSA" or key.get("use", "sig") != "sig" or key.get("alg", "RS256") != "RS256" or "d" in key:
                raise ValueError
            if "key_ops" in key and (not isinstance(key["key_ops"], list) or "verify" not in key["key_ops"]):
                raise ValueError
            public_key = jwt.PyJWK.from_dict(key, algorithm="RS256")
            claims = jwt.decode(token, public_key, algorithms=["RS256"], issuer=self.issuer, audience=self.client_id, options={
                "require": ["exp", "iss", "aud", "sub"], "verify_exp": False, "verify_iat": False,
                "verify_nbf": False, "enforce_minimum_key_length": True,
            })
            now = time.time()
            for field in ("exp", "iat", "nbf"):
                if field in claims:
                    value = claims[field]
                    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
                        raise ValueError
                    if (field == "exp" and value <= now - ID_TOKEN_CLOCK_SKEW) or (field != "exp" and value > now + ID_TOKEN_CLOCK_SKEW):
                        raise ValueError
            if not isinstance(claims["sub"], str) or not claims["sub"] or (expected_subject is not None and claims["sub"] != expected_subject):
                raise ValueError
            audiences = claims["aud"]
            if (isinstance(audiences, list) and len(audiences) > 1 and claims.get("azp") != self.client_id) or ("azp" in claims and claims["azp"] != self.client_id):
                raise ValueError
            if not refresh or "nonce" in claims:
                actual_nonce = claims.get("nonce")
                if not isinstance(nonce, str) or not nonce or not isinstance(actual_nonce, str) or not secrets.compare_digest(nonce.encode(), actual_nonce.encode()):
                    raise ValueError
            if "at_hash" in claims:
                access = response.get("access_token")
                if not isinstance(access, str) or not access:
                    raise ValueError
                digest = hashlib.sha256(access.encode("ascii")).digest()
                expected_hash = base64.urlsafe_b64encode(digest[:16]).decode("ascii").rstrip("=")
                if not isinstance(claims["at_hash"], str) or not secrets.compare_digest(claims["at_hash"].encode(), expected_hash.encode()):
                    raise ValueError
            return claims
        except (jwt.PyJWTError, TypeError, ValueError, KeyError, OverflowError, UnicodeError):
            raise OAuthError("Không xác minh được ID token FEID. Hãy đăng nhập lại.", code="id_token") from None

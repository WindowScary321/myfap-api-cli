import base64
import hashlib
import json
import time
import unittest
from unittest.mock import Mock, patch
from urllib.parse import parse_qs, urlencode, urlsplit

import jwt
import requests
from cryptography.hazmat.primitives.asymmetric import rsa

from myfap.oidc import OIDCClient, OAuthError


ISSUER = "https://identity.example.invalid"
CLIENT_ID = "cli-test"
REDIRECT_URI = "example.cli:/oauthredirect"


def response(body, status=200):
    result = requests.Response()
    result.status_code = status
    result._content = json.dumps(body).encode()
    return result


def metadata(**changes):
    data = {
        "issuer": ISSUER,
        "authorization_endpoint": ISSUER + "/connect/authorize",
        "token_endpoint": ISSUER + "/connect/token",
        "jwks_uri": ISSUER + "/.well-known/jwks",
        "id_token_signing_alg_values_supported": ["RS256"],
        "code_challenge_methods_supported": ["S256"],
    }
    return dict(data, **changes)


class OIDCTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        cls.jwk = dict(json.loads(jwt.algorithms.RSAAlgorithm.to_jwk(cls.key.public_key())), kid="test-key", use="sig", alg="RS256")

    def setUp(self):
        self.session = Mock()
        self.session.get.side_effect = [response(metadata()), response({"keys": [self.jwk]})]
        self.client = OIDCClient(self.session, timeout=2.5, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)

    def token_response(self, changes=None, header_changes=None):
        claims = {
            "iss": ISSUER, "aud": CLIENT_ID, "sub": "fake-subject",
            "exp": time.time() + 300, "iat": time.time() - 10, "nonce": "fake-nonce",
        }
        claims.update(changes or {})
        headers = dict({"kid": "test-key"}, **(header_changes or {}))
        token = jwt.encode(claims, self.key, algorithm="RS256", headers=headers)
        return {"access_token": "fake-access", "id_token": token, "refresh_token": "fake-refresh"}

    def callback(self, attempt, **params):
        return REDIRECT_URI + "?" + urlencode(dict({"code": "fake-code", "state": attempt["state"]}, **params))

    def test_discovery_is_cached_and_uses_bounded_no_redirect_requests(self):
        self.assertEqual(self.client.discover()["issuer"], ISSUER)
        self.assertEqual(self.client.discover()["issuer"], ISSUER)
        self.session.get.assert_called_once_with(ISSUER + "/.well-known/openid-configuration", timeout=2.5, allow_redirects=False)

    def test_discovery_rejects_issuer_and_untrusted_endpoint_metadata(self):
        cases = [metadata(issuer=ISSUER + "/other"), [], metadata(id_token_signing_alg_values_supported=["HS256"])]
        for field in ("authorization_endpoint", "token_endpoint", "jwks_uri"):
            for url in ("http://identity.example.invalid/endpoint", "https://evil.example.invalid/endpoint", "https://user:secret@identity.example.invalid/endpoint", ISSUER + "/endpoint#fragment", ISSUER + "\\evil/endpoint"):
                cases.append(metadata(**{field: url}))
        for data in cases:
            with self.subTest(data=str(data)[:100]):
                client = OIDCClient(Mock(get=Mock(return_value=response(data))), issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                with self.assertRaises(OAuthError):
                    client.discover()

    def test_begin_login_uses_fresh_state_nonce_and_s256_verifier(self):
        first, second = self.client.begin_login(), self.client.begin_login()
        for name in ("state", "nonce", "code_verifier", "code_challenge"):
            self.assertNotEqual(first[name], second[name])
        for attempt in (first, second):
            self.assertGreaterEqual(len(attempt["code_verifier"]), 43)
            self.assertLessEqual(len(attempt["code_verifier"]), 128)
            digest = hashlib.sha256(attempt["code_verifier"].encode("ascii")).digest()
            self.assertEqual(attempt["code_challenge"], base64.urlsafe_b64encode(digest).decode().rstrip("="))
            query = parse_qs(urlsplit(attempt["url"]).query)
            self.assertEqual(query["state"], [attempt["state"]])
            self.assertEqual(query["nonce"], [attempt["nonce"]])
            self.assertEqual(query["code_challenge_method"], ["S256"])
            self.assertEqual(query["prompt"], ["login"])
            self.assertEqual(query["redirect_uri"], [REDIRECT_URI])
            self.assertEqual(query["scope"], ["openid profile offline_access identity-service"])

    def test_callback_accepts_exact_redirect_and_ignores_unrelated_navigation(self):
        attempt = self.client.begin_login()
        callback = self.callback(attempt)
        self.assertEqual(self.client.parse_callback(callback, attempt), "fake-code")
        with self.assertRaises(OAuthError):
            self.client.parse_callback(callback, attempt)
        self.assertIsNone(self.client.parse_callback(ISSUER + "/signin?code=unrelated", attempt))

    def test_callback_rejects_state_mismatch_missing_or_duplicate_parameters(self):
        attempt = self.client.begin_login()
        correct = self.callback(attempt)
        cases = [
            correct.replace(attempt["state"], "wrong-state"),
            REDIRECT_URI + "?code=fake-code",
            correct + "&code=other-code", correct + "&state=other-state",
            correct + "&error=access_denied", correct + "#code=fragment-code",
            correct.replace("/oauthredirect?", "/oauthredirect/other?"),
            correct.replace("/oauthredirect?", "//evil.example.invalid/oauthredirect?"),
            correct + "&error=%ZZ", correct + "\n", REDIRECT_URI + "?state=" + attempt["state"],
        ]
        for url in cases:
            with self.subTest(url=url):
                with self.assertRaises(OAuthError):
                    self.client.parse_callback(url, attempt)

    def test_callback_cancellation_never_exposes_provider_description(self):
        attempt = self.client.begin_login()
        url = REDIRECT_URI + "?" + urlencode({"state": attempt["state"], "error": "access_denied", "error_description": "PRIVATE_PROVIDER_DETAIL"})
        with self.assertRaises(OAuthError) as caught:
            self.client.parse_callback(url, attempt)
        self.assertIn("hủy", str(caught.exception))
        self.assertNotIn("PRIVATE_PROVIDER_DETAIL", str(caught.exception))

    def test_token_request_is_separate_from_jwks_validation(self):
        data = {"access_token": "fake-access", "refresh_token": "fake-rotated", "id_token": "unverified", "token_type": "bearer"}
        self.session.post.return_value = response(data)
        form = {"client_id": CLIENT_ID, "grant_type": "refresh_token", "refresh_token": "fake-old"}
        self.assertEqual(self.client.request_token(form), data)
        self.session.post.assert_called_once_with(ISSUER + "/connect/token", data=form, timeout=2.5, allow_redirects=False)
        self.assertEqual(self.session.get.call_count, 1)

    def test_token_request_preserves_rotation_before_id_token_validation(self):
        for token_fields in (
            {"id_token": None},
            {"id_token": ""},
            {"id_token": "malformed-id-token"},
            {"token_type": "MAC"},
            {"id_token": None, "token_type": "MAC"},
        ):
            with self.subTest(token_fields=token_fields):
                payload = dict(access_token="fake-new-access", refresh_token="rotated-refresh", **token_fields)
                self.session.post.return_value = response(payload)
                actual = self.client.request_token({"grant_type": "refresh_token"})
                self.assertEqual(actual, payload)
                with self.assertRaises(OAuthError):
                    self.client.validate_tokens(actual, "fake-nonce", expected_subject="fake-subject", refresh=True)

        self.session.post.return_value = response({"access_token": "fake-new-access", "refresh_token": "rotated-refresh"})
        actual = self.client.request_token({"grant_type": "refresh_token"})
        self.assertIsNone(self.client.validate_tokens(actual, "fake-nonce", expected_subject="fake-subject", refresh=True))

    def test_token_response_types_and_provider_errors_fail_safely(self):
        for data in ({}, [], {"access_token": ""}, {"access_token": 123}, {"access_token": "fake", "refresh_token": None}, {"access_token": "fake", "error": "invalid_grant"}):
            with self.subTest(data=data):
                self.session.post.return_value = response(data)
                with self.assertRaises(OAuthError):
                    self.client.request_token({"grant_type": "refresh_token"})
        self.session.post.return_value = response({"error": "invalid_grant", "error_description": "PRIVATE_TOKEN_DETAIL"}, 400)
        with self.assertRaises(OAuthError) as caught:
            self.client.request_token({"grant_type": "refresh_token"})
        self.assertEqual(caught.exception.code, "invalid_grant")
        self.assertEqual(caught.exception.status_code, 400)
        self.assertNotIn("PRIVATE_TOKEN_DETAIL", str(caught.exception))
        self.session.post.return_value = response({"error": ["PRIVATE_DETAIL"]}, 400)
        with self.assertRaises(OAuthError):
            self.client.request_token({"grant_type": "refresh_token"})

    def test_network_json_and_redirect_failures_do_not_expose_private_details(self):
        malformed = response({})
        malformed._content = b"PRIVATE_JSON_DETAIL"
        cases = [requests.Timeout("PRIVATE_NETWORK_DETAIL"), malformed, response({}, 302)]
        for item in cases:
            with self.subTest(kind=type(item).__name__):
                session = Mock()
                if isinstance(item, Exception):
                    session.get.side_effect = item
                else:
                    session.get.return_value = item
                client = OIDCClient(session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                with self.assertRaises(OAuthError) as caught:
                    client.discover()
                self.assertNotIn("PRIVATE_", str(caught.exception))

    def test_id_token_validates_signature_claims_nonce_and_subject(self):
        claims = self.client.validate_tokens(self.token_response(), "fake-nonce", expected_subject="fake-subject")
        self.assertEqual(claims["sub"], "fake-subject")
        self.session.get.assert_any_call(ISSUER + "/.well-known/jwks", timeout=2.5, allow_redirects=False)

    def test_id_token_accepts_clock_skew_within_30_seconds_on_login_and_refresh(self):
        now = 1700000000.25
        cases = (("exp", 0), ("exp", -0.5), ("exp", -29.999),
                 ("iat", 0.5), ("iat", 29.999), ("iat", 30),
                 ("nbf", 0.5), ("nbf", 29.999), ("nbf", 30))
        for refresh in (False, True):
            for field, offset in cases:
                with self.subTest(refresh=refresh, field=field, offset=offset), patch("myfap.oidc.time.time", return_value=now):
                    session = Mock(get=Mock(side_effect=[response(metadata()), response({"keys": [self.jwk]})]))
                    client = OIDCClient(session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                    changes = {"exp": now + 300, "iat": now - 10}
                    changes[field] = now + offset
                    claims = client.validate_tokens(self.token_response(changes), "fake-nonce", expected_subject="fake-subject", refresh=refresh)
                    self.assertEqual(claims[field], now + offset)

    def test_id_token_rejects_time_claims_beyond_clock_skew_on_login_and_refresh(self):
        now = 1700000000.25
        cases = (("exp", -30), ("exp", -30.001), ("iat", 30.001), ("nbf", 30.001))
        for refresh in (False, True):
            for field, offset in cases:
                with self.subTest(refresh=refresh, field=field, offset=offset), patch("myfap.oidc.time.time", return_value=now):
                    session = Mock(get=Mock(side_effect=[response(metadata()), response({"keys": [self.jwk]})]))
                    client = OIDCClient(session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                    with self.assertRaises(OAuthError):
                        changes = {"exp": now + 300, "iat": now - 10}
                        changes[field] = now + offset
                        client.validate_tokens(self.token_response(changes), "fake-nonce", expected_subject="fake-subject", refresh=refresh)

    def test_id_token_clock_skew_never_accepts_invalid_time_claim_types(self):
        for refresh in (False, True):
            for field in ("exp", "iat", "nbf"):
                for value in (None, True, False, "1700000000", float("nan"), float("inf"), float("-inf"), [], {}):
                    with self.subTest(refresh=refresh, field=field, value=value):
                        session = Mock(get=Mock(side_effect=[response(metadata()), response({"keys": [self.jwk]})]))
                        client = OIDCClient(session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                        with self.assertRaises(OAuthError):
                            client.validate_tokens(self.token_response({field: value}), "fake-nonce", expected_subject="fake-subject", refresh=refresh)

    def test_id_token_rejects_bad_claims(self):
        cases = [
            {"iss": ISSUER + "/evil"}, {"aud": "other-client"}, {"aud": [CLIENT_ID, "other-client"]},
            {"aud": [CLIENT_ID], "azp": "other-client"}, {"aud": [CLIENT_ID, "other-client"], "azp": "other-client"},
            {"nonce": "other-nonce"}, {"nonce": None}, {"sub": ""}, {"sub": 123},
            {"exp": time.time() - 300}, {"exp": "9999999999"}, {"exp": float("inf")}, {"exp": float("nan")}, {"exp": True},
            {"iat": time.time() + 300}, {"iat": "1"}, {"nbf": time.time() + 300},
            {"at_hash": "wrong-access-hash"},
        ]
        for changes in cases:
            with self.subTest(changes=changes):
                self.session.get.side_effect = [response(metadata()), response({"keys": [self.jwk]})]
                client = OIDCClient(self.session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                with self.assertRaises(OAuthError):
                    client.validate_tokens(self.token_response(changes), "fake-nonce")

    def test_id_token_accepts_azp_and_access_hash(self):
        digest = hashlib.sha256(b"fake-access").digest()
        at_hash = base64.urlsafe_b64encode(digest[:16]).decode().rstrip("=")
        claims = self.client.validate_tokens(self.token_response({"aud": [CLIENT_ID, "other-client"], "azp": CLIENT_ID, "at_hash": at_hash}), "fake-nonce")
        self.assertEqual(claims["azp"], CLIENT_ID)

    def test_login_requires_id_token_and_all_identity_claims(self):
        with self.assertRaises(OAuthError):
            self.client.validate_tokens({"access_token": "fake-access"}, "fake-nonce")
        valid_claims = jwt.decode(self.token_response()["id_token"], options={"verify_signature": False})
        for field in ("exp", "iss", "aud", "sub", "nonce"):
            with self.subTest(missing=field):
                claims = dict(valid_claims)
                del claims[field]
                token = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test-key"})
                self.session.get.side_effect = [response(metadata()), response({"keys": [self.jwk]})]
                client = OIDCClient(self.session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                with self.assertRaises(OAuthError):
                    client.validate_tokens({"access_token": "fake-access", "id_token": token}, "fake-nonce")

    def test_id_token_rejects_wrong_signature_algorithm_and_remote_key_headers(self):
        data = self.token_response()
        header, payload, signature = data["id_token"].split(".")
        data["id_token"] = header + "." + payload + "." + ("A" if signature[0] != "A" else "B") + signature[1:]
        with self.assertRaises(OAuthError):
            self.client.validate_tokens(data, "fake-nonce")
        for header_changes in ({"jku": "https://evil.example.invalid/jwks"}, {"jwk": self.jwk}, {"x5u": "https://evil.example.invalid/cert"}, {"alg": "HS256"}):
            with self.subTest(headers=list(header_changes)):
                if "alg" in header_changes:
                    forged = jwt.encode({"iss": ISSUER, "aud": CLIENT_ID, "sub": "fake-subject", "exp": time.time() + 300}, "fake-symmetric-key-with-adequate-length", algorithm="HS256", headers={"kid": "test-key"})
                    data = {"access_token": "fake-access", "id_token": forged}
                else:
                    data = self.token_response(header_changes=header_changes)
                with self.assertRaises(OAuthError):
                    self.client.validate_tokens(data, "fake-nonce")

    def test_jwks_rejects_missing_duplicate_or_non_signing_key(self):
        for keys in ([], [self.jwk, self.jwk], [dict(self.jwk, use="enc")], [dict(self.jwk, alg="RS512")], [dict(self.jwk, key_ops=["sign"])], [dict(self.jwk, kid="other-key")]):
            with self.subTest(keys=len(keys)):
                session = Mock(get=Mock(side_effect=[response(metadata()), response({"keys": keys})]))
                client = OIDCClient(session, issuer=ISSUER, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)
                with self.assertRaises(OAuthError):
                    client.validate_tokens(self.token_response(), "fake-nonce")

    def test_refresh_id_token_is_optional_but_present_claims_are_validated(self):
        with self.assertRaises(OAuthError):
            self.client.validate_tokens([], "fake-nonce", refresh=True)
        self.assertIsNone(self.client.validate_tokens({"access_token": "fake-new-access"}, "fake-nonce", expected_subject="fake-subject", refresh=True))
        self.assertEqual(self.session.get.call_count, 0)
        with self.assertRaises(OAuthError):
            self.client.validate_tokens({"access_token": "fake-new-access", "id_token": None}, "fake-nonce", expected_subject="fake-subject", refresh=True)
        with self.assertRaises(OAuthError):
            self.client.validate_tokens({"access_token": "fake-new-access", "token_type": "MAC"}, "fake-nonce", expected_subject="fake-subject", refresh=True)
        claims = self.client.validate_tokens(self.token_response({"nonce": "fake-nonce"}), "fake-nonce", expected_subject="fake-subject", refresh=True)
        self.assertEqual(claims["sub"], "fake-subject")
        for changes, nonce, subject in (({"nonce": "different"}, "fake-nonce", "fake-subject"), ({"sub": "other-subject"}, "fake-nonce", "fake-subject"), ({}, None, "fake-subject")):
            with self.subTest(changes=changes):
                self.session.get.side_effect = [response({"keys": [self.jwk]})]
                with self.assertRaises(OAuthError):
                    self.client.validate_tokens(self.token_response(changes), nonce, expected_subject=subject, refresh=True)

    def test_refresh_without_nonce_claim_is_valid(self):
        data = self.token_response()
        claims = jwt.decode(data["id_token"], options={"verify_signature": False})
        del claims["nonce"]
        data["id_token"] = jwt.encode(claims, self.key, algorithm="RS256", headers={"kid": "test-key"})
        self.assertEqual(self.client.validate_tokens(data, "fake-original-nonce", expected_subject="fake-subject", refresh=True)["sub"], "fake-subject")


if __name__ == "__main__":
    unittest.main()

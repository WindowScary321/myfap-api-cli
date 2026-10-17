import base64
import hashlib
import hmac
import math
import sys
import time
from datetime import datetime
from pathlib import Path

import pytz
import requests
from playwright.sync_api import sync_playwright

from .auth_var import FEID_HOST, FAP_HOST, CLIENT_ID, REDIRECT_URI, SECRET_KEY, MAGIC_ID, SURVEY_SECRET_KEY
from .config import resolve_timeout
from .errors import ApiError, ApiSessionExpiredError, read_response
from .oidc import OIDCClient, OAuthError
from .storage import SessionFormatError, SessionStore, SessionStoreError


CONFIG_DIR = Path.home() / ".myfap-api-cli"
SESSION_FILE = CONFIG_DIR / "session.json"
ACCESS_TOKEN_REFRESH_BUFFER = 30.0


class AuthError(ApiError):
    pass


class SessionBindingError(AuthError):
    pass


def _create_checksum(identifier: str, campus: str, key: str) -> str:
    time_str = datetime.now(pytz.timezone("Asia/Ho_Chi_Minh")).strftime("%d/%m/%Y %H") + ":00"
    raw = f"{identifier}MYFAP{campus}{time_str}"
    signature = hmac.new(key.encode(), raw.encode(), hashlib.sha1).digest()
    return base64.b64encode(signature).decode()


def create_checksum(identifier: str, campus: str) -> str:
    return _create_checksum(identifier, campus, SECRET_KEY)


def create_survey_checksum(username: str) -> str:
    return _create_checksum(username.strip().lower(), "", SURVEY_SECRET_KEY)


def _text(value):
    return isinstance(value, str) and bool(value.strip())


class MyFapAuth:
    def __init__(self, campus=None, session_file=None, timeout=None, api_version=None, account_type=None):
        if campus is not None and not _text(campus):
            raise AuthError("Mã campus không hợp lệ. Hãy kiểm tra --campus.")
        if api_version not in (None, "v1", "v2"):
            raise AuthError("API version không hợp lệ.")
        if account_type is not None and not _text(account_type):
            raise AuthError("Loại tài khoản không hợp lệ.")
        self._requested = (campus, api_version, account_type)
        self.campus = campus or "APHL"
        self.api_version = api_version or "v1"
        self.account_type = account_type or "student"
        self.timeout = resolve_timeout(timeout)
        self.session_file = Path(session_file) if session_file else SESSION_FILE
        self.store = SessionStore(self.session_file)
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "okhttp/4.9.2"})
        self.authen_key = self.mssv = self.email = None
        self.jwt_token = self.refresh_token = None
        self.subject = self.login_nonce = self.access_token_expires_at = None
        self._binding = None
        self._fap_ready = None
        self._oidc_validated = False

    def _oidc(self):
        return OIDCClient(self.session, timeout=self.timeout, issuer=FEID_HOST, client_id=CLIENT_ID, redirect_uri=REDIRECT_URI)

    def _snapshot(self):
        binding = self._binding or (self.campus, self.api_version, self.account_type)
        return {
            "authen_key": self.authen_key, "mssv": self.mssv, "email": self.email,
            "jwt_token": self.jwt_token, "refresh_token": self.refresh_token,
            "campus": binding[0], "api_version": binding[1], "account_type": binding[2],
            "oidc_subject": self.subject, "oidc_nonce": self.login_nonce,
            "oidc_validated": self._oidc_validated,
            "access_token_expires_at": self.access_token_expires_at,
            "fap_needs_reauth": not (bool(self.authen_key) if self._fap_ready is None else self._fap_ready),
        }

    def _restore(self, data):
        if not isinstance(data, dict):
            raise AuthError("Session không hợp lệ. Hãy đăng nhập lại.")
        campus, version, account = data.get("campus"), data.get("api_version", "v1"), data.get("account_type", "student")
        if not _text(campus) or version not in ("v1", "v2") or not _text(account):
            raise AuthError("Session thiếu binding hợp lệ. Hãy chạy 'myfap login -f'.")
        for field in ("authen_key", "mssv", "email", "jwt_token", "refresh_token"):
            value = data.get(field)
            if value is not None and not _text(value):
                raise AuthError("Session có trường credential hoặc identity không hợp lệ. Hãy đăng nhập lại.")
        subject, nonce = data.get("oidc_subject"), data.get("oidc_nonce")
        if any(value is not None and not _text(value) for value in (subject, nonce)):
            raise AuthError("Session có metadata OIDC không hợp lệ. Hãy đăng nhập lại.")
        self._binding = (campus, version, account)
        self.campus, self.api_version, self.account_type = tuple(requested if requested is not None else stored for requested, stored in zip(self._requested, self._binding))
        for field in ("authen_key", "mssv", "email", "jwt_token", "refresh_token"):
            setattr(self, field, data.get(field))
        self.subject, self.login_nonce = subject, nonce
        self._oidc_validated = data.get("oidc_validated") is True and _text(self.subject)
        self._fap_ready = bool(self.authen_key) and data.get("fap_needs_reauth", False) is False
        self.access_token_expires_at = data.get("access_token_expires_at")

    def save_session(self):
        if self._binding is None:
            self._binding = (self.campus, self.api_version, self.account_type)
        with self.store.lock():
            self.store.write(self._snapshot())

    def resolve_api_version(self):
        if self._requested[1] is not None:
            return self._requested[1]
        try:
            with self.store.lock():
                data = self.store.read()
        except SessionStoreError:
            raise AuthError("Không đọc được API version trong session an toàn. Hãy kiểm tra --config.") from None
        version = data.get("api_version", "v1") if data is not None else "v1"
        if version not in ("v1", "v2"):
            raise AuthError("Session có API version không hợp lệ. Hãy đăng nhập lại hoặc chỉ định --api-version.")
        return version

    def ensure_bound(self, *, campus=None, api_version=None, account_type=None):
        target = (campus or self.campus, api_version or self.api_version, account_type or self.account_type)
        ready = bool(self.authen_key) if self._fap_ready is None else self._fap_ready
        if not ready or not self.authen_key or self._binding != target:
            raise SessionBindingError("Session FAP chưa khớp campus/version/loại tài khoản. Hãy đăng nhập hoặc handshake lại.")

    def _check_supported(self):
        if self.api_version not in ("v1", "v2"):
            raise SessionBindingError("API version chưa được hỗ trợ.")
        if self.account_type != "student":
            raise SessionBindingError("Luồng FEID hiện chỉ hỗ trợ tài khoản student.")

    def load_session(self):
        try:
            with self.store.lock():
                data = self.store.read()
                if data is None:
                    return False
                self._restore(data)
                self._check_supported()
                if self._binding != (self.campus, self.api_version, self.account_type) or not self._fap_ready:
                    if not self.jwt_token or not self._oidc_validated:
                        raise SessionBindingError("Session cần đăng nhập lại để xác minh binding. Hãy chạy 'myfap login -f'.")
                    if self._access_token_expired():
                        return self._refresh_locked()
                    try:
                        self._handshake()
                    except ApiSessionExpiredError:
                        return self._refresh_locked()
                    self.store.write(self._snapshot())
                    return True
                self.ensure_bound()
                return True
        except SessionStoreError:
            print("[!] Không đọc hoặc khóa được JSON session an toàn. Hãy kiểm tra --config.", file=sys.stderr)
            return False

    def _handshake(self):
        self._check_supported()
        if not self.jwt_token:
            raise AuthError("Không có FEID access token. Hãy đăng nhập lại.")
        try:
            if self.api_version == "v2":
                from . import v2

                result = v2.request(self.session, "AuthenticationByFeId", credential=self.jwt_token, campus=self.campus, timeout=self.timeout or 10)
            else:
                result = self.session.post(
                    f"{FAP_HOST}/AuthenticationByFeId",
                    params={"campusCode": self.campus, "checksum": create_checksum(MAGIC_ID, self.campus)},
                    json={"token": self.jwt_token},
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    timeout=self.timeout or 10, allow_redirects=False,
                )
        except requests.RequestException:
            raise AuthError("Không kết nối được FAP để handshake. Hãy thử lại sau.") from None
        payload = read_response(result, api_version=self.api_version, operation="AuthenticationByFeId")
        rows = payload["data"]
        if not isinstance(rows, list):
            raise AuthError("Handshake FAP không trả danh sách identity hợp lệ.")
        matches = []
        for row in rows:
            if not isinstance(row, dict):
                continue
            campus = row.get("campusCode", row.get("CampusCode"))
            if campus is not None and campus != self.campus:
                continue
            if row.get("typeAcc") == self.account_type:
                matches.append(row)
        if len(matches) != 1 or (len(rows) != 1 and not _text(matches[0].get("campusCode", matches[0].get("CampusCode")))):
            raise AuthError("Handshake FAP không xác định duy nhất identity đúng campus/loại tài khoản.")
        row = matches[0]
        key, roll, email = row.get("authenKey"), row.get("rollnumber", row.get("rollNumber")), row.get("email")
        if not all(_text(value) for value in (key, roll, email)):
            raise AuthError("Handshake FAP thiếu credential hoặc identity hợp lệ.")
        # Changing API version must not silently switch the FAP identity for the same campus/account.
        same_identity_scope = (
            self._binding is not None
            and self._binding[0] == self.campus
            and self._binding[2] == self.account_type
        )
        if same_identity_scope and self.mssv and (self.mssv != roll or self.email != email):
            raise AuthError("Identity FAP thay đổi ngoài luồng đăng nhập. Hãy đăng nhập lại.")
        self.authen_key, self.mssv, self.email = key, roll, email
        self._binding = (self.campus, self.api_version, self.account_type)
        self._fap_ready = True

    def _set_tokens(self, tokens):
        self.jwt_token = tokens["access_token"]
        self.refresh_token = tokens.get("refresh_token", self.refresh_token)
        self.access_token_expires_at = None
        self.authen_key = None
        self._fap_ready = False
        self._oidc_validated = False

    def _set_expiry(self, tokens):
        value = tokens.get("expires_in")
        if value is None:
            self.access_token_expires_at = None
            return
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value) or value < 0:
            raise AuthError("FEID trả về expires_in không hợp lệ.")
        self.access_token_expires_at = time.time() + value

    def _access_token_expired(self):
        value = self.access_token_expires_at
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool)
            and math.isfinite(value) and value <= time.time() + ACCESS_TOKEN_REFRESH_BUFFER
        )

    def _refresh_locked(self):
        self._check_supported()
        if not self.refresh_token:
            return False
        if not _text(self.subject):
            raise AuthError("Session cũ chưa có subject đã xác minh. Hãy chạy 'myfap login -f'.")
        oidc = self._oidc()
        try:
            print("[*] Đang làm mới session FEID...", file=sys.stderr)
            tokens = oidc.request_token({"client_id": CLIENT_ID, "refresh_token": self.refresh_token, "grant_type": "refresh_token"})
            self._set_tokens(tokens)
            self.store.write(self._snapshot())
            claims = oidc.validate_tokens(tokens, self.login_nonce, expected_subject=self.subject, refresh=True)
            if claims is not None:
                self.subject = claims["sub"]
            self._set_expiry(tokens)
            self._oidc_validated = True
            self.store.write(self._snapshot())
            self._handshake()
            self.store.write(self._snapshot())
            print("[*] Làm mới session thành công!", file=sys.stderr)
            return True
        except (OAuthError, ApiError, SessionStoreError):
            print("[!] Không làm mới được session; token đã rotate vẫn được giữ nếu lưu thành công. Hãy thử lại hoặc đăng nhập lại.", file=sys.stderr)
            return False

    def refresh_session(self):
        failed_key = self.authen_key
        try:
            with self.store.lock():
                data = self.store.read()
                if self._binding is not None:
                    if data is None:
                        raise SessionBindingError("Session đã bị xóa bởi tiến trình khác. Hãy chạy lại command.")
                    stored_binding = (data.get("campus"), data.get("api_version", "v1"), data.get("account_type", "student"))
                    if (
                        stored_binding != self._binding or data.get("oidc_subject") != self.subject
                        or data.get("mssv") != self.mssv or data.get("email") != self.email
                    ):
                        raise SessionBindingError("Session đã đổi identity hoặc binding ở tiến trình khác. Hãy chạy lại command.")
                if data is not None:
                    self._restore(data)
                self._check_supported()
                if failed_key and self.authen_key and failed_key != self.authen_key and self._fap_ready:
                    self.ensure_bound()
                    return True
                return self._refresh_locked()
        except SessionStoreError:
            print("[!] Không khóa hoặc lưu được JSON session. Hãy thử lại sau.", file=sys.stderr)
            return False

    def _authorize(self, oidc, attempt):
        code, failure = None, None
        with sync_playwright() as playwright:
            browser = None
            try:
                for channel in ("chrome", "msedge", None):
                    try:
                        browser = playwright.chromium.launch(channel=channel, headless=False, args=["--disable-blink-features=AutomationControlled"], ignore_default_args=["--enable-automation"]) if channel else playwright.firefox.launch(headless=False)
                        break
                    except Exception:
                        continue
                if browser is None:
                    raise AuthError("Không mở được browser. Hãy cài Chrome/Edge hoặc Firefox của Playwright.")
                page = browser.new_context(user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36").new_page()

                def callback(url):
                    nonlocal code, failure
                    if code is not None or failure is not None:
                        return
                    try:
                        code = oidc.parse_callback(url, attempt)
                    except OAuthError as error:
                        failure = error

                def redirected(response):
                    if 300 <= response.status < 400:
                        location = response.headers.get("location")
                        if location:
                            callback(location)

                page.on("request", lambda request: callback(request.url))
                page.on("response", redirected)
                print("[*] Hãy hoàn tất đăng nhập trên browser.", file=sys.stderr)
                deadline = time.monotonic() + 120
                try:
                    page.goto(attempt["url"])
                except Exception:
                    pass
                while code is None and failure is None and time.monotonic() < deadline:
                    try:
                        page.wait_for_timeout(250)
                    except Exception:
                        raise AuthError("Browser đăng nhập đã đóng. Hãy chạy lại login.") from None
            except KeyboardInterrupt:
                raise AuthError("Đã hủy đăng nhập.") from None
            except AuthError:
                raise
            except Exception:
                raise AuthError("Không hoàn tất được browser đăng nhập. Hãy thử lại.") from None
            finally:
                if browser is not None:
                    try:
                        browser.close()
                    except Exception:
                        pass
        if failure is not None:
            raise failure
        if code is None:
            raise AuthError("Đăng nhập hết thời gian chờ. Hãy chạy lại login.")
        return code

    def login(self):
        try:
            with self.store.lock():
                try:
                    existing = self.store.read()
                except SessionFormatError:
                    existing = None
                stored_campus = existing.get("campus") if existing is not None else None
                stored_version = existing.get("api_version", "v1") if existing is not None else "v1"
                self.campus = self._requested[0] or (stored_campus if _text(stored_campus) else "APHL")
                self.api_version = self._requested[1] or (stored_version if stored_version in ("v1", "v2") else "v1")
                self.account_type = self._requested[2] or "student"
            self._check_supported()
            oidc = self._oidc()
            attempt = oidc.begin_login()
            code = self._authorize(oidc, attempt)
            with self.store.lock():
                tokens = oidc.request_token({
                    "client_id": CLIENT_ID, "code": code, "redirect_uri": REDIRECT_URI,
                    "code_verifier": attempt["code_verifier"], "grant_type": "authorization_code",
                })
                claims = oidc.validate_tokens(tokens, attempt["nonce"])
                self.refresh_token = None
                self._set_tokens(tokens)
                self.subject, self.login_nonce = claims["sub"], attempt["nonce"]
                self._set_expiry(tokens)
                self._oidc_validated = True
                self._binding = None
                self.mssv = self.email = None
                self._handshake()
                self.store.write(self._snapshot())
                return self.authen_key, self.mssv
        except OAuthError as error:
            raise AuthError(str(error)) from None
        except SessionStoreError:
            raise AuthError("Không lưu được session an toàn. Hãy thử đăng nhập lại.") from None
        except AuthError:
            raise
        except ApiError:
            raise
        except Exception:
            raise AuthError("Không hoàn tất được đăng nhập an toàn. Hãy thử lại.") from None

    def logout(self):
        try:
            with self.store.lock(cleanup=True):
                return self.store.delete()
        except (OSError, SessionStoreError):
            raise AuthError("Không xóa được session an toàn.") from None

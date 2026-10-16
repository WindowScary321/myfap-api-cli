import time
import json
import base64
import hashlib
import hmac
import sys
import requests
import pkce
from pathlib import Path
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright

# Import biến từ file ngoài
from .auth_var import FEID_HOST, FAP_HOST, CLIENT_ID, REDIRECT_URI, SECRET_KEY, MAGIC_ID, SURVEY_SECRET_KEY
CONFIG_DIR = Path.home() / ".myfap-api-cli"
SESSION_FILE = CONFIG_DIR / "session.json"

def _create_checksum(identifier: str, campus: str, key: str) -> str:
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    time_str = datetime.now(tz).strftime("%d/%m/%Y %H") + ":00"
    raw = f"{identifier}MYFAP{campus}{time_str}"
    sig = hmac.new(key.encode(), raw.encode(), hashlib.sha1).digest()
    return base64.b64encode(sig).decode()


def create_checksum(identifier: str, campus: str) -> str:
    return _create_checksum(identifier, campus, SECRET_KEY)


def create_survey_checksum(username: str) -> str:
    return _create_checksum(username.strip().lower(), "", SURVEY_SECRET_KEY)

class MyFapAuth:
    def __init__(self, campus="APHL", session_file=None):
        self.campus = campus
        self.session_file = Path(session_file) if session_file else SESSION_FILE
        self.code_verifier, self.code_challenge = pkce.generate_pkce_pair()
        self.jwt_token = None
        self.refresh_token = None
        self.authen_key = None
        self.mssv = None
        self.email = None
        
        # Thiết lập session với User-Agent mạo danh app mobile FPT
        self.session = requests.Session()
        self.session.headers.update({"User-Agent": "okhttp/4.9.2"})

    def save_session(self):
        data = {
            "authen_key": self.authen_key,
            "mssv": self.mssv,
            "email": self.email,
            "jwt_token": self.jwt_token,
            "refresh_token": self.refresh_token,
            "campus": self.campus
        }
        self.session_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.session_file, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=4)
        try:
            import os
            os.chmod(self.session_file, 0o600)
        except Exception:
            pass

    def load_session(self):
        from .api import ApiError, ApiHTTPError, ApiSessionExpiredError, read_response

        if not self.session_file.exists():
            return False
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print(f"[!] Lỗi: File cấu hình '{self.session_file}' không đúng định dạng JSON.", file=sys.stderr)
                    return False
            
            if not isinstance(data, dict) or "authen_key" not in data:
                print(f"[!] Lỗi: File '{self.session_file}' không chứa dữ liệu session hợp lệ của MyFAP.", file=sys.stderr)
                return False
                
            self.authen_key = data.get("authen_key")
            self.mssv = data.get("mssv")
            self.email = data.get("email")
            self.jwt_token = data.get("jwt_token")
            self.refresh_token = data.get("refresh_token")
            # Campus có thể ghi đè bằng flag CLI
            # self.campus = data.get("campus", self.campus) 
            
            if not self.authen_key: return False

        except (OSError, ValueError):
            print("[!] Không đọc được file session. Hãy kiểm tra --config hoặc đăng nhập lại.", file=sys.stderr)
            return False

        checksum = create_checksum(MAGIC_ID, self.campus)
        try:
            r = self.session.get(
                f"{FAP_HOST}/GetSemester",
                params={"campusCode": self.campus, "Authen": self.authen_key, "checksum": checksum},
                timeout=5,
            )
        except requests.RequestException:
            raise ApiError("Không kiểm tra được session do lỗi kết nối. Hãy thử lại sau.") from None
        try:
            read_response(r)
        except ApiSessionExpiredError:
            return self.refresh_session()
        except ApiHTTPError as error:
            if error.status_code == 401:
                return self.refresh_session()
            raise
        return True


    def refresh_session(self):
        from .api import ApiError, read_response

        if not self.refresh_token: return False
        try:
            print("[*] Phiên đăng nhập hết hạn. Đang làm mới (Refresh Token)...", file=sys.stderr)
            r = self.session.post(f"{FEID_HOST}/connect/token", data={
                "client_id": CLIENT_ID, 
                "refresh_token": self.refresh_token, 
                "grant_type": "refresh_token"
            }, timeout=10)
            if r.status_code == 200:
                resp = r.json()
                self.jwt_token = resp.get('access_token', self.jwt_token)
                if 'refresh_token' in resp:
                    self.refresh_token = resp['refresh_token']
                
                # Handshake lại để lấy authen_key mới
                checksum = create_checksum(MAGIC_ID, self.campus)
                r_handshake = self.session.post(
                    f"{FAP_HOST}/AuthenticationByFeId",
                    params={"campusCode": self.campus, "checksum": checksum},
                    json={"token": self.jwt_token},
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                    timeout=10
                )
                resp_hs = read_response(r_handshake)
                if 'data' in resp_hs and len(resp_hs['data']) > 0:
                    self.authen_key = resp_hs['data'][0]['authenKey']
                    self.save_session()
                    print("[*] Làm mới phiên đăng nhập thành công!", file=sys.stderr)
                    return True
                else:
                    print("[!] Handshake sau refresh không trả về session FAP. Hãy đăng nhập lại.", file=sys.stderr)
                    return False
            else:
                print(f"[!] FEID trả về HTTP {r.status_code}.", file=sys.stderr)
                print("[!] Refresh Token thất bại hoặc đã bị thu hồi. Vui lòng chạy lệnh 'myfap login -f' để đăng nhập lại.", file=sys.stderr)
                return False
        except ApiError as error:
            print(f"[!] Không làm mới được session FAP: {error}", file=sys.stderr)
            return False
        except Exception:
            print("[!] Không làm mới được session. Hãy thử lại hoặc chạy 'myfap login -f'.", file=sys.stderr)
            return False

    def login(self):
        from .api import ApiError, read_response

        print("[*] Đang khởi chạy Playwright...", file=sys.stderr)
        auth_url = (f"{FEID_HOST}/connect/authorize?client_id={CLIENT_ID}"
                    f"&redirect_uri={REDIRECT_URI}&response_type=code"
                    f"&scope=openid%20profile%20offline_access%20identity-service"
                    f"&code_challenge={self.code_challenge}&code_challenge_method=S256")
        code = None
        
        with sync_playwright() as p:
            # Ưu tiên mở bằng Chrome có sẵn trên máy, fallback sang Edge
            # Thêm cờ để bypass tính năng nhận diện bot của Google (Couldn't sign you in)
            custom_args = ['--disable-blink-features=AutomationControlled']
            try:
                browser = p.chromium.launch(
                    channel="chrome", 
                    headless=False,
                    args=custom_args,
                    ignore_default_args=["--enable-automation"]
                )
            except Exception:
                try:
                    browser = p.chromium.launch(
                        channel="msedge", 
                        headless=False,
                        args=custom_args,
                        ignore_default_args=["--enable-automation"]
                    )
                except Exception:
                    # Nếu cả Chrome và Edge đều không có, dùng trình duyệt tải kèm playwright
                    browser = p.firefox.launch(headless=False)

            context = browser.new_context(
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/147.0.0.0 Safari/537.36"
            )
            page = context.new_page()

            def handle_response(response):
                nonlocal code
                if 300 <= response.status < 400:
                    location = response.headers.get("location", "")
                    if location and "io.identityserver.demo" in location and "code=" in location:
                        try:
                            import urllib.parse as urlparse
                            parsed = urlparse.urlparse(location)
                            code = urlparse.parse_qs(parsed.query)['code'][0]
                        except Exception:
                            code = location.split("code=")[1].split("&")[0]

            def handle_request(request):
                nonlocal code
                url = request.url
                if "io.identityserver.demo" in url and "code=" in url:
                    try:
                        import urllib.parse as urlparse
                        parsed = urlparse.urlparse(url)
                        code = urlparse.parse_qs(parsed.query)['code'][0]
                    except Exception:
                        code = url.split("code=")[1].split("&")[0]

            page.on("response", handle_response)
            page.on("request", handle_request)

            print(">>> VUI LÒNG ĐĂNG NHẬP TRÊN CỬA SỔ TRÌNH DUYỆT <<<", file=sys.stderr)
            try:
                page.goto(auth_url)
            except Exception:
                pass
            
            start_time = time.time()
            try:
                while not code and (time.time() - start_time) < 120:
                    page.wait_for_timeout(500)
            except KeyboardInterrupt:
                print("\n[!] Hủy đăng nhập bởi người dùng.", file=sys.stderr)
                browser.close()
                raise Exception("Đăng nhập bị hủy.")
            except Exception:
                pass
            browser.close()

        if not code:
            raise Exception("Lỗi: Không lấy được Code từ FEID (timeout hoặc trình duyệt bị đóng).")

        print("[*] Lấy token từ Code...", file=sys.stderr)
        try:
            r = self.session.post(f"{FEID_HOST}/connect/token", data={
                "client_id": CLIENT_ID, "code": code, "redirect_uri": REDIRECT_URI,
                "code_verifier": self.code_verifier, "grant_type": "authorization_code"
            }, timeout=10)
        except requests.RequestException:
            raise ApiError("Không kết nối được FEID. Hãy thử đăng nhập lại sau.") from None
        
        if r.status_code != 200:
            raise Exception(f"Không lấy được token FEID (HTTP {r.status_code}). Hãy đăng nhập lại.")

        self.jwt_token = r.json()['access_token']
        self.refresh_token = r.json().get('refresh_token')
        
        # Lấy MSSV và email từ Token
        parts = self.jwt_token.split('.')
        payload_str = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        payload = json.loads(base64.urlsafe_b64decode(payload_str))
        self.email = payload.get('email', '')
        try:
            proj_str = payload.get('projectCampuses', '[]')
            projects = json.loads(proj_str)
            found = False
            for p in projects:
                if p.get('CampusCode') == self.campus:
                    self.mssv = p.get('RollNumber')
                    found = True
                    break
            if not found and projects: self.mssv = projects[0].get('RollNumber')
            print(f"[*] Xin chào sinh viên: {self.mssv}", file=sys.stderr)
        except Exception:
            raise Exception("Không tìm thấy MSSV tự động trong Token. Đăng nhập thất bại.")

        print("[*] Handshake với FAP API để lấy authenKey...", file=sys.stderr)
        checksum = create_checksum(MAGIC_ID, self.campus)
        try:
            r = self.session.post(
                f"{FAP_HOST}/AuthenticationByFeId",
                params={"campusCode": self.campus, "checksum": checksum},
                json={"token": self.jwt_token},
                headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"},
                timeout=10
            )
        except requests.RequestException:
            raise ApiError("Không kết nối được FAP để hoàn tất đăng nhập. Hãy thử lại sau.") from None
        resp = read_response(r)
        if 'data' in resp and len(resp['data']) > 0:
            self.authen_key = resp['data'][0]['authenKey']
            print("[*] Handshake thành công!", file=sys.stderr)
            return self.authen_key, self.mssv
        else:
            raise Exception("Handshake không trả về session FAP. Hãy đăng nhập lại.")


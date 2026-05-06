import time
import json
import base64
import hashlib
import hmac
import requests
import pkce
from pathlib import Path
from datetime import datetime
import pytz
from playwright.sync_api import sync_playwright

# Import biến từ file ngoài
from .auth_var import FEID_HOST, FAP_HOST, CLIENT_ID, REDIRECT_URI, SECRET_KEY, MAGIC_ID
CONFIG_DIR = Path.home() / ".myfap-api-cli"
SESSION_FILE = CONFIG_DIR / "session.json"

def create_checksum(identifier: str, campus: str) -> str:
    tz = pytz.timezone('Asia/Ho_Chi_Minh')
    time_str = datetime.now(tz).strftime("%d/%m/%Y %H") + ":00"
    raw = f"{identifier}MYFAP{campus}{time_str}"
    sig = hmac.new(SECRET_KEY.encode(), raw.encode(), hashlib.sha1).digest()
    return base64.b64encode(sig).decode()

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

    def load_session(self):
        if not self.session_file.exists():
            return False
        try:
            with open(self.session_file, "r", encoding="utf-8") as f:
                try:
                    data = json.load(f)
                except json.JSONDecodeError:
                    print(f"[!] Lỗi: File cấu hình '{self.session_file}' không đúng định dạng JSON.")
                    return False
            
            if not isinstance(data, dict) or "authen_key" not in data:
                print(f"[!] Lỗi: File '{self.session_file}' không chứa dữ liệu session hợp lệ của MyFAP.")
                return False
                
            self.authen_key = data.get("authen_key")
            self.mssv = data.get("mssv")
            self.email = data.get("email")
            self.jwt_token = data.get("jwt_token")
            self.refresh_token = data.get("refresh_token")
            # Campus có thể ghi đè bằng flag CLI
            # self.campus = data.get("campus", self.campus) 
            
            if not self.authen_key: return False

            # Kiểm tra session còn sống không bằng cách gọi thử API
            checksum = create_checksum(MAGIC_ID, self.campus)
            url = f"{FAP_HOST}/GetSemester?campusCode={self.campus}&Authen={self.authen_key}&checksum={checksum}"
            r = self.session.get(url, timeout=5)
            
            if r.status_code == 200:
                resp = r.json()
                if str(resp.get("code", "")) == "201":
                    return self.refresh_session()
                return True
            return self.refresh_session()
        except:
            return self.refresh_session()


    def refresh_session(self):
        if not self.refresh_token: return False
        try:
            print("[*] Phiên đăng nhập hết hạn. Đang làm mới (Refresh Token)...")
            r = self.session.post(f"{FEID_HOST}/connect/token", data={
                "client_id": CLIENT_ID, 
                "refresh_token": self.refresh_token, 
                "grant_type": "refresh_token"
            })
            if r.status_code == 200:
                resp = r.json()
                self.jwt_token = resp.get('access_token', self.jwt_token)
                if 'refresh_token' in resp:
                    self.refresh_token = resp['refresh_token']
                
                # Handshake lại để lấy authen_key mới
                checksum = create_checksum(MAGIC_ID, self.campus)
                r_handshake = self.session.post(
                    f"{FAP_HOST}/AuthenticationByFeId?campusCode={self.campus}&checksum={checksum}",
                    json={"token": self.jwt_token},
                    headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
                )
                if r_handshake.status_code == 200:
                    resp_hs = r_handshake.json()
                    if 'data' in resp_hs and len(resp_hs['data']) > 0:
                        self.authen_key = resp_hs['data'][0]['authenKey']
                        self.save_session()
                        print("[*] Làm mới phiên đăng nhập thành công!")
                        return True
                    else:
                        print(f"[!] Lỗi handshake sau khi refresh: {resp_hs}")
                        return False
                else:
                    print(f"[!] Lỗi handshake sau khi refresh (FAP trả về {r_handshake.status_code}): {r_handshake.text}")
                    return False
            else:
                print(f"[!] Lỗi từ FEID (Mã {r.status_code}): {r.text}")
                print("[!] Refresh Token thất bại hoặc đã bị thu hồi. Vui lòng chạy lệnh 'myfap login -f' để đăng nhập lại.")
                return False
        except Exception as e:
            print(f"[!] Lỗi khi Refresh Token: {e}")
            return False

    def login(self):
        print("[*] Đang khởi chạy Playwright...")
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
                        except:
                            code = location.split("code=")[1].split("&")[0]

            def handle_request(request):
                nonlocal code
                url = request.url
                if "io.identityserver.demo" in url and "code=" in url:
                    try:
                        import urllib.parse as urlparse
                        parsed = urlparse.urlparse(url)
                        code = urlparse.parse_qs(parsed.query)['code'][0]
                    except:
                        code = url.split("code=")[1].split("&")[0]

            page.on("response", handle_response)
            page.on("request", handle_request)

            print(">>> VUI LÒNG ĐĂNG NHẬP TRÊN CỬA SỔ TRÌNH DUYỆT <<<")
            try:
                page.goto(auth_url)
            except Exception:
                pass
            
            start_time = time.time()
            while not code and (time.time() - start_time) < 120:
                try:
                    page.wait_for_timeout(500)
                except:
                    break
            browser.close()

        if not code:
            raise Exception("Lỗi: Không lấy được Code từ FEID (timeout hoặc trình duyệt bị đóng).")

        print("[*] Lấy token từ Code...")
        r = self.session.post(f"{FEID_HOST}/connect/token", data={
            "client_id": CLIENT_ID, "code": code, "redirect_uri": REDIRECT_URI,
            "code_verifier": self.code_verifier, "grant_type": "authorization_code"
        })
        
        if r.status_code != 200:
            raise Exception(f"Lỗi lấy JWT Token: {r.text}")

        self.jwt_token = r.json()['access_token']
        self.refresh_token = r.json().get('refresh_token')
        
        # Lấy MSSV và email từ Token
        parts = self.jwt_token.split('.')
        payload_str = parts[1] + "=" * ((4 - len(parts[1]) % 4) % 4)
        payload = json.loads(base64.b64decode(payload_str))
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
            print(f"[*] Xin chào sinh viên: {self.mssv}")
        except:
            self.mssv = input("[?] Không tìm thấy MSSV tự động. Nhập MSSV thủ công: ")

        print("[*] Handshake với FAP API để lấy authenKey...")
        checksum = create_checksum(MAGIC_ID, self.campus)
        r = self.session.post(
            f"{FAP_HOST}/AuthenticationByFeId?campusCode={self.campus}&checksum={checksum}",
            json={"token": self.jwt_token},
            headers={"Authorization": f"Bearer {self.jwt_token}", "Content-Type": "application/json"}
        )
        if r.status_code == 200:
            resp = r.json()
            if 'data' in resp and len(resp['data']) > 0:
                self.authen_key = resp['data'][0]['authenKey']
                print("[*] Handshake thành công!")
                return self.authen_key, self.mssv
            else:
                raise Exception(f"Lỗi handshake: {resp}")
        else:
            raise Exception(f"API Error {r.status_code}: {r.text}")

if __name__ == "__main__":
    print("--- BẮT ĐẦU TEST AUTH VÀ GỌI API ---")
    campus = "APHL"
    auth = MyFapAuth(campus=campus)
    
    try:
        authen_key, mssv = auth.login()
        
        print("\n--- TEST LẤY DANH SÁCH KỲ HỌC (GetSemester) ---")
        checksum = create_checksum(MAGIC_ID, campus)
        url_sem = f"{FAP_HOST}/GetSemester?campusCode={campus}&Authen={authen_key}&checksum={checksum}"
        r_sem = requests.get(url_sem)
        semester = "Fall2025"
        if r_sem.status_code == 200:
            semesters = r_sem.json().get('data', [])
            semesters.sort(key=lambda x: x['termID'], reverse=True)
            if semesters:
                semester = semesters[0]['semesterName']
                print(f"[*] Kỳ học hiện tại: {semester}")

        print("\n--- TEST API GetActivityStudent ---")
        checksum_api = create_checksum(mssv, campus)
        url_act = f"{FAP_HOST}/GetActivityStudent?campusCode={campus}&rollNumber={mssv}&Authen={authen_key}&checksum={checksum_api}&Semester={semester}"
        r_act = requests.get(url_act)
        
        if r_act.status_code == 200:
            data = r_act.json()
            print("[*] Gọi thành công! Dữ liệu mẫu (chỉ in vài dòng đầu):")
            print(json.dumps(data, indent=2, ensure_ascii=False)[:600] + "\n...")
        else:
            print(f"[!] Lỗi gọi API: {r_act.text}")
            
    except Exception as e:
        print(f"[!] Lỗi: {e}")

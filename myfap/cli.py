import typer
from typing import Optional
import json
from .auth import MyFapAuth
from .api import MyFapClient, MyFapEssential, MyFapOther
from .parsers import parse_marks_html, convert_schedule_to_ics

app = typer.Typer(
    help="CLI Tool dựa trên MyFAP dành cho Sinh Viên FPTU",
    rich_markup_mode=None,
    add_completion=False
)

info_app = typer.Typer(help="Xem thông tin chung (sinh viên, campus)")
app.add_typer(info_app, name="info")

other_app = typer.Typer(help="Các chức năng phụ trợ khác (survey, feedback, fee...)")
app.add_typer(other_app, name="other")

# Trạng thái toàn cục (State) để lưu trữ các cờ flag
state = {
    "campus": "APHL", # Campus Hoà Lạc
    "semester": None,
    "config": None
}

def get_auth(campus=None):
    c = campus if campus else state["campus"]
    return MyFapAuth(campus=c, session_file=state.get("config"))

@app.callback()
def main(
    campus: str = typer.Option("APHL", "--campus", "-c", help="Mã cơ sở (VD: APHL, HCM, DN)"),
    config: Optional[str] = typer.Option(None, "--config", help="Đường dẫn file session tùy chỉnh (thay vì mặc định ~/.myfap-api-cli/session.json)"),
):
    """
    Công cụ quản lý thông tin sinh viên FPT qua dòng lệnh.
    """
    state["campus"] = campus
    state["config"] = config

@app.command()
def login(
    campus: Optional[str] = typer.Option(None, "--campus", "-c", help="Mã cơ sở (VD: APHL, HCM, DN)"),
    refresh: bool = typer.Option(False, "--refresh", "-r", help="Bắt buộc làm mới token không cần qua trình duyệt"),
    force: bool = typer.Option(False, "--force", "-f", help="Bắt buộc đăng nhập lại từ đầu (mở trình duyệt)")
):
    """Đăng nhập vào hệ thống FEID"""
    target_campus = campus if campus else state["campus"]
    auth = get_auth(target_campus)

    if refresh:
        import json
        if not auth.session_file.exists():
            typer.echo("Lỗi: Không tìm thấy file session. Vui lòng chạy login bình thường.")
            raise typer.Exit(1)
        try:
            with open(auth.session_file, "r", encoding="utf-8") as f:
                data = json.load(f)
        except json.JSONDecodeError:
            typer.echo(f"Lỗi: File cấu hình '{auth.session_file}' không đúng định dạng JSON.")
            raise typer.Exit(1)
        
        if not isinstance(data, dict):
            typer.echo(f"Lỗi: File '{auth.session_file}' không chứa dữ liệu hợp lệ.")
            raise typer.Exit(1)
        auth.refresh_token = data.get("refresh_token")
        auth.jwt_token = data.get("jwt_token")
        auth.authen_key = data.get("authen_key")
        auth.mssv = data.get("mssv")
        auth.email = data.get("email")
        
        if not auth.refresh_token:
            typer.echo("Lỗi: Session cũ không chứa refresh_token. Vui lòng chạy lệnh login bình thường.")
            raise typer.Exit(1)
            
        typer.echo("[*] Đang tiến hành Refresh Token thủ công...")
        if auth.refresh_session():
            typer.echo("Refresh token và lưu session thành công!")
        else:
            typer.echo("Lỗi: Refresh thất bại.")
        return

    if target_campus == "APHL":
        typer.echo(f"[*] Không nhận được tùy chọn cơ sở, mặc định sử dụng: {target_campus} (Hòa Lạc).")
        typer.echo(f"    (Mẹo: Bạn có thể dùng 'myfap login -c HCM' để đổi cơ sở)")
    else:
        typer.echo(f"[*] Đang tiến hành đăng nhập với cơ sở: {target_campus}")
        
    if not force and auth.load_session():
        typer.echo(f"Đã có session hợp lệ (User: {auth.mssv}). Không cần đăng nhập lại.")
        return
        
    try:
        auth.login()
        auth.save_session()
        typer.echo("Đăng nhập và lưu session thành công!")
    except Exception as e:
        typer.echo(f"Lỗi đăng nhập: {e}")

@app.command()
def campuses():
    """Xem danh sách các cơ sở (Campus)"""
    essential = MyFapEssential()
    try:
        data = essential.get_campuses()
        typer.echo("Danh sách các cơ sở (Campus):")
        for c in data:
            typer.echo(f"- {c.get('campusName')} (Mã: {c.get('campusCode')})")
    except Exception as e:
        typer.echo(f"Lỗi lấy danh sách cơ sở: {e}")

@app.command()
def semesters():
    """Xem danh sách kỳ học"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    other = MyFapEssential(auth)
    try:
        data = other.get_semesters()
        typer.echo(f"Danh sách kỳ học (Cơ sở {state['campus']}):")
        for s in data:
            typer.echo(f"- {s.get('semesterName')}")
    except Exception as e:
        typer.echo(f"Lỗi lấy danh sách kỳ học: {e}")

@app.command()
def schedule(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Fall2025)"),
    ics: bool = typer.Option(False, "--ics", help="Xuất lịch học ra định dạng iCalendar (.ics)")
):
    """Xem lịch học (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    client = MyFapClient(auth)
    other = MyFapEssential(auth)
    
    # Xác định kỳ học
    sem = semester
    if not sem:
        try:
            semesters = other.get_semesters()
            sem = semesters[0]['semesterName'] if semesters else "Fall2025"
            typer.echo(f"Chưa chỉ định kỳ học, tự động chọn kỳ mới nhất: {sem}")
        except Exception as e:
            typer.echo(f"Không thể lấy danh sách kỳ học: {e}")
            raise typer.Exit(code=1)
            
    # Lấy lịch học
    try:
        data = client.get_schedule(sem)
        
        if ics:
            ics_content = convert_schedule_to_ics(data)
            filename = f"LichHoc_{auth.mssv}_{sem}.ics"
            with open(filename, "w", encoding="utf-8") as f:
                f.write(ics_content)
        else:
            filename = f"LichHoc_{auth.mssv}_{sem}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            
        typer.echo(f"Đã lưu lịch học thành công ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi lấy lịch học: {e}")

@app.command()
def marks(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    courseid: Optional[str] = typer.Option(None, "--courseid", "-cid", help="Mã môn học (VD: 82934, lấy từ bảng điểm của kỳ, ko phải mã môn như PRO192, SWE201c)"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Làm đẹp bảng điểm (chỉ áp dụng khi dùng -cid)")
):
    """Xem bảng điểm (xuất JSON)"""
    if pretty and not courseid:
        typer.echo("Lỗi: --pretty (-p) chỉ được sử dụng khi truyền mã môn --courseid (-cid)")
        raise typer.Exit(code=1)
        
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    client = MyFapClient(auth)
    other = MyFapEssential(auth)

    # Nếu truyền --courseid thì bỏ qua semester và gọi GetMarkByCourse luôn
    if courseid:
        try:
            data = client.get_mark_by_course(courseid)
            filename = f"BangDiem_{courseid}_{auth.mssv}.json"
            if pretty and isinstance(data, dict) and 'data' in data and data['data'] and '<table' in data['data']:
                data['data'] = parse_marks_html(data['data'])
                filename = f"BangDiem_{courseid}_{auth.mssv}_prettier.json"
                
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            typer.echo(f"Đã lưu điểm chi tiết môn {courseid} ra file: {filename}")
        except Exception as e:
            typer.echo(f"Lỗi lấy điểm môn {courseid}: {e}")
        return
    
    # Xác định kỳ học nếu không truyền courseid
    sem = semester
    if not sem:
        try:
            semesters = other.get_semesters()
            sem = semesters[0]['semesterName'] if semesters else "Fall2025"
            typer.echo(f"Chưa chỉ định kỳ học, tự động chọn kỳ mới nhất: {sem}")
        except Exception as e:
            typer.echo(f"Không thể lấy danh sách kỳ học: {e}")
            raise typer.Exit(code=1)
            
    # Lấy bảng điểm cả kỳ
    try:
        data = client.get_marks(sem)
        filename = f"BangDiem_{auth.mssv}_{sem}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        typer.echo(f"Đã lưu bảng điểm thành công ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi lấy bảng điểm: {e}")

@app.command()
def exams(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)")
):
    """Xem lịch thi (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    client = MyFapClient(auth)
    other = MyFapEssential(auth)
    
    # Xác định kỳ học
    sem = semester
    if not sem:
        try:
            semesters = other.get_semesters()
            sem = semesters[0]['semesterName'] if semesters else "Summer2026"
            typer.echo(f"Chưa chỉ định kỳ học, tự động chọn kỳ mới nhất: {sem}")
        except Exception as e:
            typer.echo(f"Không thể lấy danh sách kỳ học: {e}")
            raise typer.Exit(code=1)
            
    # Lấy lịch thi
    try:
        data = client.get_exams(sem)
        filename = f"LichThi_{auth.mssv}_{sem}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        typer.echo(f"Đã lưu lịch thi thành công ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi lấy lịch thi: {e}")

@app.command(name="week-timetable")
def week_timetable(
    week: Optional[int] = typer.Option(None, "--week", "-w", help="Số thứ tự của tuần (VD: 20)"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Ngày cụ thể để tra cứu tuần (VD: 2026-05-17)"),
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Năm học (VD: 2026)")
):
    """Xem lịch học theo tuần (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    client = MyFapClient(auth)
    other = MyFapEssential(auth)

    from datetime import datetime
    now = datetime.now()
    
    # Xác định năm
    target_year = year or now.year
    
    # Xác định tuần
    if week:
        target_week = week
    else:
        if date:
            try:
                # Kiểm tra đúng định dạng YYYY-MM-DD không
                datetime.strptime(date, "%Y-%m-%d")
                date_str = date
            except ValueError:
                typer.echo("Lỗi: Định dạng ngày không hợp lệ. Hãy nhập đúng format YYYY-MM-DD (VD: 2026-05-17).")
                raise typer.Exit(code=1)
        else:
            date_str = now.strftime("%Y-%m-%d")
            
        try:
            target_week = other.get_week(date_str)
            if date:
                typer.echo(f"Ngày {date_str} tương ứng với: Tuần {target_week}")
            else:
                typer.echo(f"Chưa chỉ định tuần, tự động lấy tuần hiện tại (Tuần {target_week})")
        except Exception as e:
            typer.echo(f"Lỗi lấy thông tin tuần: {e}")
            raise typer.Exit(code=1)

    # Xác định kỳ học
    sem = semester
    if not sem:
        try:
            semesters = other.get_semesters()
            sem = semesters[0]['semesterName'] if semesters else "Summer2026"
            typer.echo(f"Chưa chỉ định kỳ học, tự động chọn kỳ mới nhất: {sem}")
        except Exception as e:
            typer.echo(f"Không thể lấy danh sách kỳ học: {e}")
            raise typer.Exit(code=1)
            
    # Lấy lịch học theo tuần
    try:
        data = client.get_schedule_by_week(target_week, sem, target_year)
        filename = f"LichTuan_{target_week}_{auth.mssv}_{sem}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        typer.echo(f"Đã lưu lịch học theo tuần thành công ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi lấy lịch học theo tuần: {e}")

@app.command()
def attendance(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    subject_code: Optional[str] = typer.Option(None, "--subjectcode", "-sc", help="Mã môn học (VD: PRO192)"),
    class_name: Optional[str] = typer.Option(None, "--classname", "-cn", help="Tên lớp học (VD: SE1801)")
):
    """Xem thông tin điểm danh (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    client = MyFapClient(auth)
    other = MyFapEssential(auth)

    # Xác định kỳ học
    sem = semester
    if not sem:
        try:
            semesters = other.get_semesters()
            sem = semesters[0]['semesterName'] if semesters else "Summer2026"
            typer.echo(f"Chưa chỉ định kỳ học, tự động chọn kỳ mới nhất: {sem}")
        except Exception as e:
            typer.echo(f"Không thể lấy danh sách kỳ học: {e}")
            raise typer.Exit(code=1)

    # Nếu người dùng truyền thông tin môn học và lớp
    if subject_code or class_name:
        if not (subject_code and class_name):
            typer.echo("Lỗi: Bạn phải cung cấp CẢ -sc, --subjectcode VÀ -cn, --classname để xem chi tiết điểm danh từng buổi.")
            raise typer.Exit(code=1)
            
        try:
            data = client.get_course_attendance(sem, subject_code, class_name)
            filename = f"DiemDanhChiTiet_{subject_code}_{class_name}_{auth.mssv}_{sem}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            typer.echo(f"Đã lưu chi tiết điểm danh môn {subject_code} ra file: {filename}")
        except Exception as e:
            typer.echo(f"Lỗi lấy chi tiết điểm danh: {e}")
    else:
        # Lấy trạng thái điểm danh tổng quát của toàn bộ môn trong kỳ
        try:
            data = client.get_attendances(sem)
            filename = f"DiemDanhTongQuat_{auth.mssv}_{sem}.json"
            with open(filename, "w", encoding="utf-8") as f:
                json.dump(data, f, ensure_ascii=False, indent=4)
            typer.echo(f"Đã lưu trạng thái điểm danh tổng quát ra file: {filename}")
        except Exception as e:
            typer.echo(f"Lỗi lấy trạng thái điểm danh: {e}")

@app.command()
def applications():
    """Xem danh sách đơn từ đã gửi cho trường (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    client = MyFapClient(auth)
    
    try:
        data = client.get_applications()
        filename = f"DonTu_{auth.mssv}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        typer.echo(f"Đã lưu danh sách đơn từ thành công ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi lấy danh sách đơn từ: {e}")

@app.command()
def news():
    """Xem 10 thông báo gần nhất (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
        
    other = MyFapEssential(auth)
    
    try:
        data = other.get_news()
        filename = f"ThongBao_{auth.campus}.json"
        
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
            
        typer.echo(f"Đã lưu danh sách thông báo thành công ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi lấy danh sách thông báo: {e}")

# --- SUBCOMMAND INFO ---
@info_app.command("student")
def info_student():
    """Xem thông tin sinh viên (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.")
        raise typer.Exit(code=1)
    client = MyFapClient(auth)
    try:
        data = client.get_student_info()
        filename = f"InfoStudent_{auth.mssv}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông tin sinh viên ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")

@info_app.command("campus")
def info_campus():
    """Xem thông tin phòng dịch vụ sinh viên (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn.")
        raise typer.Exit(code=1)
    client = MyFapClient(auth)
    try:
        data = client.get_campus_info()
        filename = f"InfoCampus_{auth.campus}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông tin campus ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")


# --- SUBCOMMAND OTHER ---
@other_app.command("survey")
def other_survey():
    """Kiểm tra các survey chưa thực hiện (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        typer.echo("Lỗi: Chưa đăng nhập hoặc session hết hạn.")
        raise typer.Exit(code=1)
    other_client = MyFapOther(auth)
    try:
        data = other_client.get_required_survey()
        filename = f"Survey_{auth.mssv}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông tin Survey ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")

@other_app.command("feedback")
def other_feedback():
    """Kiểm tra Feedback (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        raise typer.Exit(code=1)
    other_client = MyFapOther(auth)
    try:
        data = other_client.check_open_feedback()
        filename = f"Feedback_{auth.mssv}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông tin Feedback ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")

@other_app.command("profile")
def other_profile():
    """Kiểm tra Update Profile (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        raise typer.Exit(code=1)
    other_client = MyFapOther(auth)
    try:
        data = other_client.check_update_profile()
        filename = f"Profile_{auth.mssv}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông tin Profile ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")

@other_app.command("notification")
def other_notification():
    """Xem thông báo qua MSSV (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        raise typer.Exit(code=1)
    other_client = MyFapOther(auth)
    try:
        data = other_client.get_notification()
        filename = f"Notification_{auth.mssv}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông báo cá nhân ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")

@other_app.command("fee")
def other_fee():
    """Lấy danh sách học phí chưa thanh toán (xuất JSON)"""
    auth = get_auth()
    if not auth.load_session():
        raise typer.Exit(code=1)
    other_client = MyFapOther(auth)
    try:
        data = other_client.get_fee()
        filename = f"Fee_{auth.mssv}.json"
        with open(filename, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=4)
        typer.echo(f"Đã lưu thông tin học phí ra file: {filename}")
    except Exception as e:
        typer.echo(f"Lỗi: {e}")

if __name__ == "__main__":
    app()

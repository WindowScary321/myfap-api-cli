import typer
import json
import os
import sys
from copy import copy
from functools import wraps
from pathlib import Path
from typing import Optional
from datetime import datetime
from rich.console import Console
from rich.table import Table
from typer.core import TyperGroup

from .auth import MyFapAuth, SessionBindingError
from .api import MyFapClient, MyFapEssential, MyFapOther
from .parsers import parse_marks_html, convert_schedule_to_ics
from .config import resolve_timeout
from importlib import metadata


def _override_common_option(ctx, param, value):
    if value is not None:
        state[param.name] = value
    return value


def _validate_common_options(callback):
    @wraps(callback)
    def invoke(*args, **kwargs):
        if state["api_version"] not in (None, "v1", "v2"):
            raise typer.BadParameter("Chỉ hỗ trợ v1 hoặc v2.", param_hint="--api-version")
        try:
            state["timeout"] = resolve_timeout(state["timeout"])
        except ValueError as error:
            raise typer.BadParameter(str(error), param_hint="--timeout / MYFAP_TIMEOUT") from None
        return callback(*args, **kwargs)
    return invoke


class CommonOptionsGroup(TyperGroup):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)

        def inherit(command):
            existing = {param.name for param in command.params}
            for param in self.params:
                if param.name not in existing:
                    option = copy(param)
                    option.expose_value = False
                    option.callback = _override_common_option
                    command.params.append(option)
            if isinstance(command, TyperGroup):
                for child in command.commands.values():
                    inherit(child)
            else:
                # Validate after child options have overridden root values and environment defaults.
                command.callback = _validate_common_options(command.callback)

        for command in self.commands.values():
            inherit(command)


app = typer.Typer(
    cls=CommonOptionsGroup,
    help="CLI Tool dựa trên MyFAP dành cho Sinh Viên FPTU",
    rich_markup_mode="rich",
    add_completion=False
)

info_app = typer.Typer(help="Xem thông tin chung (sinh viên, campus)")
app.add_typer(info_app, name="info")

other_app = typer.Typer(help="Các chức năng phụ trợ khác (survey, feedback, fee...)")
app.add_typer(other_app, name="other")

state = {
    "campus": None,
    "config": None,
    "timeout": None,
    "api_version": None,
}

console = Console()
err_console = Console(stderr=True)

def get_auth(campus=None):
    c = campus if campus else state["campus"]
    return MyFapAuth(campus=c, session_file=state.get("config"), timeout=state.get("timeout"), api_version=state.get("api_version"))

def require_auth():
    auth = get_auth()
    try:
        loaded = auth.load_session()
    except Exception as error:
        err_console.print(f"[red]Lỗi kiểm tra session: {error}[/red]")
        raise typer.Exit(code=1)
    if not loaded:
        err_console.print("[red]Lỗi: Chưa đăng nhập hoặc session hết hạn. Hãy chạy 'myfap login' trước.[/red]")
        raise typer.Exit(code=1)
    return auth

def require_operation(auth, operation):
    if getattr(auth, "api_version", "v1") != "v2":
        return
    from .v2 import OPERATION_ALIASES, SUPPORTED_OPERATIONS
    operation = OPERATION_ALIASES.get(operation, operation)
    if operation not in SUPPORTED_OPERATIONS:
        err_console.print(f"[red]Lỗi: {operation} chưa được hỗ trợ trong adapter API v2.[/red]")
        raise typer.Exit(code=1)

def resolve_semester(auth, semester_flag):
    if semester_flag:
        return semester_flag
    essential = MyFapEssential(auth)
    try:
        with err_console.status("[bold green]Đang lấy danh sách kỳ học..."):
            semesters_list = essential.get_semesters()
        if not semesters_list:
            raise ValueError("Không tìm thấy kỳ học nào.")
        sem = semesters_list[0]['semesterName']
        if not isinstance(sem, str) or not sem.strip():
            raise ValueError("Kỳ học thiếu semesterName hợp lệ.")
    except Exception as error:
        err_console.print(f"[red]Lỗi chọn kỳ học: {error} Hãy chỉ định --semester.[/red]")
        raise typer.Exit(code=1)
    err_console.print(f"[yellow]Chưa chỉ định kỳ học, tự động chọn kỳ mới nhất: {sem}[/yellow]")
    return sem

def save_output(data, default_filename: str, output_dir: Optional[str], stdout: bool, is_text: bool = False):
    """Helper để xuất dữ liệu ra file hoặc stdout"""
    if stdout:
        if is_text:
            stream = getattr(sys.stdout, "buffer", None)
            if stream is None:
                sys.stdout.write(data)
            else:
                stream.write(data.encode("utf-8"))
                stream.flush()
        else:
            print(json.dumps(data, ensure_ascii=False, indent=4))
        return

    out_path = Path(output_dir) if output_dir else Path.cwd()
    out_path.mkdir(parents=True, exist_ok=True)
    file_path = out_path / default_filename

    try:
        with open(file_path, "w", encoding="utf-8", newline="" if is_text else None) as f:
            if is_text:
                f.write(data)
            else:
                json.dump(data, f, ensure_ascii=False, indent=4)
        err_console.print(f"[green]Đã lưu dữ liệu thành công ra file: {file_path}[/green]")
    except Exception as e:
        err_console.print(f"[red]Lỗi ghi file: {e}[/red]")
        raise typer.Exit(code=1)


@app.callback()
def main(
    campus: Optional[str] = typer.Option(None, "--campus", "-c", help="Mã cơ sở; dùng session, APHL chỉ mặc định cho v1"),
    config: Optional[str] = typer.Option(None, "--config", help="Đường dẫn file session tùy chỉnh"),
    timeout: Optional[float] = typer.Option(None, "--timeout", help="Timeout HTTP theo giây; ưu tiên hơn MYFAP_TIMEOUT", metavar="SECONDS"),
    api_version: Optional[str] = typer.Option(None, "--api-version", help="Chọn API v1 hoặc v2; mặc định dùng session rồi v1", metavar="[v1|v2]"),
):
    """Công cụ quản lý thông tin sinh viên FPT qua dòng lệnh."""
    state["campus"] = campus
    state["config"] = config
    state["api_version"] = api_version
    state["timeout"] = timeout

@app.command()
def version():
    """Hiển thị phiên bản MyFap API CLI"""
    try:
        ver = metadata.version("myfap")
    except metadata.PackageNotFoundError:
        ver = "unknown (not installed via pip)"
    console.print(f"MyFap API CLI version: [bold cyan]{ver}[/bold cyan]")

@app.command()
def login(
    campus: Optional[str] = typer.Option(None, "--campus", "-c", help="Mã cơ sở theo API version; ví dụ APHL (v1), HN (v2)"),
    force: bool = typer.Option(False, "--force", "-f", help="Bắt buộc đăng nhập lại từ đầu (mở trình duyệt)")
):
    """Đăng nhập vào hệ thống FEID"""
    target_campus = campus if campus else state["campus"]
    auth = get_auth(target_campus)

    try:
        if not force:
            try:
                loaded = auth.load_session()
            except SessionBindingError:
                loaded = False
            if loaded:
                err_console.print("[green]Đã có session được lưu. Dùng 'myfap login --force' để đăng nhập lại.[/green]")
                return
        auth.login()
        err_console.print("[bold green]Đăng nhập và lưu session thành công![/bold green]")
    except Exception as e:
        err_console.print(f"[bold red]Lỗi đăng nhập: {e}[/bold red]", style="red")
        raise typer.Exit(code=1)

@app.command()
def logout():
    """Đăng xuất (Xóa session)"""
    auth = get_auth()
    try:
        if auth.logout():
            err_console.print("[green]Đã xóa session thành công (Đăng xuất).[/green]")
        else:
            err_console.print("[yellow]Bạn chưa đăng nhập (không tìm thấy file session).[/yellow]")
    except Exception as error:
        err_console.print(f"[red]Lỗi đăng xuất: {error}[/red]")
        raise typer.Exit(1)

@app.command()
def refresh():
    """Làm mới token (Refresh Token)"""
    auth = get_auth()
    try:
        with err_console.status("[bold green]Đang làm mới session..."):
            success = auth.refresh_session()
    except Exception as error:
        err_console.print(f"[red]Lỗi refresh: {error}[/red]")
        raise typer.Exit(1)

    if success:
        err_console.print("[bold green]Refresh token và lưu session thành công![/bold green]")
    else:
        err_console.print("[bold red]Lỗi: Refresh thất bại.[/bold red]")
        raise typer.Exit(1)

@app.command()
def campuses():
    """Xem danh sách các cơ sở (Campus)"""
    try:
        api_version = state.get("api_version") or get_auth().resolve_api_version()
        essential = MyFapEssential(timeout=state.get("timeout"), api_version=api_version)
        with err_console.status("[bold green]Đang lấy dữ liệu..."):
            data = essential.get_campuses()
        
        table = Table(title="Danh sách các cơ sở (Campus)")
        table.add_column("Tên cơ sở", style="cyan")
        table.add_column("Mã cơ sở", style="magenta")
        
        for c in data:
            table.add_row(c.get('campusName', ''), c.get('campusCode', ''))
        
        console.print(table)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy danh sách cơ sở: {e}[/red]", style="red")
        raise typer.Exit(code=1)

@app.command()
def semesters():
    """Xem danh sách kỳ học"""
    auth = require_auth()
    other = MyFapEssential(auth)
    try:
        with err_console.status("[bold green]Đang lấy dữ liệu..."):
            data = other.get_semesters()
        
        table = Table(title=f"Danh sách kỳ học (Cơ sở {auth.campus})")
        table.add_column("Tên kỳ học", style="cyan")
        
        for s in data:
            table.add_row(s.get('semesterName', ''))
            
        console.print(table)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy danh sách kỳ học: {e}[/red]")
        raise typer.Exit(code=1)

@app.command()
def schedule(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Fall2025)"),
    ics: bool = typer.Option(False, "--ics", help="Xuất lịch học ra định dạng iCalendar (.ics)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem lịch học"""
    auth = require_auth()
    require_operation(auth, "GetActivityStudent")
    client = MyFapClient(auth)
    sem = resolve_semester(auth, semester)
            
    try:
        with err_console.status("[bold green]Đang tải lịch học..."):
            data = client.get_schedule(sem)
        
        if ics:
            ics_content = convert_schedule_to_ics(data)
            filename = f"LichHoc_{sem}.ics"
            save_output(ics_content, filename, output, stdout, is_text=True)
        else:
            filename = f"LichHoc_{sem}.json"
            save_output(data, filename, output, stdout)
            
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy lịch học: {e}[/red]")
        raise typer.Exit(code=1)

@app.command()
def marks(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    courseid: Optional[str] = typer.Option(None, "--courseid", "-cid", help="Mã môn học"),
    pretty: bool = typer.Option(False, "--pretty", "-p", help="Làm đẹp bảng điểm (chỉ áp dụng khi dùng -cid)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem bảng điểm"""
    if pretty and not courseid:
        err_console.print("[red]Lỗi: --pretty (-p) chỉ được sử dụng khi truyền mã môn --courseid (-cid)[/red]")
        raise typer.Exit(code=1)
        
    auth = require_auth()
    require_operation(auth, "GetMarkByCourse" if courseid else "GetStudentMark")
    client = MyFapClient(auth)

    if courseid:
        try:
            with err_console.status(f"[bold green]Đang tải điểm chi tiết môn {courseid}..."):
                data = client.get_mark_by_course(courseid)
            
            filename = f"BangDiem_{courseid}.json"
            if pretty and isinstance(data, dict) and 'data' in data and data['data'] and '<table' in data['data']:
                data['data'] = parse_marks_html(data['data'])
                filename = f"BangDiem_{courseid}_prettier.json"
                
            save_output(data, filename, output, stdout)
        except Exception as e:
            err_console.print(f"[red]Lỗi lấy điểm môn {courseid}: {e}[/red]")
            raise typer.Exit(code=1)
        return
    
    sem = resolve_semester(auth, semester)
            
    try:
        with err_console.status("[bold green]Đang tải bảng điểm..."):
            data = client.get_marks(sem)
        filename = f"BangDiem_{sem}.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy bảng điểm: {e}[/red]")
        raise typer.Exit(code=1)

@app.command()
def exams(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem lịch thi"""
    auth = require_auth()
    require_operation(auth, "GetScheduleExam")
    client = MyFapClient(auth)
    sem = resolve_semester(auth, semester)
            
    try:
        with err_console.status("[bold green]Đang tải lịch thi..."):
            data = client.get_exams(sem)
        filename = f"LichThi_{sem}.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy lịch thi: {e}[/red]")
        raise typer.Exit(code=1)

@app.command(name="week-timetable")
def week_timetable(
    week: Optional[int] = typer.Option(None, "--week", "-w", help="Số thứ tự của tuần (VD: 20)"),
    date: Optional[str] = typer.Option(None, "--date", "-d", help="Ngày cụ thể để tra cứu tuần (VD: 2026-05-17)"),
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    year: Optional[int] = typer.Option(None, "--year", "-y", help="Năm học (VD: 2026)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem lịch học theo tuần"""
    now = datetime.now()
    requested_date = None
    if date:
        try:
            requested_date = datetime.strptime(date, "%Y-%m-%d")
        except ValueError:
            err_console.print("[red]Lỗi: Ngày không hợp lệ. Hãy dùng YYYY-MM-DD (VD: 2026-05-17).[/red]")
            raise typer.Exit(code=1)
    target_year = year if year is not None else (requested_date.year if requested_date else now.year)

    auth = require_auth()
    require_operation(auth, "GetActivityStudentByWeek")
    client = MyFapClient(auth)
    essential = MyFapEssential(auth)

    if week is not None:
        target_week = week
    else:
        date_str = requested_date.strftime("%Y-%m-%d") if requested_date else now.strftime("%Y-%m-%d")
            
        try:
            target_week = essential.get_week(date_str)
            if date:
                err_console.print(f"Ngày {date_str} tương ứng với: Tuần {target_week}")
            else:
                err_console.print(f"Chưa chỉ định tuần, tự động lấy tuần hiện tại (Tuần {target_week})")
        except Exception as e:
            err_console.print(f"[red]Lỗi lấy thông tin tuần: {e}[/red]")
            raise typer.Exit(code=1)

    sem = resolve_semester(auth, semester)
            
    try:
        with err_console.status(f"[bold green]Đang tải lịch học tuần {target_week}..."):
            data = client.get_schedule_by_week(target_week, sem, target_year)
        filename = f"LichTuan_{target_week}_{sem}.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy lịch học theo tuần: {e}[/red]")
        raise typer.Exit(code=1)

@app.command()
def attendance(
    semester: Optional[str] = typer.Option(None, "--semester", "-s", help="Tên kỳ học (VD: Summer2026)"),
    subject_code: Optional[str] = typer.Option(None, "--subjectcode", "-sc", help="Mã môn học (VD: PRO192)"),
    class_name: Optional[str] = typer.Option(None, "--classname", "-cn", help="Tên lớp học (VD: SE1801)"),
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem thông tin điểm danh"""
    if bool(subject_code) != bool(class_name):
        err_console.print("[red]Lỗi: Cần cả --subjectcode (-sc) và --classname (-cn) để xem chi tiết điểm danh.[/red]")
        raise typer.Exit(code=1)
    auth = require_auth()
    require_operation(auth, "getCourseAttendance" if subject_code else "GetStudentAttendances")
    client = MyFapClient(auth)
    sem = resolve_semester(auth, semester)

    if subject_code or class_name:
        try:
            with err_console.status(f"[bold green]Đang tải điểm danh môn {subject_code}..."):
                data = client.get_course_attendance(sem, subject_code, class_name)
            filename = f"DiemDanhChiTiet_{subject_code}_{class_name}_{sem}.json"
            save_output(data, filename, output, stdout)
        except Exception as e:
            err_console.print(f"[red]Lỗi lấy chi tiết điểm danh: {e}[/red]")
            raise typer.Exit(code=1)
    else:
        try:
            with err_console.status("[bold green]Đang tải trạng thái điểm danh tổng quát..."):
                data = client.get_attendances(sem)
            filename = f"DiemDanhTongQuat_{sem}.json"
            save_output(data, filename, output, stdout)
        except Exception as e:
            err_console.print(f"[red]Lỗi lấy trạng thái điểm danh: {e}[/red]")
            raise typer.Exit(code=1)

@app.command()
def applications(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem danh sách đơn từ đã gửi cho trường"""
    auth = require_auth()
    client = MyFapClient(auth)
    
    try:
        with err_console.status("[bold green]Đang tải danh sách đơn từ..."):
            data = client.get_applications()
        filename = f"DonTu.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy danh sách đơn từ: {e}[/red]")
        raise typer.Exit(code=1)

@app.command()
def news(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem 10 thông báo gần nhất"""
    auth = require_auth()
    other = MyFapEssential(auth)
    
    try:
        with err_console.status("[bold green]Đang tải thông báo..."):
            data = other.get_news()
        filename = f"ThongBao.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi lấy danh sách thông báo: {e}[/red]")
        raise typer.Exit(code=1)

# --- SUBCOMMAND INFO ---
@info_app.command("student")
def info_student(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem thông tin sinh viên"""
    auth = require_auth()
    client = MyFapClient(auth)
    try:
        data = client.get_student_info()
        filename = f"InfoStudent.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)

@info_app.command("campus")
def info_campus(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem thông tin phòng dịch vụ sinh viên"""
    auth = require_auth()
    client = MyFapClient(auth)
    try:
        data = client.get_campus_info()
        filename = f"InfoCampus.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)


# --- SUBCOMMAND OTHER ---
@other_app.command("survey")
def other_survey(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Kiểm tra các survey chưa thực hiện"""
    auth = require_auth()
    other_client = MyFapOther(auth)
    try:
        data = other_client.get_required_survey()
        filename = f"Survey.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)

@other_app.command("feedback")
def other_feedback(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Kiểm tra Feedback"""
    auth = require_auth()
    other_client = MyFapOther(auth)
    try:
        data = other_client.check_open_feedback()
        filename = f"Feedback.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)

@other_app.command("profile")
def other_profile(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Kiểm tra Update Profile"""
    auth = require_auth()
    other_client = MyFapOther(auth)
    try:
        data = other_client.check_update_profile()
        filename = f"Profile.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)

@other_app.command("notification")
def other_notification(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Xem thông báo qua MSSV"""
    auth = require_auth()
    other_client = MyFapOther(auth)
    try:
        data = other_client.get_notification()
        filename = f"Notification.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)

@other_app.command("fee")
def other_fee(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Lấy danh sách học phí và trạng thái thanh toán từng khoản"""
    auth = require_auth()
    other_client = MyFapOther(auth)
    try:
        data = other_client.get_fee()
        filename = f"Fee.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)

@other_app.command("subjects")
def other_subjects(
    output: Optional[str] = typer.Option(None, "--output", "-o", help="Thư mục xuất file"),
    stdout: bool = typer.Option(False, "--stdout", help="In kết quả ra màn hình thay vì lưu file")
):
    """Lấy danh sách tất cả môn học"""
    auth = require_auth()
    other_client = MyFapOther(auth)
    try:
        with err_console.status("[bold green]Đang tải danh sách tất cả môn học..."):
            data = other_client.get_subjects()
        filename = f"Subjects.json"
        save_output(data, filename, output, stdout)
    except Exception as e:
        err_console.print(f"[red]Lỗi: {e}[/red]")
        raise typer.Exit(code=1)


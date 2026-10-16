import html
from datetime import datetime

import requests

from .auth import FAP_HOST, MAGIC_ID, create_checksum, create_survey_checksum
from .config import DEFAULT_TIMEOUT, resolve_timeout


class ApiError(Exception):
    """Lỗi API an toàn để hiển thị, không chứa response hoặc credential."""


class ApiHTTPError(ApiError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"API trả về HTTP {status_code}.")


class ApiPayloadError(ApiError):
    pass


class ApiSessionExpiredError(ApiError):
    pass


class ApiAppCheckError(ApiError):
    pass


def _check_app_check(data):
    if isinstance(data, dict) and (data.get("code") == "APP_CHECK_FAILED" or data.get("errorMessage") == "APP_CHECK_FAILED"):
        raise ApiAppCheckError("API từ chối App Check (APP_CHECK_FAILED).")


def check_api_error(data, *, allow_survey_not_found=False):
    _check_app_check(data)
    if not isinstance(data, dict) or "code" not in data or "data" not in data:
        raise ApiPayloadError("Response API phải có code và data.")
    code = data["code"]
    if isinstance(code, bool) or not isinstance(code, (str, int)):
        raise ApiPayloadError("Mã trạng thái trong response API không hợp lệ.")
    code = str(code)
    if not code.isascii() or not code.isdecimal():
        raise ApiPayloadError("Mã trạng thái trong response API không hợp lệ.")
    if code in ("201", "401"):
        raise ApiSessionExpiredError("Phiên FAP hết hạn hoặc không hợp lệ. Hãy đăng nhập lại.")
    if code == "200":
        return data
    if allow_survey_not_found and code == "404" and data["data"] is None and data.get("message") == "Data Not Found":
        return data
    raise ApiError(f"FAP API báo lỗi (mã {code}).")


def read_response(response, *, allow_survey_not_found=False):
    if response.status_code != 200:
        try:
            _check_app_check(response.json())
        except ValueError:
            pass
        raise ApiHTTPError(response.status_code)
    try:
        payload = response.json()
    except ValueError:
        raise ApiPayloadError("Response API không phải JSON hợp lệ.") from None
    return check_api_error(payload, allow_survey_not_found=allow_survey_not_found)


def clean_json(data):
    """Giải mã HTML entity trong dữ liệu do server ASP.NET trả về."""
    if isinstance(data, dict):
        return {k: clean_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [clean_json(v) for v in data]
    if isinstance(data, str):
        return html.unescape(data)
    return data


def _get(session, url, params, *, timeout=DEFAULT_TIMEOUT, allow_survey_not_found=False):
    try:
        response = session.get(url, params=params, timeout=timeout)
    except requests.RequestException:
        raise ApiError("Không kết nối được API. Hãy thử lại sau.") from None
    return clean_json(read_response(response, allow_survey_not_found=allow_survey_not_found))


def _auth_params(auth, identifier, *, campus=None, student=False):
    campus = campus or auth.campus
    params = {"campusCode": campus, "Authen": auth.authen_key, "checksum": create_checksum(identifier, campus)}
    if student:
        params["rollNumber"] = auth.mssv
    return params


def _semester_start(semester):
    error = "Kỳ học thiếu startDate hoặc ngày không hợp lệ. Hãy chỉ định --semester."
    value = semester.get("startDate") if isinstance(semester, dict) else None
    if not isinstance(value, str) or not value.strip():
        raise ApiPayloadError(error)
    value = value.strip()
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00")).date()
    except ValueError:
        raise ApiPayloadError(error) from None


def _create_session():
    session = requests.Session()
    session.headers.update({"User-Agent": "okhttp/4.9.2"})
    return session


class MyFapEssential:
    def __init__(self, auth=None, timeout=None):
        self.auth = auth
        self.timeout = resolve_timeout(timeout if timeout is not None else getattr(auth, "timeout", None), DEFAULT_TIMEOUT)
        self.session = auth.session if auth else _create_session()

    def get_campuses(self):
        """Lấy danh sách cơ sở, không cần authenKey."""
        data = _get(self.session, f"{FAP_HOST}/GetAllActiveCampus", {}, timeout=self.timeout)["data"]
        if not isinstance(data, list):
            raise ApiPayloadError("Danh sách cơ sở trong response API không hợp lệ.")
        return data

    def get_semesters(self, campus: str = None):
        """Lấy kỳ học theo startDate mới nhất; giữ thứ tự server khi trùng ngày."""
        if not self.auth:
            raise ApiError("Cần session xác thực để lấy danh sách kỳ học.")
        params = _auth_params(self.auth, MAGIC_ID, campus=campus)
        semesters = _get(self.session, f"{FAP_HOST}/GetSemester", params, timeout=self.timeout)["data"]
        if not isinstance(semesters, list):
            raise ApiPayloadError("Danh sách kỳ học trong response API không hợp lệ.")
        return sorted(semesters, key=_semester_start, reverse=True)

    def get_week(self, date_str: str):
        """Lấy số tuần tương ứng với ngày YYYY-MM-DD."""
        value = _get(self.session, f"{FAP_HOST}/GetWeekByDate", {"date": date_str}, timeout=self.timeout)["data"]
        if isinstance(value, bool) or not isinstance(value, (str, int)):
            raise ApiPayloadError("Số tuần trong response API không hợp lệ.")
        try:
            return int(value)
        except ValueError:
            raise ApiPayloadError("Số tuần trong response API không hợp lệ.") from None

    def get_news(self, news_type: int = 1):
        """Lấy 10 thông báo gần nhất."""
        if not self.auth:
            raise ApiError("Không tìm thấy session xác thực.")
        params = _auth_params(self.auth, str(news_type))
        params["type"] = news_type
        return _get(self.session, f"{FAP_HOST}/GetTop10News", params, timeout=self.timeout)


class MyFapOther:
    def __init__(self, auth, timeout=None):
        self.auth = auth
        self.timeout = resolve_timeout(timeout if timeout is not None else getattr(auth, "timeout", None), DEFAULT_TIMEOUT)
        self.session = auth.session if auth else _create_session()

    def get_required_survey(self):
        """Lấy survey và giữ nguyên trạng thái không tìm thấy dữ liệu."""
        email = getattr(self.auth, "email", None)
        username = email.strip().lower() if isinstance(email, str) else ""
        if not username:
            raise ApiError("Không tìm thấy email trong session. Hãy chạy 'myfap login' lại.")
        params = {"username": username, "checksum": create_survey_checksum(username)}
        return _get(self.session, "https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey", params, allow_survey_not_found=True, timeout=self.timeout)

    def check_open_feedback(self):
        """Kiểm tra feedback."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/CheckOpenFeedBack", params, timeout=self.timeout)

    def check_update_profile(self):
        """Kiểm tra cập nhật hồ sơ."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/CheckUpdateProfile", params, timeout=self.timeout)

    def get_notification(self):
        """Lấy thông báo theo MSSV."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/GetNotificationByRoll", params, timeout=self.timeout)

    def get_fee(self):
        """Lấy danh sách học phí và giữ trạng thái thanh toán của từng khoản."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/GeFeeByRoll", params, timeout=self.timeout)

    def get_subjects(self):
        """Lấy danh sách môn học."""
        params = _auth_params(self.auth, MAGIC_ID)
        return _get(self.session, f"{FAP_HOST}/GetSubjets", params, timeout=max(self.timeout, 30.0))


class MyFapClient:
    def __init__(self, auth, timeout=None):
        self.auth = auth
        self.timeout = resolve_timeout(timeout if timeout is not None else getattr(auth, "timeout", None), DEFAULT_TIMEOUT)
        self.session = auth.session if auth else _create_session()

    def get_schedule(self, semester: str):
        """Lấy lịch học theo kỳ."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params["Semester"] = semester
        return _get(self.session, f"{FAP_HOST}/GetActivityStudent", params, timeout=self.timeout)

    def get_marks(self, semester: str):
        """Lấy bảng điểm theo kỳ."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params["Semester"] = semester
        return _get(self.session, f"{FAP_HOST}/GetStudentMark", params, timeout=self.timeout)

    def get_mark_by_course(self, course_id: str):
        """Lấy điểm chi tiết của môn học, gồm dữ liệu HTML."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params["CourseId"] = course_id
        return _get(self.session, f"{FAP_HOST}/GetMarkByCourse", params, timeout=self.timeout)

    def get_exams(self, semester: str):
        """Lấy lịch thi theo kỳ."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params["Semester"] = semester
        return _get(self.session, f"{FAP_HOST}/GetScheduleExam", params, timeout=self.timeout)

    def get_schedule_by_week(self, week: int, semester: str, year: int):
        """Lấy lịch học theo tuần."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params.update({"week": week, "Semester": semester, "year": year})
        return _get(self.session, f"{FAP_HOST}/GetActivityStudentByWeek", params, timeout=self.timeout)

    def get_attendances(self, semester: str):
        """Lấy trạng thái điểm danh tổng quát theo kỳ."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params["Semester"] = semester
        return _get(self.session, f"{FAP_HOST}/GetStudentAttendances", params, timeout=self.timeout)

    def get_course_attendance(self, semester: str, subject_code: str, class_name: str):
        """Lấy chi tiết điểm danh một môn học."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        params.update({"Semester": semester, "SubjectCode": subject_code, "ClassName": class_name})
        return _get(self.session, f"{FAP_HOST}/getCourseAttendance", params, timeout=self.timeout)

    def get_applications(self):
        """Lấy danh sách đơn đã gửi."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/GetApplication", params, timeout=self.timeout)

    def get_student_info(self):
        """Lấy thông tin sinh viên."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/GetStudentById", params, timeout=self.timeout)

    def get_campus_info(self):
        """Lấy thông tin phòng dịch vụ sinh viên."""
        params = _auth_params(self.auth, self.auth.mssv, student=True)
        return _get(self.session, f"{FAP_HOST}/GetCampusInfo", params, timeout=self.timeout)

import html
from datetime import datetime

import requests

from .auth import FAP_HOST, MAGIC_ID, create_checksum, create_survey_checksum
from .config import DEFAULT_TIMEOUT, resolve_timeout
from .errors import (
    AUTHENTICATED_READ_OPERATIONS,
    ApiAppCheckError,
    ApiError,
    ApiHTTPError,
    ApiOperationError,
    ApiPayloadError,
    ApiSessionExpiredError,
    check_api_error,
    read_response,
)


def clean_json(data):
    """Giải mã HTML entity trong dữ liệu do server ASP.NET trả về."""
    if isinstance(data, dict):
        return {k: clean_json(v) for k, v in data.items()}
    if isinstance(data, list):
        return [clean_json(v) for v in data]
    if isinstance(data, str):
        return html.unescape(data)
    return data


READ_OPERATIONS = AUTHENTICATED_READ_OPERATIONS | {"GetAllActiveCampus", "GetWeekByDate", "GetRequiredSurvey"}


def _get(session, url, params, *, timeout=DEFAULT_TIMEOUT, allow_survey_not_found=False,
         auth=None, operation=None, params_factory=None, api_version="v1", response_api_version=None):
    current_params = params
    retried = False
    while True:
        if auth is not None:
            _ensure_bound(auth, campus=current_params.get("campusCode"), api_version=api_version)
        try:
            response = session.get(url, params=current_params, timeout=timeout, allow_redirects=False)
        except requests.RequestException:
            raise ApiError("Không kết nối được API. Hãy thử lại sau.") from None
        try:
            return clean_json(read_response(response, allow_survey_not_found=allow_survey_not_found, api_version=response_api_version or api_version, operation=operation))
        except ApiSessionExpiredError:
            if retried or operation not in READ_OPERATIONS or auth is None or "Authen" not in params or params_factory is None:
                raise
            refresh = getattr(auth, "refresh_session", None)
            if not callable(refresh) or not refresh():
                raise
            retried = True
            current_params = params_factory()


def _v2_request(session, auth, operation, *, timeout, campus=None, params=None):
    from . import v2

    retried = False
    while True:
        _ensure_bound(auth, campus=campus, api_version="v2")
        credential = auth.authen_key if auth is not None and operation in AUTHENTICATED_READ_OPERATIONS else None
        response = v2.request(session, operation, credential=credential,
                              campus=campus or getattr(auth, "campus", None),
                              params=params, timeout=timeout)
        try:
            return clean_json(read_response(response, api_version="v2", operation=operation))
        except ApiSessionExpiredError:
            if retried or operation not in AUTHENTICATED_READ_OPERATIONS or auth is None:
                raise
            refresh = getattr(auth, "refresh_session", None)
            if not callable(refresh) or not refresh():
                raise
            retried = True


def _auth_params(auth, identifier, *, campus=None, student=False):
    campus = campus or auth.campus
    _ensure_bound(auth, campus=campus, api_version="v1")
    params = {"campusCode": campus, "Authen": auth.authen_key, "checksum": create_checksum(identifier, campus)}
    if student:
        params["rollNumber"] = auth.mssv
    return params


def _resolve_api_version(auth, api_version=None):
    version = api_version if api_version is not None else getattr(auth, "api_version", "v1")
    if version not in ("v1", "v2"):
        raise ApiError("API version phải là v1 hoặc v2.")
    return version


def _ensure_bound(auth, *, campus=None, api_version=None):
    if auth is None:
        return
    version = _resolve_api_version(auth, api_version)
    if version != getattr(auth, "api_version", "v1"):
        raise ApiError("API version không khớp session. Hãy đăng nhập lại với --api-version đã chọn.")
    hook = getattr(auth, "ensure_bound", None)
    if callable(hook):
        hook(campus=campus or auth.campus, api_version=version, account_type=getattr(auth, "account_type", None))


def _authenticated_get(session, auth, operation, identifier, *, timeout, campus=None, student=False, params=None, api_version=None):
    version = _resolve_api_version(auth, api_version)
    if version == "v2":
        query = {"rollNumber": auth.mssv, **(params or {})} if student else params
        return _v2_request(session, auth, operation, timeout=timeout, campus=campus, params=query)

    def build_params():
        return {**_auth_params(auth, identifier, campus=campus, student=student), **(params or {})}

    return _get(session, f"{FAP_HOST}/{operation}", build_params(), timeout=timeout,
                auth=auth, operation=operation, params_factory=build_params)


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
    def __init__(self, auth=None, timeout=None, api_version=None):
        self.auth = auth
        self.api_version = _resolve_api_version(auth, api_version)
        _ensure_bound(auth, api_version=self.api_version)
        self.timeout = resolve_timeout(timeout if timeout is not None else getattr(auth, "timeout", None), DEFAULT_TIMEOUT)
        self.session = auth.session if auth else _create_session()

    def get_campuses(self):
        """Lấy danh sách cơ sở, không cần authenKey."""
        if self.api_version == "v2":
            payload = _v2_request(self.session, self.auth, "GetAllActiveCampus", timeout=self.timeout)
        else:
            payload = _get(self.session, f"{FAP_HOST}/GetAllActiveCampus", {}, timeout=self.timeout, auth=self.auth, operation="GetAllActiveCampus")
        data = payload["data"]
        if not isinstance(data, list):
            raise ApiPayloadError("Danh sách cơ sở trong response API không hợp lệ.")
        return data

    def get_api_active(self):
        """Chẩn đoán proxy v2 khi được gọi rõ ràng, không đổi API version."""
        if self.api_version != "v2":
            raise ApiError("GetApiActive chưa được hỗ trợ trên API v1. Hãy chọn --api-version v2.")
        return _v2_request(self.session, self.auth, "GetApiActive", timeout=self.timeout)

    def get_semesters(self, campus: str = None):
        """Lấy kỳ học theo startDate mới nhất; giữ thứ tự server khi trùng ngày."""
        if not self.auth:
            raise ApiError("Cần session xác thực để lấy danh sách kỳ học.")
        semesters = _authenticated_get(self.session, self.auth, "GetSemester", MAGIC_ID,
                                       campus=campus, timeout=self.timeout, api_version=self.api_version)["data"]
        if not isinstance(semesters, list):
            raise ApiPayloadError("Danh sách kỳ học trong response API không hợp lệ.")
        return sorted(semesters, key=_semester_start, reverse=True)

    def get_week(self, date_str: str):
        """Lấy số tuần tương ứng với ngày YYYY-MM-DD."""
        if self.api_version == "v2":
            return _v2_request(self.session, self.auth, "GetWeekByDate", params={"date": date_str}, timeout=self.timeout)
        value = _get(self.session, f"{FAP_HOST}/GetWeekByDate", {"date": date_str}, timeout=self.timeout,
                     auth=self.auth, operation="GetWeekByDate")["data"]
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
        return _authenticated_get(self.session, self.auth, "GetTop10News", str(news_type),
                                  params={"type": news_type}, timeout=self.timeout, api_version=self.api_version)


class MyFapOther:
    def __init__(self, auth, timeout=None, api_version=None):
        self.auth = auth
        self.api_version = _resolve_api_version(auth, api_version)
        _ensure_bound(auth, api_version=self.api_version)
        self.timeout = resolve_timeout(timeout if timeout is not None else getattr(auth, "timeout", None), DEFAULT_TIMEOUT)
        self.session = auth.session if auth else _create_session()

    def get_required_survey(self):
        """Lấy survey và giữ nguyên trạng thái không tìm thấy dữ liệu."""
        email = getattr(self.auth, "email", None)
        username = email.strip().lower() if isinstance(email, str) else ""
        if not username:
            raise ApiError("Không tìm thấy email trong session. Hãy chạy 'myfap login' lại.")
        params = {"username": username, "checksum": create_survey_checksum(username)}
        return _get(self.session, "https://survey.fpt.edu.vn/API/myFAP/GetRequiredSurvey", params, allow_survey_not_found=True, timeout=self.timeout,
                    auth=self.auth, operation="GetRequiredSurvey", api_version=self.api_version, response_api_version="v1")

    def check_open_feedback(self):
        """Kiểm tra feedback."""
        return _authenticated_get(self.session, self.auth, "CheckOpenFeedBack", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

    def check_update_profile(self):
        """Kiểm tra cập nhật hồ sơ."""
        return _authenticated_get(self.session, self.auth, "CheckUpdateProfile", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

    def get_notification(self):
        """Lấy thông báo theo MSSV."""
        return _authenticated_get(self.session, self.auth, "GetNotificationByRoll", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

    def get_fee(self):
        """Lấy danh sách học phí và giữ trạng thái thanh toán của từng khoản."""
        return _authenticated_get(self.session, self.auth, "GeFeeByRoll", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

    def get_subjects(self):
        """Lấy danh sách môn học."""
        return _authenticated_get(self.session, self.auth, "GetSubjets", MAGIC_ID,
                                  timeout=max(self.timeout, 30.0), api_version=self.api_version)


class MyFapClient:
    def __init__(self, auth, timeout=None, api_version=None):
        self.auth = auth
        self.api_version = _resolve_api_version(auth, api_version)
        _ensure_bound(auth, api_version=self.api_version)
        self.timeout = resolve_timeout(timeout if timeout is not None else getattr(auth, "timeout", None), DEFAULT_TIMEOUT)
        self.session = auth.session if auth else _create_session()

    def get_schedule(self, semester: str):
        """Lấy lịch học theo kỳ."""
        return _authenticated_get(self.session, self.auth, "GetActivityStudent", self.auth.mssv,
                                  student=True, params={"Semester": semester}, timeout=self.timeout, api_version=self.api_version)

    def get_marks(self, semester: str):
        """Lấy bảng điểm theo kỳ."""
        return _authenticated_get(self.session, self.auth, "GetStudentMark", self.auth.mssv,
                                  student=True, params={"Semester": semester}, timeout=self.timeout, api_version=self.api_version)

    def get_mark_by_course(self, course_id: str):
        """Lấy điểm chi tiết của môn học, gồm dữ liệu HTML."""
        return _authenticated_get(self.session, self.auth, "GetMarkByCourse", self.auth.mssv,
                                  student=True, params={"CourseId": course_id}, timeout=self.timeout, api_version=self.api_version)

    def get_exams(self, semester: str):
        """Lấy lịch thi theo kỳ."""
        return _authenticated_get(self.session, self.auth, "GetScheduleExam", self.auth.mssv,
                                  student=True, params={"Semester": semester}, timeout=self.timeout, api_version=self.api_version)

    def get_schedule_by_week(self, week: int, semester: str, year: int):
        """Lấy lịch học theo tuần."""
        return _authenticated_get(self.session, self.auth, "GetActivityStudentByWeek", self.auth.mssv,
                                  student=True, params={"week": week, "Semester": semester, "year": year}, timeout=self.timeout, api_version=self.api_version)

    def get_attendances(self, semester: str):
        """Lấy trạng thái điểm danh tổng quát theo kỳ."""
        return _authenticated_get(self.session, self.auth, "GetStudentAttendances", self.auth.mssv,
                                  student=True, params={"Semester": semester}, timeout=self.timeout, api_version=self.api_version)

    def get_course_attendance(self, semester: str, subject_code: str, class_name: str):
        """Lấy chi tiết điểm danh một môn học."""
        return _authenticated_get(self.session, self.auth, "getCourseAttendance", self.auth.mssv,
                                  student=True, params={"Semester": semester, "SubjectCode": subject_code, "ClassName": class_name}, timeout=self.timeout, api_version=self.api_version)

    def get_applications(self):
        """Lấy danh sách đơn đã gửi."""
        return _authenticated_get(self.session, self.auth, "GetApplication", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

    def get_student_info(self):
        """Lấy thông tin sinh viên."""
        return _authenticated_get(self.session, self.auth, "GetStudentById", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

    def get_campus_info(self):
        """Lấy thông tin phòng dịch vụ sinh viên."""
        return _authenticated_get(self.session, self.auth, "GetCampusInfo", self.auth.mssv,
                                  student=True, timeout=self.timeout, api_version=self.api_version)

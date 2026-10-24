"""Safe API response validation and error classification."""


class ApiError(Exception):
    """Lỗi API an toàn để hiển thị, không chứa response hoặc credential."""


class ApiHTTPError(ApiError):
    def __init__(self, status_code):
        self.status_code = status_code
        super().__init__(f"API trả về HTTP {status_code}.")


class ApiPayloadError(ApiError):
    pass


class ApiOperationError(ApiError):
    """Lỗi nghiệp vụ của một operation, không tự suy diễn là hết phiên."""

    def __init__(self, message, *, api_version="v1", operation=None, code=None):
        self.api_version = api_version
        self.operation = operation
        self.code = str(code) if code is not None else None
        super().__init__(message)


class ApiSessionExpiredError(ApiHTTPError):
    def __init__(self, status_code=401):
        self.status_code = status_code
        ApiError.__init__(self, "Phiên FAP hết hạn hoặc không hợp lệ. Hãy đăng nhập lại.")


class ApiAppCheckError(ApiError):
    pass


AUTHENTICATED_READ_OPERATIONS = frozenset({
    "GetSemester", "GetTop10News", "CheckOpenFeedBack", "CheckUpdateProfile",
    "GetNotificationByRoll", "GeFeeByRoll", "GetSubjets", "GetBalance",
    "GetActivityStudent", "GetCourseOfSemester", "GetSubjectBySemester", "SearchNews", "AcademicTranscript", "GetDiemphongtrao", "RetriveImage",
    "GetStudentMark", "GetSemesterMark",
    "GetMarkByCourse", "GetScheduleExam",
    "GetStudentAttendances",
    "GetActivityStudentByWeek",
    "getCourseAttendance", "GetApplication", "GetStudentById", "GetCampusInfo",
})


def _check_app_check(data):
    if isinstance(data, dict) and (
        data.get("code") == "APP_CHECK_FAILED" or data.get("errorMessage") == "APP_CHECK_FAILED"
    ):
        raise ApiAppCheckError("API từ chối App Check (APP_CHECK_FAILED).")


def check_api_error(data, *, allow_survey_not_found=False, api_version="v1", operation=None):
    _check_app_check(data)
    if api_version == "v2" and isinstance(data, dict) and data.get("errorMessage") == "Unauthorized":
        raise ApiSessionExpiredError()
    if not isinstance(data, dict) or "code" not in data:
        raise ApiPayloadError("Response API phải có code và data.")
    code = data["code"]
    if isinstance(code, bool) or not isinstance(code, (str, int)):
        raise ApiPayloadError("Mã trạng thái trong response API không hợp lệ.")
    code = str(code)
    if not code.isascii() or not code.isdecimal():
        raise ApiPayloadError("Mã trạng thái trong response API không hợp lệ.")
    if api_version == "v2" and code == "401":
        raise ApiSessionExpiredError()
    if (
        api_version == "v1"
        and operation in AUTHENTICATED_READ_OPERATIONS
        and code == "201"
        and data.get("message") == "Token invalid"
    ):
        # Retry only known FAP reads with an explicit application-level expiry.
        raise ApiSessionExpiredError(200)
    if "data" not in data:
        raise ApiPayloadError("Response API phải có code và data.")
    if code == "200":
        return data
    if allow_survey_not_found and code == "404" and data["data"] is None and data.get("message") == "Data Not Found":
        return data
    raise ApiOperationError(
        f"FAP API báo lỗi (mã {code}).",
        api_version=api_version, operation=operation, code=code,
    )


def read_response(response, *, allow_survey_not_found=False, api_version="v1", operation=None):
    try:
        payload = response.json()
    except (ValueError, AttributeError):
        payload = None
    if isinstance(payload, dict):
        _check_app_check(payload)
    if response.status_code != 200:
        if response.status_code == 401:
            raise ApiSessionExpiredError(401)
        raise ApiHTTPError(response.status_code)
    if payload is None:
        raise ApiPayloadError("Response API không phải JSON hợp lệ.")
    return check_api_error(payload, allow_survey_not_found=allow_survey_not_found, api_version=api_version, operation=operation)

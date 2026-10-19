"""HTTP contracts for the opt-in FAP proxy adapter."""

import base64
import hashlib
import hmac
import time
from datetime import date

import requests

from .auth_var import FAP_PROXY_HOST, V2_BOOTSTRAP_TOKEN, V2_CLIENT_CODE, V2_SECRET_KEY
from .config import DEFAULT_TIMEOUT, resolve_timeout
from .errors import ApiError


BOOTSTRAP_OPERATIONS = frozenset({"GetAllActiveCampus", "GetApiActive"})
OPERATION_ALIASES = {"getCourseAttendance": "GetCourseAttendance"}
_READ_QUERY_FIELDS = {
    "GetSemester": (),
    "GetTop10News": ("type",),
    "CheckOpenFeedBack": ("rollNumber",),
    "CheckUpdateProfile": ("rollNumber",),
    "GetNotificationByRoll": ("rollNumber",),
    "GeFeeByRoll": ("rollNumber",),
    "GetSubjets": (),
    "GetActivityStudent": ("rollNumber", "Semester"),
    "GetStudentMark": ("rollNumber", "Semester"),
    "GetMarkByCourse": ("rollNumber", "CourseId"),
    "GetScheduleExam": ("rollNumber", "Semester"),
    "GetStudentAttendances": ("rollNumber", "Semester"),
    "GetActivityStudentByWeek": ("rollNumber", "Semester", "week", "year"),
    "GetCourseAttendance": ("rollNumber", "Semester", "SubjectCode", "ClassName"),
    "GetApplication": ("rollNumber",),
    "GetStudentById": ("rollNumber",),
    "GetCampusInfo": ("rollNumber",),
    "GetWeekByDate": ("date",),
}
_AUTHEN_QUERY_OPERATIONS = frozenset({"CheckOpenFeedBack", "CheckUpdateProfile", "GetApplication", "GetNotificationByRoll"})
READ_OPERATIONS = frozenset(_READ_QUERY_FIELDS)
SUPPORTED_OPERATIONS = BOOTSTRAP_OPERATIONS | READ_OPERATIONS | {"AuthenticationByFeId"}


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and not any(ord(character) < 32 for character in value)


def _positive_int(value):
    return (
        isinstance(value, int) and not isinstance(value, bool) and value > 0
        or isinstance(value, str) and value.isascii() and value.isdecimal() and bool(value.strip("0"))
    )


def _read_params(operation, params, campus, credential):
    query = {}
    if operation not in {"GetSemester", "GetWeekByDate"}:
        if params.pop("CampusCode", campus) != campus:
            raise ApiError("Campus trong query API v2 không khớp session.")
        query["CampusCode"] = campus
    if set(params) != set(_READ_QUERY_FIELDS[operation]):
        raise ApiError("Query của operation API v2 không hợp lệ.")
    for field, value in params.items():
        valid = _positive_int(value) if field in {"type", "week", "year"} else _text(value)
        if field == "CourseId":
            valid = valid or isinstance(value, int) and not isinstance(value, bool) and value > 0
        if field == "date" and valid:
            try:
                valid = date.fromisoformat(value).isoformat() == value
            except ValueError:
                valid = False
        if not valid:
            raise ApiError("Giá trị trong query API v2 không hợp lệ.")
    query.update(params)
    if operation in _AUTHEN_QUERY_OPERATIONS:
        # The query and signature must use the same freshly bound key after refresh.
        query["Authen"] = credential
    return query


def create_checksum(credential, timestamp=None):
    if timestamp is None:
        timestamp = int(time.time())
    if not _text(credential) or isinstance(timestamp, bool) or not isinstance(timestamp, int) or timestamp < 0:
        raise ApiError("Thông số ký request API v2 không hợp lệ.")
    message = f"{credential}{V2_CLIENT_CODE}{timestamp}".encode("utf-8")
    # CryptoJS receives the original string key, not bytes decoded from hex.
    digest = hmac.new(V2_SECRET_KEY.encode("utf-8"), message, hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode("ascii").replace("=", "%3d")
    return f"{signature}:{timestamp}"


def request(session, operation, *, credential=None, campus=None, params=None, body=None, timeout=DEFAULT_TIMEOUT):
    if not isinstance(operation, str) or operation not in SUPPORTED_OPERATIONS:
        raise ApiError("Operation này chưa được hỗ trợ trong adapter API v2.")
    if params is None:
        params = {}
    if not isinstance(params, dict):
        raise ApiError("Query API v2 không hợp lệ.")
    params = dict(params)
    method, payload = "GET", None
    if operation in BOOTSTRAP_OPERATIONS:
        if credential is not None or params or body not in (None, {}):
            raise ApiError("Bootstrap API v2 chỉ nhận query và JSON rỗng.")
        credential, campus, method, payload = V2_BOOTSTRAP_TOKEN, "HN", "POST", {}
    else:
        if not _text(credential) or not _text(campus):
            raise ApiError("Thiếu credential hoặc campus hợp lệ cho API v2.")
        if operation == "AuthenticationByFeId":
            payload = {"token": credential}
            if params or body is not None and body != payload:
                raise ApiError("Body handshake API v2 không hợp lệ.")
            method = "POST"
        else:
            if body is not None:
                raise ApiError("Operation đọc API v2 không nhận JSON body.")
            params = _read_params(operation, params, campus, credential)
    headers = {
        "Accept": "application/json, text/plain, */*",
        "Accept-Encoding": "gzip",
        "User-Agent": "okhttp/4.9.2",
        "ClientCode": V2_CLIENT_CODE,
        "CampusCode": campus,
        "Authorization": f"Bearer {credential}",
        "Checksum": create_checksum(credential),
    }
    kwargs = {"params": params, "headers": headers, "timeout": resolve_timeout(timeout, DEFAULT_TIMEOUT), "allow_redirects": False}
    if method == "POST":
        headers["Content-Type"] = "application/json"
        kwargs["json"] = payload
    try:
        return session.request(method, f"{FAP_PROXY_HOST}/{operation}", **kwargs)
    except requests.RequestException:
        raise ApiError("Không kết nối được API v2. Hãy thử lại sau.") from None

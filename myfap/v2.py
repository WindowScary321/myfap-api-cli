"""HTTP contracts for the opt-in FAP proxy adapter."""

import base64
import hashlib
import hmac
import time

import requests

from .auth_var import FAP_PROXY_HOST, V2_BOOTSTRAP_TOKEN, V2_CLIENT_CODE, V2_SECRET_KEY
from .config import DEFAULT_TIMEOUT, resolve_timeout
from .errors import ApiError


BOOTSTRAP_OPERATIONS = frozenset({"GetAllActiveCampus", "GetApiActive"})
READ_OPERATIONS = frozenset({"GetSemester", "GetActivityStudent"})
SUPPORTED_OPERATIONS = BOOTSTRAP_OPERATIONS | READ_OPERATIONS | {"AuthenticationByFeId"}


def _text(value):
    return isinstance(value, str) and bool(value.strip()) and not any(ord(character) < 32 for character in value)


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
        if operation == "GetActivityStudent":
            query_campus = params.pop("CampusCode", campus)
            if query_campus != campus or set(params) != {"rollNumber", "Semester"} or not all(_text(value) for value in params.values()) or body is not None:
                raise ApiError("Query lịch học API v2 không hợp lệ.")
            params = {"CampusCode": campus, **params}
        elif params:
            raise ApiError("Operation API v2 này yêu cầu query rỗng.")
        if operation == "AuthenticationByFeId":
            payload = {"token": credential}
            if body is not None and body != payload:
                raise ApiError("Body handshake API v2 không hợp lệ.")
            method = "POST"
        elif body is not None:
            raise ApiError("Operation đọc API v2 không nhận JSON body.")
    headers = {
        "ClientCode": V2_CLIENT_CODE,
        "Content-Type": "application/json",
        "CampusCode": campus,
        "Authorization": f"Bearer {credential}",
        "Checksum": create_checksum(credential),
    }
    kwargs = {"params": params, "headers": headers, "timeout": resolve_timeout(timeout, DEFAULT_TIMEOUT), "allow_redirects": False}
    if method == "POST":
        kwargs["json"] = payload
    try:
        return session.request(method, f"{FAP_PROXY_HOST}/{operation}", **kwargs)
    except requests.RequestException:
        raise ApiError("Không kết nối được API v2. Hãy thử lại sau.") from None

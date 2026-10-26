"""Strict response reader scoped to GetSemesterMark, not a generic text fallback."""

import json

from .errors import ApiPayloadError, read_response


MAX_SUMMARY_BYTES = 1024 * 1024


def read_semester_marks_response(response, *, api_version):
    if response.status_code != 200:
        read_response(response, api_version=api_version, operation="GetSemesterMark")
    content = getattr(response, "content", b"")
    if isinstance(content, bytes) and len(content) > MAX_SUMMARY_BYTES:
        raise ApiPayloadError("Response tổng kết vượt giới hạn xử lý cục bộ.")
    try:
        payload = response.json()
    except (ValueError, AttributeError):
        payload = None
    # Preserve the common HTTP, App Check and explicit expiry classifications.
    if response.status_code != 200 or isinstance(payload, dict):
        envelope = read_response(response, api_version=api_version, operation="GetSemesterMark")
        if not isinstance(envelope["data"], list):
            raise ApiPayloadError("Dữ liệu tổng kết phải là một danh sách.")
        return envelope
    if isinstance(payload, str):
        try:
            payload = json.loads(payload)
        except ValueError:
            raise ApiPayloadError("Định dạng tổng kết chưa được hỗ trợ.") from None
    if not isinstance(payload, list):
        raise ApiPayloadError("Response tổng kết không có danh sách hợp lệ.")
    return {"code": 200, "data": payload}

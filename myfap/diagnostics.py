"""Allowlisted diagnostics without reading or refreshing the user's session."""

from importlib import metadata

from .api import MyFapEssential, READ_OPERATIONS
from .errors import ApiError, ApiPayloadError
from .v2 import SUPPORTED_OPERATIONS


def get_diagnostics(*, api_version=None, campus=None, timeout=None, online=False):
    version = "v1" if api_version is None else api_version
    if version not in ("v1", "v2"):
        raise ApiError("API version phải là v1 hoặc v2.")
    if campus is not None and (
        not isinstance(campus, str) or not campus.strip()
        or any(ord(character) < 32 or ord(character) == 127 for character in campus)
    ):
        raise ApiError("Campus chẩn đoán không hợp lệ.")
    if online and version != "v2":
        raise ApiError("Probe GetApiActive chỉ hỗ trợ v2; hãy chọn --api-version v2.")
    try:
        package_version = metadata.version("myfap")
    except metadata.PackageNotFoundError:
        package_version = "unknown"
    operations = SUPPORTED_OPERATIONS | {"GetRequiredSurvey"} if version == "v2" else READ_OPERATIONS
    report = {
        "package_version": package_version,
        "api_version": version,
        "api_version_source": "default" if api_version is None else "explicit",
        "campus": campus,
        "available_operations": sorted(operations),
        "session_validation": "not_checked",
        "online_probe": {"requested": False},
    }
    if online:
        client = MyFapEssential(api_version="v2", timeout=timeout)
        try:
            payload = client.get_api_active()
            if not isinstance(payload.get("data"), bool):
                raise ApiPayloadError("Response GetApiActive phải chứa data boolean.")
            version_payload = client.get_version()
        finally:
            client.session.close()
        version = version_payload.get("data")
        if not isinstance(version, str) or not version.strip():
            raise ApiPayloadError("Response GetVersion phải chứa data chuỗi không rỗng.")
        report["online_probe"] = {
            "requested": True, "operation": "GetApiActive", "bootstrap_campus": "HN",
            "api_active": payload["data"], "backend_version": version, "scope": "proxy_bootstrap_only",
        }
    return report

import math
import os


DEFAULT_TIMEOUT = 10.0


def resolve_timeout(value=None, default=None):
    value = value if value is not None else os.getenv("MYFAP_TIMEOUT")
    if value is None:
        return default
    error = "Timeout phải là số giây hữu hạn lớn hơn 0. Hãy sửa --timeout hoặc MYFAP_TIMEOUT."
    try:
        timeout = float(value)
    except (TypeError, ValueError, OverflowError):
        raise ValueError(error) from None
    if not math.isfinite(timeout) or timeout <= 0:
        raise ValueError(error)
    return timeout

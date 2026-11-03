"""Input checking shared by every feature, and the error type handlers raise."""
from datetime import date


class ApiError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status
        self.message = message


MAX_TEXT = 20_000


def text(body: dict, key: str, *, required=False, max_len=MAX_TEXT) -> str:
    value = body.get(key, "")
    if value is None:
        value = ""
    if not isinstance(value, str):
        raise ApiError(400, f"{key} must be text")
    value = value.strip()
    if required and not value:
        raise ApiError(400, f"{key} is required")
    if len(value) > max_len:
        raise ApiError(400, f"{key} is too long (max {max_len} characters)")
    return value


def parse_date(value: str) -> str:
    try:
        return date.fromisoformat(value).isoformat()
    except (TypeError, ValueError):
        raise ApiError(400, "Date must be YYYY-MM-DD")


def parse_id(value, what="id") -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ApiError(400, f"Invalid {what}")

from datetime import datetime

__all__ = ["ensure_timezone_aware"]


def ensure_timezone_aware(dt: datetime) -> datetime:
    if dt.tzinfo is None:
        # use local timezone instead of UTC
        local_tz = datetime.now().astimezone().tzinfo
        return dt.replace(tzinfo=local_tz)
    return dt

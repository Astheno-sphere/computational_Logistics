import json
import sys
from typing import Tuple
# from decorator import decorator
import datetime
import time
from loguru import logger
import humanize
from settings import Settings, settings


# @decorator
# def time_it(func, *args, **kwargs):
#     start = time.perf_counter()
#     result = func(*args, **kwargs)
#     end = time.perf_counter()
#     print(f"Function '{func.__name__}' executed in {end - start:.6f} seconds")
#     return result


def to_24h_timestamp(timestamp: int) -> int:
    """
    Convert a timestamp to a 24-hour format.
    :param timestamp: The timestamp to convert.
    :return: The converted timestamp in 24-hour format.
    """
    return timestamp % (24 * 60 * 60)  # Assuming timestamp is in seconds


def to_timestamp_based_on_day(target_24h_timestamp: int, based_on: int) -> int:
    """
    Convert a target 24-hour timestamp to a timestamp based on a given day.
    :param target_24h_timestamp: The target 24-hour timestamp to convert.
    :param based_on: The base timestamp to use for conversion.
    :return: The converted timestamp based on the given day.
    """
    return (based_on // (24 * 60 * 60)) * (24 * 60 * 60) + target_24h_timestamp


def to_24h_timestamp_full(timestamp: int) -> Tuple[int, int]:
    """ :return: The converted timestamp in 24-hour format as a tuple of (day_of_week, total_seconds_in_day). """
    d_ = datetime.datetime.fromtimestamp(timestamp)
    day_of_week = d_.weekday()  # Monday is 0 and Sunday is 6
    total_seconds_in_day = timestamp % (24 * 60 * 60)
    return day_of_week, total_seconds_in_day


def ensure_timestamp_in_seconds(timestamp: int) -> int:
    """
    Ensure the timestamp is in seconds.
    :param timestamp: The timestamp to check.
    :return: The timestamp in seconds.
    """
    if timestamp > 1_000_000_0000:
        return timestamp // 1000
    return timestamp


def get_weekday_category(timestamp: int) -> int:
    """
    Get the weekday category based on the timestamp.
    :param timestamp: The timestamp to check.
    :return: The category of the day (0: Monday, 1: Tuesday, 2: Wednesday, 3: Thursday, 4: Friday, 5: Saturday, 6: Sunday).
    """
    timestamp = ensure_timestamp_in_seconds(timestamp)
    weekday = datetime.datetime.fromtimestamp(timestamp).weekday()
    return "Weekend" if weekday >= 5 else "Weekday"


def categorize_date_time_short(timestamp: int) -> int:
    """
    Categorize the time of day based on the timestamp.
    :param timestamp: The timestamp to categorize.
    :return: The category of the time of day (0: night, 1: morning, 2: afternoon, 3: evening).
    """
    timestamp = ensure_timestamp_in_seconds(timestamp)

    def _get_day_time():
        hour = datetime.datetime.fromtimestamp(timestamp).hour
        if 6 <= hour < 12:
            return "morning"
        elif 12 <= hour < 18:
            return "afternoon"
        elif 18 <= hour < 24:
            return "evening"
        else:
            return "night"
        
    return datetime.datetime.fromtimestamp(timestamp).strftime('%A') + f" {_get_day_time()}"


def humanize_date(timestamp: int) -> str:
    """
    Convert a timestamp to a human-readable date string.
    :param timestamp: The timestamp to convert.
    :return: The converted date string in the format "YYYY-MM-DD HH:MM:SS".
    """
    timestamp = ensure_timestamp_in_seconds(timestamp)
    return datetime.datetime.fromtimestamp(timestamp).strftime('%d %B %Y, %H:%M')


def humanize_date_short(timestamp: int) -> str:
    """
    Convert a timestamp to a human-readable date string.
    :param timestamp: The timestamp to convert.
    :return: The converted date string in the format "YYYY-MM-DD HH:MM:SS".
    """
    timestamp = ensure_timestamp_in_seconds(timestamp)
    return datetime.datetime.fromtimestamp(timestamp).strftime('%A, %H:%M')


def format_route_id(route_id: str) -> str:
    if ":" in route_id:
        return route_id.replace("line:", "").replace(":", " ")
    return route_id


def duration_to_bucket_text(seconds) -> str:
    if seconds < 60:
        return "very short (under 1 minute)"
    elif seconds < 5*60:
        return "short (under 5 minutes)"
    elif seconds < 10*60:
        return "moderate (under 10 minutes)"
    elif seconds < 20*60:
        return "long (under 20 minutes)"
    else:
        return "very long (20 minutes or more)"


def time_to_bucket_text(timestamp: int) -> str:
    hour = datetime.datetime.fromtimestamp(timestamp).hour
    if 6 <= hour <= 10:
        return "morning rush hour (6:00 - 10:00)"
    if 10 < hour <= 16:
        return "daytime (10:00 - 16:00)"
    if 16 < hour <= 20:
        return "evening rush hour (16:00 - 20:00)"
    return "night time (20:00 - 6:00)"


def humanize_time(timestamp: int) -> str:
    """
    Convert a timestamp to a human-readable hour string.
    :param timestamp: The timestamp to convert.
    :return: The converted hour string in the format "HH:MM".
    """
    timestamp = ensure_timestamp_in_seconds(timestamp)
    return datetime.datetime.fromtimestamp(timestamp).strftime('%H:%M')


def humanize_duration(seconds: int) -> str:
    """
    Convert a duration in seconds to a human-readable string.
    :param duration: The duration in seconds to convert.
    :return: The converted duration string in the format "X hours Y minutes".
    """
    duration = datetime.timedelta(seconds=seconds)
    # The duration shoule be like 1 hour, 15 minutes and 16 seconds, we drop the seconds
    return humanize.precisedelta(duration).split("and")[0].strip()


def time_window_generalize(timestamp: int) -> str:
    timestamp = ensure_timestamp_in_seconds(timestamp)
    hour = datetime.datetime.fromtimestamp(timestamp).hour
    if hour < 6:
        return "early morning"
    elif hour < 9:
        return "morning rush hour"
    elif hour < 12:
        return "morning"
    elif hour < 16:
        return "afternoon"
    elif hour < 18:
        return "end of the workday"
    else:
        return "evening"
    

def lower_first_char(s: str) -> str:
    if not s:
        return s
    return s[0].lower() + s[1:]


def create_json_logger():
    # Remove default stdout sink
    logger.remove()

    NOT_SYSTEM_LOG = ["history"]

    # STDOUT: only show system logs
    logger.add(
        sink=sys.stdout,
        filter=lambda record: record["extra"].get("log_type") not in NOT_SYSTEM_LOG,
        level=settings.app.log_level,
    )

    # log system log to file
    logger.add(
        sink=settings.app.log_file,
        filter=lambda record: record["extra"].get("log_type") not in NOT_SYSTEM_LOG,
        level=settings.app.log_level,
    )

    # log history to file
    def json_sink(message):
        with open(settings.app.history_file, "a") as f:
            f.write(json.dumps({
                "time": message.record["time"].isoformat(),
                "message": message.record["message"],
                **message.record["extra"]
            }, ensure_ascii=False) + "\n")

    logger.add(
        sink=json_sink,
        filter=lambda record: record["extra"].get("log_type") == "history",
    )


def setup_logging(settings: Settings):
    """Configure loguru logging based on settings."""
    logger.remove()  # Remove default handler
    
    # Add console handler
    logger.add(
        sys.stderr,
        level=settings.app.log_level,
        format="<green>{time:YYYY-MM-DD HH:mm:ss}</green> | <level>{level: <8}</level> | <cyan>{name}</cyan>:<cyan>{function}</cyan>:<cyan>{line}</cyan> - <level>{message}</level>"
    )
    
    # Add file handler if log_file is specified
    if settings.app.log_file:
        logger.add(
            settings.app.log_file,
            level=settings.app.log_level,
            rotation="10 MB",
            retention="7 days"
        )

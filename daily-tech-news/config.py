"""Load application settings from environment variables."""

import os
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from dotenv import load_dotenv

load_dotenv()

MONGODB_URI = os.getenv("MONGODB_URI", "mongodb://localhost:27017/")
MONGODB_DATABASE = os.getenv("MONGODB_DATABASE", "tech_news")


def _read_schedule_value(name: str, default: int, minimum: int, maximum: int) -> int:
    """Read and validate an integer schedule setting."""
    value = os.getenv(name, str(default))

    try:
        parsed_value = int(value)
    except ValueError as error:
        raise ValueError(f"{name} must be an integer.") from error

    if not minimum <= parsed_value <= maximum:
        raise ValueError(f"{name} must be between {minimum} and {maximum}.")

    return parsed_value


NEWS_SCHEDULE_HOUR = _read_schedule_value("NEWS_SCHEDULE_HOUR", 6, 0, 23)
NEWS_SCHEDULE_MINUTE = _read_schedule_value("NEWS_SCHEDULE_MINUTE", 0, 0, 59)
NEWS_TIMEZONE = os.getenv("NEWS_TIMEZONE", "Asia/Kolkata")

try:
    ZoneInfo(NEWS_TIMEZONE)
except (ZoneInfoNotFoundError, ValueError) as error:
    raise ValueError("NEWS_TIMEZONE must be a valid timezone name.") from error

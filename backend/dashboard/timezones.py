"""Timezone selection for on-screen timestamps. Uses the stdlib zoneinfo
(Python 3.9+) rather than pytz — no extra dependency, and this app already
targets an offline embedded kiosk (see app.py's font-stack comment for the
same reasoning applied there)."""
from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

TIMEZONES = {
    "UTC": "UTC",
    "ET": "America/New_York",
    "CT": "America/Chicago",
    "MT": "America/Denver",
    "PT": "America/Los_Angeles",
    "IST": "Asia/Kolkata",
}

DEFAULT_TZ_KEY = "UTC"


def get_zone(tz_key: str) -> ZoneInfo:
    return ZoneInfo(TIMEZONES.get(tz_key, TIMEZONES[DEFAULT_TZ_KEY]))


def now_in(tz_key: str) -> datetime:
    return datetime.now(get_zone(tz_key))


def format_ts(unix_ts: float, tz_key: str, with_date: bool = False) -> str:
    dt = datetime.fromtimestamp(unix_ts, tz=get_zone(tz_key))
    return dt.strftime("%Y-%m-%d %H:%M:%S" if with_date else "%H:%M:%S")


def format_iso(iso_string: str, tz_key: str) -> str:
    """Converts an ISO-8601 timestamp string (as stored in JSON, always
    UTC-aware from pydantic) to HH:MM:SS in the selected timezone."""
    dt = datetime.fromisoformat(iso_string)
    return dt.astimezone(get_zone(tz_key)).strftime("%H:%M:%S")

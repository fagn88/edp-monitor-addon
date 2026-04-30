# helpers.py — pure logic for EDP Voucher Monitor
"""
No Selenium / no requests imports. Stdlib only so tests.py can run anywhere.
"""

from datetime import datetime, timedelta


def parse_attempt_time(time_str: str, ref: datetime) -> datetime:
    """Parse 'HH:MM' into a datetime on the same date as ref."""
    h, m = time_str.strip().split(":")
    return ref.replace(hour=int(h), minute=int(m), second=0, microsecond=0)


def next_day_at(time_str: str, now: datetime) -> datetime:
    """Return tomorrow's date at the given HH:MM."""
    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return parse_attempt_time(time_str, tomorrow)

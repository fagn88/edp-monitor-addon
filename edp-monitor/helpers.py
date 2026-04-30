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


def compute_cycle_start(now: datetime, start_day: int, attempt_times: list) -> datetime:
    """Return the next datetime to wake up at to begin a new cycle.

    Cases (in order of evaluation):
    - Today's date < start_day: this month's start_day at attempt_times[0]
    - Today's date == start_day and any attempt_time is still future: that future slot today
    - Today's date == start_day but all slots have passed: next month's start_day at attempt_times[0]
    - Today's date > start_day: next month's start_day at attempt_times[0]
    """
    if now.day < start_day:
        target = now.replace(day=start_day, hour=0, minute=0, second=0, microsecond=0)
        return parse_attempt_time(attempt_times[0], target)

    if now.day == start_day:
        for slot_str in attempt_times:
            slot = parse_attempt_time(slot_str, now)
            if slot > now:
                return slot
        # All slots passed → fall through to next-month logic

    # Today > start_day OR (today == start_day and all slots past)
    if now.month == 12:
        next_month = datetime(now.year + 1, 1, start_day)
    else:
        next_month = datetime(now.year, now.month + 1, start_day)
    return parse_attempt_time(attempt_times[0], next_month)


def log(msg: str, level: str = "INFO", _now: datetime | None = None) -> None:
    """Print a timestamped log line to stdout, flushed.

    `_now` is for testing; real callers don't pass it.
    """
    ts = (_now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)

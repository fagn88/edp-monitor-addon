# helpers.py — pure logic for EDP Voucher Monitor
"""
No Selenium / no requests imports. Stdlib only so tests.py can run anywhere.
"""

import json
import os
import re
import time
from datetime import datetime, timedelta


PT_MONTHS = {
    "jan": 1, "fev": 2, "mar": 3, "abr": 4, "mai": 5, "jun": 6,
    "jul": 7, "ago": 8, "set": 9, "out": 10, "nov": 11, "dez": 12,
}


def parse_attempt_time(time_str: str, ref: datetime) -> datetime:
    """Parse 'HH:MM' into a datetime on the same date as ref."""
    h, m = time_str.strip().split(":")
    return ref.replace(hour=int(h), minute=int(m), second=0, microsecond=0)


def log(msg: str, level: str = "INFO", _now: datetime | None = None) -> None:
    """Print a timestamped log line to stdout, flushed.

    `_now` is for testing; real callers don't pass it.
    """
    ts = (_now or datetime.now()).strftime("%Y-%m-%d %H:%M:%S")
    print(f"[{ts}] [{level}] {msg}", flush=True)


def parse_voucher_status(body_text: str, button_disabled: bool,
                         codigos_disponiveis: int | None = None) -> tuple:
    """Decide voucher state from page body text + main button's disabled
    flag + the parsed `Códigos disponíveis: N` count.

    Returns (available, status_code):
      (True,  "disponivel")            — button enabled, can claim now
      (False, "saldo_insuficiente")    — in stock but balance too low
      (False, "esgotado")              — out of stock for this cycle
      (None,  "precisa_login")         — login redirect detected
      (None,  "erro: estado_incerto")  — unrecognised state
    """
    lowered = body_text.lower()

    if (("login" in lowered or "iniciar" in lowered) and len(body_text) < 500):
        return (None, "precisa_login")

    if not button_disabled:
        return (True, "disponivel")

    if "saldo insuficiente" in lowered:
        return (False, "saldo_insuficiente")

    if "esgotad" in lowered or "volte no próximo" in lowered:
        return (False, "esgotado")

    # Strongest signal: explicit zero count means there's nothing to claim,
    # regardless of what surrounding copy the portal happens to use.
    if codigos_disponiveis == 0:
        return (False, "esgotado")

    return (None, "erro: estado_incerto")


def sleep_until(target: datetime) -> None:
    """Sleep in 1-hour chunks until `target` is reached.

    Chunked so SIGTERM during an HA addon stop can interrupt promptly.
    """
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            return
        chunk = min(remaining, 3600)
        time.sleep(chunk)


def month_key(now: datetime) -> str:
    """Return 'YYYY-MM' for grouping claims by month."""
    return now.strftime("%Y-%m")


def load_history(path: str) -> dict:
    """Load claim history from disk. Returns {} if missing or corrupt.

    Schema: {voucher_name: {"month": "YYYY-MM", "code": str,
                            "validity": str, "claimed_at": ISO8601}}
    """
    try:
        with open(path) as f:
            data = json.load(f)
        if not isinstance(data, dict):
            return {}
        return data
    except (FileNotFoundError, json.JSONDecodeError):
        return {}


def save_history(path: str, name: str, month: str, code: str, validity: str,
                 claimed_at: datetime) -> None:
    """Atomically update one entry in the history file."""
    history = load_history(path)
    history[name] = {
        "month": month,
        "code": code,
        "validity": validity,
        "claimed_at": claimed_at.isoformat(timespec="seconds"),
    }
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(history, f, indent=2, ensure_ascii=False)
        f.flush()
        os.fsync(f.fileno())
    os.replace(tmp, path)


def unclaimed_for_month(targets: list, history: dict, month: str) -> list:
    """Return list of target names that have no history entry for `month`."""
    return [t["name"] for t in targets
            if history.get(t["name"], {}).get("month") != month]


def _first_of_next_month(now: datetime, start_day: int, first_slot: str) -> datetime:
    """Return next month's start_day at first_slot."""
    if now.month == 12:
        nm = datetime(now.year + 1, 1, start_day)
    else:
        nm = datetime(now.year, now.month + 1, start_day)
    return parse_attempt_time(first_slot, nm)


def compute_next_wakeup(now: datetime, history: dict, targets: list,
                        start_day: int, attempt_times: list) -> datetime:
    """Decide when to next attempt a claim, considering already-claimed history.

    Returns a datetime in the future. Caller sleeps until then, then runs
    one attempt for each target still unclaimed for the wakeup's month.

    Cases (in evaluation order):
    1. All targets already claimed for the current month → next month's
       start_day at attempt_times[0].
    2. Today is before this month's start_day → this month's start_day at
       attempt_times[0].
    3. Today is at-or-past start_day with unclaimed targets:
       a. If any attempt_time today is still in the future → that slot.
       b. Else if tomorrow is still in the current month → tomorrow at
          attempt_times[0].
       c. Else (today is end-of-month, all slots passed) → next month's
          start_day at attempt_times[0].
    """
    current = month_key(now)
    if not unclaimed_for_month(targets, history, current):
        return _first_of_next_month(now, start_day, attempt_times[0])

    if now.day < start_day:
        target_day = now.replace(day=start_day, hour=0, minute=0,
                                 second=0, microsecond=0)
        return parse_attempt_time(attempt_times[0], target_day)

    for slot_str in attempt_times:
        slot = parse_attempt_time(slot_str, now)
        if slot > now:
            return slot

    tomorrow = (now + timedelta(days=1)).replace(hour=0, minute=0,
                                                  second=0, microsecond=0)
    if tomorrow.month != now.month:
        return _first_of_next_month(now, start_day, attempt_times[0])
    return parse_attempt_time(attempt_times[0], tomorrow)


def parse_validity_to_month(text: str) -> str | None:
    """Parse 'Até DD Mmm YYYY' (Portuguese) into a 'YYYY-MM' month key.

    Returns None if no recognisable validity is found in `text`.
    Examples:
      'Até 31 Mai 2026'  → '2026-05'
      'até 28 fev 2026'  → '2026-02'
      'no validity here' → None
    """
    m = re.search(r"At[ée]\s+\d{1,2}\s+([A-Za-zçÇ]{3,})\s+(\d{4})",
                  text, re.IGNORECASE)
    if not m:
        return None
    month_pt = m.group(1).lower()[:3]
    if month_pt not in PT_MONTHS:
        return None
    return f"{m.group(2)}-{PT_MONTHS[month_pt]:02d}"


def find_claimed_targets(active_codes: list, targets: list,
                         current_month: str) -> dict:
    """Match portal active codes against config targets for the current month.

    `active_codes` is a list of (partner_text, validity_text) tuples scraped
    from /beneficios/ativos. `targets` is config.targets list.

    Returns {target_name: validity_text} for targets that have an active code
    whose validity falls in `current_month`.
    """
    matched = {}
    for target in targets:
        name = target["name"]
        if name in matched:
            continue
        for partner_text, validity_text in active_codes:
            if name.lower() not in partner_text.lower():
                continue
            month = parse_validity_to_month(validity_text)
            if month == current_month:
                matched[name] = validity_text
                break
    return matched


def should_run_immediately(now: datetime, history: dict, targets: list,
                           start_day: int) -> bool:
    """At startup (or manual restart), decide whether to run an attempt
    right away — used so that `hassio.addon_restart` doubles as a
    'try claim now' button.

    True when there are unclaimed targets for the current month AND we're
    at-or-past start_day. Time-of-day inside the day doesn't matter:
    extra attempts are idempotent (claim flow only fires when button enabled).
    """
    current = month_key(now)
    if not unclaimed_for_month(targets, history, current):
        return False
    return now.day >= start_day

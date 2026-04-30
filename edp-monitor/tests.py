# tests.py — stdlib-only test runner for helpers.py
"""
Run with: python3 tests.py
Tests only the pure logic in helpers.py (no Selenium, no requests).
"""

import sys
import traceback
from datetime import datetime


def run_all_tests():
    tests = [(name, fn) for name, fn in globals().items()
             if name.startswith("test_") and callable(fn)]
    failed = 0
    for name, fn in tests:
        try:
            fn()
            print(f"PASS  {name}")
        except AssertionError as e:
            failed += 1
            print(f"FAIL  {name}: {e}")
        except Exception as e:
            failed += 1
            print(f"ERROR {name}: {type(e).__name__}: {e}")
            traceback.print_exc()
    total = len(tests)
    print(f"\n{total - failed}/{total} passed")
    return failed


def test_runner_works():
    # Sanity check that the runner finds and executes tests
    assert 1 + 1 == 2


from helpers import parse_attempt_time, next_day_at


def test_parse_attempt_time_basic():
    ref = datetime(2026, 5, 1, 12, 0)
    got = parse_attempt_time("08:05", ref)
    assert got == datetime(2026, 5, 1, 8, 5), got


def test_parse_attempt_time_strips_whitespace():
    ref = datetime(2026, 5, 1, 12, 0)
    got = parse_attempt_time("  09:05 ", ref)
    assert got == datetime(2026, 5, 1, 9, 5), got


def test_parse_attempt_time_invalid_raises():
    ref = datetime(2026, 5, 1, 12, 0)
    try:
        parse_attempt_time("nope", ref)
        assert False, "should have raised"
    except ValueError:
        pass


def test_next_day_at_basic():
    now = datetime(2026, 5, 1, 23, 0)
    got = next_day_at("08:05", now)
    assert got == datetime(2026, 5, 2, 8, 5), got


def test_next_day_at_crosses_month():
    now = datetime(2026, 5, 31, 23, 0)
    got = next_day_at("08:05", now)
    assert got == datetime(2026, 6, 1, 8, 5), got


from helpers import compute_cycle_start


def test_cycle_start_today_is_before_start_day():
    # Today = May 15, start_day = 20 → wait for May 20 first slot
    now = datetime(2026, 5, 15, 14, 0)
    got = compute_cycle_start(now, 20, ["08:05", "08:35", "09:05"])
    assert got == datetime(2026, 5, 20, 8, 5), got


def test_cycle_start_today_is_start_day_with_future_slot():
    # Today = May 1 at 07:00, start_day = 1 → 08:05 today
    now = datetime(2026, 5, 1, 7, 0)
    got = compute_cycle_start(now, 1, ["08:05", "08:35", "09:05"])
    assert got == datetime(2026, 5, 1, 8, 5), got


def test_cycle_start_today_is_start_day_between_slots():
    # Today = May 1 at 08:20, start_day = 1 → 08:35 today (next future slot)
    now = datetime(2026, 5, 1, 8, 20)
    got = compute_cycle_start(now, 1, ["08:05", "08:35", "09:05"])
    assert got == datetime(2026, 5, 1, 8, 35), got


def test_cycle_start_today_is_start_day_all_slots_past():
    # Today = May 1 at 23:00, start_day = 1 → next month's start_day
    now = datetime(2026, 5, 1, 23, 0)
    got = compute_cycle_start(now, 1, ["08:05", "08:35", "09:05"])
    assert got == datetime(2026, 6, 1, 8, 5), got


def test_cycle_start_today_is_past_start_day():
    # Today = May 5, start_day = 1 → next month's start_day
    now = datetime(2026, 5, 5, 14, 0)
    got = compute_cycle_start(now, 1, ["08:05", "08:35", "09:05"])
    assert got == datetime(2026, 6, 1, 8, 5), got


def test_cycle_start_year_rollover():
    # Today = Dec 5, start_day = 1 → Jan 1 next year
    now = datetime(2026, 12, 5, 14, 0)
    got = compute_cycle_start(now, 1, ["08:05"])
    assert got == datetime(2027, 1, 1, 8, 5), got


import io
import contextlib
from helpers import log


def test_log_default_level_info():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        log("hello", _now=datetime(2026, 4, 30, 22, 15, 30))
    out = buf.getvalue()
    assert out == "[2026-04-30 22:15:30] [INFO] hello\n", repr(out)


def test_log_custom_level():
    buf = io.StringIO()
    with contextlib.redirect_stdout(buf):
        log("oops", level="ERROR", _now=datetime(2026, 4, 30, 22, 15, 30))
    out = buf.getvalue()
    assert out == "[2026-04-30 22:15:30] [ERROR] oops\n", repr(out)


from helpers import parse_voucher_status


def test_status_disponivel_when_button_enabled():
    text = "Códigos disponíveis: 2 usa 3 € Como usar..."
    available, status = parse_voucher_status(text, button_disabled=False)
    assert available is True and status == "disponivel", (available, status)


def test_status_saldo_insuficiente():
    text = "Códigos disponíveis: 2 Saldo insuficiente. Tente novamente ao receber o seu saldo mensal"
    available, status = parse_voucher_status(text, button_disabled=True)
    assert available is False and status == "saldo_insuficiente", (available, status)


def test_status_esgotado_via_esgotad():
    text = "Esgotado neste momento. Volte no próximo mês"
    available, status = parse_voucher_status(text, button_disabled=True)
    assert available is False and status == "esgotado", (available, status)


def test_status_esgotado_via_volte_no_proximo():
    text = "Volte no próximo mês para ver mais ofertas"
    available, status = parse_voucher_status(text, button_disabled=True)
    assert available is False and status == "esgotado", (available, status)


def test_status_precisa_login_short_body_with_iniciar():
    text = "Iniciar sessão"
    available, status = parse_voucher_status(text, button_disabled=True)
    assert available is None and status == "precisa_login", (available, status)


def test_status_erro_estado_incerto_when_button_disabled_and_no_known_text():
    text = "Algo estranho aconteceu, sem texto conhecido"
    available, status = parse_voucher_status(text, button_disabled=True)
    assert available is None and status.startswith("erro"), (available, status)


if __name__ == "__main__":
    sys.exit(run_all_tests())

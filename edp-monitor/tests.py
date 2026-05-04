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


from helpers import parse_attempt_time


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


from helpers import (
    compute_next_wakeup,
    load_history,
    month_key,
    save_history,
    should_run_immediately,
    unclaimed_for_month,
)
import os
import tempfile

TARGETS_ONE = [{"name": "Pingo Doce", "partner_id": 1197}]
TARGETS_TWO = [{"name": "Pingo Doce", "partner_id": 1197},
               {"name": "Domino's", "partner_id": 1199}]
SLOTS = ["08:05", "08:35", "09:05"]


def test_month_key():
    assert month_key(datetime(2026, 5, 4, 10, 0)) == "2026-05"
    assert month_key(datetime(2026, 12, 31, 23, 59)) == "2026-12"


def test_load_history_missing_returns_empty():
    assert load_history("/nonexistent/path/xxx.json") == {}


def test_load_history_corrupt_returns_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("not valid json {{{")
        path = f.name
    try:
        assert load_history(path) == {}
    finally:
        os.unlink(path)


def test_load_history_non_dict_returns_empty():
    with tempfile.NamedTemporaryFile(mode="w", suffix=".json", delete=False) as f:
        f.write("[1, 2, 3]")
        path = f.name
    try:
        assert load_history(path) == {}
    finally:
        os.unlink(path)


def test_save_then_load_roundtrip():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        save_history(path, "Pingo Doce", "2026-05", "ABC123", "31/05/2026",
                     datetime(2026, 5, 4, 9, 35, 12))
        h = load_history(path)
        assert h["Pingo Doce"]["month"] == "2026-05"
        assert h["Pingo Doce"]["code"] == "ABC123"
        assert h["Pingo Doce"]["validity"] == "31/05/2026"
        assert h["Pingo Doce"]["claimed_at"] == "2026-05-04T09:35:12"
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_save_history_preserves_other_entries():
    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as f:
        path = f.name
    os.unlink(path)
    try:
        save_history(path, "Pingo Doce", "2026-05", "AAA", "x",
                     datetime(2026, 5, 4))
        save_history(path, "Domino's", "2026-05", "BBB", "y",
                     datetime(2026, 5, 4))
        h = load_history(path)
        assert set(h.keys()) == {"Pingo Doce", "Domino's"}
        assert h["Pingo Doce"]["code"] == "AAA"
        assert h["Domino's"]["code"] == "BBB"
    finally:
        if os.path.exists(path):
            os.unlink(path)


def test_unclaimed_for_month_all_unclaimed():
    assert unclaimed_for_month(TARGETS_TWO, {}, "2026-05") == \
        ["Pingo Doce", "Domino's"]


def test_unclaimed_for_month_partial():
    history = {"Pingo Doce": {"month": "2026-05", "code": "x"}}
    assert unclaimed_for_month(TARGETS_TWO, history, "2026-05") == ["Domino's"]


def test_unclaimed_for_month_old_claim_doesnt_count():
    history = {"Pingo Doce": {"month": "2026-04", "code": "x"}}
    assert unclaimed_for_month(TARGETS_ONE, history, "2026-05") == ["Pingo Doce"]


def test_unclaimed_for_month_all_claimed():
    history = {"Pingo Doce": {"month": "2026-05", "code": "x"},
               "Domino's": {"month": "2026-05", "code": "y"}}
    assert unclaimed_for_month(TARGETS_TWO, history, "2026-05") == []


def test_next_wakeup_all_claimed_jumps_to_next_month():
    # Mid-May, voucher already claimed for May → June 1 first slot
    now = datetime(2026, 5, 4, 9, 30)
    history = {"Pingo Doce": {"month": "2026-05", "code": "x"}}
    got = compute_next_wakeup(now, history, TARGETS_ONE, 1, SLOTS)
    assert got == datetime(2026, 6, 1, 8, 5), got


def test_next_wakeup_before_start_day():
    # Today = May 15, start_day = 20 → May 20 first slot
    now = datetime(2026, 5, 15, 14, 0)
    got = compute_next_wakeup(now, {}, TARGETS_ONE, 20, SLOTS)
    assert got == datetime(2026, 5, 20, 8, 5), got


def test_next_wakeup_today_with_future_slot():
    # Today = May 4 at 08:20, start_day = 1 → next slot 08:35
    now = datetime(2026, 5, 4, 8, 20)
    got = compute_next_wakeup(now, {}, TARGETS_ONE, 1, SLOTS)
    assert got == datetime(2026, 5, 4, 8, 35), got


def test_next_wakeup_today_all_slots_passed_tomorrow_in_month():
    # Today = May 4 at 23:00, all slots passed → May 5 first slot
    now = datetime(2026, 5, 4, 23, 0)
    got = compute_next_wakeup(now, {}, TARGETS_ONE, 1, SLOTS)
    assert got == datetime(2026, 5, 5, 8, 5), got


def test_next_wakeup_end_of_month_all_slots_passed():
    # Today = May 31 at 23:00, slots passed → June 1 first slot
    now = datetime(2026, 5, 31, 23, 0)
    got = compute_next_wakeup(now, {}, TARGETS_ONE, 1, SLOTS)
    assert got == datetime(2026, 6, 1, 8, 5), got


def test_next_wakeup_year_rollover():
    now = datetime(2026, 12, 31, 23, 0)
    got = compute_next_wakeup(now, {}, TARGETS_ONE, 1, SLOTS)
    assert got == datetime(2027, 1, 1, 8, 5), got


def test_next_wakeup_partial_claimed_keeps_today_schedule():
    # 2 targets, 1 claimed → still daily schedule for the other
    now = datetime(2026, 5, 4, 8, 20)
    history = {"Pingo Doce": {"month": "2026-05", "code": "x"}}
    got = compute_next_wakeup(now, history, TARGETS_TWO, 1, SLOTS)
    assert got == datetime(2026, 5, 4, 8, 35), got


def test_should_run_immediately_yes_when_unclaimed_and_past_start_day():
    now = datetime(2026, 5, 4, 9, 30)
    assert should_run_immediately(now, {}, TARGETS_ONE, 1) is True


def test_should_run_immediately_yes_when_unclaimed_and_on_start_day():
    now = datetime(2026, 5, 1, 7, 0)
    assert should_run_immediately(now, {}, TARGETS_ONE, 1) is True


def test_should_run_immediately_no_when_before_start_day():
    now = datetime(2026, 5, 15, 14, 0)
    assert should_run_immediately(now, {}, TARGETS_ONE, 20) is False


def test_should_run_immediately_no_when_all_claimed_this_month():
    now = datetime(2026, 5, 4, 9, 30)
    history = {"Pingo Doce": {"month": "2026-05", "code": "x"}}
    assert should_run_immediately(now, history, TARGETS_ONE, 1) is False


def test_should_run_immediately_yes_when_old_claim_only():
    # Previous month's claim doesn't count
    now = datetime(2026, 5, 4, 9, 30)
    history = {"Pingo Doce": {"month": "2026-04", "code": "x"}}
    assert should_run_immediately(now, history, TARGETS_ONE, 1) is True


if __name__ == "__main__":
    sys.exit(run_all_tests())

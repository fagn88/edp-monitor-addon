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


if __name__ == "__main__":
    sys.exit(run_all_tests())

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


if __name__ == "__main__":
    sys.exit(run_all_tests())

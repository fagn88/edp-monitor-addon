# Changelog

## 1.2.0

- **Auto-claim**: when a target voucher is detected as available, the addon now clicks through the full claim flow (Gerar código → accept terms → confirm) and captures the generated code, sending it in the ntfy notification body.
- **New schedule**: replaced random 4–6min interval with explicit daily slots (`attempt_times`, default 08:05/08:35/09:05). Cycle starts on `start_day` (default 1) and retries every day until all configured `targets` are claimed.
- **End-of-day notification**: a single ntfy message after the last slot of a day if any target is still unclaimed; no more spam between attempts.
- **Login flow**: on detected login expiry, sends ntfy immediately and repeats every `login_reminder_interval` seconds (default 600s = 10min) until login is restored, then resumes mid-day.
- **Config schema changed**: `targets` (list of `{name, partner_id}`), `start_day`, `attempt_times`, `login_reminder_interval`. Removed: `check_interval_min`, `check_interval_max`, `schedule_hour`.
- **Logging**: all log lines now `[YYYY-MM-DD HH:MM:SS] [LEVEL]`-prefixed and flushed on every call.
- **Refactor**: pure logic split into `helpers.py`; `tests.py` runs stdlib-only with `python3 tests.py`.
- **Selectors validated** 2026-04-30 against the live portal via Chrome DevTools MCP (Domino's voucher claim, code DEDP2526).

## 1.1.1

- Open browser at startup for login validation via noVNC
- Notify if login is needed on addon start
- Reuse browser session for scheduled monitoring

## 1.1.0

- Add monthly auto-scheduling (default: day 1 at 00:00)
- Add configurable `schedule_day` and `schedule_hour` options
- Change boot mode to `auto` (addon starts with Home Assistant)
- Add notification when monitoring starts
- Add notification when login is required or expired
- Add notification on driver/browser errors
- Add notification with next scheduled execution date

## 1.0.2

- Add debug logging with unbuffered output
- Add import verification at startup
- Add traceback on fatal errors
- Fix Python output buffering issue

## 1.0.1

- Simplify to single s6 service
- Add `init: false` to config
- Combine Xvfb, x11vnc, noVNC, and monitor in single run script
- Fix s6-overlay compatibility

## 1.0.0

- Initial release
- Monitors EDP Packs voucher availability
- Sends ntfy push notifications
- noVNC interface for initial login
- Persistent Chrome session

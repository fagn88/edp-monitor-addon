# Changelog

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

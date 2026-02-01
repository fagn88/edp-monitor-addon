# Changelog

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

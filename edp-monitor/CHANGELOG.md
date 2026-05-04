# Changelog

## 1.2.6

- **Fix portal sync navigation**: direct `driver.get('/beneficios/ativos')` left Angular half-bootstrapped (`{{QTT_GENERATED_CODE}}` placeholder visible, zero cards rendered, repro'd live 2026-05-04). Now navigates via `/beneficios/pack` first, then JS-clicks the "Códigos ativos" navbar link — Angular bootstraps properly, all active codes render.
- **`codigos_disponiveis=0` → `esgotado`**: when the detail page's button is disabled AND parser sees `Códigos disponíveis: 0`, treat as `esgotado` regardless of surrounding copy. Previously fell through to `erro: estado_incerto` and triggered a misleading "Erro a reclamar" ntfy. Observed 2026-05-04 10:51 after manual claim — page text didn't match `esgotad`/`saldo`, but count was 0.
- Both timeouts on portal sync bumped 15s → 30s.

## 1.2.5

- **Portal sync at startup**: addon now scrapes `/beneficios/ativos` after session validation and reconciles any active codes for the current month into `claim_history.json`. This means a manual claim on the website (or via the EDP mobile app) is detected on the next addon restart — no more wasted daily attempts on something the user already claimed.
- **Validity parser**: new `parse_validity_to_month` understands EDP's `"Até DD <Mmm> YYYY"` format (Portuguese month abbreviations, case-insensitive). Tested against all 12 months.
- DOM structure validated 2026-05-04 against the live portal: `benefits-card` cards on `/beneficios/ativos` with `.benefits-card-footer-tip` for partner name and validity text in card body.

## 1.2.4

- **Persistent claim history (`/data/claim_history.json`)**: every successful claim is recorded with month, code, validity, and timestamp. Restarts now resume mid-cycle correctly instead of jumping to next month — fixes the bug where any restart after start_day silently skipped the rest of the month's window.
- **Restart-as-trigger**: addon detects unclaimed targets at startup and runs an immediate attempt before entering the schedule. Use `service: hassio.addon_restart` with `addon: ae424729_edp_voucher_monitor` as a "try claim now" dashboard button.
- **Smarter scheduling (`compute_next_wakeup`)**: replaces the old monthly-cycle outer loop. Each iteration evaluates state-from-disk and decides next wakeup: today's next slot, tomorrow's first slot, or next month's `start_day`. Robust to restarts at any point.
- **Fixed slot-skip race in old `run_daily_attempts`**: `sleep_until(slot)` returned ~0.5s after the target, then `slot < datetime.now()` caused the slot to be skipped. New flow doesn't have inner slot loops, so the race is gone.
- **End-of-day ntfy only fires when actually moving to next day** (or next month). Avoids spurious "Indisponíveis hoje" between intra-day slots.
- **Removed unused `compute_cycle_start` and `next_day_at`** (dead code from the old cycle model).

## 1.2.3

- **Fix terms checkbox click in `claim_voucher`**: native `cb.click()` was raising `ElementNotInteractableException` (input is visually hidden — Bootstrap form-check pattern). Replaced with JS click. Observed 2026-05-04 08:35 and 09:05 slots: voucher detected as `disponivel` (codigos_disponiveis=1) but claim aborted at the checkbox step both times.
- **Distinguish unavailable vs claim error in end-of-day ntfy**: previous message said "Vouchers ainda não disponíveis hoje" even when a voucher was available but the claim crashed. Now splits into "Indisponíveis hoje" and "Erro a reclamar".

## 1.2.2

- **Fix Angular render race in `navigate_to_voucher`**: replaced fixed `time.sleep(3)` after `driver.get(PACKS_URL)` with `WebDriverWait` for the first `<benefits-card>` to be present (15s timeout). Observed 2026-05-01 08:35 slot finding 0 cards because Angular hadn't rendered yet; now waits for actual DOM readiness.

## 1.2.1

- **Login detection latency**: `wait_for_login` now polls every 30s (was tied to `login_reminder_interval`, default 600s). User logging in is detected within ~30s instead of waiting up to 10min. ntfy reminders still throttled to `login_reminder_interval`.

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

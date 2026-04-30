#!/usr/bin/env python3
"""EDP Voucher Monitor — Home Assistant Add-on."""

import json
import sys
import time
import traceback
from datetime import datetime

# Force unbuffered output so HA addon log tails immediately
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

from helpers import (
    compute_cycle_start,
    log,
    next_day_at,
    parse_attempt_time,
    parse_voucher_status,
    sleep_until,
)

log("Starting EDP Monitor script...")

try:
    import requests
    log("requests OK")
except Exception as e:
    log(f"Failed to import requests: {e}", "ERROR")

try:
    from selenium import webdriver
    from selenium.common.exceptions import NoSuchElementException, TimeoutException
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.common.keys import Keys
    from selenium.webdriver.support import expected_conditions as EC
    from selenium.webdriver.support.ui import WebDriverWait
    log("selenium OK")
except Exception as e:
    log(f"Failed to import selenium: {e}", "ERROR")
    traceback.print_exc()
    sys.exit(1)

CONFIG_PATH = "/data/options.json"
PROFILE_PATH = "/data/chrome-profile"
PACKS_URL = "https://particulares.cliente.edp.pt/beneficios/pack"

DEFAULT_CONFIG = {
    "ntfy_topic": "edp-voucher",
    "start_day": 1,
    "attempt_times": ["08:05", "08:35", "09:05"],
    "login_reminder_interval": 600,
    "targets": [{"name": "Pingo Doce", "partner_id": 1197}],
}


def load_config() -> dict:
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        log(f"Error loading config, using defaults: {e}", "WARN")
        return DEFAULT_CONFIG


def notify_phone(topic: str, title: str, message: str) -> None:
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={"Title": title, "Priority": "urgent", "Tags": "moneybag,rotating_light"},
            timeout=10,
        )
        log(f"ntfy → '{title}' (status {resp.status_code})")
    except Exception as e:
        log(f"ntfy error: {e}", "ERROR")


def create_driver():
    options = Options()
    options.add_argument("--no-sandbox")
    options.add_argument("--disable-dev-shm-usage")
    options.add_argument("--disable-gpu")
    options.add_argument("--disable-software-rasterizer")
    options.add_argument(f"--user-data-dir={PROFILE_PATH}")
    options.add_argument("--window-size=1280,720")
    options.binary_location = "/usr/bin/chromium-browser"
    service = Service("/usr/bin/chromedriver")
    try:
        return webdriver.Chrome(service=service, options=options)
    except Exception as e:
        log(f"Error creating driver: {e}", "ERROR")
        return None


def navigate_to_voucher(driver, voucher_name: str) -> bool:
    """Navigate from any starting page to the voucher's detail page.

    Logic:
    1. Go to /beneficios/pack
    2. Find <benefits-card> whose text contains voucher_name (case-insensitive)
    3. Click its .benefits-card-wrapper via dispatched pointer events
       (Angular ignores plain .click() on this element)
    4. Wait up to 10s for URL to contain /beneficios/detalhe/

    Returns True if landed on a detail page; False if card not found
    or timeout. Caller decides whether to log/notify.
    """
    log(f"[{voucher_name}] Navigating to packs page")
    driver.get(PACKS_URL)
    time.sleep(3)

    cards = driver.find_elements(By.TAG_NAME, "benefits-card")
    log(f"[{voucher_name}] Found {len(cards)} benefits-card elements on page")

    target_card = None
    for card in cards:
        if voucher_name.lower() in card.text.lower():
            target_card = card
            break

    if not target_card:
        log(f"[{voucher_name}] Card not found on packs page", "WARN")
        return False

    try:
        wrapper = target_card.find_element(By.CSS_SELECTOR, ".benefits-card-wrapper")
    except NoSuchElementException:
        log(f"[{voucher_name}] benefits-card-wrapper not inside card", "ERROR")
        return False

    log(f"[{voucher_name}] Dispatching pointer events on card wrapper")
    driver.execute_script(
        """
        const wrapper = arguments[0];
        const rect = wrapper.getBoundingClientRect();
        const x = rect.left + 10, y = rect.top + 10;
        ['pointerdown','mousedown','pointerup','mouseup','click'].forEach(t => {
            wrapper.dispatchEvent(new MouseEvent(t, {
                bubbles: true, cancelable: true, view: window,
                clientX: x, clientY: y, button: 0
            }));
        });
        """,
        wrapper,
    )

    try:
        WebDriverWait(driver, 10).until(
            lambda d: "/beneficios/detalhe/" in d.current_url
        )
    except TimeoutException:
        log(f"[{voucher_name}] Did not navigate to detalhe page within 10s "
            f"(still at {driver.current_url})", "ERROR")
        return False

    log(f"[{voucher_name}] Landed on {driver.current_url}")
    return True


def check_voucher(driver, voucher_name: str) -> tuple:
    """Inspect the current detail page and return (available, status).

    Caller must have navigated to the detail page first. See parse_voucher_status
    for the five possible status codes.
    """
    body_text = driver.find_element(By.TAG_NAME, "body").text

    try:
        btn = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary.edp-large-button")
        btn_disabled = btn.get_attribute("disabled") is not None
    except NoSuchElementException:
        log(f"[{voucher_name}] 'Gerar código' button not found - treating as disabled", "WARN")
        btn_disabled = True

    available, status = parse_voucher_status(body_text, btn_disabled)

    # Extract codigos_disponiveis count for the log line if present
    import re
    m = re.search(r"C[óo]digos dispon[íi]veis:?\s*(\d+)", body_text)
    codigos = m.group(1) if m else "?"
    log(f"[{voucher_name}] state={status} button_disabled={btn_disabled} "
        f"codigos_disponiveis={codigos}")

    return (available, status)


class ClaimError(Exception):
    """Raised when any step of the claim flow fails."""


def claim_voucher(driver, voucher_name: str) -> dict:
    """Run the claim flow on the voucher detail page. Caller MUST have navigated
    there and verified status == 'disponivel' (button enabled).

    Returns {"code": str, "validity": str} on success.
    Raises ClaimError on any timeout / element-missing.
    """
    log(f"[{voucher_name}] Starting claim flow")

    # Step 1: Click 1st "Gerar código"
    try:
        btn1 = driver.find_element(By.CSS_SELECTOR, "button.btn.btn-primary.edp-large-button")
    except NoSuchElementException:
        raise ClaimError(f"[{voucher_name}] 1st 'Gerar código' button not found")
    btn1.click()
    log(f"[{voucher_name}] Clicked 1st 'Gerar código'")

    # Step 2: Wait for modal
    try:
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "ngb-modal-window"))
        )
    except TimeoutException:
        raise ClaimError(f"[{voucher_name}] Modal did not open within 10s")
    log(f"[{voucher_name}] Modal opened")

    # Step 3: Click terms checkbox (native click - dispatched events don't work with Angular forms)
    try:
        cb = driver.find_element(
            By.CSS_SELECTOR, "ngb-modal-window input#form-terms.form-check-input"
        )
    except NoSuchElementException:
        raise ClaimError(f"[{voucher_name}] Terms checkbox not found")
    cb.click()
    log(f"[{voucher_name}] Terms checkbox ticked")

    # Step 4: Wait for submit button to enable
    def submit_enabled(d):
        try:
            b = d.find_element(
                By.CSS_SELECTOR, "ngb-modal-window button.btn.btn-primary.submit-button"
            )
            return b if b.get_attribute("disabled") is None else False
        except NoSuchElementException:
            return False

    try:
        submit = WebDriverWait(driver, 10).until(submit_enabled)
    except TimeoutException:
        raise ClaimError(f"[{voucher_name}] Submit button did not enable within 10s")

    # Step 5: Click submit
    submit.click()
    log(f"[{voucher_name}] Submit clicked")

    # Step 6: Wait for success modal (the code element)
    try:
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, ".code-card-body-text-code"))
        )
    except TimeoutException:
        raise ClaimError(
            f"[{voucher_name}] Success modal with code did not appear within 15s"
        )

    # Step 7: Read code + validity
    code = driver.find_element(By.CSS_SELECTOR, ".code-card-body-text-code").text.strip()
    try:
        validity_raw = driver.find_element(
            By.CSS_SELECTOR, ".code-card-body-text-date"
        ).text.strip()
        # Strip "Até " prefix if present
        validity = validity_raw.replace("Até ", "").strip()
    except NoSuchElementException:
        validity = "?"

    log(f"[{voucher_name}] Code captured: {code} (valid until {validity})")

    # Step 8: Close success modal with Escape
    try:
        driver.find_element(By.TAG_NAME, "body").send_keys(Keys.ESCAPE)
    except Exception as e:
        log(f"[{voucher_name}] Could not send Escape to close modal: {e}", "WARN")

    return {"code": code, "validity": validity}


def wait_for_login(driver, ntfy_topic: str, reminder_interval: int) -> None:
    """Block until login is detected, sending a ntfy reminder every `reminder_interval` seconds."""
    log("Login required - sending first notification", "WARN")
    notify_phone(
        ntfy_topic,
        "EDP Monitor - Login Necessário",
        "Login necessário! Abre noVNC porta 6080 para fazer login",
    )

    while True:
        time.sleep(reminder_interval)
        log("Checking login status...")
        try:
            driver.get(PACKS_URL)
            time.sleep(3)
            body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
            still_login = ("login" in body_text or "iniciar" in body_text) and len(body_text) < 500
            if not still_login:
                log("Login restored")
                notify_phone(ntfy_topic, "EDP Monitor", "Login detectado! A retomar...")
                return
        except Exception as e:
            log(f"Error during login check: {e}", "ERROR")

        log("Still waiting for login - sending reminder", "WARN")
        notify_phone(
            ntfy_topic,
            "EDP Monitor - Login Necessário",
            "Login ainda em falta! Abre noVNC porta 6080",
        )


def run_daily_attempts(driver, config: dict, claimed_set: set) -> dict:
    """Run all *still-future* attempt_times for the current calendar day.

    Mutates `claimed_set` in place when a target gets claimed.
    Returns dict {target_name: last_state_string} for end-of-day notification.
    """
    targets = config["targets"]
    attempt_times = config["attempt_times"]
    ntfy_topic = config["ntfy_topic"]
    login_reminder = config["login_reminder_interval"]

    states = {}

    for slot_str in attempt_times:
        slot = parse_attempt_time(slot_str, datetime.now())
        if slot < datetime.now():
            log(f"Skipping past slot {slot_str} (already in the past)")
            continue

        log(f"Sleeping until next slot {slot.strftime('%Y-%m-%d %H:%M:%S')}")
        sleep_until(slot)

        log(f"=== Slot {slot_str} starting ===")

        for target in targets:
            name = target["name"]
            if name in claimed_set:
                log(f"[{name}] Already claimed this cycle - skip")
                continue

            log(f"[{name}] Checking availability...")
            try:
                ok = navigate_to_voucher(driver, name)
                if not ok:
                    states[name] = "erro: card_not_found_or_nav_failed"
                    continue
                available, status = check_voucher(driver, name)
            except Exception as e:
                log(f"[{name}] Error during check: {e}", "ERROR")
                traceback.print_exc()
                states[name] = f"erro: {e}"
                continue

            states[name] = status

            if status == "precisa_login":
                wait_for_login(driver, ntfy_topic, login_reminder)
                # Retry this voucher inside the same slot after login
                try:
                    ok = navigate_to_voucher(driver, name)
                    if not ok:
                        states[name] = "erro: nav_failed_after_login"
                        continue
                    available, status = check_voucher(driver, name)
                    states[name] = status
                except Exception as e:
                    log(f"[{name}] Error after login retry: {e}", "ERROR")
                    states[name] = f"erro: {e}"
                    continue

            if available is True:
                try:
                    result = claim_voucher(driver, name)
                    notify_phone(
                        ntfy_topic,
                        "Voucher reclamado!",
                        f"{name}: {result['code']} (válido até {result['validity']})",
                    )
                    claimed_set.add(name)
                    states[name] = "reclamado"
                    log(f"[{name}] CLAIMED: {result['code']}")
                except ClaimError as e:
                    log(f"[{name}] Claim failed: {e}", "ERROR")
                    notify_phone(
                        ntfy_topic,
                        "Erro ao reclamar voucher",
                        f"{name}: {e}",
                    )
                    states[name] = f"erro_claim: {e}"
                except Exception as e:
                    log(f"[{name}] Unexpected error during claim: {e}", "ERROR")
                    traceback.print_exc()
                    states[name] = f"erro_claim: {e}"

    return states


def main() -> None:
    config = load_config()
    log("=" * 60)
    log("EDP Voucher Monitor — Starting")
    log("=" * 60)
    log(f"ntfy_topic={config['ntfy_topic']}")
    log(f"start_day={config['start_day']}")
    log(f"attempt_times={config['attempt_times']}")
    log(f"login_reminder_interval={config['login_reminder_interval']}s")
    log(f"targets={[t['name'] for t in config['targets']]}")
    log("=" * 60)

    # Wait for Xvfb / x11vnc / noVNC
    log("Waiting 10s for display services to be ready...")
    time.sleep(10)

    log("Creating Chrome driver...")
    driver = create_driver()
    if driver is None:
        log("First driver create failed, retrying in 30s", "WARN")
        time.sleep(30)
        driver = create_driver()
    if driver is None:
        log("Driver creation failed twice. Aborting.", "ERROR")
        notify_phone(
            config["ntfy_topic"],
            "EDP Monitor - Erro Fatal",
            "Falha ao criar browser. Verificar logs do addon.",
        )
        return
    log("Driver created OK")

    # Initial session validation
    log("Validating EDP session...")
    try:
        driver.get(PACKS_URL)
        time.sleep(5)
        body_text = driver.find_element(By.TAG_NAME, "body").text.lower()
        if ("login" in body_text or "iniciar" in body_text) and len(body_text) < 500:
            log("Session NOT logged in", "WARN")
            wait_for_login(driver, config["ntfy_topic"], config["login_reminder_interval"])
        else:
            log("Session OK")
    except Exception as e:
        log(f"Error validating session: {e}", "ERROR")
        traceback.print_exc()

    log(">>> noVNC available at port 6080 for visual inspection <<<")

    # Outer cycle loop — one iteration per monthly cycle
    while True:
        next_cycle = compute_cycle_start(
            datetime.now(), config["start_day"], config["attempt_times"]
        )
        log(f"Next cycle starts at {next_cycle.strftime('%Y-%m-%d %H:%M:%S')}")
        notify_phone(
            config["ntfy_topic"],
            "EDP Monitor",
            f"Próxima ronda: {next_cycle.strftime('%d/%m/%Y às %H:%M')}",
        )
        sleep_until(next_cycle)

        log(f"=== Starting cycle. Targets: {[t['name'] for t in config['targets']]} ===")
        claimed_set = set()

        # Inner daily loop — one iteration per calendar day in the cycle
        while len(claimed_set) < len(config["targets"]):
            run_daily_attempts(driver, config, claimed_set)

            if len(claimed_set) == len(config["targets"]):
                log("All targets claimed for this cycle")
                break

            unclaimed = [t["name"] for t in config["targets"] if t["name"] not in claimed_set]
            log(f"End of day. Unclaimed: {unclaimed}")
            notify_phone(
                config["ntfy_topic"],
                "EDP Monitor",
                f"Vouchers ainda não disponíveis hoje: {', '.join(unclaimed)}. "
                f"Tentarei amanhã às {config['attempt_times'][0]}.",
            )

            tomorrow = next_day_at(config["attempt_times"][0], datetime.now())
            log(f"Sleeping until {tomorrow.strftime('%Y-%m-%d %H:%M:%S')}")
            sleep_until(tomorrow)


if __name__ == "__main__":
    log("Entering main...")
    try:
        main()
    except Exception as e:
        log(f"FATAL: {e}", "ERROR")
        traceback.print_exc()
        sys.exit(1)

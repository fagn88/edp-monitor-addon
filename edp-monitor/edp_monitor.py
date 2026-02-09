#!/usr/bin/env python3
"""
EDP Voucher Monitor - Home Assistant Add-on
"""

import sys
import json
import os
import random
import time
import traceback

# Force unbuffered output
sys.stdout.reconfigure(line_buffering=True)
sys.stderr.reconfigure(line_buffering=True)

print("[init] Starting EDP Monitor script...", flush=True)

try:
    import requests
    print("[init] requests OK", flush=True)
except Exception as e:
    print(f"[init] Failed to import requests: {e}", flush=True)

try:
    from selenium import webdriver
    from selenium.webdriver.chrome.options import Options
    from selenium.webdriver.chrome.service import Service
    from selenium.webdriver.common.by import By
    from selenium.webdriver.support.ui import WebDriverWait
    from selenium.webdriver.support import expected_conditions as EC
    print("[init] selenium OK", flush=True)
except Exception as e:
    print(f"[init] Failed to import selenium: {e}", flush=True)
    traceback.print_exc()
    sys.exit(1)

from datetime import datetime

# Configuration
CONFIG_PATH = "/data/options.json"
PROFILE_PATH = "/data/chrome-profile"

# URLs
PACKS_URL = "https://particulares.cliente.edp.pt/beneficios/pack"
VOUCHER_URL = "https://particulares.cliente.edp.pt/beneficios/detalhe/1197"


def load_config():
    """Load add-on configuration"""
    try:
        with open(CONFIG_PATH) as f:
            return json.load(f)
    except Exception as e:
        print(f"[config] Error loading config: {e}")
        return {
            "ntfy_topic": "edp-voucher",
            "check_interval_min": 240,
            "check_interval_max": 360,
            "schedule_day": 1,
            "schedule_hour": 0
        }


def notify_phone(topic, title, message):
    """Send notification via ntfy"""
    try:
        resp = requests.post(
            f"https://ntfy.sh/{topic}",
            data=message.encode("utf-8"),
            headers={
                "Title": title,
                "Priority": "urgent",
                "Tags": "moneybag,rotating_light"
            },
            timeout=10
        )
        print(f"[ntfy] Notification sent: {title} (status: {resp.status_code})")
    except Exception as e:
        print(f"[ntfy] Error: {e}")


def create_driver():
    """Create Chrome driver with persistent profile"""
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
        driver = webdriver.Chrome(service=service, options=options)
        return driver
    except Exception as e:
        print(f"[driver] Error creating driver: {e}")
        return None


def check_voucher(driver):
    """Check voucher availability"""
    try:
        # Navigate to packs page
        print("[check] Navigating to packs page...")
        driver.get(PACKS_URL)

        # Wait for Pingo Doce link
        print("[check] Waiting for Pingo Doce...")
        try:
            pingo_doce = WebDriverWait(driver, 20).until(
                EC.presence_of_element_located((
                    By.XPATH,
                    "//*[contains(translate(text(), 'ABCDEFGHIJKLMNOPQRSTUVWXYZ', 'abcdefghijklmnopqrstuvwxyz'), 'pingo doce')]"
                ))
            )
        except:
            # Try alternative - look for links
            print("[check] Trying alternative search...")
            links = driver.find_elements(By.TAG_NAME, "a")
            pingo_doce = None
            for link in links:
                if "pingo" in link.text.lower():
                    pingo_doce = link
                    break

            if not pingo_doce:
                text = driver.find_element(By.TAG_NAME, "body").text.lower()
                if "login" in text or "iniciar" in text:
                    return None, "precisa_login"
                return None, "pingo_doce_nao_encontrado"

        # Click on Pingo Doce
        print("[check] Clicking Pingo Doce...")
        pingo_doce.click()
        time.sleep(5)

        # Get page text
        text = driver.find_element(By.TAG_NAME, "body").text.lower()
        url = driver.current_url

        print(f"[check] Current URL: {url}")

        # Check status
        if "esgotad" in text or "volte no próximo" in text:
            return False, "esgotado"

        if "gerar código" in text and "esgotad" not in text:
            return True, "disponivel"

        if "login" in text and len(text) < 500:
            return None, "precisa_login"

        return None, "estado_incerto"

    except Exception as e:
        print(f"[check] Error: {e}")
        return None, f"erro: {e}"


def wait_until_schedule(schedule_day, schedule_hour, ntfy_topic):
    """Wait until the scheduled day/hour to start monitoring"""
    now = datetime.now()

    # Build target datetime for this month
    try:
        target = now.replace(day=schedule_day, hour=schedule_hour,
                             minute=0, second=0, microsecond=0)
    except ValueError:
        # Day doesn't exist in this month (e.g. day 31 in Feb)
        # Skip to next month
        if now.month == 12:
            target = datetime(now.year + 1, 1, schedule_day,
                              schedule_hour, 0, 0)
        else:
            target = datetime(now.year, now.month + 1, schedule_day,
                              schedule_hour, 0, 0)

    # If we're already past the target this month, schedule for next month
    if target <= now:
        if now.month == 12:
            target = datetime(now.year + 1, 1, schedule_day,
                              schedule_hour, 0, 0)
        else:
            try:
                target = datetime(now.year, now.month + 1, schedule_day,
                                  schedule_hour, 0, 0)
            except ValueError:
                # Day doesn't exist in next month either, skip to month after
                month = now.month + 2 if now.month <= 10 else (now.month + 2 - 12)
                year = now.year if now.month <= 10 else now.year + 1
                target = datetime(year, month, schedule_day,
                                  schedule_hour, 0, 0)

    delta = (target - now).total_seconds()

    if delta <= 0:
        # Should not happen, but safety check
        return

    days = delta / 86400
    hours = delta / 3600
    target_str = target.strftime("%d/%m/%Y às %H:%M")

    print(f"[schedule] Próxima execução: {target_str} (em {days:.1f} dias)")
    notify_phone(ntfy_topic, "EDP Monitor - Agendado",
                 f"Próxima execução: {target_str} (em {days:.1f} dias)")

    # Sleep in chunks of 1 hour to keep the process responsive
    while True:
        now = datetime.now()
        remaining = (target - now).total_seconds()
        if remaining <= 0:
            break
        sleep_time = min(remaining, 3600)
        time.sleep(sleep_time)


def run_monitoring(config):
    """Run the voucher monitoring loop"""
    ntfy_topic = config.get("ntfy_topic", "edp-voucher")
    interval_min = config.get("check_interval_min", 240)
    interval_max = config.get("check_interval_max", 360)

    print("=" * 60)
    print("  EDP Voucher Monitor - Monitorização Iniciada")
    print("=" * 60)
    print(f"  ntfy topic: {ntfy_topic}")
    print(f"  Interval: {interval_min//60}-{interval_max//60} min")
    print("=" * 60)
    print()
    print(">>> Open noVNC at port 6080 to login if needed <<<")
    print()

    # Notify that monitoring has started
    notify_phone(ntfy_topic, "EDP Monitor Iniciado",
                 f"Monitorização de vouchers iniciada! Intervalo: {interval_min//60}-{interval_max//60} min")

    # Wait for Xvfb and VNC to start
    print("[monitor] Waiting for display services...")
    time.sleep(10)

    # Create driver
    print("[monitor] Creating Chrome driver...")
    driver = create_driver()

    if not driver:
        print("[monitor] Failed to create driver, retrying in 30s...")
        time.sleep(30)
        driver = create_driver()

    if not driver:
        print("[monitor] Could not create driver. Check logs.")
        notify_phone(ntfy_topic, "EDP Monitor - Erro",
                     "Falha ao criar browser. Verificar logs.")
        return

    print("[monitor] Driver created successfully")

    # Initial check
    print("[monitor] Initial check...")
    available, status = check_voucher(driver)
    timestamp = datetime.now().strftime("%H:%M:%S")

    if status == "precisa_login":
        print(f"[{timestamp}] LOGIN REQUIRED!")
        print("=" * 60)
        print(">>> Open noVNC at http://<your-ha-ip>:6080 and login <<<")
        print("=" * 60)
        notify_phone(ntfy_topic, "EDP Monitor - Login Necessário",
                     "Login necessario! Abre noVNC porta 6080 para fazer login")

        # Wait for manual login
        while True:
            time.sleep(60)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for login...")
            available, status = check_voucher(driver)
            if status != "precisa_login":
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Login detected!")
                notify_phone(ntfy_topic, "EDP Monitor",
                             "Login detectado! A iniciar monitorização...")
                break

    if available is True:
        print(f"[{timestamp}] AVAILABLE!")
        notify_phone(ntfy_topic, "VOUCHER DISPONIVEL!", "Pingo Doce 10 EUR - VAI JA!")
        driver.quit()
        return
    elif available is False:
        print(f"[{timestamp}] Sold out")
    else:
        print(f"[{timestamp}] Status: {status}")

    # Monitoring loop
    check_count = 1
    while True:
        interval = random.randint(interval_min, interval_max)
        next_check = datetime.fromtimestamp(
            datetime.now().timestamp() + interval
        ).strftime("%H:%M:%S")
        print(f"[monitor] #{check_count} | Next: {next_check} ({interval}s)")

        time.sleep(interval)
        check_count += 1

        timestamp = datetime.now().strftime("%H:%M:%S")
        print(f"[{timestamp}] Checking...")

        try:
            available, status = check_voucher(driver)
        except Exception as e:
            print(f"[{timestamp}] Error during check: {e}")
            # Try to recreate driver
            try:
                driver.quit()
            except:
                pass
            driver = create_driver()
            if not driver:
                print("[monitor] Could not recreate driver")
                notify_phone(ntfy_topic, "EDP Monitor - Erro",
                             "Falha ao recriar browser. Verificar logs.")
                time.sleep(60)
                continue
            available, status = None, "driver_recreated"

        if available is True:
            print(f"[{timestamp}] AVAILABLE!")
            notify_phone(ntfy_topic, "VOUCHER DISPONIVEL!", "Pingo Doce 10 EUR - VAI JA BUSCAR!")

            # Keep notifying
            for i in range(10):
                time.sleep(60)
                notify_phone(ntfy_topic, "VOUCHER DISPONIVEL!", f"Pingo Doce 10 EUR - VAI JA! ({i+1}/10)")
            break

        elif available is False:
            print(f"[{timestamp}] Sold out")
        elif status == "precisa_login":
            print(f"[{timestamp}] Login expired!")
            notify_phone(ntfy_topic, "EDP Monitor - Login Necessário",
                         "Login expirado! Abre noVNC porta 6080 para fazer login")
        else:
            print(f"[{timestamp}] Status: {status}")

    try:
        driver.quit()
    except:
        pass
    print("[monitor] Monitoring cycle finished")


def main():
    config = load_config()
    ntfy_topic = config.get("ntfy_topic", "edp-voucher")
    schedule_day = config.get("schedule_day", 1)
    schedule_hour = config.get("schedule_hour", 0)

    print("=" * 60)
    print("  EDP Voucher Monitor - Home Assistant Add-on")
    print("=" * 60)
    print(f"  ntfy topic: {ntfy_topic}")
    print(f"  Schedule: day {schedule_day} at {schedule_hour:02d}:00")
    print("=" * 60)
    print()

    while True:
        # Wait until scheduled time
        wait_until_schedule(schedule_day, schedule_hour, ntfy_topic)

        # Run monitoring
        print(f"[main] Schedule triggered! Starting monitoring...")
        run_monitoring(config)

        # After monitoring finishes, loop back to wait for next month
        print(f"[main] Monitoring cycle complete. Waiting for next schedule...")


if __name__ == "__main__":
    print("[init] Entering main...", flush=True)
    try:
        main()
    except Exception as e:
        print(f"[FATAL] Uncaught exception: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

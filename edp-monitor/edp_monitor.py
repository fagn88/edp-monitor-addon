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
            "check_interval_max": 360
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


def main():
    config = load_config()
    ntfy_topic = config.get("ntfy_topic", "edp-voucher")
    interval_min = config.get("check_interval_min", 240)
    interval_max = config.get("check_interval_max", 360)

    print("=" * 60)
    print("  EDP Voucher Monitor - Home Assistant Add-on")
    print("=" * 60)
    print(f"  ntfy topic: {ntfy_topic}")
    print(f"  Interval: {interval_min//60}-{interval_max//60} min")
    print("=" * 60)
    print()
    print(">>> Open noVNC at port 6080 to login if needed <<<")
    print()

    # Wait for Xvfb and VNC to start
    print("[main] Waiting for display services...")
    time.sleep(10)

    # Create driver
    print("[main] Creating Chrome driver...")
    driver = create_driver()

    if not driver:
        print("[main] Failed to create driver, retrying in 30s...")
        time.sleep(30)
        driver = create_driver()

    if not driver:
        print("[main] Could not create driver. Check logs.")
        notify_phone(ntfy_topic, "EDP Monitor Error", "Falha ao criar browser")
        return

    print("[main] Driver created successfully")

    # Initial check
    print("[main] Initial check...")
    available, status = check_voucher(driver)
    timestamp = datetime.now().strftime("%H:%M:%S")

    if status == "precisa_login":
        print(f"[{timestamp}] LOGIN REQUIRED!")
        print("=" * 60)
        print(">>> Open noVNC at http://<your-ha-ip>:6080 and login <<<")
        print("=" * 60)
        notify_phone(ntfy_topic, "EDP Monitor", "Login necessario! Abre noVNC porta 6080")

        # Wait for manual login
        while True:
            time.sleep(60)
            print(f"[{datetime.now().strftime('%H:%M:%S')}] Waiting for login...")
            available, status = check_voucher(driver)
            if status != "precisa_login":
                print(f"[{datetime.now().strftime('%H:%M:%S')}] Login detected!")
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
        print(f"[main] #{check_count} | Next: {next_check} ({interval}s)")

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
                print("[main] Could not recreate driver")
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
        else:
            print(f"[{timestamp}] Status: {status}")

    try:
        driver.quit()
    except:
        pass
    print("[main] Monitor finished")


if __name__ == "__main__":
    print("[init] Entering main...", flush=True)
    try:
        main()
    except Exception as e:
        print(f"[FATAL] Uncaught exception: {e}", flush=True)
        traceback.print_exc()
        sys.exit(1)

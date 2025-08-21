# === Tor Bot Multi Instance: bot.py ===

import threading
import socket
import time, os, random, sys, requests
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.support.ui import WebDriverWait

# ====== Configuration =======
SOCKS_PORT = 9051
CONTROL_PORT = 9011
TOR_PASSWORD = "bot"

site_link = "https://www.browserless.io/"
paste_link = "https://www.aaro.online/"
geckodriver_path = os.path.join(os.getcwd(), "geckodriver")

user_agents = [
    "Mozilla/5.0 (Linux; Android 12; SM-G991B)...",
    "Mozilla/5.0 (Linux; Android 11; Pixel 5)...",
    "Mozilla/5.0 (iPhone; CPU iPhone OS 16_6)..."
]

ip_change_count = 0
seen_ips = set()
ip_file = "ip.txt"

# Retry Counter
retry_counter = 0
MAX_RETRIES = 5

# ====== IP File Functions =======
def load_seen_ips():
    global seen_ips
    if os.path.exists(ip_file):
        with open(ip_file, "r") as f:
            seen_ips = set(line.strip() for line in f if line.strip())
    else:
        open(ip_file, "w").close()  # create empty file if not exists

def save_ip(ip):
    with open(ip_file, "a") as f:
        f.write(ip + "\n")

# ====== IP Functions =======
def get_current_ip():
    try:
        ip = requests.get("https://api.ipify.org", proxies={
            'http': f'socks5h://127.0.0.1:{SOCKS_PORT}',
            'https': f'socks5h://127.0.0.1:{SOCKS_PORT}'
        }, timeout=5).text.strip()
        return ip
    except:
        return "❌"

def new_tor_ip(password=TOR_PASSWORD):
    global ip_change_count, seen_ips
    try:
        s = socket.create_connection(("127.0.0.1", CONTROL_PORT))
        s.send(f'AUTHENTICATE "{password}"\r\n'.encode())
        if b"250 OK" in s.recv(1024):
            while True:
                s.send(b'SIGNAL NEWNYM\r\n')
                s.recv(1024)
                time.sleep(3)
                new_ip = get_current_ip()
                if new_ip == "❌":
                    print("❌ IP detect failed, retrying...")
                    continue

                if new_ip not in seen_ips:
                    seen_ips.add(new_ip)
                    save_ip(new_ip)
                    ip_change_count += 1
                    print(f"\n🔄 [New Unique IP] {new_ip} | Total Unique: {ip_change_count}")
                    break
                else:
                    print(f"⚠️ Duplicate IP {new_ip}, retrying...")
                    time.sleep(2)
                    continue
        else:
            print("❌ Tor Auth Failed")
        s.close()
    except Exception as e:
        print("❌ IP Change Error:", e)

def ip_changer_loop(interval=300):
    while True:
        new_tor_ip()
        time.sleep(interval)

# ====== Utility =======
def countdown(seconds):
    for remaining in range(seconds, 0, -1):
        sys.stdout.write(f"\r⏳ Waiting {remaining} sec... ")
        sys.stdout.flush()
        time.sleep(1)
    print("\r✅ Done waiting.                  ")

def init_driver():
    options = webdriver.FirefoxOptions()
    # options.add_argument("-headless")  # Optional: Headless Mode
    options.set_preference("general.useragent.override", random.choice(user_agents))
    options.set_preference("network.proxy.type", 1)
    options.set_preference("network.proxy.socks", "127.0.0.1")
    options.set_preference("network.proxy.socks_port", SOCKS_PORT)
    options.set_preference("network.proxy.socks_version", 5)
    options.set_preference("network.proxy.no_proxies_on", "")
    return webdriver.Firefox(service=Service(geckodriver_path), options=options)

def is_page_loaded():
    return driver.execute_script("return document.readyState") == "complete"

def safe_get(url, retries=3):
    for attempt in range(retries):
        try:
            driver.get(url)
            if is_page_loaded():
                return True
        except Exception as e:
            print(f"❌ Failed on attempt {attempt+1}: {e}")
            new_tor_ip()
            countdown(5)
    print("❌ All retries failed.")
    return False

def get_run_button_class():
    try:
        return driver.find_element(By.ID, "snapshot-submit-button").get_attribute("class")
    except:
        return ""

def click_accept_cookie():
    try:
        driver.find_element(By.CSS_SELECTOR, 'a[fs-cc="allow"]').click()
        print("🍪 Cookie accepted")
        countdown(1)
    except:
        pass

def type_link():
    box = driver.find_element(By.ID, "snapshot-submit-input")
    box.click()
    box.clear()
    for ch in paste_link:
        box.send_keys(ch)
        time.sleep(0.05)

def click_run():
    try:
        driver.find_element(By.ID, "snapshot-submit-button").click()
        print("▶️ Clicked Run")
    except:
        print("❌ Failed to click Run")

def wait_until_ready_or_refresh(timeout=5):
    for _ in range(timeout):
        if is_page_loaded():
            return True
        time.sleep(1)
    print("🔄 Refreshing...")
    driver.refresh()
    return False

# ====== Start Background IP Thread =======
load_seen_ips()   # Load IP history from ip.txt
t = threading.Thread(target=ip_changer_loop, args=(300,), daemon=True)
t.start()

# ====== Main Loop =======
driver = init_driver()
wait = WebDriverWait(driver, 30)

while True:
    try:
        print("🌍 Opening site...")
        if not safe_get(site_link): continue
        if not wait_until_ready_or_refresh(): continue

        print("✅ Page loaded, waiting 8s...")
        countdown(8)
        click_accept_cookie()

        while True:
            run_class = get_run_button_class()

            if "snapshot-button-disabled" in run_class or "disabled" in run_class:
                print("✏️ Typing link...")
                type_link()
                countdown(1)
                run_class = get_run_button_class()
                if "disabled" in run_class:
                    print("❌ Still disabled.")
                    continue

            if "snapshot-button-loading" in run_class:
                print("⏳ Loading... wait 60s")
                countdown(60)
                break

            if "unblocker plausible-event-name=Tester+Click" in run_class:
                print("✅ Run button enabled")
                try:
                    dropdown = driver.find_element(By.ID, "snapshot-submit-select")
                    dropdown.click()
                    dropdown.find_element(By.XPATH, ".//option[@value='other']").click()
                    print("✅ Selected 'Other'")
                except:
                    print("⚠️ Dropdown issue")

                click_run()
                countdown(2)

                if "snapshot-button-loading" in get_run_button_class():
                    print("⏳ Loading started... waiting")
                    countdown(45)
                    retry_counter = 0   # Reset on success
                    break
                else:
                    retry_counter += 1
                    print(f"🔁 Not running, retrying... ({retry_counter}/{MAX_RETRIES})")
                    countdown(2)

                    if retry_counter >= MAX_RETRIES:
                        print("⚠️ Too many retries, changing IP...")
                        new_tor_ip()
                        retry_counter = 0
                    break

    except Exception as e:
        print(f"\n💥 Crash: {e}")
        try: driver.quit()
        except: pass
        time.sleep(5)
        driver = init_driver()
        wait = WebDriverWait(driver, 30)
        countdown(5)
        continue

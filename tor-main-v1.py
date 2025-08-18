# ==== tor_bot_firefox.py ====
import threading
import socket
import time
import os
import random
import sys
import requests
import tempfile
import shutil
import json
from selenium import webdriver
from selenium.webdriver.firefox.options import Options
from selenium.webdriver.firefox.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import *
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.common.keys import Keys
from fake_useragent import UserAgent
import job  # External job file

# Tor settings
TOR_CONTROL_PORT = 9011
TOR_PROXY_PORT = 9051
TOR_PASSWORD = "bot"
ip_change_count = 0
seen_ips = set()

def get_current_ip():
    try:
        print("\U0001F310 Checking IP...")
        ip = requests.get(
            "https://api.ipify.org",
            proxies={'http': f'socks5h://127.0.0.1:{TOR_PROXY_PORT}', 
                     'https': f'socks5h://127.0.0.1:{TOR_PROXY_PORT}'},
            timeout=10
        ).text.strip()
        print(f"✅ Current IP: {ip}")
        return ip
    except Exception as e:
        print(f"❌ IP fetch error: {str(e)[:50]}")
        return "❌ (Failed to fetch IP)"

def new_tor_ip():
    global ip_change_count, seen_ips
    attempt = 0
    max_attempts = 10
    while attempt < max_attempts:
        try:
            print("\U0001F501 Getting new Tor IP...")
            with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
                s.settimeout(10)
                s.connect(("127.0.0.1", TOR_CONTROL_PORT))
                s.send(f'AUTHENTICATE "{TOR_PASSWORD}"\r\n'.encode())
                response = s.recv(1024)
                if b"250 OK" in response:
                    s.send(b'SIGNAL NEWNYM\r\n')
                    s.recv(1024)
                    time.sleep(5)
                    new_ip = get_current_ip()
                    if new_ip != "❌ (Failed to fetch IP)" and new_ip not in seen_ips:
                        seen_ips.add(new_ip)
                        ip_change_count += 1
                        print(f"🔄 [IP changed] {new_ip} | Unique IPs: {ip_change_count}")
                        return new_ip
                    else:
                        print(f"⚠️ Duplicate or invalid IP: {new_ip}")
                else:
                    print(f"❌ Tor authentication failed: {response.decode()[:50]}")
        except Exception as e:
            print(f"❌ Tor IP change error: {str(e)[:50]}")
        attempt += 1
        countdown(5, f"Retrying IP change ({attempt})")
    print("❌ Failed to get new IP after multiple attempts")
    return None

def countdown(sec, msg="Waiting"):
    for s in range(sec, 0, -1):
        sys.stdout.write(f"\r⏳ {msg}: {s}s... ")
        sys.stdout.flush()
        time.sleep(1)
    print("\r" + " " * 50 + "\r", end='')

def init_driver(user_agent):
    print("🧩 Initializing Firefox with ad compatibility...")
    try:
        # Create temp profile
        profile_path = tempfile.mkdtemp()
        
        # Setup Firefox profile with balanced privacy
        profile = webdriver.FirefoxProfile(profile_path)
        
        # Privacy settings (adjusted for ad compatibility)
        profile.set_preference("privacy.trackingprotection.enabled", False)  # Allow ads
        profile.set_preference("privacy.trackingprotection.socialtracking.enabled", False)
        profile.set_preference("privacy.resistFingerprinting", True)  # Keep fingerprinting protection
        profile.set_preference("privacy.spoof_english", 2)
        profile.set_preference("privacy.firstparty.isolate", True)
        profile.set_preference("webgl.disabled", True)
        profile.set_preference("media.peerconnection.enabled", False)
        profile.set_preference("media.navigator.enabled", False)
        
        # Cache settings (enable for ads)
        profile.set_preference("browser.cache.disk.enable", True)  # Enable disk cache
        profile.set_preference("browser.cache.disk.capacity", 1048576)  # 1GB cache
        profile.set_preference("browser.cache.memory.enable", True)
        profile.set_preference("browser.cache.offline.enable", False)
        
        # Session settings
        profile.set_preference("browser.sessionstore.resume_from_crash", False)
        profile.set_preference("browser.sessionstore.max_tabs_undo", 0)
        profile.set_preference("browser.sessionstore.max_windows_undo", 0)
        profile.set_preference("browser.sessionstore.enabled", False)
        
        # Network settings
        profile.set_preference("network.http.use-cache", True)
        profile.set_preference("dom.webdriver.enabled", False)
        profile.set_preference("network.proxy.socks_remote_dns", True)
        profile.set_preference("network.proxy.type", 1)
        profile.set_preference("network.proxy.socks", "127.0.0.1")
        profile.set_preference("network.proxy.socks_port", TOR_PROXY_PORT)
        profile.set_preference("network.proxy.socks_version", 5)
        profile.set_preference("general.useragent.override", user_agent)
        
        # Anti-fingerprinting (keep essential protections)
        profile.set_preference("dom.enable_performance", False)
        profile.set_preference("dom.enable_resource_timing", False)
        profile.set_preference("dom.enable_user_timing", False)
        profile.set_preference("dom.gamepad.enabled", False)
        profile.set_preference("device.sensors.enabled", False)
        profile.set_preference("dom.vibrator.enabled", False)
        profile.set_preference("browser.send_pings", False)
        profile.set_preference("dom.battery.enabled", False)
        
        # Geolocation (keep disabled)
        profile.set_preference("geo.enabled", False)
        profile.set_preference("geo.provider.network.url", "")
        profile.set_preference("geo.provider.use_corelocation", False)
        profile.set_preference("geo.wifi.uri", "")
        
        # Notifications (keep disabled)
        profile.set_preference("dom.webnotifications.enabled", False)
        profile.set_preference("dom.push.enabled", False)
        
        # Safe Browsing (enable for Google services)
        profile.set_preference("browser.safebrowsing.malware.enabled", True)
        profile.set_preference("browser.safebrowsing.phishing.enabled", True)
        profile.set_preference("browser.safebrowsing.blockedURIs.enabled", True)
        # Keep Google URLs for ad services
        profile.set_preference("browser.safebrowsing.provider.google.gethashURL", "https://safebrowsing.googleapis.com/v4/fullHashes:find?$req=%REQUEST%&key=%GOOGLE_API_KEY%&$httpMethod=POST")
        profile.set_preference("browser.safebrowsing.provider.google.updateURL", "https://safebrowsing.googleapis.com/v4/threatListUpdates:fetch?$req=%REQUEST%&key=%GOOGLE_API_KEY%&$httpMethod=POST")
        profile.set_preference("browser.safebrowsing.provider.google4.gethashURL", "https://safebrowsing.googleapis.com/v4/fullHashes:find?$req=%REQUEST%&key=%GOOGLE_API_KEY%&$httpMethod=POST")
        profile.set_preference("browser.safebrowsing.provider.google4.updateURL", "https://safebrowsing.googleapis.com/v4/threatListUpdates:fetch?$req=%REQUEST%&key=%GOOGLE_API_KEY%&$httpMethod=POST")
        
        # Firefox options
        options = Options()
        options.profile = profile
        options.headless = False
        options.set_preference("javascript.enabled", True)
        
        # Disable automation flags
        options.set_preference("dom.webdriver.enabled", False)
        options.set_preference("useAutomationExtension", False)
        
        # Initialize Firefox
        service = Service(log_path=os.devnull)
        driver = webdriver.Firefox(
            service=service,
            options=options
        )
        
        # Set window size and position
        driver.set_window_size(
            width=random.randint(1200, 1400),
            height=random.randint(800, 900)
        )
        driver.set_window_position(
            x=random.randint(0, 100),
            y=random.randint(0, 100)
        )
        
        # Execute anti-detection scripts
        driver.execute_script("""
            Object.defineProperty(navigator, 'webdriver', {
                get: () => undefined
            });
            Object.defineProperty(navigator, 'connection', {
                get: () => ({
                    downlink: 10,
                    effectiveType: '4g',
                    rtt: 100,
                    saveData: false,
                    type: 'wifi'
                })
            });
            Object.defineProperty(navigator, 'hardwareConcurrency', {
                value: 4
            });
            Object.defineProperty(navigator, 'deviceMemory', {
                value: 8
            });
            Object.defineProperty(navigator, 'languages', {
                get: () => ['en-US', 'en']
            });
            Object.defineProperty(navigator, 'platform', {
                get: () => 'Win32'
            });
            Object.defineProperty(window, 'chrome', {
                get: () => undefined
            });
            Object.defineProperty(window, 'outerWidth', {
                value: window.innerWidth + 16
            });
            Object.defineProperty(window, 'outerHeight', {
                value: window.innerHeight + 94
            });
        """)
        
        print("🟢 Firefox initialized with ad compatibility")
        return driver, profile_path
    except Exception as e:
        print(f"WebDriver error: {e}")
        return None, None

def check_adsense_ads(driver):
    """Check for AdSense ads on the current page"""
    try:
        ads = driver.find_elements(By.CSS_SELECTOR, "ins.adsbygoogle")
        if ads:
            print(f"📢 Found {len(ads)} AdSense ads")
            for i, ad in enumerate(ads):
                try:
                    if ad.is_displayed():
                        print(f"  ✅ Ad {i+1} is visible")
                    else:
                        print(f"  ⚠️ Ad {i+1} is present but not visible")
                except:
                    print(f"  ❌ Ad {i+1} status check failed")
        else:
            print("⚠️ No AdSense ads detected")
    except Exception as e:
        print(f"❌ AdSense check error: {str(e)[:50]}")

def close_driver(driver, profile_path):
    try:
        driver.quit()
    except:
        pass
    try:
        shutil.rmtree(profile_path, ignore_errors=True)
    except:
        pass

def main_bot_loop():
    driver = None
    profile_path = None
    
    while True:
        try:
            # Get new Tor IP
            new_ip = new_tor_ip()
            if new_ip is None:
                countdown(30, "Restarting after IP failure")
                continue
                
            # Get random user agent
            ua = UserAgent()
            user_agent = ua.random
            print(f"🆔 User Agent: {user_agent}")
            
            # Initialize driver
            driver, profile_path = init_driver(user_agent)
            if driver is None:
                countdown(30, "Restarting after driver failure")
                continue
                
            # Run job from external file
            pages = random.randint(2, 7)
            print(f"🚀 Starting new session ({pages} pages)")
            
            # Execute job with ad checking
            success = job.run_job(driver, pages)
            
            # Check for ads after job completion
            print("\n🔍 Checking for AdSense ads...")
            check_adsense_ads(driver)
            
            # Post-session cleanup
            close_driver(driver, profile_path)
            driver = None
            profile_path = None
            
            if success:
                countdown(random.randint(10, 20), "Waiting between sessions")
            else:
                countdown(random.randint(10, 30), "Restarting after job failure")
                
        except Exception as e:
            print(f"💥 Critical error: {e}")
            if driver:
                close_driver(driver, profile_path)
            countdown(30, "Recovering from crash")

if __name__ == "__main__":
    print("🔥 Undetectable Tor Bot v3.1 (AdSense Compatible) Starting...")
    main_bot_loop()

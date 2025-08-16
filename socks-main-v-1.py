# ==== proxy_bot_firefox.py ====
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

# Proxy settings
GIST_URL = "https://gist.githubusercontent.com/shanto68/7e6e92e04bea94e7d8c313277c3ff27f/raw/e3553336997ca6964e1a82c6e4b2d234adde5797/shanto"  # Replace with your gist URL
WORKING_PROXIES_LOG = "working_proxies.json"
TEST_URLS = [
    "https://api.myip.com",
    "https://ifconfig.me/ip",
    "https://ipinfo.io/json",
    "https://api.ipify.org?format=json"
]
proxy_change_count = 0
working_proxies = []
failed_proxies = set()
last_proxy_fetch_time = 0
current_proxy_index = 0  # Track current proxy position

def fetch_proxies():
    """Fetch proxies from GitHub gist"""
    global working_proxies, last_proxy_fetch_time
    try:
        print("🌐 Fetching proxies from gist...")
        response = requests.get(GIST_URL, timeout=10)
        proxies = []
        
        for line in response.text.strip().split('\n'):
            if line.strip():
                parts = line.strip().split(':')
                if len(parts) == 4:
                    ip, port, username, password = parts
                    proxies.append({
                        'ip': ip,
                        'port': port,
                        'username': username,
                        'password': password,
                        'type': None  # Will be determined later
                    })
        
        print(f"✅ Fetched {len(proxies)} proxies from gist")
        last_proxy_fetch_time = time.time()
        return proxies
    except Exception as e:
        print(f"❌ Proxy fetch error: {str(e)[:50]}")
        return []

def test_proxy_type(proxy):
    """Test proxy to determine its type (HTTP, HTTPS, SOCKS4, SOCKS5)"""
    proxy_types = [
        ('http', 'HTTP'),
        ('https', 'HTTPS'),
        ('socks4', 'SOCKS4'),
        ('socks5', 'SOCKS5')
    ]
    
    for proto, name in proxy_types:
        try:
            # Build proxy string with authentication
            proxy_string = f'{proto}://{proxy["username"]}:{proxy["password"]}@{proxy["ip"]}:{proxy["port"]}'
            proxy_dict = {
                'http': proxy_string,
                'https': proxy_string
            }
            
            # Try multiple test URLs for reliability
            for test_url in TEST_URLS:
                try:
                    response = requests.get(
                        test_url,
                        proxies=proxy_dict,
                        timeout=10,
                        headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                    )
                    
                    if response.status_code == 200:
                        # Extract IP from response to verify proxy is working
                        if 'json' in test_url:
                            try:
                                ip_data = response.json()
                                if 'ip' in ip_data:
                                    ip = ip_data['ip']
                                else:
                                    ip = response.text.strip()
                            except:
                                ip = response.text.strip()
                        else:
                            ip = response.text.strip()
                        
                        print(f"✅ Proxy {proxy['ip']}:{proxy['port']} works as {name} | IP: {ip}")
                        return proto
                    elif response.status_code in [403, 407]:
                        print(f"❌ Proxy {proxy['ip']}:{proxy['port']} authentication failed ({response.status_code}) for {name}")
                        break  # Skip to next proxy type
                    else:
                        print(f"⚠️ Proxy {proxy['ip']}:{proxy['port']} returned status {response.status_code} for {name}")
                        continue  # Try next test URL
                except requests.exceptions.ProxyError as e:
                    print(f"❌ Proxy error for {name}: {str(e)[:50]}")
                    break  # Skip to next proxy type
                except requests.exceptions.Timeout:
                    print(f"⚠️ Timeout for {name} with {proxy['ip']}:{proxy['port']}")
                    continue  # Try next test URL
                except Exception as e:
                    print(f"⚠️ Error testing {name}: {str(e)[:50]}")
                    continue  # Try next test URL
        except Exception as e:
            print(f"❌ Failed to test {name}: {str(e)[:50]}")
            continue
    
    return None

def log_working_proxies():
    """Log working proxies to a file for later use"""
    try:
        with open(WORKING_PROXIES_LOG, 'w') as f:
            json.dump(working_proxies, f, indent=2)
        print(f"💾 Saved {len(working_proxies)} working proxies to {WORKING_PROXIES_LOG}")
    except Exception as e:
        print(f"❌ Failed to log working proxies: {str(e)[:50]}")

def load_working_proxies():
    """Load previously working proxies from log file"""
    global working_proxies
    try:
        if os.path.exists(WORKING_PROXIES_LOG):
            with open(WORKING_PROXIES_LOG, 'r') as f:
                loaded_proxies = json.load(f)
                print(f"📂 Loaded {len(loaded_proxies)} working proxies from {WORKING_PROXIES_LOG}")
                
                # Test each loaded proxy to ensure it's still working
                for proxy in loaded_proxies:
                    if proxy['ip'] not in failed_proxies and proxy['ip'] not in [p['ip'] for p in working_proxies]:
                        if test_proxy_type(proxy):
                            working_proxies.append(proxy)
    except Exception as e:
        print(f"❌ Failed to load working proxies: {str(e)[:50]}")

def refresh_proxy_list():
    """Refresh the proxy list and test new proxies"""
    global working_proxies, failed_proxies, current_proxy_index
    
    # Load previously working proxies first
    if not working_proxies:
        load_working_proxies()
    
    # Clear failed proxies periodically (every hour)
    if time.time() - last_proxy_fetch_time > 3600:
        print("🔄 Clearing failed proxies list (hourly refresh)")
        failed_proxies.clear()
    
    # Fetch new proxies
    all_proxies = fetch_proxies()
    if not all_proxies:
        return
    
    # Test new proxies
    new_working_count = 0
    for proxy in all_proxies:
        if proxy['ip'] not in failed_proxies and proxy['ip'] not in [p['ip'] for p in working_proxies]:
            proxy_type = test_proxy_type(proxy)
            if proxy_type:
                proxy['type'] = proxy_type
                working_proxies.append(proxy)
                new_working_count += 1
                print(f"✅ Added new working proxy: {proxy['ip']}:{proxy['port']} ({proxy_type})")
            else:
                failed_proxies.add(proxy['ip'])
                print(f"❌ Proxy failed type test: {proxy['ip']}:{proxy['port']}")
    
    if new_working_count > 0:
        log_working_proxies()
    
    # Reset current index if we're at the end
    if current_proxy_index >= len(working_proxies):
        current_proxy_index = 0

def get_next_proxy():
    """Get the next proxy in sequence, with fallback to refresh"""
    global working_proxies, current_proxy_index, proxy_change_count
    
    # Refresh proxy list if needed
    if len(working_proxies) < 3 or time.time() - last_proxy_fetch_time > 1800:  # Every 30 minutes
        refresh_proxy_list()
    
    # If no working proxies, wait and try again
    if not working_proxies:
        print("❌ No working proxies available")
        return None
    
    # Get next proxy in sequence
    proxy = working_proxies[current_proxy_index]
    current_proxy_index = (current_proxy_index + 1) % len(working_proxies)
    
    proxy_change_count += 1
    print(f"🔄 Trying proxy {proxy['ip']}:{proxy['port']} ({proxy['type']}) | Proxy changes: {proxy_change_count}")
    return proxy

def test_proxy_connection(proxy):
    """Test if proxy is working by checking IP"""
    try:
        print("\U0001F310 Testing proxy connection...")
        proxy_dict = {
            'http': f'{proxy["type"]}://{proxy["username"]}:{proxy["password"]}@{proxy["ip"]}:{proxy["port"]}',
            'https': f'{proxy["type"]}://{proxy["username"]}:{proxy["password"]}@{proxy["ip"]}:{proxy["port"]}'
        }
        
        # Try multiple test URLs for reliability
        for test_url in TEST_URLS:
            try:
                response = requests.get(
                    test_url,
                    proxies=proxy_dict,
                    timeout=15,  # Longer timeout for slow proxies
                    headers={'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36'}
                )
                
                if response.status_code == 200:
                    # Extract IP from response
                    if 'json' in test_url:
                        try:
                            ip_data = response.json()
                            ip = ip_data.get('ip', response.text.strip())
                        except:
                            ip = response.text.strip()
                    else:
                        ip = response.text.strip()
                    
                    print(f"✅ Proxy working! Current IP: {ip}")
                    return ip
            except Exception as e:
                print(f"⚠️ Test URL {test_url} failed: {str(e)[:50]}")
                continue
        
        return None
    except Exception as e:
        print(f"❌ Proxy test failed: {str(e)[:50]}")
        return None

def get_working_proxy():
    """Get a working proxy with automatic fallback"""
    global working_proxies, current_proxy_index
    
    max_attempts = 5
    for attempt in range(max_attempts):
        proxy = get_next_proxy()
        if proxy is None:
            countdown(30, "Waiting for proxies")
            continue
        
        # Test the proxy connection
        ip = test_proxy_connection(proxy)
        if ip is not None:
            return proxy
        
        # Remove failed proxy from working list
        working_proxies = [p for p in working_proxies if p['ip'] != proxy['ip']]
        failed_proxies.add(proxy['ip'])
        print(f"❌ Removed failed proxy: {proxy['ip']}:{proxy['port']}")
        
        # Update log file
        log_working_proxies()
        
        # Adjust current index if needed
        if current_proxy_index >= len(working_proxies) and working_proxies:
            current_proxy_index = 0
        
        countdown(5, f"Trying next proxy (attempt {attempt + 1}/{max_attempts})")
    
    print("❌ All proxy attempts failed")
    return None

def countdown(sec, msg="Waiting"):
    for s in range(sec, 0, -1):
        sys.stdout.write(f"\r⏳ {msg}: {s}s... ")
        sys.stdout.flush()
        time.sleep(1)
    print("\r" + " " * 50 + "\r", end='')

def init_driver(user_agent, proxy):
    """Initialize Firefox with proxy settings"""
    print("🧩 Initializing Firefox with proxy...")
    try:
        # Create temp profile
        profile_path = tempfile.mkdtemp()
        
        # Setup Firefox profile with proxy settings
        profile = webdriver.FirefoxProfile(profile_path)
        
        # Set proxy based on type
        if proxy['type'] in ['socks4', 'socks5']:
            profile.set_preference("network.proxy.type", 1)
            profile.set_preference("network.proxy.socks", proxy['ip'])
            profile.set_preference("network.proxy.socks_port", int(proxy['port']))
            profile.set_preference("network.proxy.socks_version", 5 if proxy['type'] == 'socks5' else 4)
            profile.set_preference("network.proxy.socks_remote_dns", True)
            
            # Set SOCKS proxy authentication
            profile.set_preference("network.proxy.socks_username", proxy['username'])
            profile.set_preference("network.proxy.socks_password", proxy['password'])
        else:  # HTTP/HTTPS
            profile.set_preference("network.proxy.type", 1)
            profile.set_preference("network.proxy.http", proxy['ip'])
            profile.set_preference("network.proxy.http_port", int(proxy['port']))
            profile.set_preference("network.proxy.ssl", proxy['ip'])
            profile.set_preference("network.proxy.ssl_port", int(proxy['port']))
            
            # Set HTTP proxy authentication
            profile.set_preference("network.proxy.http_username", proxy['username'])
            profile.set_preference("network.proxy.http_password", proxy['password'])
        
        # Common proxy settings
        profile.set_preference("network.proxy.auth_prompt", False)
        profile.set_preference("signon.autologin.proxy", True)
        profile.set_preference("network.proxy.no_proxies_on", "")
        
        # Additional proxy authentication settings
        profile.set_preference("network.proxy.share_proxy_settings", True)
        profile.set_preference("network.automatic-ntlm-auth.allow-proxies", True)
        profile.set_preference("network.auth.force-generic-ntlm", True)
        
        # Privacy settings (adjusted for ad compatibility)
        profile.set_preference("privacy.trackingprotection.enabled", False)
        profile.set_preference("privacy.trackingprotection.socialtracking.enabled", False)
        profile.set_preference("privacy.resistFingerprinting", True)
        profile.set_preference("privacy.spoof_english", 2)
        profile.set_preference("privacy.firstparty.isolate", True)
        profile.set_preference("webgl.disabled", True)
        profile.set_preference("media.peerconnection.enabled", False)
        profile.set_preference("media.navigator.enabled", False)
        
        # Cache settings
        profile.set_preference("browser.cache.disk.enable", True)
        profile.set_preference("browser.cache.disk.capacity", 1048576)
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
        profile.set_preference("general.useragent.override", user_agent)
        
        # Anti-fingerprinting
        profile.set_preference("dom.enable_performance", False)
        profile.set_preference("dom.enable_resource_timing", False)
        profile.set_preference("dom.enable_user_timing", False)
        profile.set_preference("dom.gamepad.enabled", False)
        profile.set_preference("device.sensors.enabled", False)
        profile.set_preference("dom.vibrator.enabled", False)
        profile.set_preference("browser.send_pings", False)
        profile.set_preference("dom.battery.enabled", False)
        
        # Geolocation
        profile.set_preference("geo.enabled", False)
        profile.set_preference("geo.provider.network.url", "")
        profile.set_preference("geo.provider.use_corelocation", False)
        profile.set_preference("geo.wifi.uri", "")
        
        # Notifications
        profile.set_preference("dom.webnotifications.enabled", False)
        profile.set_preference("dom.push.enabled", False)
        
        # Safe Browsing
        profile.set_preference("browser.safebrowsing.malware.enabled", True)
        profile.set_preference("browser.safebrowsing.phishing.enabled", True)
        profile.set_preference("browser.safebrowsing.blockedURIs.enabled", True)
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
        
        print("🟢 Firefox initialized with proxy")
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
    
    # Initial proxy fetch
    refresh_proxy_list()
    
    while True:
        try:
            # Get a working proxy
            proxy = get_working_proxy()
            if proxy is None:
                countdown(30, "Waiting for proxies")
                continue
                
            # Get random user agent
            ua = UserAgent()
            user_agent = ua.random
            print(f"🆔 User Agent: {user_agent}")
            
            # Initialize driver with proxy
            driver, profile_path = init_driver(user_agent, proxy)
            if driver is None:
                countdown(30, "Restarting after driver failure")
                continue
                
            # Run job from external file
            pages = random.randint(2, 4)
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
                countdown(random.randint(120, 300), "Waiting between sessions")
            else:
                countdown(random.randint(10, 30), "Restarting after job failure")
                
        except Exception as e:
            print(f"💥 Critical error: {e}")
            if driver:
                close_driver(driver, profile_path)
            countdown(30, "Recovering from crash")

if __name__ == "__main__":
    print("🔥 Undetectable Proxy Bot v4.0 (Enhanced Proxy Management) Starting...")
    main_bot_loop()

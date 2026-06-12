import customtkinter as ctk
import requests
import threading
import time
import re
import webbrowser
import sys
import platform
import ctypes
import os
import random
import string
import qrcode
from PIL import Image
import json
import keyring
from datetime import datetime
from tkinter import messagebox
import tkinter.font as tkFont
import tkinter as tk

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from concurrent.futures import ThreadPoolExecutor

# ================= CONFIGURATION =================
ICON_ICO = "icon.ico"       # Windows taskbar/titlebar icon (.ico)
ICON_PNG = "icon.png"       # Linux/macOS icon (.png)
DEBUG_MODE = False         # Set to True to enable verbose debug logging to terminal
VERSION = "2.5.0"           # Current app version — bump this + version.txt on every release
YOUTUBE_GUIDE_URL = "https://www.youtube.com/watch?v=6L_nF6Kc2Uw"  # Replace with your actual video link

# ================= OS DETECTION & SOUND =================
IS_WINDOWS = platform.system() == "Windows"

def play_sound():
    """Cross-platform beep"""
    if IS_WINDOWS:
        try:
            import winsound
            winsound.MessageBeep(winsound.MB_ICONASTERISK)
        except: pass
    else:
        print('\a'); sys.stdout.flush()

def flash_window(root_window):
    """Flashes the taskbar icon on Windows"""
    if IS_WINDOWS:
        try: ctypes.windll.user32.FlashWindow(ctypes.windll.user32.GetForegroundWindow(), True)
        except: pass

def resource_path(relative_path):
    """ Get absolute path to resource, works for dev and for PyInstaller .exe """
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

class KFUPMSniperBackend:
    def __init__(self):
        self.BASE_URL = "https://banner9-registration.kfupm.edu.sa/StudentRegistrationSsb"
        self.session = requests.Session()
        self.scan_interval = 2.5 # Default safe value
        self.term_code = None
        self.running = False
        self.debug_mode = DEBUG_MODE

        self.dashboard_cache = {} # {crn: {code, sec, title, instr, seats, dept}}
        self.target_depts = set() # Departments to monitor
        self.log_callback = None
        self.all_subjects = self._get_all_subjects() # List of all department codes
        self.target_gender = "Male" # Default

        # Auto-Register Settings
        self.auto_reg_enabled = False
        self.reg_user = ""
        self.reg_pass = ""
        self.reg_browser = "Chrome"
        self.auto_reg_list = set() # Set of CRNs to auto-register
        self.is_registering = False # Simple flag to prevent simultaneous sessions
        self.dept_cache = {} # Cache for department lists: {term_code: {dept: [sections]}}
        
        # Default notification topic (randomized for each new user)
        self.ntfy_topic = ''.join(random.choices(string.ascii_lowercase + string.digits, k=12))
        
        self.data_file = os.path.join(os.path.expanduser("~"), ".kfupm_sniper", "sniper_data.json")
        self.seen_welcome = False
        self.load_data()

    def get_data_file_path(self):
        return self.data_file

    def save_data(self):
        data = {
            "term_code": self.term_code,
            "watch_list": self.watch_list_snapshot if hasattr(self, 'watch_list_snapshot') else [],
            "scan_interval": self.scan_interval, 
            "ntfy_topic": self.ntfy_topic,
            "reg_user": self.reg_user,
            "reg_browser": self.reg_browser,
            "dept_cache": self.dept_cache,
            "seen_welcome": self.seen_welcome
        }
        
        # Save password to secure OS keyring instead of JSON
        if self.reg_user:
            try:
                if self.reg_pass:
                    keyring.set_password("KFUPM_Sniper", self.reg_user, self.reg_pass)
                else:
                    try:
                        keyring.delete_password("KFUPM_Sniper", self.reg_user)
                    except Exception:
                        pass
            except Exception as e:
                print(f"Keyring save error: {e}")

        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Failed to save data: {e}")

    def debug_log(self, msg):
        if self.debug_mode:
            print(f"[DEBUG {time.strftime('%H:%M:%S.%f')[:-3]}] {msg}")

    def load_data(self):
        if not os.path.exists(self.data_file): return
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                raw_term = data.get("term_code")
                self.term_code = self.convert_term_code(raw_term) if raw_term else None
                self.saved_watch_list = data.get("watch_list", [])
                self.scan_interval = data.get("scan_interval", 2.5)
                self.debug_mode = DEBUG_MODE  # Always use the constant, not saved state

                if "ntfy_topic" in data: self.ntfy_topic = data["ntfy_topic"]
                
                # Auto Reg Settings
                self.reg_user = data.get("reg_user", "")
                self.reg_browser = data.get("reg_browser", "Chrome")
                self.dept_cache = data.get("dept_cache", {})
                self.seen_welcome = data.get("seen_welcome", False)
                
                # Load password securely from OS keyring
                stored_pass = None
                if self.reg_user:
                    try:
                        stored_pass = keyring.get_password("KFUPM_Sniper", self.reg_user)
                    except Exception as e:
                        print(f"Keyring load error: {e}")
                
                # Fallback to json for backward compatibility during initial migration
                self.reg_pass = stored_pass if stored_pass is not None else data.get("reg_pass", "")
                
        except Exception as e:
            print(f"Failed to load data: {e}")

    def clear_data(self):
        if os.path.exists(self.data_file):
            try: os.remove(self.data_file)
            except: pass
        self.term_code = None
        self.target_depts = set()
        self.dashboard_cache = {}
        self.saved_watch_list = []

    def _get_all_subjects(self):
        # This is a hardcoded list for KFUPM. Can be fetched dynamically if needed.
        return ['ACCT', 'AS', 'AE', 'AECM', 'ARE', 'ARC', 'BIOE', 'BIOL', 'BUS', 'CHE', 'CHEM', 'CRP', 'CP', 'CE', 'CGS', 'CPG', 'COE', 'CSE', 'CEM', 'CIE', 'DSE', 'ECON', 'EE', 'EM', 'ENGL', 'ELD', 'ELI', 'ENVS', 'ESE', 'FIN', 'GEOL', 'GEOP', 'GS', 'HRM', 'ISE', 'ICS', 'ITD', 'IAS', 'LS', 'MGT', 'MIS', 'MKT', 'MBA', 'MSE', 'MATH', 'ME', 'MINE', 'NPM', 'OM', 'PETE', 'PE', 'PHYS', 'SIA', 'SSC', 'SWE', 'STAT', 'SE', 'SCE', 'RES']

    def find_in_cache(self, item):
        if not self.term_code: return None
        term_cache = self.dept_cache.get(self.term_code, {})
        self.debug_log(f"find_in_cache('{item}') called. term_cache length: {len(term_cache)}")
        for dept, cache_entry in term_cache.items():
            # Support new cache format and ignore old/invalid cache
            if isinstance(cache_entry, list): 
                continue
            if not isinstance(cache_entry, dict) or "timestamp" not in cache_entry or "data" not in cache_entry:
                continue
                
            # Check if cache is older than 3 days (3 * 24 * 60 * 60 = 259200 seconds)
            if time.time() - cache_entry["timestamp"] > 259200:
                self.debug_log(f"find_in_cache: {dept} cache expired (>3 days).")
                continue

            for sec in cache_entry["data"]:
                crn = str(sec.get('courseReferenceNumber'))
                code = f"{sec.get('subject')}{sec.get('courseNumber')}"
                full_course_sec = f"{code}-{sec.get('sequenceNumber')}"
                
                campus = sec.get('campusDescription', '').lower()
                target = self.target_gender
                if target == "Male" and "female" in campus:
                    continue
                if target == "Female" and "female" not in campus:
                    continue
                    
                if item == crn or item == full_course_sec:
                    self.debug_log(f"find_in_cache: Match found for {item} in {dept} -> CRN: {crn}")
                    return dept, sec
        self.debug_log(f"find_in_cache: '{item}' not found locally.")
        return None
    def log(self, msg):
        if self.log_callback:
            self.log_callback(msg)
        else:
            print(msg)

    def convert_term_code(self, term_input):
        if len(term_input) == 3:
            current_year = datetime.now().year
            # KFUPM terms are like 251 (2025-1st sem), 252 (2025-2nd sem), 253 (2025-summer)
            # Assuming 251 means 202510, 252 means 202520, 253 means 202530
            year_prefix = str(current_year // 100) # e.g., 20 for 2024
            full_year = year_prefix + term_input[:2]
            semester_code = {'1': '10', '2': '20', '3': '30'}.get(term_input[2], '10')
            return f"{full_year}{semester_code}"
        return term_input # Assume it's already in full format

    def auth(self):
        self.log("Attempting to authenticate...")
        s = requests.Session()
        s.headers.update({
            'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'{self.BASE_URL}/ssb/classSearch/classSearch'
        })
        try:
            # 1. Initialize Search Mode
            r = s.get(f'{self.BASE_URL}/ssb/term/termSelection?mode=search', timeout=10)
            token = None
            patterns = [r'<meta name="synchronizerToken" content="([^"]+)"', r'MyBannerSettings\.csrfToken\s*=\s*["\']([^"\']+)["\']']
            for p in patterns:
                if (match := re.search(p, r.text)):
                    token = match.group(1)
                    break
            
            if not token: 
                self.log("Error: CSRF Token not found.")
                return False
            
            s.headers.update({'X-Synchronizer-Token': token, 'X-Requested-With': 'XMLHttpRequest'})
            
            # Set Term for Search
            payload = {'term': self.term_code}
            s.post(f'{self.BASE_URL}/ssb/term/search?mode=search', data=payload)
            
            self.session = s
            self.log("Auth Success!")
            return True
        except Exception as e:
            self.log(f"Connection Error: {e}")
            return False


    def reset_form(self):
        try: 
            self.debug_log("reset_form() calling /ssb/classSearch/resetDataForm...")
            self.session.post(f'{self.BASE_URL}/ssb/classSearch/resetDataForm', timeout=5)
        except Exception as e:
            self.debug_log(f"reset_form() failed: {e}")

    def fetch_dept(self, dept):
        try:
            # Clear previous search state and re-bind term (needed for some Banner 9 versions)
            self.reset_form()
            self.session.post(f'{self.BASE_URL}/ssb/term/search?mode=search', data={'term': self.term_code}, timeout=5)

            params = {
                'txt_subject': dept, 
                'txt_term': self.term_code, 
                'pageMaxSize': '500',
                '_': str(int(time.time() * 1000))
            }
            self.debug_log(f"fetch_dept('{dept}') -> URL: {self.BASE_URL}/ssb/searchResults/searchResults")
            self.debug_log(f"fetch_dept('{dept}') -> Params: {params}")
            
            r = self.session.get(f'{self.BASE_URL}/ssb/searchResults/searchResults', params=params, timeout=8)
            
            self.debug_log(f"fetch_dept('{dept}') -> Status: {r.status_code}")
            self.debug_log(f"fetch_dept('{dept}') -> Response Header: {r.headers.get('Content-Type')}")
            self.debug_log(f"fetch_dept('{dept}') -> Raw Body (First 200 chars): {r.text[:200]}")
            
            if r.status_code != 200: return "EXPIRED"
            data = r.json()
            if not data.get('success'):
                self.debug_log(f"fetch_dept('{dept}') -> success=False.tomcat context issue?")
            else:
                self.debug_log(f"fetch_dept('{dept}') -> success=True. Returned {len(data.get('data') or [])} sections.")
            return (data.get('data') or []) if data.get('success') else []
        except Exception as e:
            self.debug_log(f"fetch_dept('{dept}') raised Exception: {e}")
            return "ERROR"

    def check_for_updates(self):
        """Silently fetches version.txt from GitHub and returns (latest, current) if update available, else None."""
        try:
            url = "https://raw.githubusercontent.com/bibo242/KFUPM-Sniper/main/version.txt"
            r = requests.get(url, timeout=5)
            if r.status_code != 200:
                return None
            latest = r.text.strip().lstrip('vV')
            current = VERSION.lstrip('vV')
            def parse(v):
                try: return tuple(int(x) for x in v.split('.'))
                except: return (0,)
            if parse(latest) > parse(current):
                return latest
        except:
            pass
        return None

    def send_notification(self, message):
        try:
            requests.post(f"https://ntfy.sh/{self.ntfy_topic}", 
                          data=message.encode(encoding='utf-8'),
                          headers={"Title": "KFUPM Sniper Alert", "Priority": "high"},
                          timeout=5)
            self.log("Push notification sent!")
        except Exception as e:
            self.log(f"Push notification error: {e}")

class BannerRegister:
    def __init__(self, username, password, browser, log_callback):
        self.username = username
        self.password = password
        self.browser = browser
        self.log = log_callback
        self.base_url = "https://banner9-registration.kfupm.edu.sa/StudentRegistrationSsb/ssb"
        self.driver = None
        self.cookies = {}
        self.token = None
        self.headers = {}

    def _find_chromium_binary(self):
        """Auto-detect Chrome, Brave, or Edge binary on the system."""
        candidates = [
            # Chrome
            r"C:\Program Files\Google\Chrome\Application\chrome.exe",
            r"C:\Program Files (x86)\Google\Chrome\Application\chrome.exe",
            # Brave
            r"C:\Program Files\BraveSoftware\Brave-Browser\Application\brave.exe",
            r"C:\Program Files (x86)\BraveSoftware\Brave-Browser\Application\brave.exe",
            # Edge
            r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
            r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
            # Linux
            "/usr/bin/google-chrome",
            "/usr/bin/google-chrome-stable",
            "/usr/bin/brave-browser",
            "/usr/bin/brave-browser-stable",
            "/usr/bin/chromium-browser",
            "/usr/bin/chromium",
            "/usr/bin/microsoft-edge",
            "/usr/bin/microsoft-edge-stable",
            # macOS
            "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
            "/Applications/Brave Browser.app/Contents/MacOS/Brave Browser",
            "/Applications/Microsoft Edge.app/Contents/MacOS/Microsoft Edge",
        ]
        for path in candidates:
            if os.path.exists(path):
                return path
        return None

    def setup_driver(self):
        try:
            if self.browser in ("Chrome", "Brave"):
                options = webdriver.ChromeOptions()
                options.add_argument("--headless=new")
                options.add_argument("--disable-gpu")
                options.add_argument("--window-size=1920,1080")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                binary = self._find_chromium_binary()
                if binary:
                    options.binary_location = binary
                else:
                    self.log("No Chrome/Brave/Edge browser found. Install one or switch to Firefox.")
                    return False
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
            else:
                options = webdriver.FirefoxOptions()
                options.add_argument("-headless")
                service = FirefoxService(GeckoDriverManager().install())
                self.driver = webdriver.Firefox(service=service, options=options)
            return True
        except Exception as e:
            self.log(f"Driver Setup Error: {e}")
            return False

    def run(self, target_crn, term):
        self.log(f"[*] Starting Auto-Registration for {target_crn}...")
        if not self.setup_driver(): return
        
        try:
            if self.full_login_flow(term):
                self.extract_tokens()
                self.execute_mirror_logic(target_crn, term)
        except Exception as e:
            self.log(f"[!] Registration Error: {e}")
        finally:
            if self.driver:
                time.sleep(5)
                self.driver.quit()

    def full_login_flow(self, term):
        self.log("[*] Step 1: Logging in via Selenium...")
        self.driver.get(f"{self.base_url}/classRegistration/classRegistration")
        try:
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.CSS_SELECTOR, "input[type='email']"))).send_keys(self.username + Keys.RETURN)
            pwd = WebDriverWait(self.driver, 20).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "input[type='password']")))
            time.sleep(1.5)
            pwd.send_keys(self.password + Keys.RETURN)
            try: WebDriverWait(self.driver, 5).until(EC.element_to_be_clickable((By.ID, "idSIButton9"))).click()
            except: pass
            
            self.log("[*] Dashboard loaded. Navigating to Add/Drop...")
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.ID, "registerLink"))).click()
            WebDriverWait(self.driver, 20).until(EC.element_to_be_clickable((By.ID, "s2id_txt_term"))).click()
            search = WebDriverWait(self.driver, 10).until(EC.visibility_of_element_located((By.CSS_SELECTOR, "#select2-drop input.select2-input")))
            search.send_keys(term)
            time.sleep(1)
            search.send_keys(Keys.RETURN)
            time.sleep(3)
            WebDriverWait(self.driver, 10).until(EC.element_to_be_clickable((By.ID, "term-go"))).click()
            WebDriverWait(self.driver, 30).until(EC.presence_of_element_located((By.ID, "search-go")))
            return True
        except Exception as e:
            self.log(f"[!] UI/Login Error: {e}")
            return False

    def extract_tokens(self):
        meta_tag = self.driver.find_element(By.CSS_SELECTOR, "meta[name='synchronizerToken']")
        self.token = meta_tag.get_attribute("content")
        selenium_cookies = self.driver.get_cookies()
        for cookie in selenium_cookies:
            self.cookies[cookie['name']] = cookie['value']
        self.headers = {
            'User-Agent': self.driver.execute_script("return navigator.userAgent;"),
            'X-Synchronizer-Token': self.token,
            'X-Requested-With': 'XMLHttpRequest',
            'Origin': 'https://banner9-registration.kfupm.edu.sa',
            'Referer': f'{self.base_url}/classRegistration/classRegistration'
        }

    def execute_mirror_logic(self, target_crn, term):
        session = requests.Session()
        session.cookies.update(self.cookies)
        session.headers.update(self.headers)
        submit_url = f"{self.base_url}/classRegistration/submitRegistration/batch"
        add_url = f"{self.base_url}/classRegistration/addCRNRegistrationItems"

        # 1. ADD TO CART
        self.log(f"[*] Adding {target_crn} to Cart...")
        add_headers = self.headers.copy()
        add_headers['Content-Type'] = 'application/x-www-form-urlencoded; charset=UTF-8'
        session.post(add_url, headers=add_headers, data={'term': term, 'crnList': target_crn})

        # 2. PROBE
        self.log("[*] Probing server state...")
        submit_headers = self.headers.copy()
        submit_headers['Content-Type'] = 'application/json'
        payload_probe = {
            "create": [],
            "update": [{"courseReferenceNumber": str(target_crn), "term": str(term), "selectedAction": "RW"}],
            "destroy": []
        }
        res_probe = session.post(submit_url, headers=submit_headers, json=payload_probe)
        data_probe = res_probe.json()
        
        def get_all_objects(json_data):
            items = []
            if 'update' in json_data: items.extend(json_data['update'])
            if 'data' in json_data and 'update' in json_data['data']:
                items.extend(json_data['data']['update'])
            return items

        all_items = get_all_objects(data_probe)
        target_obj = next((i for i in all_items if str(i.get('courseReferenceNumber')) == str(target_crn)), None)

        if not target_obj:
            self.log("[-] CRITICAL: Target CRN missing from server response.")
            return

        if target_obj.get('courseRegistrationStatus') == 'RW' and not target_obj.get('errorFlag'):
            self.log(f"SUCCESS: Registered {target_crn} immediately!")
            return

        message = target_obj.get('message') or ""
        self.log(f"[*] Server Message: {message}")

        # FIND CONFLICT
        conflict_crn = None
        if "Time conflict" in message:
            match = re.search(r'CRN (\d{5})', message)
            if match:
                conflict_crn = match.group(1)
                self.log(f"[+] CONFLICT IDENTIFIED: {conflict_crn}")
        elif "Duplicate" in message:
            match = re.search(r'(\d{5})', message)
            if match:
                conflict_crn = match.group(1)
                self.log(f"[+] CONFLICT IDENTIFIED: {conflict_crn}")

        if conflict_crn:
            self.log(f"[*] EXECUTING MIRROR SWAP for {conflict_crn}...")
            conflict_obj = next((i for i in all_items if str(i.get('courseReferenceNumber')) == str(conflict_crn)), None)
            if not conflict_obj:
                self.log("[-] Could not find conflict object. Cannot swap.")
                return

            target_obj['selectedAction'] = "RW"
            target_obj['errorFlag'] = None
            target_obj['message'] = None
            conflict_obj['selectedAction'] = "DW"
            conflict_obj['conditionalAddDrop'] = True
            
            payload_swap = {"create": [], "update": [target_obj, conflict_obj], "destroy": []}
            res_swap = session.post(submit_url, headers=submit_headers, json=payload_swap)
            data_swap = res_swap.json()
            
            final_items = get_all_objects(data_swap)
            final_target = next((i for i in final_items if str(i.get('courseReferenceNumber')) == str(target_crn)), None)
            if final_target and final_target.get('courseRegistrationStatus') == 'RW' and not final_target.get('errorFlag'):
                self.log(f"SUCCESS: SWAP COMPLETE! You are in {target_crn}.")
            else:
                self.log(f"FAILURE: Swap Failed. {final_target.get('message') if final_target else 'Unknown error'}")
        else:
            self.log(f"FAILURE: {message}")

# ================= GUI APP =================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("KFUPM Sniper")
        self.geometry("1100x900")
        self.resizable(True, True)
        # --- SET WINDOW ICON ---
        try:
            # iconphoto() works cross-platform (Linux, macOS, Windows)
            ico_path = resource_path(ICON_ICO)
            png_path = resource_path(ICON_PNG)
            if os.path.exists(png_path):
                self._icon_image = tk.PhotoImage(file=png_path)
                self.iconphoto(True, self._icon_image)
            elif os.path.exists(ico_path):
                self.iconbitmap(ico_path)
        except Exception:
            pass

        self.backend = KFUPMSniperBackend()
        self.backend.log_callback = self.log_msg_threadsafe
        
        self.crn_entries = []
        self.watch_list = []
        self.table_rows = {}
        self.is_monitoring_phase = False
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_ui()
        self.restore_ui_state()
        self.log_msg_threadsafe("Monitor started. Logs will appear here.")
        threading.Thread(target=self._run_update_check, daemon=True).start()
        if not self.backend.seen_welcome:
            self.after(300, self.show_welcome_dialog)

    def show_welcome_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Welcome to KFUPM Sniper")
        dialog.geometry("480x620")
        dialog.resizable(False, False)
        dialog.grab_set() # Modal
        dialog.lift()
        dialog.focus_force()

        # Center over parent
        self.update_idletasks()
        px, py = self.winfo_x(), self.winfo_y()
        pw, ph = self.winfo_width(), self.winfo_height()
        dialog.geometry(f"480x620+{px + (pw - 480)//2}+{py + (ph - 620)//2}")



        frame = ctk.CTkFrame(dialog, fg_color="transparent")
        frame.pack(fill="both", expand=True, padx=24, pady=20)

        ctk.CTkLabel(frame, text="Getting Started", font=ctk.CTkFont(size=22, weight="bold")).pack(anchor="w", pady=(0, 12))

        tips = [
            ("Keep app open (or minimized) while monitoring.",
             "Some laptops auto-sleep and will stop the monitor. Disable auto-sleep in your power settings."),
            ("Auto-registration handles conflicts automatically.",
             "It drops time-slot conflicts and duplicate-course conflicts (another section of the same course). Only enable it if you are prepared for that."),
            ("Auto-registration runs invisibly in the background.",
             "You do NOT need to have a browser open or be logged into the portal yourself."),
            ("If the bottom of the window is cut off, reduce display scaling.",
             "Go to Windows Settings > Display > Scale, and lower it (e.g. from 150% to 125%)."),
            ("Found a bug or have a suggestion?",
             "Open an issue at github.com/bibo242/KFUPM-Sniper/issues"),
        ]

        for title, subtitle in tips:
            row = ctk.CTkFrame(frame, fg_color="#2a2a2a", corner_radius=8)
            row.pack(fill="x", pady=5)
            inner = ctk.CTkFrame(row, fg_color="transparent")
            inner.pack(fill="x", padx=12, pady=10)
            ctk.CTkLabel(inner, text=title, font=ctk.CTkFont(size=13, weight="bold"), wraplength=390, justify="left").pack(anchor="w")
            ctk.CTkLabel(inner, text=subtitle, font=("Arial", 11), text_color="#aaaaaa", wraplength=390, justify="left").pack(anchor="w", pady=(2, 0))

        dont_show_var = ctk.BooleanVar(value=False)
        ctk.CTkCheckBox(frame, text="Don't show this again", variable=dont_show_var,
                        font=("Arial", 12), text_color="#aaaaaa").pack(anchor="w", pady=(10, 4))

        btn_frame = ctk.CTkFrame(frame, fg_color="transparent")
        btn_frame.pack(fill="x", pady=(4, 0))
        ctk.CTkButton(btn_frame, text="Video Guide", height=36, fg_color="#c0392b", hover_color="#962d22",
                      font=ctk.CTkFont(size=13, weight="bold"),
                      command=lambda: webbrowser.open_new_tab(YOUTUBE_GUIDE_URL)).pack(side="left", expand=True, fill="x", padx=(0, 6))

        def on_got_it():
            if dont_show_var.get():
                self.backend.seen_welcome = True
                self.backend.save_data()
            dialog.destroy()

        ctk.CTkButton(btn_frame, text="Got it!", height=36, font=ctk.CTkFont(size=14, weight="bold"),
                      command=on_got_it).pack(side="left", expand=True, fill="x", padx=(6, 0))



    def _run_update_check(self):
        latest = self.backend.check_for_updates()
        if latest:
            self.after(0, lambda: self._show_update_banner(latest))

    def _show_update_banner(self, latest_version):
        self.update_version_label.configure(text=f"⬆  New version v{latest_version} is available! You're on v{VERSION}")
        self.update_bar.grid()

    def restore_ui_state(self):

        # Restore Term
        if self.backend.term_code:
            self.term_var.set(self.backend.term_code)
        else:
            # Set default to current term if none saved
            options = self.generate_term_options()
            if options: self.term_var.set(options[2]) # Default term code is 261 now 
        
        # Restore CRNs
        if hasattr(self.backend, 'saved_watch_list'):
            # Clear default empty field if we have saved data
            if self.backend.saved_watch_list:
                for entry in list(self.crn_entries): self.remove_crn(entry[0], force=True)
                for crn in self.backend.saved_watch_list:
                    self.add_crn_field(crn)
        
        # Restore Table
        for crn, data in self.backend.dashboard_cache.items():
            self.update_table_row(crn, data, is_stale=True)  # Mark as stale on startup

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(1, weight=1) # row 0 = update bar (optional), row 1 = main content

        # === FULL-WIDTH UPDATE BAR (hidden until update detected) ===
        self.update_bar = ctk.CTkFrame(self, fg_color="#1a7a3c", corner_radius=0, height=18)
        self.update_bar.grid(row=0, column=0, columnspan=2, sticky="ew")
        self.update_bar.grid_remove() # Hidden by default
        self.update_bar.grid_propagate(False)

        self.update_version_label = ctk.CTkLabel(
            self.update_bar, text="",
            font=ctk.CTkFont(size=11), text_color="white", cursor="hand2"
        )
        self.update_version_label.pack(side="left", padx=12, pady=0)
        self.update_version_label.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://github.com/bibo242/KFUPM-Sniper"))

        # Underlined "Download ↗" link on the right
        self.update_dl_label = ctk.CTkLabel(
            self.update_bar, text="Download ↗",
            font=("Arial", 11, "underline"), text_color="white", cursor="hand2"
        )
        self.update_dl_label.pack(side="right", padx=12, pady=0)
        self.update_dl_label.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://github.com/bibo242/KFUPM-Sniper"))

        # Make the whole bar clickable too
        self.update_bar.bind("<Button-1>", lambda e: webbrowser.open_new_tab("https://github.com/bibo242/KFUPM-Sniper"))
        self.update_bar.configure(cursor="hand2")


        # === SIDEBAR ===
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=1, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1) # Push settings to bottom

        # Logo
        self.logo_label = ctk.CTkLabel(self.sidebar, text="KFUPM SNIPER", font=ctk.CTkFont(size=25, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))

        ctk.CTkLabel(self.sidebar, text="Term Code:",font=("Arial", 15, "bold")).grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        
        self.term_var = ctk.StringVar()
        self.term_menu = ctk.CTkOptionMenu(
            self.sidebar, 
            variable=self.term_var, 
            values=self.generate_term_options(), 
            command=self.snapshot_and_save,
            width=200
        )
        self.term_menu.grid(row=2, column=0, padx=20, pady=(0, 10))

        # Buttons
        self.start_btn = ctk.CTkButton(self.sidebar, text="START MONITOR", fg_color="green", command=self.toggle_scan)
        self.start_btn.grid(row=3, column=0, padx=20, pady=10)
        
        self.link_btn = ctk.CTkButton(self.sidebar, text="GO TO REGISTER ↗", fg_color="gray", state="disabled", command=self.open_portal)
        self.link_btn.grid(row=4, column=0, padx=20, pady=10)

        # Alerts
        self.sound_var = ctk.BooleanVar(value=True)
        self.popup_var = ctk.BooleanVar(value=True)
        self.push_var = ctk.BooleanVar(value=True)

        ctk.CTkSwitch(self.sidebar, text="Sound Alerts", font=("Arial", 15, "bold"), variable=self.sound_var).grid(row=5, column=0, padx=20, pady=10, sticky="w")
        ctk.CTkSwitch(self.sidebar, text="Popup Alerts", font=("Arial", 15, "bold"), variable=self.popup_var).grid(row=6, column=0, padx=20, pady=10, sticky="w")
        
        ctk.CTkSwitch(self.sidebar, text="Phone Notifications", font=("Arial", 15, "bold"), variable=self.push_var, command=self.toggle_push_ui).grid(row=7, column=0, padx=20, pady=10, sticky="w")
        

        # Push Info Frame (QR + Copy Link)
        self.push_info_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.push_info_frame.grid(row=9, column=0, padx=20, pady=5, sticky="ew")
        self.push_info_frame.grid_remove() # Hide initially

        self.qr_label = ctk.CTkLabel(self.push_info_frame, text="")
        self.qr_label.pack(pady=5)

        self.copy_btn = ctk.CTkButton(self.push_info_frame, text="Copy link", width=100, fg_color="#3498db", command=self.copy_link)
        self.copy_btn.pack(pady=5)

        # === AUTO REGISTER SETTINGS ===
        self.auto_reg_frame = ctk.CTkFrame(self.sidebar, fg_color="transparent")
        self.auto_reg_frame.grid(row=10, column=0, padx=20, pady=10, sticky="ew")
        
        ctk.CTkLabel(self.auto_reg_frame, text="AUTO REGISTER SETTINGS", font=ctk.CTkFont(size=15, weight="bold")).pack(pady=(0, 5))
        
        self.reg_settings_container = ctk.CTkFrame(self.auto_reg_frame, fg_color="transparent")
        self.reg_settings_container.pack(fill="x")
            
        ctk.CTkLabel(self.reg_settings_container, text="Login:", font=("Arial", 15, "bold")).pack(pady=(5, 0), anchor="w")
        
        self.reg_user_entry = ctk.CTkEntry(self.reg_settings_container, placeholder_text="Username", height=28)
        self.reg_user_entry.insert(0, self.backend.reg_user)
        self.reg_user_entry.pack(pady=2, fill="x")
        self.reg_user_entry.bind("<KeyRelease>", self.snapshot_and_save)
        
        self.reg_pass_entry = ctk.CTkEntry(self.reg_settings_container, placeholder_text="Password", show="*", height=28)
        self.reg_pass_entry.insert(0, self.backend.reg_pass)
        self.reg_pass_entry.pack(pady=2, fill="x")
        self.reg_pass_entry.bind("<KeyRelease>", self.snapshot_and_save)

        # Create the Eye Button as a child of the Entry widget
        self.eye_btn = ctk.CTkButton(
            self.reg_pass_entry, 
            text="👁", 
            width=25, 
            height=20, 
            fg_color="transparent", 
            hover_color="#333333", # Dark gray hover to match theme
            text_color="#A0A0A0", 
            font=("Arial", 16),
            command=self.toggle_password_visibility
        )
        
        # Place it on the far right inside the entry
        self.eye_btn.place(relx=1.0, rely=0.5, anchor="e", x=-5)
        # --- PASSWORD ENTRY END ---
        
        ctk.CTkLabel(self.reg_settings_container, text="Browser:", font=("Arial", 15, "bold")).pack(pady=(5, 0), anchor="w")
        self.reg_browser_var = ctk.StringVar(value=self.backend.reg_browser)
        self.reg_browser_selector = ctk.CTkSegmentedButton(
            self.reg_settings_container,
            values=["Chrome", "Brave", "Firefox"],
            variable=self.reg_browser_var,
            command=self.snapshot_and_save,
            height=28,
            width=200
        )
        self.reg_browser_selector.pack(pady=2, fill="x")

        # Mode
        self.mode_menu = ctk.CTkOptionMenu(self.sidebar, width=200, values=["Dark", "Light"], command=ctk.set_appearance_mode)
        self.mode_menu.grid(row=11, column=0, padx=20, pady=(10, 10), sticky="s")

        # Initialize Push UI state
        self.toggle_push_ui()

        # === MAIN AREA ===
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=1, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(4, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # Target Inputs
        crn_container = ctk.CTkFrame(self.main_frame)
        crn_container.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        
        # Header with gender selector
        header_frame = ctk.CTkFrame(crn_container, fg_color="transparent")
        header_frame.pack(fill="x", padx=10, pady=2)
        
        ctk.CTkLabel(header_frame, text="Target Sections (By CRN e.g., 25132) or (Course-Sec e.g., ME401-01)", font=("Arial", 15, "bold")).pack(side="left", anchor="w")
        
        self.gender_var = ctk.StringVar(value="Male")
        self.gender_selector = ctk.CTkSegmentedButton(
            header_frame, 
            values=["Male", "Female"],
            variable=self.gender_var,
            width=120,
            height=28
        )
        self.gender_selector.pack(side="right", padx=5)
        
        self.crn_scroll = ctk.CTkScrollableFrame(crn_container, height=60, orientation="horizontal")
        self.crn_scroll.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(crn_container, text="+ Add Target", width=100, height=24, command=self.add_crn_field).pack(pady=5)
        self.add_crn_field()

        # === STATUS BAR & SPEED CONTROL ===
        status_frame = ctk.CTkFrame(self.main_frame, height=40, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))

        # 1. Status Text (Far Left)
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Idle", font=("Consolas", 15))
        self.status_label.pack(side="left")

        # 2. Metrics (Far Right)
        self.delay_label = ctk.CTkLabel(status_frame, text="Cycle: --s", font=("Consolas", 15), text_color="gray")
        self.delay_label.pack(side="right", padx=10)
        
        self.last_scan_label = ctk.CTkLabel(status_frame, text="Last Scan: --:--:--", font=("Consolas", 15), text_color="gray")
        self.last_scan_label.pack(side="right", padx=(10, 0))

        # 3. Speed Slider (Center-Right, next to metrics)
        # We put it in a small frame to keep the label and slider together
        slider_frame = ctk.CTkFrame(status_frame, fg_color="transparent")
        slider_frame.pack(side="right", padx=20)

        self.speed_label_title = ctk.CTkLabel(slider_frame, text=f"Wait: {self.backend.scan_interval}s", font=("Consolas", 15))
        self.speed_label_title.pack(side="left", padx=(0, 5))

        self.delay_slider = ctk.CTkSlider(
            slider_frame, 
            from_=0.0, 
            to=10.0, 
            number_of_steps=20, 
            width=120, # Compact width
            command=self.update_scan_interval
        )
        self.delay_slider.set(self.backend.scan_interval)
        self.delay_slider.pack(side="left")
        # --- CONFIGURATION ---
        # Fixed widths for columns [CRN, COURSE, SEC, TITLE, INSTRUCTOR, SEATS, AUTO REG]
        self.col_widths = [70, 80, 50, 250, 180, 60, 80]
        headers = ["CRN", "COURSE", "SEC", "TITLE", "INSTRUCTOR", "SEATS", "AUTO REG"]

        # Table Header
        self.header_frame = ctk.CTkFrame(self.main_frame, height=30, corner_radius=5, fg_color="#34495e")
        self.header_frame.grid(row=3, column=0, sticky="ew", padx=10, pady=(0, 0))

        for i, header_text in enumerate(headers):
            lbl = ctk.CTkLabel(
                self.header_frame, 
                text=header_text, 
                width=self.col_widths[i], 
                font=("Arial", 12, "bold"),
                text_color="white",
                anchor="center" if i != 3 and i != 4 else "w"
            )
            lbl.grid(row=0, column=i, padx=2, pady=5)

        # Table Body
        self.table_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.table_scroll.grid(row=4, column=0, sticky="nsew")

        # Logs
        self.log_box = ctk.CTkTextbox(self.main_frame, height=200, font=("Arial", 15), state="disabled")
        self.log_box.grid(row=5, column=0, sticky="ew", pady=(15, 0))
        
        # Configure tags for highlighting
        self.log_box.tag_config("yellow", foreground="#f1c40f")
        self.log_box.tag_config("blue", foreground="#3498db")
        self.log_box.tag_config("green", foreground="#2ecc71")

    # --- UI HELPERS ---
    def add_crn_field(self, value=""):
        if self.backend.running:
            messagebox.showwarning("Monitor Running", "Stop the monitor before editing targets.")
            return
        f = ctk.CTkFrame(self.crn_scroll, fg_color="transparent")
        f.pack(side="left", padx=5)
        
        placeholder = "(e.g. 25123)" if not self.crn_entries else ""
        e = ctk.CTkEntry(f, width=100, placeholder_text=placeholder, justify="center")
        if value: e.insert(0, value)
        e.pack(side="left")
        e.bind("<FocusOut>", self.snapshot_and_save)
        
        ctk.CTkButton(f, text="×", width=25, fg_color="#e74c3c", command=lambda: self.remove_crn(f)).pack(side="left", padx=2)
        self.crn_entries.append((f, e))
        self.snapshot_and_save()

    def remove_crn(self, frame, force=False):
        if self.backend.running and not force:
            messagebox.showwarning("Monitor Running", "Stop the monitor before editing targets.")
            return
            
        # Identify the CRN being removed
        crn_to_remove = None
        for f, e in self.crn_entries:
            if f == frame:
                crn_to_remove = e.get().strip()
                break

        frame.destroy()
        self.crn_entries = [x for x in self.crn_entries if x[0].winfo_exists()]
        
        if not force and crn_to_remove:
            if crn_to_remove in self.backend.dashboard_cache:
                del self.backend.dashboard_cache[crn_to_remove]
            if crn_to_remove in self.table_rows:
                for w in self.table_rows[crn_to_remove].values(): w.destroy()
                del self.table_rows[crn_to_remove]
        
        self.snapshot_and_save()

    def toggle_password_visibility(self):
        current_show = self.reg_pass_entry.cget("show")
        if current_show == "*":
            self.reg_pass_entry.configure(show="")
            self.eye_btn.configure(text="Ø") # Symbol for "Hidden/Close"
        else:
            self.reg_pass_entry.configure(show="*")
            self.eye_btn.configure(text="👁") # Symbol for "Show/Open"

    def clear_table(self):
        for crn in list(self.table_rows.keys()):
            for widget in self.table_rows[crn].values():
                widget.destroy()
            del self.table_rows[crn]
        self.backend.dashboard_cache = {}
        self.backend.target_depts = set()

    def generate_term_options(self):
        now = datetime.now()
        yy = now.year % 100
        
        # User logic: YY1, YY2, YY3, (YY+1)1
        # We also add (YY-1)2, (YY-1)3 if we are early in the year to cover current Spring/Summer
        options = []
        if now.month < 7:
            options.extend([f"{yy-1}2", f"{yy-1}3"])
        
        options.extend([f"{yy}1", f"{yy}2", f"{yy}3", f"{yy+1}1"])
        return options

    def clear_table_ui(self):
        """Clear only the visible table, keep the cache intact"""
        for crn in list(self.table_rows.keys()):
            for widget in self.table_rows[crn].values():
                widget.destroy()
            del self.table_rows[crn]

    def open_portal(self):
        webbrowser.open(f"{self.backend.BASE_URL}/ssb/registration/registration")

    def toggle_push_ui(self):
        if self.push_var.get():
            self.push_info_frame.grid()
            
            # Generate QR Code
            url = f"https://ntfy.sh/{self.backend.ntfy_topic}"
            qr = qrcode.make(url)
            img = ctk.CTkImage(light_image=qr.get_image(), size=(150, 150))
            self.qr_label.configure(image=img)
            self.qr_label.image = img # Keep reference
            
            self.log_msg_threadsafe("Push notifications enabled. Scan QR or copy link to subscribe on ntfy.")
        else:
            self.push_info_frame.grid_remove()

    def copy_link(self):
        url = f"https://ntfy.sh/{self.backend.ntfy_topic}"
        self.clipboard_clear()
        self.clipboard_append(url)
        self.update() # Now it stays on the clipboard
        self.log_msg_threadsafe("Link copied to clipboard!")

    def update_scan_interval(self, value):
        val = round(value, 1)
        self.backend.scan_interval = val
        self.speed_label_title.configure(text=f"Wait: {val}s")
        
        # Safety Color Coding
        if val < 1.0:
            self.speed_label_title.configure(text_color="#e74c3c") # Red (Danger)
        elif val < 3.0:
            self.speed_label_title.configure(text_color="#f1c40f") # Yellow (Aggressive)
        else:
            self.speed_label_title.configure(text_color="#2ecc71") # Green (Safe)
            
        self.snapshot_and_save()

    def update_table_row(self, crn, data, is_stale=False):
        # Use gray for stale data (not actively monitoring), green/red for live data
        if is_stale:
            seat_color = "#95a5a6"  # Gray for stale data
        else:
            seat_color = "#2ecc71" if data['seats'] > 0 else "#e74c3c"
        
        if crn not in self.table_rows:
            # --- THE FIX: Create a Frame for the Row ---
            row_wrapper = ctk.CTkFrame(self.table_scroll, height=30)
            row_wrapper.grid(row=len(self.table_rows), column=0, sticky="ew", pady=1)

            # Auto Reg Checkbox (Always unchecked by default per user request)
            reg_var = ctk.BooleanVar(value=False)
            
            # Checkbox Column with fixed width container
            chk_container = ctk.CTkFrame(row_wrapper, width=self.col_widths[6], height=25, fg_color="transparent")
            chk_container.grid(row=0, column=6, padx=2)
            chk_container.grid_propagate(False)

            reg_cb = ctk.CTkCheckBox(chk_container, text="", variable=reg_var, width=20, height=20, command=lambda c=crn, v=reg_var: self.toggle_crn_auto_reg(c, v))
            reg_cb.place(relx=0.5, rely=0.5, anchor="center")
            
            widgets = {
                'crn': ctk.CTkLabel(row_wrapper, text=crn, width=self.col_widths[0], anchor="center"),
                'code': ctk.CTkLabel(row_wrapper, text=data['code'], width=self.col_widths[1], anchor="center"),
                'sec': ctk.CTkLabel(row_wrapper, text=data['sec'], width=self.col_widths[2], anchor="center"),
                'title': ctk.CTkLabel(row_wrapper, text=data['title'][:30], width=self.col_widths[3], anchor="w"),
                'instr': ctk.CTkLabel(row_wrapper, text=data['instr'][:20], width=self.col_widths[4], anchor="w"),
                'seats': ctk.CTkLabel(row_wrapper, text=str(data['seats']), width=self.col_widths[5], font=("Arial", 15, "bold"), text_color=seat_color, anchor="center"),
                'auto_reg': reg_cb,
                'wrapper': row_wrapper
            }
            
            # Grid labels (except checkbox which is already handled)
            for i, key in enumerate(['crn', 'code', 'sec', 'title', 'instr', 'seats']):
                widgets[key].grid(row=0, column=i, padx=2)
                
            self.table_rows[crn] = widgets
        else:
            self.table_rows[crn]['seats'].configure(text=str(data['seats']), text_color=seat_color)

    def toggle_crn_auto_reg(self, crn, var):
        if var.get():
            self.backend.auto_reg_list.add(crn)
        else:
            self.backend.auto_reg_list.discard(crn)
        self.backend.save_data()

    def log_msg_threadsafe(self, msg):
        self.after(0, lambda: self._log(msg))

    def snapshot_and_save(self, event=None):
        # Capture current UI state
        self.backend.watch_list_snapshot = [e.get().strip().upper().replace(" ", "") for _, e in self.crn_entries if e.get().strip()]
        
        raw_term = self.term_var.get()
        self.backend.term_code = self.backend.convert_term_code(raw_term)
        
        # Auto Reg State
        self.backend.reg_user = self.reg_user_entry.get().strip()
        self.backend.reg_pass = self.reg_pass_entry.get().strip()
        self.backend.reg_browser = self.reg_browser_var.get()
        
        self.backend.save_data()

    def _log(self, msg):
        self.log_box.configure(state="normal")
        
        # Get start index for tagging
        start_index = self.log_box.index("end-1c")
        
        full_msg = f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n"
        self.log_box.insert("end", full_msg)
        
        # Apply tags to the newly inserted line
        # 1. Highlight "Caution" in yellow
        search_start = start_index
        while True:
            pos = self.log_box.search("Caution", search_start, stopindex="end")
            if not pos: break
            end_pos = f"{pos}+{len('Caution')}c"
            self.log_box.tag_add("yellow", pos, end_pos)
            search_start = end_pos
            
        # 2. Highlight links in blue
        search_start = start_index
        while True:
            pos = self.log_box.search("http", search_start, stopindex="end")
            if not pos: break
            # Find end of link (space or newline)
            end_pos = self.log_box.search(r"[\s\n]", pos, stopindex="end", regexp=True)
            if not end_pos: end_pos = "end-1c"
            self.log_box.tag_add("blue", pos, end_pos)
            search_start = end_pos

        # 3. Highlight "STAYS ON" in green
        search_start = start_index
        while True:
            pos = self.log_box.search("STAYS ON", search_start, stopindex="end")
            if not pos: break
            end_pos = f"{pos}+{len('STAYS ON')}c"
            self.log_box.tag_add("green", pos, end_pos)
            search_start = end_pos
            
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # --- MAIN LOGIC ---
    def toggle_scan(self):
        if not self.backend.running:
            self.watch_list = [e.get().strip().upper().replace(" ", "") for _, e in self.crn_entries if e.get().strip()]
            term = self.term_var.get()
            
            if not self.watch_list:
                self._log("Enter at least one Target (CRN or Course-Section).")
                return
            if not term:
                self._log("Enter a Term Code (e.g. 202520).")
                return
            
            # Convert term code if short format
            term = self.backend.convert_term_code(term)
            
            # Clear the visible table (but keep cache for smart discovery)
            self.clear_table_ui()
            
            self.backend.term_code = term
            self.backend.target_gender = self.gender_var.get()
            
            # --- LOCK SLIDER ---
            self.delay_slider.configure(state="disabled")

            # Snapshot for saving
            self.backend.watch_list_snapshot = self.watch_list
            self.backend.save_data()

            self.backend.running = True
            self.start_btn.configure(text="STOP MONITOR", fg_color="#c0392b")
            self.term_menu.configure(state="disabled")
            threading.Thread(target=self.worker, daemon=True).start()
        else:
            self.backend.running = False
            self.start_btn.configure(text="Stopping...", state="disabled")

    def worker(self):
        self.log_msg_threadsafe("Initializing fresh session tracking...")
        # 1. ALWAYS RE-AUTH WITH THE CORRECT TERM!
        # The GUI initializes auth() on load, which means if the user changes the dropdown 
        # or has an empty cache, the session gets bound to the wrong term natively!
        if not self.backend.auth():
            self.log_msg_threadsafe("Fatal Auth Error.")
            self.after(0, self.stop_gracefully)
            return

        self.log_msg_threadsafe("Auto-Discovery started...")
        self.after(0, lambda: self.status_label.configure(text="Status: Discovery", text_color="#3498db"))

        # 1. Identify departments from course codes to prioritize
        prioritized_depts = set()
        for item in self.watch_list:
            if not item.isdigit():
                match = re.match(r'^([A-Z]+)', item)
                if match: prioritized_depts.add(match.group(1))
            
        # --- CACHE CHECK ---
        unresolved_items = set(self.watch_list)
        for item in list(unresolved_items):
            res = self.backend.find_in_cache(item)
            if res:
                dept, sec = res
                self.backend.target_depts.add(dept)
                self.log_msg_threadsafe(f"Found {item} in cache (Dept: {dept})")
                crn = str(sec.get('courseReferenceNumber'))
                self.update_cache_and_gui(crn, sec, dept)
                unresolved_items.remove(item)

        # 2. Build search order: prioritized first, then the rest
        remaining_depts = [d for d in self.backend.all_subjects if d not in prioritized_depts]
        search_order = list(prioritized_depts) + remaining_depts

        # Discovery Phase
        if unresolved_items:
            self.log_msg_threadsafe(f"Searching {len(search_order)} departments for missing items... This process only happens once.")
            for dept in search_order:
                if not self.backend.running: break
                
                res = self.backend.fetch_dept(dept)
                
                if res == "EXPIRED":
                    self.backend.auth()
                    continue
                if res == "ERROR": continue
                
                if isinstance(res, list):
                    # Save to cache
                    if self.backend.term_code not in self.backend.dept_cache:
                        self.backend.dept_cache[self.backend.term_code] = {}
                    self.backend.dept_cache[self.backend.term_code][dept] = {
                        "timestamp": time.time(),
                        "data": res
                    }
                    
                    for sec in res:
                        campus = sec.get('campusDescription', '').lower()
                        target = self.backend.target_gender 
    
                        if target == "Male" and "female" in campus:
                            continue
                        if target == "Female" and "female" not in campus:
                            continue
    
                        crn = str(sec.get('courseReferenceNumber'))
                        code = f"{sec.get('subject')}{sec.get('courseNumber')}"
                        
                        full_course_sec = f"{code}-{sec.get('sequenceNumber')}"
                        
                        if crn in self.watch_list or full_course_sec in self.watch_list:
                            if dept not in self.backend.target_depts:
                                self.backend.target_depts.add(dept)
                                self.log_msg_threadsafe(f"Found {crn or full_course_sec} in {dept} (Site)")
                            self.update_cache_and_gui(crn, sec, dept)
                            
            self.backend.save_data()

        if not self.backend.target_depts:
            self.log_msg_threadsafe("No CRNs/Courses found! Check inputs.")
            self.after(0, self.stop_gracefully)
            return

        self.is_monitoring_phase = True
        self.backend.debug_log("-----------------------------------------")
        self.backend.debug_log(f"Monitor Phase starts. Target Depts: {self.backend.target_depts}")
        self.log_msg_threadsafe("Monitoring started (Parallel Mode)...")
        self.after(0, lambda: self.status_label.configure(text="Status: Monitoring", text_color="#2ecc71"))

        # Monitor Phase (Parallelized)
        first_scan = True
        while self.backend.running:
            current_scan_start = time.time()
            self.backend.debug_log(f"Top of scan cycle loop. Threads starting for {len(self.backend.target_depts)} depts.")
            
            with ThreadPoolExecutor(max_workers=10) as executor:
                futures = [executor.submit(self.backend.fetch_dept, dept) for dept in self.backend.target_depts]
                
                for future, dept in zip(futures, self.backend.target_depts):
                    if not self.backend.running: break
                    
                    try:
                        res = future.result()
                        self.backend.debug_log(f"Future resolved for {dept}. Result type: {type(res)}")
                        
                        if res == "EXPIRED":
                            self.backend.debug_log(f"Session marked EXPIRED while parsing {dept}. Re-authenticating...")
                            self.log_msg_threadsafe("Session expired, renewing...")
                            self.backend.auth()
                            continue
                        
                        if isinstance(res, list):
                            self.backend.debug_log(f"Department {dept} mapped. Analyzing {len(res)} sections for targets.")
                            if self.backend.term_code not in self.backend.dept_cache:
                                self.backend.dept_cache[self.backend.term_code] = {}
                            self.backend.dept_cache[self.backend.term_code][dept] = {
                                "timestamp": time.time(),
                                "data": res
                            }
                            
                            for sec in res:
                                crn = str(sec.get('courseReferenceNumber'))
                                code = f"{sec.get('subject')}{sec.get('courseNumber')}"
                                full_course_sec = f"{code}-{sec.get('sequenceNumber')}"
                                
                                if crn in self.watch_list or full_course_sec in self.watch_list:
                                    self.update_cache_and_gui(crn, sec, dept, suppress_new_alerts=first_scan)
                    except Exception as e:
                        self.backend.debug_log(f"Error fetching {dept}: {e}")

            elapsed = time.time() - current_scan_start
            self.after(0, lambda d=elapsed: self.delay_label.configure(text=f"Cycle: {d:.2f}s", text_color="#3498db"))
            self.after(0, lambda: self.last_scan_label.configure(text=f"Last Scan: {datetime.now().strftime('%H:%M:%S')}", text_color="#2ecc71"))
            
            first_scan = False
            time.sleep(self.backend.scan_interval)

        self.after(0, self.stop_gracefully)

    def update_cache_and_gui(self, crn, sec, dept, suppress_new_alerts=False):
        new_seats = sec.get('seatsAvailable', 0)
        prev_seats = self.backend.dashboard_cache.get(crn, {}).get('seats', new_seats)
        
        self.backend.debug_log(f"update_cache_and_gui(crn={crn}) | new_seats={new_seats} | prev_seats={prev_seats}")
        self.backend.debug_log(f"update_cache_and_gui(crn={crn}) | suppress_new_alerts={suppress_new_alerts} | is_monitoring_phase={self.is_monitoring_phase}")

        instr = "TBA"
        if sec.get('faculty') and len(sec['faculty']) > 0:
            instr = sec['faculty'][0].get('displayName', 'TBA')
        code = f"{sec.get('subject')}{sec.get('courseNumber')}"
        title = sec.get('courseTitle', 'Unknown')
        
        data = {
            'code': code,
            'sec': sec.get('sequenceNumber'),
            'title': title,
            'instr': instr,
            'seats': new_seats,
            'dept': dept
        }
        
        is_new_section = crn not in self.backend.dashboard_cache
        self.backend.dashboard_cache[crn] = data
        self.after(0, self.update_table_row, crn, data)
        
        if new_seats > 0:
            self.after(0, lambda: self.link_btn.configure(state="normal", fg_color="#2ecc71"))
            
        if is_new_section and self.is_monitoring_phase:
            if new_seats > 0:
                self.backend.debug_log(f"update_cache_and_gui(crn={crn}) -> Triggering NEW SECTION logic (skip_reg={suppress_new_alerts})")
                self.trigger_alert(f"NEW SECTION: {code}-{data['sec']}", crn=crn, skip_auto_reg=suppress_new_alerts)
        elif new_seats > prev_seats and new_seats > 0:
            self.backend.debug_log(f"update_cache_and_gui(crn={crn}) -> Triggering SEAT OPEN logic! (Diff: {new_seats} > {prev_seats}, skip_reg={suppress_new_alerts})")
            self.trigger_alert(f"OPEN: {code}-{data['sec']} ({new_seats} seats)", crn=crn, skip_auto_reg=suppress_new_alerts)
        else:
            if new_seats == 0 and prev_seats > 0:
                self.backend.debug_log(f"update_cache_and_gui(crn={crn}) -> Seat was TAKEN. Dropped from {prev_seats} to 0.")
            elif new_seats == prev_seats:
                pass

    def trigger_alert(self, msg, crn=None, skip_auto_reg=False):
        if crn and crn in self.backend.auto_reg_list and not skip_auto_reg:
            if self.backend.is_registering:
                self.log_msg_threadsafe(f"[!] Registration busy. Retrying {crn} in 45s...")
                threading.Timer(45, self.trigger_alert, args=(msg, crn)).start()
            else:
                self.log_msg_threadsafe(f"[*] Triggering Auto-Registration for {crn}...")
                threading.Thread(
                    target=self.run_registration_with_flag, 
                    args=(crn, self.backend.convert_term_code(self.backend.term_code)), 
                    daemon=True
                ).start()

        self.log_msg_threadsafe(f"🚨 {msg}")
        self.after(0, lambda: self.link_btn.configure(state="normal", fg_color="#2ecc71"))
        
        if self.sound_var.get(): play_sound()
        if self.push_var.get():
            threading.Thread(target=self.backend.send_notification, args=(msg,)).start()

        if self.popup_var.get(): 
            flash_window(self)
            messagebox.showinfo("SEAT FOUND!", f"{msg}\n\nCheck logs for registration status!")

    def run_registration_with_flag(self, crn, term):
        try:
            self.backend.is_registering = True
            reg_bot = BannerRegister(
                self.backend.reg_user, 
                self.backend.reg_pass, 
                self.backend.reg_browser, 
                self.log_msg_threadsafe
            )
            reg_bot.run(crn, term)
        except Exception as e:
            self.log_msg_threadsafe(f"[!] Registration Wrapper Error: {e}")
        finally:
            self.backend.is_registering = False

    def stop_gracefully(self):
        self.log_msg_threadsafe(f"Stopping Monitoring...")
        self.backend.running = False
        self.is_monitoring_phase = False
        self.start_btn.configure(text="START MONITOR", fg_color="green", state="normal")
        self.status_label.configure(text="Status: Stopped", text_color="gray")
        self.term_menu.configure(state="normal")
        
        for crn, widgets in self.table_rows.items():
            widgets['seats'].configure(text_color="#95a5a6")

        self.delay_slider.configure(state="normal")
        
        self.backend.watch_list_snapshot = [e.get().strip().upper().replace(" ", "") for _, e in self.crn_entries if e.get().strip()]
        self.backend.term_code = self.term_var.get()
        self.backend.save_data()


    def on_closing(self):
        self.backend.watch_list_snapshot = [e.get().strip().upper().replace(" ", "") for _, e in self.crn_entries if e.get().strip()]
        self.backend.term_code = self.term_var.get()
        
        self.backend.save_data()
        self.backend.running = False
        self.destroy()

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()

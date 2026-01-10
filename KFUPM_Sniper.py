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
from datetime import datetime
from tkinter import messagebox

# ================= CONFIGURATION =================
ICON_FILENAME = "icon.ico"  # Window Title/Taskbar Icon

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
        self.term_code = None
        self.running = False
        self.dashboard_cache = {} # {crn: {code, sec, title, instr, seats, dept}}
        self.target_depts = set() # Departments to monitor
        self.log_callback = None
        self.all_subjects = self._get_all_subjects() # List of all department codes

        # ntfy.sh Topic
        self.ntfy_topic = f"kfupm_sniper_{''.join(random.choices(string.ascii_lowercase + string.digits, k=6))}"
        
        self.data_file = os.path.join(os.path.expanduser("~"), ".kfupm_sniper", "sniper_data.json")
        self.load_data()

    def get_data_file_path(self):
        return self.data_file

    def save_data(self):
        data = {
            "term_code": self.term_code,
            "target_depts": list(self.target_depts),
            "dashboard_cache": self.dashboard_cache,
            "watch_list": self.watch_list_snapshot if hasattr(self, 'watch_list_snapshot') else [],
            "watch_courses": self.watch_courses_snapshot if hasattr(self, 'watch_courses_snapshot') else [],
            "ntfy_topic": self.ntfy_topic
        }
        try:
            os.makedirs(os.path.dirname(self.data_file), exist_ok=True)
            with open(self.data_file, 'w') as f:
                json.dump(data, f)
        except Exception as e:
            print(f"Failed to save data: {e}")

    def load_data(self):
        if not os.path.exists(self.data_file): return
        try:
            with open(self.data_file, 'r') as f:
                data = json.load(f)
                self.term_code = data.get("term_code")
                self.target_depts = set(data.get("target_depts", []))
                self.dashboard_cache = data.get("dashboard_cache", {})
                self.saved_watch_list = data.get("watch_list", [])
                self.saved_watch_courses = data.get("watch_courses", [])
                if "ntfy_topic" in data: self.ntfy_topic = data["ntfy_topic"]
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
        self.saved_watch_courses = []

    def _get_all_subjects(self):
        # This is a hardcoded list for KFUPM. Can be fetched dynamically if needed.
        return [
            "AE", "AR", "BI", "CE", "CHE", "CH", "CI", "COE", "CP", "CS", "DES", "EE", "EN", "ES", "GE", "GL", "GS", "IAM", "IE", "IS", "MA", "ME", "MGT", "MIS", "MSE", "NANO", "OE", "PET", "PH", "PM", "SE", "SYS"
        ]

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
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/120.0.0.0 Safari/537.36',
            'Referer': f'{self.BASE_URL}/ssb/classSearch/classSearch'
        })
        try:
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
            payload = {'term': self.term_code}
            resp = s.post(f'{self.BASE_URL}/ssb/term/search?mode=search', data=payload)
            
            if resp.status_code == 200:
                self.session = s
                self.log("Auth Success!")
                return True
            self.log(f"Auth failed: Status {resp.status_code}")
            return False
        except Exception as e:
            self.log(f"Connection Error: {e}")
            return False

    def reset_form(self):
        try: self.session.post(f'{self.BASE_URL}/ssb/classSearch/resetDataForm')
        except: pass

    def fetch_dept(self, dept):
        try:
            self.reset_form()
            params = {'txt_subject': dept, 'txt_term': self.term_code, 'pageMaxSize': '500'}
            r = self.session.get(f'{self.BASE_URL}/ssb/searchResults/searchResults', params=params, timeout=8)
            if r.status_code != 200: return "EXPIRED"
            data = r.json()
            return (data.get('data') or []) if data.get('success') else []
        except: return "ERROR"

    def send_notification(self, message):
        try:
            requests.post(f"https://ntfy.sh/{self.ntfy_topic}", 
                          data=message.encode(encoding='utf-8'),
                          headers={"Title": "KFUPM Sniper Alert", "Priority": "high"},
                          timeout=5)
            self.log("Push notification sent!")
        except Exception as e:
            self.log(f"Push notification error: {e}")

# ================= GUI APP =================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("KFUPM Sniper")
        self.geometry("1100x750")
        self.resizable(False, False)
        
        # --- SET WINDOW ICON ---
        try:
            # Requires .ico file for Windows taskbar/titlebar
            icon_path = resource_path(ICON_FILENAME)
            if os.path.exists(icon_path):
                self.iconbitmap(icon_path)
        except Exception:
            pass # Fail silently if icon is missing or not Windows

        self.backend = KFUPMSniperBackend()
        self.backend.log_callback = self.log_msg_threadsafe
        
        self.crn_entries = []
        self.course_entries = []
        self.watch_list = []
        self.watch_courses = []
        self.table_rows = {}
        self.is_monitoring_phase = False
        
        self.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.setup_ui()
        self.restore_ui_state()

    def restore_ui_state(self):
        # Restore Term
        if self.backend.term_code:
            self.term_entry.insert(0, self.backend.term_code)
        
        # Restore CRNs
        if hasattr(self.backend, 'saved_watch_list'):
            # Clear default empty field if we have saved data
            if self.backend.saved_watch_list:
                for entry in list(self.crn_entries): self.remove_crn(entry[0], force=True)
                for crn in self.backend.saved_watch_list:
                    self.add_crn_field(crn)
        
        # Restore Courses
        if hasattr(self.backend, 'saved_watch_courses'):
            if self.backend.saved_watch_courses:
                for entry in list(self.course_entries): self.remove_course(entry[0], force=True)
                for course in self.backend.saved_watch_courses:
                    self.add_course_field(course)

        # Restore Table
        for crn, data in self.backend.dashboard_cache.items():
            self.update_table_row(crn, data)

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR ===
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(9, weight=1) # Adjusted for new items

        # Logo Text Only
        self.logo_label = ctk.CTkLabel(self.sidebar, text="KFUPM SNIPER", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        ctk.CTkLabel(self.sidebar, text="Term Code:").grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.term_entry = ctk.CTkEntry(self.sidebar, placeholder_text="e.g. 251 or 202510")
        self.term_entry.grid(row=2, column=0, padx=20, pady=(0, 20))
        self.term_entry.bind("<KeyRelease>", self.snapshot_and_save)
        
        # Buttons
        self.start_btn = ctk.CTkButton(self.sidebar, text="START MONITOR", fg_color="green", command=self.toggle_scan)
        self.start_btn.grid(row=3, column=0, padx=20, pady=10)
        
        self.link_btn = ctk.CTkButton(self.sidebar, text="GO TO REGISTER ↗", fg_color="gray", state="disabled", command=self.open_portal)
        self.link_btn.grid(row=4, column=0, padx=20, pady=10)

        # Alerts
        self.sound_var = ctk.BooleanVar(value=True)
        self.popup_var = ctk.BooleanVar(value=True)
        self.push_var = ctk.BooleanVar(value=False)

        ctk.CTkSwitch(self.sidebar, text="Sound Alerts", variable=self.sound_var).grid(row=5, column=0, padx=20, pady=10, sticky="w")
        ctk.CTkSwitch(self.sidebar, text="Popup Alerts", variable=self.popup_var).grid(row=6, column=0, padx=20, pady=10, sticky="w")
        
        ctk.CTkSwitch(self.sidebar, text="Push Notify", variable=self.push_var, command=self.toggle_push_ui).grid(row=7, column=0, padx=20, pady=10, sticky="w")
        
        self.qr_btn = ctk.CTkButton(self.sidebar, text="Show QR", width=100, fg_color="#8e44ad", command=self.show_qr)
        # Initially hidden
        self.qr_btn.grid(row=8, column=0, padx=20, pady=5, sticky="ew")
        self.qr_btn.grid_remove() # Hide initially

        # Mode
        self.mode_menu = ctk.CTkOptionMenu(self.sidebar, values=["Dark", "Light"], command=ctk.set_appearance_mode)
        self.mode_menu.grid(row=10, column=0, padx=20, pady=20, sticky="s")

        # === MAIN AREA ===
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(4, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # CRN Inputs
        crn_container = ctk.CTkFrame(self.main_frame)
        crn_container.grid(row=0, column=0, sticky="ew", pady=(0, 5))
        ctk.CTkLabel(crn_container, text="Target CRNs", font=("Arial", 14, "bold")).pack(pady=2, anchor="w", padx=10)
        self.crn_scroll = ctk.CTkScrollableFrame(crn_container, height=60, orientation="horizontal")
        self.crn_scroll.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(crn_container, text="+ Add CRN", width=100, height=24, command=self.add_crn_field).pack(pady=5)
        self.add_crn_field()

        # Course Inputs
        course_container = ctk.CTkFrame(self.main_frame)
        course_container.grid(row=1, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(course_container, text="Target Courses (e.g. ME432)", font=("Arial", 14, "bold")).pack(pady=2, anchor="w", padx=10)
        self.course_scroll = ctk.CTkScrollableFrame(course_container, height=60, orientation="horizontal")
        self.course_scroll.pack(fill="x", padx=10, pady=2)
        ctk.CTkButton(course_container, text="+ Add Course", width=100, height=24, command=self.add_course_field).pack(pady=5)
        self.add_course_field()

        # Status Bar
        status_frame = ctk.CTkFrame(self.main_frame, height=40, fg_color="transparent")
        status_frame.grid(row=2, column=0, sticky="ew", pady=(0, 5))
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Idle", font=("Consolas", 14))
        self.status_label.pack(side="left")
        self.last_scan_label = ctk.CTkLabel(status_frame, text="Last Scan: --:--:--", font=("Consolas", 14), text_color="gray")
        self.last_scan_label.pack(side="right")

        # Table Header
        header = ctk.CTkFrame(self.main_frame, height=30, fg_color="#34495e")
        header.grid(row=3, column=0, sticky="ew")
        cols = [("CRN", 10), ("COURSE", 15), ("SEC", 10), ("TITLE", 35), ("INSTRUCTOR", 30), ("SEATS", 10)]
        for i, (text, weight) in enumerate(cols):
            header.grid_columnconfigure(i, weight=weight)
            ctk.CTkLabel(header, text=text, font=("Arial", 12, "bold"), text_color="white").grid(row=0, column=i, sticky="w", pady=5, padx=5)

        # Table Body
        self.table_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.table_scroll.grid(row=4, column=0, sticky="nsew")
        for i, (_, weight) in enumerate(cols): self.table_scroll.grid_columnconfigure(i, weight=weight)

        # Logs
        self.log_box = ctk.CTkTextbox(self.main_frame, height=100, font=("Consolas", 11), state="disabled")
        self.log_box.grid(row=5, column=0, sticky="ew", pady=(15, 0))

    # --- UI HELPERS ---
    def add_crn_field(self, value=""):
        if self.backend.running:
            messagebox.showwarning("Monitor Running", "Stop the monitor before editing targets.")
            return
        f = ctk.CTkFrame(self.crn_scroll, fg_color="transparent")
        f.pack(side="left", padx=5)
        e = ctk.CTkEntry(f, width=80, placeholder_text="CRN", justify="center")
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

    def add_course_field(self, value=""):
        if self.backend.running:
            messagebox.showwarning("Monitor Running", "Stop the monitor before editing targets.")
            return
        f = ctk.CTkFrame(self.course_scroll, fg_color="transparent")
        f.pack(side="left", padx=5)
        e = ctk.CTkEntry(f, width=100, placeholder_text="Course Code", justify="center")
        if value: e.insert(0, value)
        e.pack(side="left")
        e.bind("<FocusOut>", self.snapshot_and_save)
        ctk.CTkButton(f, text="×", width=25, fg_color="#e74c3c", command=lambda: self.remove_course(f)).pack(side="left", padx=2)
        self.course_entries.append((f, e))
        self.snapshot_and_save()

    def remove_course(self, frame, force=False):
        if self.backend.running and not force:
            messagebox.showwarning("Monitor Running", "Stop the monitor before editing targets.")
            return
            
        # Identify the Course being removed
        course_to_remove = None
        for f, e in self.course_entries:
            if f == frame:
                course_to_remove = e.get().strip().upper().replace(" ", "")
                break

        frame.destroy()
        self.course_entries = [x for x in self.course_entries if x[0].winfo_exists()]
        
        if not force and course_to_remove:
            # Find all CRNs matching this course and remove them
            crns_to_delete = []
            for crn, data in self.backend.dashboard_cache.items():
                if data['code'] == course_to_remove:
                    crns_to_delete.append(crn)
            
            for crn in crns_to_delete:
                del self.backend.dashboard_cache[crn]
                if crn in self.table_rows:
                    for w in self.table_rows[crn].values(): w.destroy()
                    del self.table_rows[crn]
        
        self.snapshot_and_save()

    def clear_table(self):
        for crn in list(self.table_rows.keys()):
            for widget in self.table_rows[crn].values():
                widget.destroy()
            del self.table_rows[crn]
        self.backend.dashboard_cache = {}
        self.backend.target_depts = set()

    def open_portal(self):
        webbrowser.open(f"{self.backend.BASE_URL}/ssb/registration/registration")

    def toggle_push_ui(self):
        if self.push_var.get():
            self.qr_btn.grid()
            self.log_msg_threadsafe("Push notifications enabled. Scan QR to subscribe.")
        else:
            self.qr_btn.grid_remove()

    def show_qr(self):
        top = ctk.CTkToplevel(self)
        top.title("Scan for Notifications")
        top.geometry("300x350")
        top.attributes('-topmost', True)
        
        url = f"https://ntfy.sh/{self.backend.ntfy_topic}"
        qr = qrcode.make(url)
        img = ctk.CTkImage(light_image=qr.get_image(), size=(200, 200))
        
        ctk.CTkLabel(top, text="Scan to Subscribe", font=("Arial", 16, "bold")).pack(pady=10)
        ctk.CTkLabel(top, image=img, text="").pack(pady=10)
        ctk.CTkLabel(top, text=f"Topic: {self.backend.ntfy_topic}", text_color="gray").pack(pady=5)

    def update_table_row(self, crn, data):
        seat_color = "#2ecc71" if data['seats'] > 0 else "#e74c3c"
        if crn not in self.table_rows:
            r = len(self.table_rows)
            widgets = {
                'crn': ctk.CTkLabel(self.table_scroll, text=crn),
                'code': ctk.CTkLabel(self.table_scroll, text=data['code']),
                'sec': ctk.CTkLabel(self.table_scroll, text=data['sec']),
                'title': ctk.CTkLabel(self.table_scroll, text=data['title'][:30], anchor="w"),
                'instr': ctk.CTkLabel(self.table_scroll, text=data['instr'][:20], anchor="w"),
                'seats': ctk.CTkLabel(self.table_scroll, text=str(data['seats']), font=("Arial", 13, "bold"), text_color=seat_color)
            }
            for i, w in enumerate(widgets.values()): w.grid(row=r, column=i, sticky="w", pady=3, padx=5)
            self.table_rows[crn] = widgets
        else:
            self.table_rows[crn]['seats'].configure(text=str(data['seats']), text_color=seat_color)

    def log_msg_threadsafe(self, msg):
        self.after(0, lambda: self._log(msg))

    def snapshot_and_save(self, event=None):
        # Capture current UI state
        self.backend.watch_list_snapshot = [e.get().strip() for _, e in self.crn_entries if e.get().strip()]
        self.backend.watch_courses_snapshot = [e.get().strip().upper().replace(" ", "") for _, e in self.course_entries if e.get().strip()]
        self.backend.term_code = self.term_entry.get().strip()
        self.backend.save_data()

    def _log(self, msg):
        self.log_box.configure(state="normal")
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")
        self.log_box.configure(state="disabled")

    # --- MAIN LOGIC ---
    def toggle_scan(self):
        if not self.backend.running:
            self.watch_list = [e.get().strip() for _, e in self.crn_entries if e.get().strip()]
            self.watch_courses = [e.get().strip().upper().replace(" ", "") for _, e in self.course_entries if e.get().strip()]
            term = self.term_entry.get().strip()
            
            if not self.watch_list and not self.watch_courses:
                self._log("Enter at least one CRN or Course Code.")
                return
            if not term:
                self._log("Enter a Term Code (e.g. 202520).")
                return
            
            # Convert term code if short format
            term = self.backend.convert_term_code(term)
            
            # We do NOT clear table here anymore to preserve cache for smart discovery
            # self.clear_table() 
            
            self.backend.term_code = term
            
            # Snapshot for saving
            self.backend.watch_list_snapshot = self.watch_list
            self.backend.watch_courses_snapshot = self.watch_courses
            self.backend.save_data()

            self.backend.running = True
            self.start_btn.configure(text="STOP MONITOR", fg_color="#c0392b")
            self.term_entry.configure(state="disabled")
            threading.Thread(target=self.worker, daemon=True).start()
        else:
            self.backend.running = False
            self.start_btn.configure(text="Stopping...", state="disabled")

    def worker(self):
        if not self.backend.auth():
            self.log_msg_threadsafe("Fatal Auth Error.")
            self.after(0, self.stop_gracefully)
            return

        self.log_msg_threadsafe("Auto-Discovery started...")
        self.after(0, lambda: self.status_label.configure(text="Status: Discovery", text_color="#3498db"))

        # Smart Discovery Check
        skip_discovery = False
        if self.backend.target_depts:
            self.log_msg_threadsafe("Restoring from cache... (Smart Discovery)")
            skip_discovery = True

        if not skip_discovery:
            # Discovery Phase
            for dept in self.backend.all_subjects:
                if not self.backend.running: break
                res = self.backend.fetch_dept(dept)
                
                if res == "EXPIRED":
                    self.backend.auth()
                    continue
                if res == "ERROR": continue
                
                if not isinstance(res, list): continue
                
                for sec in res:
                    crn = sec.get('courseReferenceNumber')
                    code = f"{sec.get('subject')}{sec.get('courseNumber')}"
                    
                    if crn in self.watch_list or code in self.watch_courses:
                        self.backend.target_depts.add(dept)
                        self.update_cache_and_gui(crn, sec, dept)
                        self.log_msg_threadsafe(f"Found {crn} ({code})")

            if not self.backend.target_depts:
                self.log_msg_threadsafe("No CRNs/Courses found! Check inputs.")
                self.after(0, self.stop_gracefully)
                return

        self.is_monitoring_phase = True
        self.after(0, lambda: self.status_label.configure(text="Status: Monitoring", text_color="#2ecc71"))

        # Monitor Phase
        first_scan = True  # Don't alert on first scan (populating newly added courses)
        while self.backend.running:
            for dept in self.backend.target_depts:
                if not self.backend.running: break
                res = self.backend.fetch_dept(dept)
                if res == "EXPIRED":
                    self.log_msg_threadsafe("Session expired, renewing...")
                    self.backend.auth()
                    continue
                
                if isinstance(res, list):
                    for sec in res:
                        crn = sec.get('courseReferenceNumber')
                        code = f"{sec.get('subject')}{sec.get('courseNumber')}"
                        
                        if crn in self.watch_list or code in self.watch_courses:
                            # Pass first_scan flag to prevent alerts during initial population
                            self.update_cache_and_gui(crn, sec, dept, suppress_new_alerts=first_scan)
                time.sleep(0.5)
            
            first_scan = False  # After first complete scan, enable alerts
            self.after(0, lambda: self.last_scan_label.configure(text=f"Last Scan: {datetime.now().strftime('%H:%M:%S')}", text_color="#2ecc71"))
            time.sleep(10)

        self.after(0, self.stop_gracefully)

    def update_cache_and_gui(self, crn, sec, dept, suppress_new_alerts=False):
        new_seats = sec.get('seatsAvailable', 0)
        prev_seats = self.backend.dashboard_cache.get(crn, {}).get('seats', new_seats)
        
        instr = sec['faculty'][0]['displayName'] if sec.get('faculty') else "TBA"
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
        
        # Alert Logic
        # status_text = self.status_label.cget("text") # Not thread safe
        
        if is_new_section and self.is_monitoring_phase and not suppress_new_alerts:
            self.trigger_alert(f"NEW SECTION: {code}-{data['sec']}")
        elif new_seats > prev_seats and new_seats > 0:
            self.trigger_alert(f"OPEN: {code}-{data['sec']} ({new_seats} seats)")

    def trigger_alert(self, msg):
        self.log_msg_threadsafe(f"🚨 {msg}")
        self.after(0, lambda: self.link_btn.configure(state="normal", fg_color="#2ecc71"))
        
        if self.sound_var.get(): play_sound()
        if self.popup_var.get(): 
            flash_window(self)
            messagebox.showinfo("SEAT FOUND!", f"{msg}\n\nGo register immediately!")
        if self.push_var.get():
            threading.Thread(target=self.backend.send_notification, args=(msg,)).start()

    def stop_gracefully(self):
        self.backend.running = False
        self.is_monitoring_phase = False
        self.start_btn.configure(text="START MONITOR", fg_color="green", state="normal")
        self.status_label.configure(text="Status: Stopped", text_color="gray")
        self.term_entry.configure(state="normal")
        
        # Save state on stop
        self.backend.watch_list_snapshot = [e.get().strip() for _, e in self.crn_entries if e.get().strip()]
        self.backend.watch_courses_snapshot = [e.get().strip().upper().replace(" ", "") for _, e in self.course_entries if e.get().strip()]
        self.backend.term_code = self.term_entry.get().strip()
        self.backend.save_data()

    def on_closing(self):
        # Capture current UI state before saving
        self.backend.watch_list_snapshot = [e.get().strip() for _, e in self.crn_entries if e.get().strip()]
        self.backend.watch_courses_snapshot = [e.get().strip().upper().replace(" ", "") for _, e in self.course_entries if e.get().strip()]
        self.backend.term_code = self.term_entry.get().strip()
        
        self.backend.save_data()
        self.backend.running = False
        self.destroy()

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()

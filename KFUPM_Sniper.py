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
            winsound.Beep(1000, 1000)
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

# ================= BACKEND ENGINE =================
class KFUPMSniperBackend:
    BASE_URL = 'https://banner9-registration.kfupm.edu.sa/StudentRegistrationSsb'
    
    def __init__(self):
        self.session = None
        self.term_code = ""
        self.running = False
        self.log_callback = None
        
        self.all_subjects = ['ACCT', 'AS', 'AE', 'AECM', 'ARE', 'ARC', 'BIOE', 'BIOL', 'BUS', 'CHE', 'CHEM', 'CRP', 'CP', 'CE', 'CGS', 'CPG', 'COE', 'CSE', 'CEM', 'CIE', 'DSE', 'ECON', 'EE', 'EM', 'ENGL', 'ELD', 'ELI', 'ENVS', 'ESE', 'FIN', 'GEOL', 'GEOP', 'GS', 'HRM', 'ISE', 'ICS', 'ITD', 'IAS', 'LS', 'MGT', 'MIS', 'MKT', 'MBA', 'MSE', 'MATH', 'ME', 'MINE', 'NPM', 'OM', 'PETE', 'PE', 'PHYS', 'SIA', 'SSC', 'SWE', 'STAT', 'SE', 'SCE', 'URO']
        self.target_depts = set()
        self.dashboard_cache = {} 

    def log(self, msg):
        if self.log_callback: self.log_callback(msg)

    def auth(self):
        self.log("Authenticating...")
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
            return data.get('data', []) if data.get('success') else []
        except: return "ERROR"

# ================= GUI APP =================
ctk.set_appearance_mode("Dark")
ctk.set_default_color_theme("blue")

class SniperApp(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("KFUPM Sniper")
        self.geometry("1100x700")
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
        self.watch_list = []
        self.table_rows = {}
        
        self.setup_ui()

    def setup_ui(self):
        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # === SIDEBAR ===
        self.sidebar = ctk.CTkFrame(self, width=250, corner_radius=0)
        self.sidebar.grid(row=0, column=0, sticky="nsew")
        self.sidebar.grid_rowconfigure(8, weight=1)

        # Logo Text Only
        self.logo_label = ctk.CTkLabel(self.sidebar, text="KFUPM SNIPER", font=ctk.CTkFont(size=20, weight="bold"))
        self.logo_label.grid(row=0, column=0, padx=20, pady=(30, 20))
        
        ctk.CTkLabel(self.sidebar, text="Term Code:").grid(row=1, column=0, padx=20, pady=(10, 0), sticky="w")
        self.term_entry = ctk.CTkEntry(self.sidebar, placeholder_text="e.g. 202520")
        self.term_entry.grid(row=2, column=0, padx=20, pady=(0, 20))
        
        # Buttons
        self.start_btn = ctk.CTkButton(self.sidebar, text="START MONITOR", fg_color="green", command=self.toggle_scan)
        self.start_btn.grid(row=3, column=0, padx=20, pady=10)
        
        self.link_btn = ctk.CTkButton(self.sidebar, text="GO TO REGISTER ↗", fg_color="gray", state="disabled", command=self.open_portal)
        self.link_btn.grid(row=4, column=0, padx=20, pady=10)

        # Mode
        self.mode_menu = ctk.CTkOptionMenu(self.sidebar, values=["Dark", "Light"], command=ctk.set_appearance_mode)
        self.mode_menu.grid(row=9, column=0, padx=20, pady=20, sticky="s")

        # === MAIN AREA ===
        self.main_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.main_frame.grid(row=0, column=1, sticky="nsew", padx=20, pady=20)
        self.main_frame.grid_rowconfigure(3, weight=1)
        self.main_frame.grid_columnconfigure(0, weight=1)

        # CRN Inputs
        crn_container = ctk.CTkFrame(self.main_frame)
        crn_container.grid(row=0, column=0, sticky="ew", pady=(0, 10))
        ctk.CTkLabel(crn_container, text="Target CRNs", font=("Arial", 16, "bold")).pack(pady=5, anchor="w", padx=10)
        self.crn_scroll = ctk.CTkScrollableFrame(crn_container, height=70, orientation="horizontal")
        self.crn_scroll.pack(fill="x", padx=10, pady=5)
        ctk.CTkButton(crn_container, text="+ Add CRN", width=100, command=self.add_crn_field).pack(pady=5)
        
        # Start with one empty field
        self.add_crn_field()

        # Status Bar
        status_frame = ctk.CTkFrame(self.main_frame, height=40, fg_color="transparent")
        status_frame.grid(row=1, column=0, sticky="ew", pady=(0, 5))
        self.status_label = ctk.CTkLabel(status_frame, text="Status: Idle", font=("Consolas", 14))
        self.status_label.pack(side="left")
        self.last_scan_label = ctk.CTkLabel(status_frame, text="Last Scan: --:--:--", font=("Consolas", 14), text_color="gray")
        self.last_scan_label.pack(side="right")

        # Table Header
        header = ctk.CTkFrame(self.main_frame, height=30, fg_color="#34495e")
        header.grid(row=2, column=0, sticky="ew")
        cols = [("CRN", 10), ("COURSE", 15), ("SEC", 10), ("TITLE", 35), ("INSTRUCTOR", 30), ("SEATS", 10)]
        for i, (text, weight) in enumerate(cols):
            header.grid_columnconfigure(i, weight=weight)
            ctk.CTkLabel(header, text=text, font=("Arial", 12, "bold"), text_color="white").grid(row=0, column=i, sticky="w", pady=5, padx=5)

        # Table Body
        self.table_scroll = ctk.CTkScrollableFrame(self.main_frame, fg_color="transparent")
        self.table_scroll.grid(row=3, column=0, sticky="nsew")
        for i, (_, weight) in enumerate(cols): self.table_scroll.grid_columnconfigure(i, weight=weight)

        # Logs
        self.log_box = ctk.CTkTextbox(self.main_frame, height=120, font=("Consolas", 11))
        self.log_box.grid(row=4, column=0, sticky="ew", pady=(15, 0))

    # --- UI HELPERS ---
    def add_crn_field(self, value=""):
        f = ctk.CTkFrame(self.crn_scroll, fg_color="transparent")
        f.pack(side="left", padx=5)
        e = ctk.CTkEntry(f, width=80, placeholder_text="CRN", justify="center")
        if value: e.insert(0, value)
        e.pack(side="left")
        ctk.CTkButton(f, text="×", width=25, fg_color="#e74c3c", command=lambda: self.remove_crn(f)).pack(side="left", padx=2)
        self.crn_entries.append((f, e))

    def remove_crn(self, frame):
        frame.destroy()
        self.crn_entries = [x for x in self.crn_entries if x[0].winfo_exists()]

    def log_msg_threadsafe(self, msg): self.after(0, lambda: self._log(msg))
    def _log(self, msg):
        self.log_box.insert("end", f"[{datetime.now().strftime('%H:%M:%S')}] {msg}\n")
        self.log_box.see("end")

    def open_portal(self): 
        webbrowser.open("https://banner9-registration.kfupm.edu.sa/StudentRegistrationSsb/ssb/term/termSelection?mode=registration")

    def clear_table(self):
        for _, widgets in self.table_rows.items():
            for w in widgets.values(): w.destroy()
        self.table_rows = {}
        self.backend.dashboard_cache = {}
        self.backend.target_depts = set()

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

    # --- MAIN LOGIC ---
    def toggle_scan(self):
        if not self.backend.running:
            self.watch_list = [e.get().strip() for _, e in self.crn_entries if e.get().strip()]
            term = self.term_entry.get().strip()
            
            if not self.watch_list:
                self._log("Enter at least one CRN.")
                return
            if not term:
                self._log("Enter a Term Code (e.g. 202520).")
                return
            
            self.clear_table()
            self.backend.term_code = term
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

        # Discovery Phase
        for dept in self.backend.all_subjects:
            if not self.backend.running: break
            res = self.backend.fetch_dept(dept)
            
            if res == "EXPIRED":
                self.backend.auth()
                continue
            if res == "ERROR": continue
            
            for sec in res:
                crn = sec.get('courseReferenceNumber')
                if crn in self.watch_list:
                    self.backend.target_depts.add(dept)
                    self.update_cache_and_gui(crn, sec, dept)
                    self.log_msg_threadsafe(f"Found {crn} in {dept}")

        if not self.backend.target_depts:
            self.log_msg_threadsafe("No CRNs found! Check Term/CRNs.")
            self.after(0, self.stop_gracefully)
            return

        self.after(0, lambda: self.status_label.configure(text="Status: Monitoring", text_color="#2ecc71"))

        # Monitor Phase
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
                        if crn in self.watch_list:
                            self.update_cache_and_gui(crn, sec, dept)
                time.sleep(0.5)
            
            self.after(0, lambda: self.last_scan_label.configure(text=f"Last Scan: {datetime.now().strftime('%H:%M:%S')}", text_color="#2ecc71"))
            time.sleep(10)

        self.after(0, self.stop_gracefully)

    def update_cache_and_gui(self, crn, sec, dept):
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
        self.backend.dashboard_cache[crn] = data
        self.after(0, self.update_table_row, crn, data)
        
        if new_seats > prev_seats:
            self.trigger_alert(f"OPEN: {title} ({new_seats} seats)")

    def trigger_alert(self, msg):
        self.log_msg_threadsafe(f"🚨 {msg}")
        self.after(0, lambda: self.link_btn.configure(state="normal", fg_color="#2ecc71"))
        
        play_sound()
        flash_window(self)
        messagebox.showinfo("SEAT FOUND!", f"{msg}\n\nGo register immediately!")

    def stop_gracefully(self):
        self.backend.running = False
        self.start_btn.configure(text="START MONITOR", fg_color="green", state="normal")
        self.status_label.configure(text="Status: Stopped", text_color="gray")
        self.term_entry.configure(state="normal")

if __name__ == "__main__":
    app = SniperApp()
    app.mainloop()

<img width="160" height="160" alt="kfupm_sniper_icon" src="https://github.com/user-attachments/assets/ecab7613-095c-4fb7-a274-0e0ce5255ef5" />


# KFUPM Sniper

---
<h2 align="center">Downloads | التحميل</h2>

<div align="center">
  <a href="https://github.com/bibo242/KFUPM-Sniper/releases/latest" title="Download Latest Release (.exe)">
    <img src="https://img.shields.io/badge/DOWNLOAD%20LATEST%20RELEASE%20(.EXE)-brightgreen?style=for-the-badge&logo=windows&logoColor=white" alt="Download Latest Release (.exe)">
  </a>
  <p align="center"><small><em>(Note: Windows might show a "Windows protected your PC" security warning. Click "More info" and then "Run anyway".)</em></small></p>
  <p align="center"><small><em>This happens because the app isn't yet code-signed (a process that verifies the publisher).</em></small></p>
  <p align="center">⭐ <small>If you find this project helpful, please consider starring it on GitHub! Your support is appreciated. ⭐</small></p>
  <p align="center"><small> View all versions on the <a href="https://github.com/bibo242/KFUPM-Sniper/releases">Releases Page</a>.</small></p>
</div>

---
<br>

The **KFUPM Course Sniper** is a modern desktop application designed to monitor course availability on the KFUPM system in real-time. It saves you the pain of manually refreshing the registrar page thousands of times hoping for a seat to open.

This tool works by communicating directly with the Registrar's API in the background. When a seat opens in one of your target courses, the app instantly alerts you with sound, a popup, and a visual indicator, allowing you to register before anyone else.

**No Login Required for Monitoring:** It uses the public guest search features, so you don't need to risk your password or account security for basic monitoring.

<img width="1092" height="917" alt="image" src="https://github.com/user-attachments/assets/beb44c77-aad9-448c-817a-c6517e36d163" />




---

##  Features

- **Modern GUI:** A clean, user-friendly interface built with CustomTkinter.
- **Smart Auto-Discovery:** Simply input the CRN, and the tool automatically finds which department the course belongs to.
- **Course Section Targeting:** Monitor entire courses (e.g., "ME432") or specific sections (e.g., "ME401-01").
- **Gender Selection:** Filter course sections based on gender (Male/Female).
- **Real-Time Dashboard:** View live seat counts, instructor names, and course titles in a structured table.
- **⚡ Auto-Registration (New):** Automatically register for a course as soon as a seat becomes available.
  - **Conflict Handling:** Automatically drops conflicting courses if a seat is found (Mirror Swap logic).
  - **Browser Support:** Supports both Chrome and Firefox (Headless mode).
- **Instant Alerts:**
  - 🔊 **Sound:** Plays a system beep/alert sound (toggleable).
  - 🚨 **Visual:** The specific course row turns bright green.
  - 💻 **Popup:** A window pops up on top of other apps (toggleable).
  - 📱 **Push Notifications:** Get alerts on your phone via ntfy.sh. Scan the QR code or copy the link to subscribe.
  - ⚡ **Taskbar Flash:** The app icon flashes orange in the taskbar if minimized (Windows).
- **Direct Link:** A "Go To Register" button activates immediately when a seat is found, taking you directly to the add/drop page.
- **Dark/Light Mode:** Toggle between themes to suit your preference.
- **Standalone Application:** No need to install Python if you use the `.exe` file.

---

##  How to Use the Application (`.exe`)

This is the recommended method for most users. No installation is required!

1.  **Download the latest release.**
    - Go to the [**Releases Page**](https://github.com/bibo242/KFUPM-Sniper/releases).
    - Under the latest version, download the `KFUPM_Sniper.exe` file from the "Assets" section.

2.  **Run the application.**
    - Double-click the downloaded `.exe` file.
    - _(Note: Windows might show a security warning. Click "More info" -> "Run anyway".)_

3.  **Configure.**
    - **Term Code:** Enter the semester code (e.g., `251` for First Semester 2025, or `202510`).
    - **Add CRNs:** Type the CRN (Course Reference Number) of the closed section you want and click `+ Add CRN`.
    - **Add Courses:** Type the course code (e.g., `ME432`) or a specific section (e.g., `ME401-01`) and click `+ Add Course`.
    - **Gender:** Select "Male" or "Female" to filter sections.
    - **Notifications:** Enable "Phone Notifications" and scan the QR code or copy the link to your phone.
    - **Auto-Registration (Optional):**
      - Enter your KFUPM credentials in the "AUTO REGISTER SETTINGS" sidebar.
      - Select your preferred browser (Chrome/Firefox).
      - Check the "AUTO REG" box next to the CRN in the dashboard.

4.  **Start.**
    - Click **"START MONITOR"**.
    - The status bar will show "Auto-Discovery" while it locates your courses, then switch to "Monitoring".

5.  **Wait for the Alert.**
    - **IMPORTANT:** Leave the app running in the background. You can minimize it, but **do not close it**.
    - When a seat opens, the app will beep, flash, and show a popup. If Auto-Registration is enabled, it will attempt to register you automatically!

## How to Use the Application on MacOS 

1. Download the MacOS version from the releases page
2. Open **Terminal**.
3. Type `chmod +x ` (make sure there is a space) and **drag the file** into the terminal window. Press **Enter**.
4. Type `xattr -cr ` (make sure there is a space) and **drag the file** into the terminal window. Press **Enter**.
5. Now double-click the file to run it.




##  How to Run from Source (`.py` file)

This method is for developers or Mac/Linux users.

1.  **Clone the repository.**
    Open your terminal or Git Bash and run:
    ```bash
    git clone https://github.com/bibo242/KFUPM-Sniper.git
    ```

2.  **Navigate to the project folder.**
    ```bash
    cd KFUPM-Sniper
    ```

3.  **(Optional but Recommended) Create and activate a virtual environment.**
    ```bash
    # Create the environment
    python -m venv venv
    # Activate it (on Windows)
    .\venv\Scripts\activate
    # Activate it (on Linux/Mac)
    source venv/bin/activate
    ```

4.  **Install the required packages.**
    ```bash
    pip install customtkinter requests qrcode pillow selenium webdriver-manager
    ```

5.  **Run the script.**
    ```bash
    python KFUPM_Sniper.py
    ```

---

## How It Works

The application operates in three phases:

1.  **Discovery Phase:**
    - It authenticates with the Banner9 registration system using a guest session (no credentials required).
    - It scans all departments to find the specific CRNs or Courses you requested.
    - It builds a dashboard of the target sections.

2.  **Monitoring Phase:**
    - It continuously polls the specific departments containing your target courses.
    - It compares the current seat count with the previous count.
    - If `current_seats > previous_seats` AND `current_seats > 0`, it triggers an alert.
    - If a new section appears for a monitored course, it triggers a "New Section" alert.

3.  **Auto-Registration Phase (Optional):**
    - If a seat is found and "AUTO REG" is checked, the app launches a headless browser session.
    - It logs in using your provided credentials and attempts to add the CRN.
    - If a time conflict is detected, it uses "Mirror Swap" logic to drop the conflicting course and add the new one simultaneously.

---

## Contributing

Contributions are welcome!
1.  Fork the repository.
2.  Create a feature branch (`git checkout -b feature/AmazingFeature`).
3.  Commit your changes.
4.  Push to the branch.
5.  Open a Pull Request.

---

##  Disclaimer

This tool is provided for educational and personal use only. The **Auto-Registration** feature is experimental and should be used with caution. The user is solely responsible for complying with all terms of service of King Fahd University of Petroleum & Minerals (KFUPM). Use this tool responsibly; setting polling intervals to be extremely fast may result in your IP being temporarily blocked by the university firewall.

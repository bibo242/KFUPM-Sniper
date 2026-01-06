

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
  <p align="center"><small> View all versions on the <a href="https://github.com/yourusername/KFUPM-Course-Sniper/releases">Releases Page</a>.</small></p>
</div>

---
<br>

The **KFUPM Course Sniper** is a modern desktop application designed to monitor course availability on the KFUPM system in real-time. It saves you the pain of manually refreshing the registrar page thousands of times hoping for a seat to open.

This tool works by communicating directly with the Registrar's API in the background. When a seat opens in one of your target courses, the app instantly alerts you with sound, a popup, and a visual indicator, allowing you to register before anyone else.

**No Login Required:** It uses the public guest search features, so you don't need to risk your password or account security.

<img width="1090" height="713" alt="image" src="https://github.com/user-attachments/assets/4f85f83a-ac58-4456-8ac0-c9ca454402dc" />


---

##  Features

- **Modern GUI:** A clean, user-friendly interface built with CustomTkinter.
- **Smart Auto-Discovery:** Simply input the CRN, and the tool automatically finds which department the course belongs to.
- **Real-Time Dashboard:** View live seat counts, instructor names, and course titles in a structured table.
- **Instant Alerts:**
  - 🔊 **Sound:** Plays a system beep/alert sound.
  - 🚨 **Visual:** The specific course row turns bright green.
  - 💻 **Popup:** A window pops up on top of other apps.
  - ⚡ **Taskbar Flash:** The app icon flashes orange in the taskbar if minimized (Windows).
- **Direct Link:** A "Go To Register" button activates immediately when a seat is found, taking you directly to the add/drop page.
- **Dark/Light Mode:** Toggle between themes to suit your preference.
- **Standalone Application:** No need to install Python if you use the `.exe` file.

---

##  How to Use the Application (`.exe`)

This is the recommended method for most users. No installation is required!

1.  **Download the latest release.**
    - Go to the [**Releases Page**](https://github.com/yourusername/KFUPM-Course-Sniper/releases).
    - Under the latest version, download the `KFUPM_Sniper.exe` file from the "Assets" section.

2.  **Run the application.**
    - Double-click the downloaded `.exe` file.
    - _(Note: Windows might show a security warning. Click "More info" -> "Run anyway".)_

3.  **Configure.**
    - **Term Code:** Enter the current semester code (e.g., `202520` for Second Semester 2025).
    - **Add CRNs:** Type the CRN (Course Reference Number) of the closed section you want and click `+ Add CRN`. You can add as many as you like.

4.  **Start.**
    - Click **"START MONITOR"**.
    - The status bar will show "Auto-Discovery" while it locates your courses, then switch to "Monitoring".

5.  **Wait for the Alert.**
    - Leave the app running in the background.
    - When a seat opens, the app will beep, flash, and show a popup. Click the **"GO TO REGISTER"** button immediately to secure your spot!

### System Requirements
- An active internet connection.
- Windows 10 or 11 (for the `.exe` and taskbar flashing features).
- _(Mac/Linux users can run the source code directly)._

---

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
    ```

4.  **Install the required packages.**
    ```bash
    pip install customtkinter requests
    ```

5.  **Run the script.**
    ```bash
    python KFUPM_Sniper.py
    ```

---

##  Disclaimer

This tool is provided for educational and personal use only. It is a **monitoring tool**, not a bot that registers for you. The user is solely responsible for complying with all terms of service of King Fahd University of Petroleum & Minerals (KFUPM). Use this tool responsibly; setting polling intervals to be extremely fast may result in your IP being temporarily blocked by the university firewall.

Multi-Display Image Cycle
=========================

A desktop app for assigning fullscreen display content per monitor.

What It Does
------------
- Detects all monitors.
- Opens one fullscreen image window on each monitor.
- Keeps display output windows fullscreen during playback.
- Lists each display so you can assign either an image or a Power BI embed source.
- Lets you add individual files or a whole folder to the main image list for quick assignment.
- Supports leaving some displays unassigned (they remain blank).
- Requires a password before starting and for stopping while playback is active.

Requirements
------------
- Python 3.10+
- Windows/Linux/macOS

Setup
-----
1. Create and activate a virtual environment.
2. Install dependencies:
   - `pip install -r requirements.txt`

Run
---
- `python main.py`
- or `python pbdisplay/app.py`

Supported Image Formats
-----------------------
- `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp`, `.tif`, `.tiff`

Usage
-----
1. Click `Add Images` or `Add Folder`.
2. In `Display Image Assignment`, click a display row.
3. Assign content:
   - `Assign Image` picks a file directly.
   - `Assign Power BI` accepts either a `reportEmbed` URL or full iframe HTML.
   - `Use Selected Playlist Image` uses the selected item from the main playlist.
4. Assign content only to the displays you want to use. Unassigned displays stay blank.
5. Click `Set Password` and define the exit password.
6. Click `Start`.
7. During fullscreen playback, any mouse click or key press prompts for the password.
8. Enter the correct password to stop playback and return to the control window.

Power BI Login Behavior
-----------------------
- `Prompt Power BI sign-in (isolated browser session)` is enabled by default.
- When enabled, Power BI displays open in isolated/private browser sessions so existing logged-in browser accounts are not reused.
- This is useful when you want each user to authenticate with their own account that has report access.

Notes
-----
- On Windows, monitor detection works without extra system setup.
- `screeninfo` is included to improve cross-platform monitor detection.
- Power BI assignments launch in Edge/Chrome app windows positioned fullscreen on the assigned monitor.
- On stop, browser windows started for Power BI assignments are closed by the app.
- Private Power BI reports may still require a signed-in browser session unless you use a public embed model.

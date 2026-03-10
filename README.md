Multi-Display Image Cycle
=========================

A simple desktop app that cycles through local images across all connected displays.

What It Does
------------
- Detects all monitors.
- Opens one fullscreen image window on each monitor.
- Keeps display output windows fullscreen during playback.
- Lists each display so you can assign one image to each monitor.
- Lets you add individual files or a whole folder to the main image list for quick selection.

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

Supported Image Formats
-----------------------
- `.jpg`, `.jpeg`, `.png`, `.bmp`, `.gif`, `.webp`, `.tif`, `.tiff`

Usage
-----
1. Click `Add Images` or `Add Folder`.
2. In `Display Image Assignment`, click a display row.
3. Assign an image:
   - `Assign Image` picks a file directly.
   - `Use Selected Playlist Image` uses the selected item from the main playlist.
4. Assign images only to the displays you want to use. Unassigned displays stay blank.
5. Click `Set Password` and define the exit password.
6. Click `Start`.
7. During fullscreen playback, any mouse click or key press prompts for the password.
8. Enter the correct password to stop playback and return to the control window.

Notes
-----
- On Windows, monitor detection works without extra system setup.
- `screeninfo` is included to improve cross-platform monitor detection.

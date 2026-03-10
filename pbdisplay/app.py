from __future__ import annotations

import ctypes
import html
import os
import re
import shutil
import subprocess
from pathlib import Path
from tkinter import (
    BOTH,
    END,
    LEFT,
    RIGHT,
    TOP,
    X,
    Y,
    Listbox,
    StringVar,
    Tk,
    Toplevel,
    filedialog,
    messagebox,
    simpledialog,
)
from tkinter import ttk

from PIL import Image, ImageOps, ImageTk, UnidentifiedImageError

from .display_manager import Monitor, enumerate_monitors

APP_TITLE = "Multi-Display Image Cycle"
SUPPORTED_EXTENSIONS = {".jpg", ".jpeg", ".png", ".bmp", ".gif", ".webp", ".tif", ".tiff"}

IS_WINDOWS = os.name == "nt"

if IS_WINDOWS:
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    kernel32 = ctypes.windll.kernel32

    WH_KEYBOARD_LL = 13
    WH_MOUSE_LL = 14
    HC_ACTION = 0
    WM_KEYDOWN = 0x0100
    WM_SYSKEYDOWN = 0x0104
    WM_LBUTTONDOWN = 0x0201
    WM_RBUTTONDOWN = 0x0204
    WM_MBUTTONDOWN = 0x0207
    WM_XBUTTONDOWN = 0x020B

    KeyboardProcType = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
    MouseProcType = ctypes.WINFUNCTYPE(ctypes.c_long, ctypes.c_int, wintypes.WPARAM, wintypes.LPARAM)
else:
    wintypes = None
    user32 = None
    kernel32 = None


class ImageCycleApp(Tk):
    def __init__(self):
        super().__init__()
        self.title(APP_TITLE)
        self.geometry("900x620")
        self.minsize(820, 520)

        self.monitors: list[Monitor] = enumerate_monitors()
        self.image_paths: list[Path] = []
        self.display_assignments: dict[str, dict[str, str]] = {m.id: {"type": "none", "value": ""} for m in self.monitors}
        self.status_var = StringVar(value="Idle")
        self.password_state_var = StringVar(value="Password not set")

        self._windows: dict[str, Toplevel] = {}
        self._labels: dict[str, ttk.Label] = {}
        self._photo_refs: dict[str, ImageTk.PhotoImage] = {}
        self._cycle_job: str | None = None
        self._running = False
        self._browser_processes: dict[str, subprocess.Popen] = {}
        self._unlock_password: str | None = None
        self._auth_prompt_active = False
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_hook_proc = None
        self._mouse_hook_proc = None

        self._build_ui()
        self.protocol("WM_DELETE_WINDOW", self._on_close)

    def _build_ui(self):
        root = ttk.Frame(self, padding=14)
        root.pack(fill=BOTH, expand=True)

        top = ttk.Frame(root)
        top.pack(fill=X)

        ttk.Label(top, text="Image Playlist", font=("Segoe UI", 11, "bold")).pack(side=LEFT)
        ttk.Button(top, text="Add Images", command=self._add_images).pack(side=RIGHT, padx=(8, 0))
        ttk.Button(top, text="Add Folder", command=self._add_folder).pack(side=RIGHT)

        body = ttk.Frame(root)
        body.pack(fill=BOTH, expand=True, pady=(10, 0))

        self.listbox = Listbox(body, activestyle="none")
        self.listbox.pack(side=LEFT, fill=BOTH, expand=True)

        controls = ttk.Frame(body)
        controls.pack(side=RIGHT, fill=Y, padx=(12, 0))
        ttk.Button(controls, text="Remove Selected", command=self._remove_selected).pack(fill=X, pady=(0, 6))
        ttk.Button(controls, text="Clear All", command=self._clear_all).pack(fill=X)

        per_display = ttk.LabelFrame(root, text="Display Image Assignment", padding=10)
        per_display.pack(fill=BOTH, expand=True, pady=(12, 0))
        per_display.columnconfigure(0, weight=1)
        per_display.rowconfigure(0, weight=1)

        assignment_body = ttk.Frame(per_display)
        assignment_body.grid(row=0, column=0, sticky="nsew")
        assignment_body.columnconfigure(0, weight=1)
        assignment_body.rowconfigure(0, weight=1)

        self.display_tree = ttk.Treeview(
            assignment_body,
            columns=("display", "source_type", "source_value"),
            show="headings",
            height=8,
            selectmode="browse",
        )
        self.display_tree.heading("display", text="Display")
        self.display_tree.heading("source_type", text="Type")
        self.display_tree.heading("source_value", text="Assigned Source")
        self.display_tree.column("display", width=220, anchor="w")
        self.display_tree.column("source_type", width=90, anchor="w")
        self.display_tree.column("source_value", width=470, anchor="w")
        self.display_tree.grid(row=0, column=0, sticky="nsew")

        per_controls = ttk.Frame(assignment_body)
        per_controls.grid(row=0, column=1, sticky="ns", padx=(10, 0))
        ttk.Button(per_controls, text="Assign Image", command=self._assign_image_to_selected_display).pack(fill=X, pady=(0, 6))
        ttk.Button(per_controls, text="Assign Power BI", command=self._assign_powerbi_to_selected_display).pack(fill=X, pady=(0, 6))
        ttk.Button(per_controls, text="Use Selected Playlist Image", command=self._assign_selected_playlist_image).pack(fill=X, pady=(0, 6))
        ttk.Button(per_controls, text="Clear Assignment", command=self._clear_selected_assignment).pack(fill=X)

        options = ttk.LabelFrame(root, text="Playback", padding=10)
        options.pack(fill=X, pady=(12, 0))
        options.columnconfigure(0, weight=1)

        ttk.Button(options, text="Set Password", command=self._set_password).grid(row=0, column=0, sticky="w")
        ttk.Label(options, textvariable=self.password_state_var).grid(row=0, column=1, sticky="w", padx=(10, 0))

        monitor_text = self._monitor_summary()
        ttk.Label(options, text=monitor_text).grid(row=1, column=0, columnspan=2, sticky="w", pady=(8, 0))

        actions = ttk.Frame(root)
        actions.pack(fill=X, pady=(12, 0))
        ttk.Button(actions, text="Start", command=self.start).pack(side=RIGHT)
        ttk.Button(actions, text="Stop", command=self.stop_with_password).pack(side=RIGHT, padx=(0, 8))

        status = ttk.Label(root, textvariable=self.status_var, anchor="w")
        status.pack(fill=X, pady=(12, 0))

        self._refresh_display_tree()

    def _refresh_display_tree(self):
        for item_id in self.display_tree.get_children():
            self.display_tree.delete(item_id)
        for mon in self.monitors:
            assigned = self.display_assignments.get(mon.id, {"type": "none", "value": ""})
            source_type = assigned.get("type", "none")
            source_value = assigned.get("value", "") or "(not assigned)"
            display_text = f"{mon.id} ({mon.width}x{mon.height} @ {mon.x},{mon.y})"
            self.display_tree.insert("", END, iid=mon.id, values=(display_text, source_type, source_value))

    def _selected_tree_monitor_id(self) -> str | None:
        selected = self.display_tree.selection()
        if not selected:
            messagebox.showinfo("Select display", "Select a display row first.")
            return None
        mon_id = selected[0]
        if mon_id not in self.display_assignments:
            return None
        return mon_id

    def _assign_image_to_selected_display(self):
        mon_id = self._selected_tree_monitor_id()
        if not mon_id:
            return
        path = filedialog.askopenfilename(
            title=f"Select image for {mon_id}",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff")],
        )
        if not path:
            return
        resolved = Path(path).resolve()
        self.display_assignments[mon_id] = {"type": "image", "value": str(resolved)}
        self._refresh_display_tree()
        self.status_var.set(f"Assigned image to {mon_id}: {resolved.name}")

    def _assign_powerbi_to_selected_display(self):
        mon_id = self._selected_tree_monitor_id()
        if not mon_id:
            return
        raw = simpledialog.askstring(
            "Assign Power BI",
            "Paste Power BI report URL or iframe HTML:",
            parent=self,
        )
        if raw is None:
            return
        url = self._extract_powerbi_url(raw)
        if not url:
            messagebox.showwarning(
                "Invalid Power BI input",
                "Could not find a valid Power BI embed URL. Paste a reportEmbed URL or iframe HTML.",
            )
            return
        self.display_assignments[mon_id] = {"type": "powerbi", "value": url}
        self._refresh_display_tree()
        self.status_var.set(f"Assigned Power BI to {mon_id}.")

    def _extract_powerbi_url(self, raw_value: str) -> str | None:
        raw = raw_value.strip()
        if not raw:
            return None
        if "<iframe" in raw.lower():
            match = re.search(r"src\s*=\s*['\"]([^'\"]+)['\"]", raw, flags=re.IGNORECASE)
            if not match:
                return None
            raw = html.unescape(match.group(1).strip())
        if not raw.lower().startswith("http"):
            return None
        if "app.powerbi.com/" not in raw.lower():
            return None
        return raw

    def _assign_selected_playlist_image(self):
        mon_id = self._selected_tree_monitor_id()
        if not mon_id:
            return
        selected = list(self.listbox.curselection())
        if not selected:
            messagebox.showinfo("No selection", "Select one image in the main playlist first.")
            return
        idx = selected[0]
        if idx >= len(self.image_paths):
            return
        self.display_assignments[mon_id] = {"type": "image", "value": str(self.image_paths[idx])}
        self._refresh_display_tree()
        self.status_var.set(f"Assigned playlist image to {mon_id}: {self.image_paths[idx].name}")

    def _clear_selected_assignment(self):
        mon_id = self._selected_tree_monitor_id()
        if not mon_id:
            return
        self.display_assignments[mon_id] = {"type": "none", "value": ""}
        self._refresh_display_tree()
        self.status_var.set(f"Cleared assignment for {mon_id}.")

    def _monitor_summary(self) -> str:
        if not self.monitors:
            return "No monitors detected."
        parts = [f"{m.id}: {m.width}x{m.height} @ {m.x},{m.y}" for m in self.monitors]
        return "Detected monitors: " + " | ".join(parts)

    def _add_images(self):
        paths = filedialog.askopenfilenames(
            title="Select images",
            filetypes=[("Images", "*.jpg *.jpeg *.png *.bmp *.gif *.webp *.tif *.tiff")],
        )
        if not paths:
            return
        self._append_paths([Path(p) for p in paths])

    def _add_folder(self):
        folder = filedialog.askdirectory(title="Select folder with images")
        if not folder:
            return
        files = sorted(p for p in Path(folder).iterdir() if p.is_file() and p.suffix.lower() in SUPPORTED_EXTENSIONS)
        if not files:
            messagebox.showinfo("No images", "No supported image files were found in that folder.")
            return
        self._append_paths(files)

    def _append_paths(self, paths: list[Path]):
        added = 0
        existing = {p.resolve() for p in self.image_paths}
        for path in paths:
            try:
                resolved = path.resolve()
            except Exception:
                continue
            if resolved in existing:
                continue
            if resolved.suffix.lower() not in SUPPORTED_EXTENSIONS:
                continue
            self.image_paths.append(resolved)
            self.listbox.insert(END, str(resolved))
            existing.add(resolved)
            added += 1
        self.status_var.set(f"Loaded {len(self.image_paths)} images ({added} newly added).")

    def _remove_selected(self):
        selected = list(self.listbox.curselection())
        if not selected:
            return
        for idx in reversed(selected):
            del self.image_paths[idx]
            self.listbox.delete(idx)
        self.status_var.set(f"Loaded {len(self.image_paths)} images.")

    def _clear_all(self):
        self.image_paths.clear()
        self.listbox.delete(0, END)
        self.status_var.set("Playlist cleared.")

    def start(self):
        if self._running:
            messagebox.showinfo("Running", "Image cycle is already running.")
            return
        if not self._ensure_password_before_start():
            self.status_var.set("Start cancelled: password was not set.")
            return
        if not self.monitors:
            messagebox.showerror("No monitors", "No displays were detected.")
            return
        assigned_count = sum(
            1
            for mon in self.monitors
            if self.display_assignments.get(mon.id, {}).get("type") in {"image", "powerbi"}
        )
        if assigned_count == 0:
            messagebox.showwarning("No assignments", "Assign at least one image or Power BI source to start playback.")
            return
        self._open_display_windows()
        self._open_powerbi_windows()
        self._running = True
        self.status_var.set(
            f"Running on {len(self.monitors)} display(s): {assigned_count} assigned, {len(self.monitors) - assigned_count} blank."
        )
        self._show_assigned_images()

    def stop(self):
        self._running = False
        self._remove_global_input_hooks()
        self._stop_powerbi_windows()
        if self._cycle_job is not None:
            self.after_cancel(self._cycle_job)
            self._cycle_job = None
        for win in list(self._windows.values()):
            try:
                win.destroy()
            except Exception:
                pass
        self._windows.clear()
        self._labels.clear()
        self._photo_refs.clear()
        self.status_var.set("Stopped")

    def stop_with_password(self):
        if not self._running:
            self.stop()
            return
        if self._verify_password("Enter password to stop playback:"):
            self.stop()
            messagebox.showinfo("Unlocked", "Playback stopped.")

    def _open_display_windows(self):
        self.stop()
        self._running = True
        for mon in self.monitors:
            assignment = self.display_assignments.get(mon.id, {"type": "none", "value": ""})
            if assignment.get("type") == "powerbi":
                continue
            win = Toplevel(self)
            win.overrideredirect(True)
            win.attributes("-topmost", True)
            win.configure(background="black")
            win.geometry(f"{mon.width}x{mon.height}+{mon.x}+{mon.y}")
            lbl = ttk.Label(win, anchor="center")
            lbl.pack(fill=BOTH, expand=True)
            for seq in ("<ButtonPress>", "<KeyPress>"):
                win.bind(seq, self._on_protected_interaction)
                lbl.bind(seq, self._on_protected_interaction)
            self._windows[mon.id] = win
            self._labels[mon.id] = lbl
        if self._windows:
            try:
                next(iter(self._windows.values())).focus_force()
            except Exception:
                pass
        self._install_global_input_hooks()

    def _open_powerbi_windows(self):
        for mon in self.monitors:
            assignment = self.display_assignments.get(mon.id, {"type": "none", "value": ""})
            if assignment.get("type") != "powerbi":
                continue
            url = assignment.get("value", "").strip()
            if not url:
                continue
            proc = self._launch_browser_on_monitor(url, mon)
            if proc is not None:
                self._browser_processes[mon.id] = proc

    def _stop_powerbi_windows(self):
        for mon_id, proc in list(self._browser_processes.items()):
            try:
                if proc.poll() is None:
                    proc.terminate()
            except Exception:
                pass
            self._browser_processes.pop(mon_id, None)

    def _launch_browser_on_monitor(self, url: str, mon: Monitor) -> subprocess.Popen | None:
        browser = self._find_browser_executable()
        if not browser:
            self.status_var.set("No supported browser found (Edge/Chrome) for Power BI display.")
            return None
        args = [
            browser,
            "--new-window",
            f"--window-position={mon.x},{mon.y}",
            f"--window-size={max(1, mon.width)},{max(1, mon.height)}",
            "--start-fullscreen",
            f"--app={url}",
        ]
        creationflags = 0
        if os.name == "nt":
            creationflags = subprocess.CREATE_NEW_PROCESS_GROUP
        try:
            return subprocess.Popen(args, creationflags=creationflags)
        except Exception as exc:
            self.status_var.set(f"Failed to launch browser for {mon.id}: {exc}")
            return None

    def _find_browser_executable(self) -> str | None:
        candidates = [
            shutil.which("msedge"),
            shutil.which("chrome"),
            shutil.which("google-chrome"),
            r"C:\\Program Files (x86)\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files\\Microsoft\\Edge\\Application\\msedge.exe",
            r"C:\\Program Files\\Google\\Chrome\\Application\\chrome.exe",
            r"C:\\Program Files (x86)\\Google\\Chrome\\Application\\chrome.exe",
        ]
        for candidate in candidates:
            if candidate and os.path.exists(candidate):
                return candidate
        return None

    def _install_global_input_hooks(self):
        if not IS_WINDOWS:
            return
        if self._keyboard_hook or self._mouse_hook:
            return
        if user32 is None or kernel32 is None:
            return
        try:
            self._keyboard_hook_proc = KeyboardProcType(self._keyboard_hook_callback)
            self._mouse_hook_proc = MouseProcType(self._mouse_hook_callback)
            mod = kernel32.GetModuleHandleW(None)
            self._keyboard_hook = user32.SetWindowsHookExW(WH_KEYBOARD_LL, self._keyboard_hook_proc, mod, 0)
            self._mouse_hook = user32.SetWindowsHookExW(WH_MOUSE_LL, self._mouse_hook_proc, mod, 0)
        except Exception:
            self._remove_global_input_hooks()

    def _remove_global_input_hooks(self):
        if not IS_WINDOWS:
            return
        if user32 is None:
            return
        if self._keyboard_hook:
            try:
                user32.UnhookWindowsHookEx(self._keyboard_hook)
            except Exception:
                pass
        if self._mouse_hook:
            try:
                user32.UnhookWindowsHookEx(self._mouse_hook)
            except Exception:
                pass
        self._keyboard_hook = None
        self._mouse_hook = None
        self._keyboard_hook_proc = None
        self._mouse_hook_proc = None

    def _trigger_protected_prompt(self):
        if not self._running or self._auth_prompt_active:
            return
        self._auth_prompt_active = True
        self.after(0, self._prompt_password_and_maybe_stop)

    def _keyboard_hook_callback(self, nCode, wParam, lParam):
        if user32 is None:
            return 0
        if nCode == HC_ACTION and self._running and wParam in (WM_KEYDOWN, WM_SYSKEYDOWN):
            self._trigger_protected_prompt()
        if self._keyboard_hook:
            return user32.CallNextHookEx(self._keyboard_hook, nCode, wParam, lParam)
        return user32.CallNextHookEx(0, nCode, wParam, lParam)

    def _mouse_hook_callback(self, nCode, wParam, lParam):
        if user32 is None:
            return 0
        if nCode == HC_ACTION and self._running and wParam in (
            WM_LBUTTONDOWN,
            WM_RBUTTONDOWN,
            WM_MBUTTONDOWN,
            WM_XBUTTONDOWN,
        ):
            self._trigger_protected_prompt()
        if self._mouse_hook:
            return user32.CallNextHookEx(self._mouse_hook, nCode, wParam, lParam)
        return user32.CallNextHookEx(0, nCode, wParam, lParam)

    def _set_password(self) -> bool:
        if self._running:
            messagebox.showinfo("Password", "Stop playback before changing the password.")
            return False
        new_password = simpledialog.askstring(
            "Set Password",
            "Set the password required to exit fullscreen playback:",
            show="*",
            parent=self,
        )
        if new_password is None:
            return False
        new_password = new_password.strip()
        if not new_password:
            messagebox.showwarning("Set Password", "Password cannot be empty.")
            return False
        confirm = simpledialog.askstring(
            "Confirm Password",
            "Re-enter the password:",
            show="*",
            parent=self,
        )
        if confirm is None:
            return False
        if confirm.strip() != new_password:
            messagebox.showwarning("Set Password", "Passwords did not match.")
            return False
        self._unlock_password = new_password
        self.password_state_var.set("Password set")
        self.status_var.set("Exit password configured.")
        return True

    def _ensure_password_before_start(self) -> bool:
        if self._unlock_password:
            return True
        messagebox.showinfo("Password Required", "Set an exit password before starting playback.")
        return self._set_password()

    def _on_protected_interaction(self, _event=None):
        if not self._running:
            return None
        if self._auth_prompt_active:
            return "break"
        self._auth_prompt_active = True
        self.after(0, self._prompt_password_and_maybe_stop)
        return "break"

    def _prompt_password_and_maybe_stop(self):
        windows = list(self._windows.values())
        for win in windows:
            try:
                win.attributes("-topmost", False)
            except Exception:
                pass
        try:
            self.deiconify()
            self.lift()
            self.focus_force()
        except Exception:
            pass

        try:
            if self._verify_password("Mouse/keyboard input detected. Enter password to stop playback:"):
                self.stop()
                messagebox.showinfo("Unlocked", "Playback stopped.")
                return
            self.status_var.set("Playback remains locked.")
        finally:
            if self._running:
                for win in windows:
                    try:
                        win.attributes("-topmost", True)
                    except Exception:
                        pass
                if windows:
                    try:
                        windows[0].focus_force()
                    except Exception:
                        pass
            self._auth_prompt_active = False

    def _verify_password(self, prompt: str) -> bool:
        if not self._unlock_password:
            messagebox.showerror("Password Missing", "No password is set for this session.")
            return False
        entered = simpledialog.askstring("Password Required", prompt, show="*", parent=self)
        if entered is None:
            self.status_var.set("Password prompt cancelled.")
            return False
        if entered == self._unlock_password:
            return True
        messagebox.showerror("Incorrect Password", "Playback remains locked.")
        return False

    def _show_assigned_images(self):
        if not self._running:
            return

        shown: list[str] = []
        blank = 0
        for mon in self.monitors:
            assignment = self.display_assignments.get(mon.id, {"type": "none", "value": ""})
            if assignment.get("type") == "powerbi":
                shown.append(f"{mon.id}: Power BI")
                continue
            if assignment.get("type") != "image":
                label = self._labels.get(mon.id)
                if label is not None:
                    label.configure(image="", text="")
                self._photo_refs.pop(mon.id, None)
                blank += 1
                continue
            path = Path(assignment.get("value", ""))
            try:
                photo = self._render_for_monitor(path, mon)
            except (FileNotFoundError, UnidentifiedImageError, OSError) as exc:
                self.status_var.set(f"Failed to load image for {mon.id}: {path.name} ({exc})")
                continue
            label = self._labels.get(mon.id)
            if label is None:
                continue
            label.configure(image=photo, text="")
            self._photo_refs[mon.id] = photo
            shown.append(f"{mon.id}: {path.name}")

        if shown:
            status = "Assigned images active: " + " | ".join(shown[:3]) + (" | ..." if len(shown) > 3 else "")
            if blank:
                status += f" | blank displays: {blank}"
            self.status_var.set(status)

    def _render_for_monitor(self, path: Path, mon: Monitor) -> ImageTk.PhotoImage:
        with Image.open(path) as source:
            # Fit image inside each monitor while preserving aspect ratio.
            fitted = ImageOps.contain(source.convert("RGB"), (max(1, mon.width), max(1, mon.height)))
            canvas = Image.new("RGB", (max(1, mon.width), max(1, mon.height)), color="black")
            x = (canvas.width - fitted.width) // 2
            y = (canvas.height - fitted.height) // 2
            canvas.paste(fitted, (x, y))
            return ImageTk.PhotoImage(canvas)

    def _on_close(self):
        if self._running:
            if not self._verify_password("Enter password to exit the application:"):
                return
        self.stop()
        self.destroy()


def main():
    app = ImageCycleApp()
    app.mainloop()


if __name__ == "__main__":
    main()

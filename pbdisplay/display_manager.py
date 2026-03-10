from __future__ import annotations

import sys
from dataclasses import dataclass
from typing import List

try:
    from screeninfo import get_monitors
except Exception:  # pragma: no cover - allow import to fail gracefully if not installed yet
    get_monitors = None

# Monitor dataclass to represent a display monitor's properties
@dataclass
class Monitor:
    id: str
    x: int
    y: int
    width: int
    height: int
    name: str

# Platform-specific implementation to enumerate monitors on Windows using ctypes
def _enumerate_monitors_windows() -> List[Monitor]:  # pragma: no cover - platform specific
    import ctypes
    from ctypes import wintypes

    user32 = ctypes.windll.user32

    class RECT(ctypes.Structure):
        _fields_ = [
            ("left", ctypes.c_long),
            ("top", ctypes.c_long),
            ("right", ctypes.c_long),
            ("bottom", ctypes.c_long),
        ]
# Extended monitor info structure to include device name
    class MONITORINFOEXW(ctypes.Structure):
        _fields_ = [
            ("cbSize", ctypes.c_ulong),
            ("rcMonitor", RECT),
            ("rcWork", RECT),
            ("dwFlags", ctypes.c_ulong),
            ("szDevice", ctypes.c_wchar * 32),
        ]

    monitors: List[Monitor] = []

    MonitorEnumProc = ctypes.WINFUNCTYPE(
        ctypes.c_int,  # bool
        wintypes.HMONITOR,
        wintypes.HDC,
        ctypes.POINTER(RECT),
        wintypes.LPARAM,
    )
# Callback function for EnumDisplayMonitors to collect monitor information
    def _cb(hMonitor, hdc, lprcMonitor, lParam):  # noqa: N802 - Windows callback naming
        mi = MONITORINFOEXW()
        mi.cbSize = ctypes.sizeof(MONITORINFOEXW)
        user32.GetMonitorInfoW(hMonitor, ctypes.byref(mi))
        x, y = mi.rcMonitor.left, mi.rcMonitor.top
        w, h = mi.rcMonitor.right - mi.rcMonitor.left, mi.rcMonitor.bottom - mi.rcMonitor.top
        name = mi.szDevice
        monitors.append(Monitor(id="", x=x, y=y, width=w, height=h, name=name))
        return 1

    user32.EnumDisplayMonitors(0, 0, MonitorEnumProc(_cb), 0)

    out: List[Monitor] = []
    for idx, monitor in enumerate(monitors):
        mid = f"Monitor-{idx}"
        out.append(Monitor(id=mid, x=monitor.x, y=monitor.y, width=monitor.width, height=monitor.height, name=monitor.name or mid))
    return out

# Main function to enumerate monitors, using screeninfo if available, otherwise falling back to platform-specific methods
def enumerate_monitors() -> List[Monitor]:
    if get_monitors is not None:
        mons = []
        for idx, m in enumerate(get_monitors()):
            mid = f"Monitor-{idx}"
            name = getattr(m, "name", None) or mid
            mons.append(Monitor(id=mid, x=m.x, y=m.y, width=m.width, height=m.height, name=name))
        return mons

    # Fallback for Windows if screeninfo is not installed
    if sys.platform.startswith("win"):
        return _enumerate_monitors_windows()

    raise RuntimeError(
        "screeninfo is not installed and no platform fallback is available. "
        "Install dependencies with `pip install -r requirements.txt`."
    )

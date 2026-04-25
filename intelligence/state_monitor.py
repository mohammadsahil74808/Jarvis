import os
import time
import psutil
import socket
from datetime import datetime
from pathlib import Path

try:
    import pygetwindow as gw
except ImportError:
    gw = None

try:
    # Windows specific for idle time and active window
    import ctypes
    from ctypes import wintypes
except ImportError:
    ctypes = None

class StateMonitor:
    def __init__(self):
        self.coding_tools = ["code.exe", "pycharm", "sublime_text", "visual studio", "vscode"]
        self.browser_names = ["msedge.exe", "chrome.exe", "firefox.exe", "brave.exe"]
        self._last_input_time = time.time()

    def get_system_state(self):
        """Returns a snapshot of the current system state."""
        state = {
            "cpu_percent": psutil.cpu_percent(interval=None),
            "ram_percent": psutil.virtual_memory().percent,
            "battery": self._get_battery_status(),
            "internet": self._check_internet(),
            "disk_free_gb": self._get_disk_free(),
            "idle_seconds": self._get_idle_time(),
            "timestamp": datetime.now()
        }
        return state

    def get_context_state(self):
        """Returns information about currently open apps and context."""
        active_app = self._get_active_window_title()
        open_processes = [p.name().lower() for p in psutil.process_iter(['name'])]
        
        is_coding = any(tool.lower() in [p for p in open_processes] for tool in self.coding_tools)
        
        state = {
            "active_app": active_app,
            "is_coding_mode": is_coding,
            "browser_open": any(b in open_processes for b in self.browser_names),
            "time_of_day": datetime.now().strftime("%H:%M"),
            "hour": datetime.now().hour,
            "open_apps_count": len(set(open_processes))
        }
        return state

    def _get_battery_status(self):
        battery = psutil.sensors_battery()
        if battery:
            return {
                "percent": battery.percent,
                "power_plugged": battery.power_plugged,
                "secsleft": battery.secsleft
            }
        return None

    def _check_internet(self):
        try:
            # Connect to a reliable host
            socket.create_connection(("8.8.8.8", 53), timeout=2)
            return True
        except OSError:
            return False

    def _get_disk_free(self):
        usage = psutil.disk_usage('/')
        return usage.free / (1024**3) # GB

    def _get_idle_time(self):
        if ctypes and os.name == 'nt':
            class LASTINPUTINFO(ctypes.Structure):
                _fields_ = [("cbSize", wintypes.UINT), ("dwTime", wintypes.DWORD)]

            lii = LASTINPUTINFO()
            lii.cbSize = ctypes.sizeof(lii)
            if ctypes.windll.user32.GetLastInputInfo(ctypes.byref(lii)):
                millis = ctypes.windll.kernel32.GetTickCount() - lii.dwTime
                return millis / 1000.0
        return 0

    def _get_active_window_title(self):
        if gw:
            try:
                active = gw.getActiveWindow()
                if active:
                    return active.title
            except Exception:
                pass
        return "Unknown"

# Example Usage
if __name__ == "__main__":
    monitor = StateMonitor()
    print("System State:", monitor.get_system_state())
    print("Context State:", monitor.get_context_state())

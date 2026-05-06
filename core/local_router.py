import re
import time
import subprocess
import webbrowser
import urllib.parse
from datetime import datetime
from ctypes import cast, POINTER
from comtypes import CLSCTX_ALL
from pycaw.pycaw import AudioUtilities, IAudioEndpointVolume

class LocalRouter:
    def __init__(self, jarvis_instance=None):
        self.jarvis = jarvis_instance
        self.routes = [
            (r"^(open )?(chrome|browser)$", self.open_chrome),
            (r"^open edge$", self.open_edge),
            (r"^open notepad$", self.open_notepad),
            (r"^(open )?calc(ulator)?$", self.open_calculator),
            (r"^open file explorer$", self.open_explorer),
            (r"^open cmd$", self.open_cmd),
            
            (r"^(shutdown|turn off) pc$", self.shutdown_pc),
            (r"^restart pc$", self.restart_pc),
            (r"^(sleep pc|sleep)$", self.sleep_pc),
            (r"^(lock|lock pc)$", self.lock_pc),
            
            (r"^(open |show )?(desktop|downloads|documents)$", self.open_folder),
            (r"^organize desktop$", self.organize_desktop),
            
            (r"^(what time is it|time|what is the time)$", self.get_time),
            (r"^(what is todays date|date|what is the date)$", self.get_date),
            (r"^volume up$", self.volume_up),
            (r"^volume down$", self.volume_down),
            (r"^mute$", self.mute_sys),
            (r"^unmute$", self.unmute_sys),
            (r"^set volume to (\d+)$", self.set_volume),
            
            (r"^open youtube$", self.open_youtube),
            (r"^open google$", self.open_google),
            (r"^search google for (.+)$", self.search_google),
            (r"^search youtube for (.+)$", self.search_youtube),

            (r"^(play |open )?spotify$", self.open_spotify),
            (r"^open vs\s?code$", self.open_vscode),
            (r"^what('?s| is) my (ip|ip address)$", self.get_ip),
            (r"^(show |open )?task manager$", self.open_taskmanager),
            (r"^(empty|clear) recycle bin$", self.empty_recycle),
            (r"^screenshot$", self.take_screenshot_fast),
            (r"^(wifi|wi-fi) (on|off)$", self.toggle_wifi),
            (r"^(close yourself|shut down jarvis|exit jarvis)$", self.close_jarvis),
        ]

    def route(self, command: str) -> bool:
        start_time = time.time()
        cmd_lower = command.lower().strip()
        cmd_alphanumeric = re.sub(r'[^\w\s]', '', cmd_lower)

        for pattern, handler in self.routes:
            match = re.search(pattern, cmd_alphanumeric)
            if match:
                try:
                    res = handler(*match.groups())
                    exc_time = time.time() - start_time
                    log_msg = f"SYS: ⚡ Fast local execution ({exc_time:.4f}s): {res}"
                    print(f"[LocalRouter] {log_msg}")
                    if self.jarvis:
                        if hasattr(self.jarvis, "ui"):
                            self.jarvis.ui.write_log(log_msg)
                        if hasattr(self.jarvis, "speak"):
                            cmd = f"[System Directive: State this exact confirmation phrase natively and quickly to the user without adding 'okay' or 'sure': '{res}']"
                            self.jarvis.speak(cmd)
                    return True
                except Exception as e:
                    print(f"[LocalRouter] Handler error: {e}")
                    return False
        return False

    def _sanitize(self, text: str) -> str:
        """Removes dangerous shell characters to prevent injection."""
        return re.sub(r'[;&|`$><!]', '', text).strip()

    def _safe_start(self, target: str):
        """Safely starts a target (file/app/url) using subprocess."""
        subprocess.Popen(["cmd", "/c", "start", "", target], shell=False)

    def open_chrome(self, *args):
        self._safe_start("chrome")
        return "Opened Chrome"

    def open_edge(self, *args):
        self._safe_start("msedge")
        return "Opened Edge"

    def open_notepad(self, *args):
        self._safe_start("notepad")
        return "Opened Notepad"

    def open_calculator(self, *args):
        self._safe_start("calc")
        return "Opened Calculator"

    def open_explorer(self, *args):
        self._safe_start("explorer")
        return "Opened File Explorer"

    def open_cmd(self, *args):
        self._safe_start("cmd")
        return "Opened Command Prompt"

    def shutdown_pc(self, *args):
        subprocess.Popen(["shutdown", "/s", "/t", "1"], shell=False)
        return "Shutting down PC"

    def restart_pc(self, *args):
        subprocess.Popen(["shutdown", "/r", "/t", "1"], shell=False)
        return "Restarting PC"

    def sleep_pc(self, *args):
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
        return "Sleeping PC"

    def lock_pc(self, *args):
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
        return "Locking PC"

    def open_folder(self, _, folder_name):
        from pathlib import Path
        folder_name = self._sanitize(folder_name.lower())
        paths = {
            "desktop": str(Path.home() / "Desktop"),
            "downloads": str(Path.home() / "Downloads"),
            "documents": str(Path.home() / "Documents")
        }
        target = paths.get(folder_name, str(Path.home()))
        self._safe_start(target)
        return f"Opened {folder_name}"

    def organize_desktop(self, *args):
        from actions.file_manager import organize_desktop
        res = organize_desktop()
        return res

    def get_time(self, *args):
        now = datetime.now().strftime("%I:%M %p")
        return f"Sir, abhi time {now} ho raha hai."

    def get_date(self, *args):
        today = datetime.now().strftime("%A, %B %d, %Y")
        return f"Today is {today}"

    # Simple PowerShell media keys wrapper
    def volume_up(self, *args):
        subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]175)"], creationflags=subprocess.CREATE_NO_WINDOW)
        return "Volume Increased"

    def volume_down(self, *args):
        subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]174)"], creationflags=subprocess.CREATE_NO_WINDOW)
        return "Volume Decreased"

    def mute_sys(self, *args):
        subprocess.run(["powershell", "-c", "(new-object -com wscript.shell).SendKeys([char]173)"], creationflags=subprocess.CREATE_NO_WINDOW)
        return "System Mute Toggled"

    def set_volume(self, *args):
        try:
            target = float(args[0]) / 100.0 if args else 1.0
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMasterVolumeLevelScalar(target, None)
            return f"Volume set to {int(target * 100)}%"
        except Exception as e:
            return f"Could not set volume: {e}"

    def unmute_sys(self, *args):
        try:
            devices = AudioUtilities.GetSpeakers()
            interface = devices.Activate(IAudioEndpointVolume._iid_, CLSCTX_ALL, None)
            volume = cast(interface, POINTER(IAudioEndpointVolume))
            volume.SetMute(0, None)
            return "System Unmuted"
        except Exception as e:
            return f"Could not unmute: {e}"

    def open_youtube(self, *args):
        webbrowser.open("https://www.youtube.com")
        return "Opened YouTube"

    def open_google(self, *args):
        webbrowser.open("https://www.google.com")
        return "Opened Google"

    def search_google(self, *args):
        query = self._sanitize(args[0]) if args else ""
        encoded_query = urllib.parse.quote(query)
        webbrowser.open(f"https://www.google.com/search?q={encoded_query}")
        return f"Google par {query} search kar diya hai, sir."

    def search_youtube(self, *args):
        query = self._sanitize(args[0]) if args else ""
        encoded_query = urllib.parse.quote(query)
        webbrowser.open(f"https://www.youtube.com/results?search_query={encoded_query}")
        return f"YouTube par {query} open kar diya hai, sir."

    def open_spotify(self, *args):
        self._safe_start("spotify:")
        return "Spotify open kar diya hai."

    def open_vscode(self, *args):
        self._safe_start("code")
        return "VS Code open ho raha hai, sir."

    def get_ip(self, *args):
        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return f"Sir, aapka local IP address {local_ip} hai."
        except Exception:
            return "Sir, IP address nahi mil pa raha hai."

    def open_taskmanager(self, *args):
        subprocess.Popen(["taskmgr"], shell=False)
        return "Task Manager open kar diya hai."

    def empty_recycle(self, *args):
        subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Confirm:$false"], 
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return "Recycle Bin khali kar diya hai, sir."

    def take_screenshot_fast(self, *args):
        try:
            import pyautogui
            from datetime import datetime
            path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            pyautogui.screenshot().save(path)
            return f"Screenshot capture ho gaya hai: {path}"
        except Exception as e:
            return f"Screenshot failed: {e}"

    def toggle_wifi(self, *args):
        # _, state
        state = args[1].lower() if len(args) > 1 else ""
        status = "ENABLED" if state == "on" else "DISABLED"
        try:
            # Note: This might require admin privileges on some systems
            subprocess.run(["netsh", "interface", "set", "interface", "name=Wi-Fi", f"admin={status}"], 
                           creationflags=subprocess.CREATE_NO_WINDOW)
            return f"Wi-Fi {state} kar diya hai, sir."
        except Exception as e:
            return f"Wi-Fi toggle failed: {e}"

    def close_jarvis(self, *args):
        if self.jarvis and hasattr(self.jarvis, "ui"):
            self.jarvis.ui.write_log("SYS: Shutting down JARVIS. Goodbye, sir.")
            # Trigger UI destruction in main thread
            self.jarvis.ui.root.after(1000, self.jarvis.ui.root.destroy)
        return "Goodbye, sir. Shutting down."

_global_router = None
def route_command(command: str, jarvis_instance=None) -> bool:
    global _global_router
    if not _global_router:
        _global_router = LocalRouter(jarvis_instance)
    _global_router.jarvis = jarvis_instance
    return _global_router.route(command)

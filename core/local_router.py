import re
import time
import subprocess
from datetime import datetime


class LocalRouter:
    def __init__(self, jarvis_instance=None):
        self.jarvis = jarvis_instance
        # ── LOCAL-ONLY ROUTES ─────────────────────────────────────
        # These commands execute instantly via regex and do NOT invoke the LLM.
        # We only keep routes here that have NO overlapping Gemini tool (e.g. open_app, web_search),
        # ensuring consistent UX between typed and voice commands.
        self.routes = [
            (r"^(sleep pc|sleep)$", self.sleep_pc),
            (r"^(lock|lock pc)$", self.lock_pc),
            
            (r"^(what time is it|time|what is the time)$", self.get_time),
            (r"^(what is todays date|date|what is the date)$", self.get_date),
            
            (r"^what('?s| is) my (ip|ip address)$", self.get_ip),
            (r"^(empty|clear) recycle bin$", self.empty_recycle),
            (r"^screenshot$", self.take_screenshot_fast),
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



    def sleep_pc(self, *args):
        subprocess.Popen(["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"], shell=False)
        return "Sleeping PC"

    def lock_pc(self, *args):
        subprocess.Popen(["rundll32.exe", "user32.dll,LockWorkStation"], shell=False)
        return "Locking PC"



    def get_time(self, *args):
        now = datetime.now().strftime("%I:%M %p")
        return f"Sir, abhi time {now} ho raha hai."

    def get_date(self, *args):
        today = datetime.now().strftime("%A, %B %d, %Y")
        return f"Today is {today}"



    def get_ip(self, *args):
        import socket
        try:
            hostname = socket.gethostname()
            local_ip = socket.gethostbyname(hostname)
            return f"Sir, aapka local IP address {local_ip} hai."
        except Exception:
            return "Sir, IP address nahi mil pa raha hai."



    def empty_recycle(self, *args):
        subprocess.run(["powershell", "-Command", "Clear-RecycleBin -Confirm:$false"], 
                       creationflags=subprocess.CREATE_NO_WINDOW)
        return "Recycle Bin khali kar diya hai, sir."

    def take_screenshot_fast(self, *args):
        try:
            import pyautogui # type: ignore
            from datetime import datetime
            path = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
            pyautogui.screenshot().save(path)
            return f"Screenshot capture ho gaya hai: {path}"
        except Exception as e:
            return f"Screenshot failed: {e}"



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

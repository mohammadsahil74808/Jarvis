# core/app_watcher.py  ← REPLACE
import psutil, time, threading

WATCHED_APPS = {
    "chrome.exe","msedge.exe","firefox.exe","brave.exe",
    "code.exe","pycharm64.exe","WindowsTerminal.exe","cmd.exe","powershell.exe",
    "spotify.exe","vlc.exe","discord.exe","slack.exe","teams.exe","zoom.exe",
    "notepad.exe","notepad++.exe","WINWORD.EXE","EXCEL.EXE","POWERPNT.EXE",
    "steam.exe","explorer.exe","taskmgr.exe",
}

class AppWatcher:
    def __init__(self, callback=None, interval: int = 15):
        self.callback  = callback
        self.interval  = interval
        self.running   = True
        self.last_apps : set = set()
        self.thread    = threading.Thread(
            target=self._watch_loop, daemon=True, name="AppWatcher")

    def start(self):
        self.last_apps = self._get_watched_apps()
        self.thread.start()

    def stop(self):
        self.running = False

    def _get_watched_apps(self) -> set:
        running = set()
        try:
            for p in psutil.process_iter(["name"]):
                try:
                    n = p.info["name"]
                    if n and n in WATCHED_APPS:
                        running.add(n)
                except (psutil.NoSuchProcess, psutil.AccessDenied):
                    continue
        except Exception:
            pass
        return running

    def _watch_loop(self):
        while self.running:
            try:
                current = self._get_watched_apps()
                opened  = list(current - self.last_apps)
                closed  = list(self.last_apps - current)
                if (opened or closed) and self.callback:
                    self.callback(opened, closed)
                self.last_apps = current
            except Exception:
                pass
            time.sleep(self.interval)

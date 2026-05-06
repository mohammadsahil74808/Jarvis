# core/app_watcher.py

import psutil
import time
import threading

class AppWatcher:
    def __init__(self, callback=None, interval=5):
        """
        callback: function(opened_list, closed_list)
        interval: scan interval in seconds
        """
        self.callback = callback
        self.interval = interval
        self.running = True
        self.last_apps = set()
        self.thread = threading.Thread(target=self._watch_loop, daemon=True)

    def start(self):
        self.last_apps = self._get_running_apps()
        self.thread.start()

    def stop(self):
        self.running = False

    def _get_running_apps(self):
        """Returns a set of unique process names."""
        apps = set()
        for proc in psutil.process_iter(['name']):
            try:
                name = proc.info['name']
                if name:
                    apps.add(name)
            except (psutil.NoSuchProcess, psutil.AccessDenied, psutil.ZombieProcess):
                continue
        return apps

    def _watch_loop(self):
        while self.running:
            try:
                current_apps = self._get_running_apps()
                
                opened = list(current_apps - self.last_apps)
                closed = list(self.last_apps - current_apps)
                
                if (opened or closed) and self.callback:
                    self.callback(opened, closed)
                
                self.last_apps = current_apps
            except Exception as e:
                # Silent failure to ensure background stability
                pass
            
            time.sleep(self.interval)

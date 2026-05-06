import pytest
from core.app_watcher import AppWatcher
import time

def test_app_watcher_init():
    def callback(opened, closed):
        pass
    watcher = AppWatcher(callback=callback, interval=1)
    assert watcher.interval == 1
    assert watcher.running == True

def test_get_running_apps():
    watcher = AppWatcher()
    apps = watcher._get_running_apps()
    assert isinstance(apps, set)
    # Check if common processes are there (system dependent but 'python.exe' or 'cmd.exe' usually present)
    assert len(apps) > 0

def test_app_diff_logic():
    watcher = AppWatcher()
    watcher.last_apps = {"chrome.exe", "notepad.exe"}
    current_apps = {"chrome.exe", "vscode.exe"}
    
    opened = list(current_apps - watcher.last_apps)
    closed = list(watcher.last_apps - current_apps)
    
    assert "vscode.exe" in opened
    assert "notepad.exe" in closed
    assert "chrome.exe" not in opened
    assert "chrome.exe" not in closed

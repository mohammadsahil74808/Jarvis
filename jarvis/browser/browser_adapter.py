# jarvis/browser/browser_adapter.py

from .browser_controller import BrowserController

_adapter = None

def get_browser_adapter():
    global _adapter
    if _adapter is None:
        _adapter = BrowserController()
    return _adapter
# jarvis/browser/browser_adapter.py
"""
Facade adapter bridging J.A.R.V.I.S. tool executor with Browser Use engine.
Provides a clean, thread-safe, non-invasive API for Firefox browser automation
behind an abstraction layer so upstream Browser Use can be updated independently.
"""

from __future__ import annotations

import threading
from typing import Any, Dict, Optional

from .browser_controller import BrowserController
from .browser_manager import BrowserManager


class BrowserUseAdapter:
    """
    Facade API exposing Browser Use capabilities to J.A.R.V.I.S.
    Maintains zero code modifications to upstream Browser Use.
    """

    _instance: BrowserUseAdapter | None = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self.manager = BrowserManager.get_instance()
        self.controller = BrowserController(self.manager)

    @classmethod
    def get_instance(cls) -> BrowserUseAdapter:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def open_website(self, url: str) -> str:
        return self.controller.open_website(url)

    def search_web(self, query: str) -> str:
        return self.controller.search_web(query)

    def click_element(self, target: str) -> str:
        return self.controller.click_element(target)

    def type_text(self, target: str, text: str) -> str:
        return self.controller.type_text(target, text)

    def fill_form(self, fields: Dict[str, str]) -> str:
        return self.controller.fill_form(fields)

    def extract_data(self, query: str = "main text content") -> str:
        return self.controller.extract_data(query)

    def download_file(self, url: str) -> str:
        return self.controller.download_file(url)

    def navigate(self, action: str = "reload") -> str:
        return self.controller.navigate(action)

    def capture_page(self) -> bytes:
        return self.controller.capture_page()

    def perform_task(self, task_description: str) -> str:
        return self.controller.perform_task(task_description)

    def scroll(self, direction: str = "down", amount: int = 500) -> str:
        return self.controller.scroll(direction, amount)

    def list_tabs(self) -> str:
        return self.controller.list_tabs()

    def switch_tab(self, index: int) -> str:
        return self.controller.switch_tab(index)

    def close_tab(self, index: int = -1) -> str:
        return self.controller.close_tab(index)

    def execute_js(self, script: str) -> str:
        return self.controller.execute_js(script)

    def go_back(self) -> str:
        return self.controller.go_back()

    def go_forward(self) -> str:
        return self.controller.go_forward()

    def get_status(self) -> Dict[str, Any]:
        return {
            "browser_engine": "Firefox Persistent",
            "detected_profile": str(self.manager._detected_profile_path or "Not Initialized"),
            "persistent_context_active": self.manager._persistent_context is not None,
            "active_url": self.controller.state.active_url,
            "active_title": self.controller.state.active_title,
            "tab_count": len(self.controller.state.open_tabs),
            "action_count": len(self.controller.state.action_history),
        }

    def shutdown(self) -> None:
        self.manager.close()


def get_browser_adapter() -> BrowserUseAdapter:
    """Factory helper to obtain singleton BrowserUseAdapter instance."""
    return BrowserUseAdapter.get_instance()

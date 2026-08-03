# jarvis/browser/browser_state.py
"""
Real-time state and history tracker for Browser Use integration in J.A.R.V.I.S.
Tracks active URL, page title, open tabs, action history, and download paths.
"""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from core.config import get_base_dir


@dataclass
class TabInfo:
    tab_id: str
    url: str
    title: str
    is_active: bool = True
    last_accessed: float = field(default_factory=time.time)


@dataclass
class BrowserState:
    """Encapsulates the current operational state of the Google Chrome browser."""

    active_url: str = ""
    active_title: str = ""
    open_tabs: List[TabInfo] = field(default_factory=list)
    action_history: List[Dict[str, Any]] = field(default_factory=list)
    download_history: List[Dict[str, Any]] = field(default_factory=list)
    last_screenshot_bytes: Optional[bytes] = None
    last_search_query: str = ""
    search_results: List[Dict[str, Any]] = field(default_factory=list)
    search_context: Dict[str, Any] = field(default_factory=dict)
    last_updated: float = field(default_factory=time.time)

    def update_active_tab(self, url: str, title: str) -> None:
        """Updates the active tab URL and title."""
        self.active_url = url
        self.active_title = title
        self.last_updated = time.time()

        # Update or append in open_tabs
        found = False
        for tab in self.open_tabs:
            if tab.url == url or tab.is_active:
                tab.url = url
                tab.title = title
                tab.is_active = True
                tab.last_accessed = time.time()
                found = True
            else:
                tab.is_active = False

        if not found:
            self.open_tabs.append(TabInfo(tab_id=str(len(self.open_tabs) + 1), url=url, title=title, is_active=True))

    def log_action(self, action: str, details: Dict[str, Any], result: str) -> None:
        """Logs an action to memory history."""
        self.action_history.append({
            "timestamp": time.time(),
            "action": action,
            "details": details,
            "result": str(result)[:500],
        })

    def save_persistent_state(self) -> None:
        """Saves session memory state to memory/browser_sessions/browser_memory.json."""
        try:
            mem_dir = get_base_dir() / "memory" / "browser_sessions"
            mem_dir.mkdir(parents=True, exist_ok=True)
            data = {
                "active_url": self.active_url,
                "active_title": self.active_title,
                "action_count": len(self.action_history),
                "last_actions": self.action_history[-10:],
                "last_search_query": self.last_search_query,
                "search_results": self.search_results,
                "search_context": self.search_context,
                "last_updated": self.last_updated,
            }
            with open(mem_dir / "browser_memory.json", "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2)
        except Exception:
            pass

    def load_persistent_state(self) -> None:
        """Loads session memory state from disk so search context survives across separate calls."""
        try:
            mem_file = get_base_dir() / "memory" / "browser_sessions" / "browser_memory.json"
            if mem_file.exists():
                data = json.loads(mem_file.read_text(encoding="utf-8"))
                self.active_url = data.get("active_url", self.active_url)
                self.active_title = data.get("active_title", self.active_title)
                self.last_search_query = data.get("last_search_query", self.last_search_query)
                self.search_results = data.get("search_results", self.search_results)
                self.search_context = data.get("search_context", self.search_context)
                if not self.search_context and self.search_results:
                    self.search_context = {
                        "query": self.last_search_query,
                        "timestamp": data.get("last_updated", time.time()),
                        "results": self.search_results
                    }
        except Exception as e:
            print(f"[BROWSER_STATE WARNING] Could not read disk memory: {e}")

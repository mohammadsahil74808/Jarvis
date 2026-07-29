# tests/test_browser_use_integration.py
"""Automated unit test suite for Upstream Browser Use integration into JARVIS."""

import pytest
from jarvis.browser.browser_state import BrowserState
from jarvis.browser.browser_context import BrowserContextManager
from jarvis.browser.browser_manager import BrowserManager
from jarvis.browser.browser_adapter import get_browser_adapter


def test_browser_state_tracking():
    state = BrowserState()
    assert state.active_url == ""

    state.update_active_tab("https://example.com", "Example Domain")
    assert state.active_url == "https://example.com"
    assert state.active_title == "Example Domain"

    state.log_action("open_website", {"url": "https://example.com"}, "OK")
    assert len(state.action_history) == 1
    assert state.action_history[0]["action"] == "open_website"


def test_browser_context_paths():
    ctx_mgr = BrowserContextManager()
    assert ctx_mgr.base_dir.exists()
    assert ctx_mgr.downloads_dir.exists()


def test_browser_manager_singleton():
    mgr1 = BrowserManager.get_instance()
    mgr2 = BrowserManager.get_instance()
    assert mgr1 is mgr2


def test_browser_use_module_loading():
    mgr = BrowserManager.get_instance()
    browser_mod, session_mod, controller_mod, agent_service = mgr.get_browser_use_modules()
    assert browser_mod is not None
    assert session_mod is not None
    assert controller_mod is not None
    assert agent_service is not None


def test_adapter_instance():
    adapter = get_browser_adapter()
    from jarvis.browser.browser_controller import BrowserController
    assert isinstance(adapter, BrowserController)
    status = adapter.get_status()
    assert isinstance(status, dict)
    assert "browser_engine" in status

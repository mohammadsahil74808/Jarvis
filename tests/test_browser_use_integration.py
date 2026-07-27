# tests/test_browser_use_integration.py
"""Automated unit test suite for Upstream Browser Use integration into JARVIS."""

import unittest
from jarvis.browser.browser_state import BrowserState, TabInfo
from jarvis.browser.browser_context import BrowserContextManager
from jarvis.browser.browser_manager import BrowserManager
from jarvis.browser.browser_adapter import BrowserUseAdapter, get_browser_adapter


class TestBrowserUseStateAndContext(unittest.TestCase):
    def test_browser_state_tracking(self):
        state = BrowserState()
        self.assertEqual(state.active_url, "")

        state.update_active_tab("https://example.com", "Example Domain")
        self.assertEqual(state.active_url, "https://example.com")
        self.assertEqual(state.active_title, "Example Domain")

        state.log_action("open_website", {"url": "https://example.com"}, "OK")
        self.assertEqual(len(state.action_history), 1)
        self.assertEqual(state.action_history[0]["action"], "open_website")

    def test_browser_context_paths(self):
        ctx_mgr = BrowserContextManager()
        self.assertTrue(ctx_mgr.base_dir.exists())
        self.assertTrue(ctx_mgr.downloads_dir.exists())


class TestBrowserManagerLifecycle(unittest.TestCase):
    def test_browser_manager_singleton(self):
        mgr1 = BrowserManager.get_instance()
        mgr2 = BrowserManager.get_instance()
        self.assertIs(mgr1, mgr2)

    def test_browser_use_module_loading(self):
        mgr = BrowserManager.get_instance()
        browser_mod, session_mod, controller_mod, agent_service = mgr.get_browser_use_modules()
        self.assertIsNotNone(browser_mod)
        self.assertIsNotNone(session_mod)
        self.assertIsNotNone(controller_mod)
        self.assertIsNotNone(agent_service)


class TestBrowserAdapterFacade(unittest.TestCase):
    def test_adapter_instance(self):
        adapter = get_browser_adapter()
        self.assertIsInstance(adapter, BrowserUseAdapter)
        status = adapter.get_status()
        self.assertEqual(status["browser_engine"], "Firefox")
        self.assertIn("active_url", status)


if __name__ == "__main__":
    unittest.main()

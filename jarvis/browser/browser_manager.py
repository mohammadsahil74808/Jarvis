# jarvis/browser/browser_manager.py
"""
Lifecycle and event loop manager for Firefox Playwright automation in J.A.R.V.I.S.

Runs an isolated background asyncio event loop to execute asynchronous Playwright
and Browser Use actions cleanly from synchronous JARVIS tool executor threads.
Enforces real Firefox persistent profile usage, profile lock detection, context reuse,
and step-by-step debug logging.
"""

from __future__ import annotations

import asyncio
import sys
import threading
import traceback
from pathlib import Path
from typing import Any, Coroutine, TypeVar

from core.config import get_base_dir
from playwright.async_api import async_playwright

from .browser_context import BrowserContextManager

# Ensure jarvis/browser is in sys.path so browser_use package resolves cleanly
_JARVIS_ROOT = get_base_dir()
_BROWSER_DIR = str(_JARVIS_ROOT / "jarvis" / "browser")
if _BROWSER_DIR not in sys.path:
    sys.path.insert(0, _BROWSER_DIR)

# Automatically sync JARVIS config API keys to os.environ for Browser Use
# Removed global os.environ mutation as per Phase 4 Security Audit
# API Keys should be passed locally via kwargs to the LLM constructor where needed.

T = TypeVar("T")


class PersistentBrowserContextWrapper:
    """
    Wrapper around Playwright's BrowserContext providing helper methods
    like get_current_page() while delegating all standard BrowserContext
    calls directly to the underlying Playwright instance.
    """

    def __init__(self, context: Any, manager: BrowserManager) -> None:
        self._context = context
        self._manager = manager

    async def get_current_page(self) -> Any:
        return await self._manager.get_current_page()

    def __getattr__(self, name: str) -> Any:
        return getattr(self._context, name)


class BrowserManager:
    """
    Singleton manager for the isolated background asyncio loop and Playwright Browser instance.
    Guarantees thread-safe coroutine execution, real Firefox persistent profile reuse,
    and locked profile detection without temporary fallbacks.
    """

    _instance: BrowserManager | None = None
    _lock = threading.RLock()

    def __init__(self) -> None:
        self._loop: asyncio.AbstractEventLoop | None = None
        self._thread: threading.Thread | None = None
        self._playwright_instance: Any = None
        self._persistent_context: Any = None
        self._context_wrapper: PersistentBrowserContextWrapper | None = None
        self._active_page: Any = None
        self._detected_profile_path: Path | None = None
        self._context_mgr = BrowserContextManager()
        self._is_running = False

    @classmethod
    def get_instance(cls) -> BrowserManager:
        with cls._lock:
            if cls._instance is None:
                cls._instance = cls()
                cls._instance._start_event_loop()
            return cls._instance

    def _start_event_loop(self) -> None:
        if self._is_running and self._loop and self._loop.is_running():
            return

        def _loop_worker(loop: asyncio.AbstractEventLoop):
            asyncio.set_event_loop(loop)
            loop.run_forever()

        self._loop = asyncio.new_event_loop()
        self._thread = threading.Thread(
            target=_loop_worker,
            args=(self._loop,),
            name="JarvisBrowserLoop",
            daemon=True,
        )
        self._thread.start()
        self._is_running = True
        print("[BROWSER_MANAGER] Background JarvisBrowserLoop started.")

    def run_async(self, coro: Coroutine[Any, Any, T], timeout: float = 120.0) -> T:
        """Submits a coroutine to the background asyncio event loop and waits for completion."""
        try:
            current_loop = asyncio.get_running_loop()
        except RuntimeError:
            current_loop = None

        if current_loop is self._loop:
            raise RuntimeError(
                "Cannot call run_async synchronously from inside the JarvisBrowserLoop event loop! "
                "Use await or async helper methods instead."
            )

        with self._lock:
            if not self._is_running or not self._loop:
                self._start_event_loop()

        assert self._loop is not None
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    async def async_get_or_create_browser(self, headful: bool = True) -> tuple[Any, Any]:
        """
        Async coroutine to get or initialize singleton Firefox persistent context.
        Can be safely called and awaited directly from inside coroutines running on JarvisBrowserLoop.
        """
        if self._persistent_context is not None:
            print(f"[BROWSER_MANAGER] Reusing existing persistent Firefox context (Profile: {self._detected_profile_path}).")
            return self, self._context_wrapper

        # STEP 1: Detect profile
        print("[STEP 1] Detecting profile...")
        try:
            profile_path, profile_name = self._context_mgr.detect_firefox_profile()
            print(f"[STEP 1 DONE] Target real profile: {profile_path} (Name: '{profile_name}')")
        except Exception as e:
            print(f"[STEP 1 ERROR] Profile detection failed: {e}")
            traceback.print_exc()
            raise

        self._detected_profile_path = profile_path

        # Lock check
        is_locked, lock_reason = self._context_mgr.is_profile_locked(profile_path)
        if is_locked:
            warning_msg = (
                f"\n========================================================================\n"
                f"[FIREFOX PROFILE LOCKED WARNING]\n"
                f"Your real Firefox profile is currently locked by an active Firefox process!\n"
                f"Profile Path: {profile_path}\n"
                f"Reason: {lock_reason}\n\n"
                f"ACTION REQUIRED: Please close all open Firefox windows so JARVIS can attach\n"
                f"to your real profile with your saved logins, cookies, and extensions.\n"
                f"========================================================================\n"
            )
            print(warning_msg)
            raise RuntimeError(warning_msg)

        # STEP 2: Launch Playwright driver
        print("[STEP 2] Launching Playwright driver...")
        try:
            if self._playwright_instance is None:
                self._playwright_instance = await async_playwright().start()
            print("[STEP 2 DONE] Playwright driver ready.")
        except Exception as e:
            print(f"[STEP 2 ERROR] Playwright driver launch failed: {e}")
            traceback.print_exc()
            raise

        # STEP 3: Launch persistent context
        print(f"[STEP 3] Launching persistent Firefox browser context at '{profile_path}'...")
        downloads_dir = self._context_mgr.get_downloads_path()
        try:
            context = await self._playwright_instance.firefox.launch_persistent_context(
                user_data_dir=str(profile_path),
                headless=not headful,
                accept_downloads=True,
                downloads_path=downloads_dir,
            )
            print("[STEP 3 DONE] Persistent Firefox browser context launched successfully.")
        except Exception as e:
            err_str = str(e)
            print(f"[STEP 3 ERROR] launch_persistent_context failed: {err_str}")
            traceback.print_exc()
            if "locked" in err_str.lower() or "busy" in err_str.lower() or "process" in err_str.lower():
                warning_msg = (
                    f"\n[FIREFOX PROFILE LOCKED WARNING] Failed to open profile at '{profile_path}'.\n"
                    f"Playwright error: {err_str}\n"
                    f"Please ensure Firefox is completely closed and try again."
                )
                print(warning_msg)
                raise RuntimeError(warning_msg) from e
            raise

        # STEP 4: Wrap context
        print("[STEP 4] Creating context wrapper...")
        try:
            self._persistent_context = context
            self._context_wrapper = PersistentBrowserContextWrapper(context, self)
            print("[STEP 4 DONE] Persistent context wrapper created.")
        except Exception as e:
            print(f"[STEP 4 ERROR] Context wrapping failed: {e}")
            traceback.print_exc()
            raise

        # STEP 5: First page creation
        print("[STEP 5] Accessing/creating primary active page...")
        try:
            if context.pages:
                self._active_page = context.pages[0]
            else:
                self._active_page = await context.new_page()
            print(f"[STEP 5 DONE] Active primary page acquired: {self._active_page}")
        except Exception as e:
            print(f"[STEP 5 ERROR] Primary page creation failed: {e}")
            traceback.print_exc()
            raise

        print(f"[BROWSER_MANAGER] Persistent Firefox context initialized successfully with profile: {profile_path}")
        return self, self._context_wrapper

    def get_or_create_browser(self, headful: bool = True) -> tuple[Any, Any]:
        """
        Gets or initializes singleton Firefox persistent context using real user profile.
        Safely detects whether called from inside or outside the event loop.
        """
        with self._lock:
            if self._persistent_context is not None:
                print(f"[BROWSER_MANAGER] Reusing existing persistent Firefox context (Profile: {self._detected_profile_path}).")
                return self, self._context_wrapper

            try:
                current_loop = asyncio.get_running_loop()
            except RuntimeError:
                current_loop = None

            if current_loop is self._loop:
                raise RuntimeError(
                    "get_or_create_browser() cannot be called synchronously from inside JarvisBrowserLoop! "
                    "Use await self.manager.async_get_or_create_browser() instead."
                )

            return self.run_async(self.async_get_or_create_browser(headful=headful))

    async def get_current_page(self) -> Any:
        """Returns active Playwright Page, creating one if no pages exist."""
        if self._active_page and not self._active_page.is_closed():
            return self._active_page

        if self._persistent_context:
            if self._persistent_context.pages:
                self._active_page = self._persistent_context.pages[0]
                return self._active_page
            else:
                self._active_page = await self._persistent_context.new_page()
                return self._active_page

        raise RuntimeError("BrowserContext has not been initialized.")

    def close(self) -> None:
        """Closes the persistent context and Playwright instance cleanly."""
        with self._lock:
            if self._persistent_context:

                async def _close():
                    try:
                        if self._persistent_context:
                            await self._persistent_context.close()
                        if self._playwright_instance:
                            await self._playwright_instance.stop()
                    except Exception as e:
                        print(f"[BROWSER_MANAGER WARNING] Error closing browser context: {e}")

                try:
                    self.run_async(_close(), timeout=10.0)
                except Exception:
                    pass

                self._persistent_context = None
                self._context_wrapper = None
                self._active_page = None
                self._playwright_instance = None
                print("[BROWSER_MANAGER] Persistent Firefox context closed.")

            if self._loop and self._loop.is_running():
                self._loop.call_soon_threadsafe(self._loop.stop)
                self._is_running = False

    def get_browser_use_modules(self) -> tuple[Any, Any, Any, Any]:
        """Loads and returns browser_use modules dynamically."""
        import importlib
        agent_service = importlib.import_module("browser_use.agent.service")
        browser_mod = importlib.import_module("browser_use.browser.session")
        session_mod = importlib.import_module("browser_use.browser.session")
        controller_mod = importlib.import_module("browser_use.tools.service")
        return browser_mod, session_mod, controller_mod, agent_service

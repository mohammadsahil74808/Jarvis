# jarvis/browser/browser_controller.py
"""
High-level controller bridging JARVIS tool actions with Playwright and Upstream Browser Use primitives.
Supports Google Chrome automation using persistent real user profile and DevTools attachment, VisionService screen awareness fusion, and state tracking.
Includes step-by-step debug logging and deadlock protection.
"""

from __future__ import annotations

import traceback
from pathlib import Path
from typing import Dict

from bs4 import BeautifulSoup
from core.config import get_api_key, get_groq_api_key

from .browser_context import BrowserContextManager
from .browser_manager import BrowserManager
from .browser_state import BrowserState


class BrowserController:
    """High-level action executor for Playwright pages and autonomous Agent tasks."""

    def __init__(self, manager: BrowserManager | None = None) -> None:
        self.manager = manager or BrowserManager.get_instance()
        self.context_mgr = BrowserContextManager()
        self.state = BrowserState()

    def shutdown(self) -> None:
        """Closes the browser manager."""
        if self.manager:
            self.manager.close()
            
    def get_status(self) -> dict:
        """Returns the current browser status."""
        return {
            "browser_engine": "Google Chrome",
            "active_url": self.state.active_tab_url if hasattr(self.state, "active_tab_url") else ""
        }

    def _run_with_recovery(self, action_func, timeout: float = 90.0):
        """Executes an async browser action with automatic retry recovery if a TargetClosedError occurs."""
        try:
            return self.manager.run_async(action_func(), timeout=timeout)
        except Exception as e:
            err_str = str(e).lower()
            if any(term in err_str for term in ["closed", "target", "disconnect", "connection", "stale"]):
                print(f"[LIFECYCLE RECOVERY] Stale connection detected ({e}). Resetting browser state and retrying...")
                if hasattr(self.manager, "force_reset_connection"):
                    self.manager.force_reset_connection()
                return self.manager.run_async(action_func(), timeout=timeout)
            raise

    def open_website(self, url: str) -> str:
        """Navigates current active Google Chrome tab to the specified URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

        from jarvis.browser.browser_context import check_chrome_cdp_endpoint, find_real_chrome_executable
        import psutil, subprocess, os, webbrowser

        cdp_active = check_chrome_cdp_endpoint(9222)
        chrome_running = False
        if psutil:
            try:
                for p in psutil.process_iter(["name"]):
                    name = (p.info.get("name") or "").lower()
                    if "chrome" in name and "chromedriver" not in name:
                        chrome_running = True
                        break
            except Exception:
                pass

        if not cdp_active and chrome_running:
            print(f"[CHROME AUTOMATION] Opening '{url}' directly inside running normal Chrome session via IPC (zero killing)...")
            exe_path = find_real_chrome_executable()
            try:
                if exe_path and os.path.exists(str(exe_path)):
                    subprocess.Popen([str(exe_path), url], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, close_fds=True)
                else:
                    webbrowser.open(url)
            except Exception as e:
                print(f"[CHROME AUTOMATION WARNING] IPC launch failed: {e}, falling back to webbrowser...")
                webbrowser.open(url)

            title = f"Webpage ({url})"
            self.state.update_active_tab(url, title)
            self.state.log_action("open_website", {"url": url}, title)
            self.state.save_persistent_state()
            return f"Successfully opened {url} in Google Chrome"

        async def _action():
            try:
                print(f"[STEP 0] Entering open_website action for: {url}")
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()

                print(f"[STEP 6] Navigating page to: {url}")
                await page.goto(url, wait_until="domcontentloaded", timeout=60000)
                print(f"[STEP 6 DONE] Page navigation completed for: {url}")

                print(f"[STEP 7] Fetching page title and current URL...")
                title = await page.title()
                current_url = page.url
                print(f"[STEP 7 DONE] Loaded: '{title}' ({current_url})")
                return title, current_url
            except Exception as e:
                print(f"[STEP ERROR] Exception in open_website coroutine: {e}")
                traceback.print_exc()
                raise

        title, current_url = self._run_with_recovery(_action, timeout=90.0)
        self.state.update_active_tab(current_url, title)
        self.state.log_action("open_website", {"url": url}, title)
        self.state.save_persistent_state()
        return f"Successfully opened {current_url} — '{title}' in Google Chrome"

    def search_web(self, query: str) -> str:
        """Executes a Google search in Google Chrome."""
        search_url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        res = self.open_website(search_url)
        self.state.log_action("search_web", {"query": query}, res)
        return f"Searched Google for '{query}'"

    def click_element(self, target: str) -> str:
        """Clicks an element on the active page by CSS selector or inner text."""

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                print(f"[BROWSER_ACTION] Clicking target: '{target}'")
                try:
                    await page.click(target, timeout=5000)
                except Exception:
                    await page.get_by_text(target).first.click(timeout=8000)
                title = await page.title()
                return title
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Click failed for '{target}': {e}")
                traceback.print_exc()
                raise

        title = self._run_with_recovery(_action)
        self.state.log_action("click_element", {"target": target}, title)
        return f"Clicked '{target}' on page '{title}'"

    def type_text(self, target: str, text: str) -> str:
        """Fills text into an input target element."""

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                print(f"[BROWSER_ACTION] Typing text into '{target}'")
                try:
                    await page.fill(target, text, timeout=5000)
                except Exception:
                    await page.get_by_text(target).first.fill(text, timeout=8000)
                title = await page.title()
                return title
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Type text failed into '{target}': {e}")
                traceback.print_exc()
                raise

        title = self._run_with_recovery(_action)
        self.state.log_action("type_text", {"target": target, "text": text}, title)
        return f"Typed text into '{target}' on page '{title}'"

    def fill_form(self, fields: Dict[str, str]) -> str:
        """Fills multiple form fields on the active page."""
        results = []
        for selector, text in fields.items():
            res = self.type_text(selector, text)
            results.append(res)
        return f"Form submission completed ({len(fields)} fields filled)."

    def extract_data(self, query: str = "main text content") -> str:
        """
        Extracts clean text content from the active webpage.
        Integrates with VisionService to reuse active window context when available.
        """
        try:
            from vision.context_store import get_screen_context
            ctx = get_screen_context()
            win_title = str(getattr(ctx, "window_title", "") or "")
            ocr_txt = str(getattr(ctx, "ocr_text", "") or "")
            if ctx and ("Chrome" in win_title or "Google" in win_title):
                if len(ocr_txt) > 100:
                    return f"Extracted via Screen Vision ({win_title}):\n{ocr_txt[:1200]}"
        except Exception:
            pass

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                content = await page.content()
                title = await page.title()
                url = page.url
                return content, title, url
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Extract data failed: {e}")
                traceback.print_exc()
                raise

        content, title, url = self._run_with_recovery(_action)
        soup = BeautifulSoup(content, "html.parser")
        text = soup.get_text(separator=" ", strip=True)
        summary = f"Extracted from '{title}' ({url}):\n{text[:1500]}"
        self.state.log_action("extract_data", {"query": query}, summary[:200])
        return summary

    def download_file(self, url: str) -> str:
        """Downloads a file to memory/browser_sessions/downloads/."""
        dest_dir = self.context_mgr.get_downloads_path()

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                async with page.expect_download() as download_info:
                    await page.goto(url)
                download = await download_info.value
                save_path = str(Path(dest_dir) / download.suggested_filename)
                await download.save_as(save_path)
                return save_path
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Download failed for {url}: {e}")
                traceback.print_exc()
                raise

        try:
            saved_file = self._run_with_recovery(_action)
            return f"Successfully downloaded file to: {saved_file}"
        except Exception as e:
            return f"Download initiated/processed for {url}: {e}"

    def navigate(self, action: str = "reload") -> str:
        """Performs browser navigation (back, forward, reload)."""

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                if action == "back":
                    await page.go_back()
                elif action == "forward":
                    await page.go_forward()
                else:
                    await page.reload()
                return await page.title(), page.url
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Navigation '{action}' failed: {e}")
                traceback.print_exc()
                raise

        title, url = self._run_with_recovery(_action)
        self.state.update_active_tab(url, title)
        return f"Navigated ({action}) — '{title}' ({url})"

    def capture_page(self) -> bytes:
        """Captures current active Google Chrome page screenshot as PNG bytes."""

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                return await page.screenshot(type="png", full_page=False)
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Page capture failed: {e}")
                traceback.print_exc()
                raise

        png_bytes = self._run_with_recovery(_action)
        self.state.last_screenshot_bytes = png_bytes
        return png_bytes

    def perform_task(self, task_description: str) -> str:
        """Runs upstream Browser Use Agent autonomously for complex multi-step tasks."""
        browser_mod, session_mod, controller_mod, agent_service = self.manager.get_browser_use_modules()

        async def _run_agent():
            try:
                browser, context = await self.manager.async_get_or_create_browser()
                gemini_key = get_api_key()
                groq_key = get_groq_api_key()

                if gemini_key:
                    from langchain_google_genai import ChatGoogleGenerativeAI

                    class WrappedGoogleLLM(ChatGoogleGenerativeAI):
                        provider: str = "google"

                        @property
                        def model_name(self) -> str:
                            return getattr(self, "model", "gemini-2.0-flash")

                    llm = WrappedGoogleLLM(model="gemini-2.0-flash", google_api_key=gemini_key)
                elif groq_key:
                    import importlib
                    langchain_groq = importlib.import_module("langchain_groq")
                    llm = langchain_groq.ChatGroq(model="llama-3.3-70b-versatile", groq_api_key=groq_key)
                    setattr(llm, "provider", "groq")
                    setattr(llm, "model_name", "llama-3.3-70b-versatile")
                else:
                    raise ValueError("No LLM API key found in config/api_keys.json")

                agent = agent_service.Agent(
                    task=task_description,
                    llm=llm,
                    browser_context=context,
                )
                history = await agent.run(max_steps=10)
                return history.final_result()
            except Exception as e:
                print(f"[AGENT TASK ERROR] Autonomous agent execution failed: {e}")
                traceback.print_exc()
                raise

        try:
            result = self._run_with_recovery(_run_agent, timeout=180.0)
            return f"Autonomous Task Finished: {result}"
        except Exception as e:
            return f"Autonomous task status: {e}"

    def scroll(self, direction: str = "down", amount: int = 500) -> str:
        """Scrolls active browser page up or down."""
        async def _action():
            _, context = await self.manager.async_get_or_create_browser()
            page = await context.get_current_page()
            delta = amount if direction.lower() == "down" else -amount
            await page.evaluate(f"window.scrollBy(0, {delta})")
            return f"Scrolled {direction} by {amount}px"

        try:
            res = self._run_with_recovery(_action)
            self.state.log_action("scroll", {"direction": direction, "amount": amount}, res)
            return res
        except Exception as e:
            return f"Scroll failed: {e}"

    def list_tabs(self) -> str:
        """Lists all active browser tabs."""
        async def _action():
            _, context = await self.manager.async_get_or_create_browser()
            pages = context.pages
            tabs_info = []
            for i, p in enumerate(pages):
                title = await p.title()
                tabs_info.append(f"[{i}] {title} ({p.url})")
            return "\n".join(tabs_info) if tabs_info else "No open tabs found."

        try:
            return self._run_with_recovery(_action)
        except Exception as e:
            return f"Failed to list tabs: {e}"

    def switch_tab(self, index: int) -> str:
        """Switches to the tab at the given 0-based index."""
        async def _action():
            _, context = await self.manager.async_get_or_create_browser()
            pages = context.pages
            if 0 <= index < len(pages):
                page = pages[index]
                await page.bring_to_front()
                self.manager._active_page = page
                title = await page.title()
                return f"Switched to tab [{index}]: '{title}' ({page.url})"
            return f"Tab index {index} out of bounds (open tabs: {len(pages)})"

        try:
            res = self._run_with_recovery(_action)
            self.state.log_action("switch_tab", {"index": index}, res)
            return res
        except Exception as e:
            return f"Failed to switch tab: {e}"

    def close_tab(self, index: int = -1) -> str:
        """Closes tab at given index (defaults to active/last tab)."""
        async def _action():
            _, context = await self.manager.async_get_or_create_browser()
            pages = context.pages
            if not pages:
                return "No open tabs to close."
            target_page = pages[index] if 0 <= index < len(pages) else pages[-1]
            title = await target_page.title()
            await target_page.close()
            return f"Closed tab: '{title}'"

        try:
            res = self._run_with_recovery(_action)
            self.state.log_action("close_tab", {"index": index}, res)
            return res
        except Exception as e:
            return f"Failed to close tab: {e}"

    def execute_js(self, script: str) -> str:
        """Executes JavaScript code in active page context."""
        async def _action():
            _, context = await self.manager.async_get_or_create_browser()
            page = await context.get_current_page()
            result = await page.evaluate(script)
            return str(result)

        try:
            res = self._run_with_recovery(_action)
            self.state.log_action("execute_js", {"script": script[:50]}, res)
            return f"JS Result: {res}"
        except Exception as e:
            return f"JS execution failed: {e}"

    def go_back(self) -> str:
        """Navigates to previous page in history."""
        return self.navigate("back")

    def go_forward(self) -> str:
        """Navigates to next page in history."""
        return self.navigate("forward")


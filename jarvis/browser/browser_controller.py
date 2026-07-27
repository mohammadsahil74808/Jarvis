# jarvis/browser/browser_controller.py
"""
High-level controller bridging JARVIS tool actions with Playwright and Upstream Browser Use primitives.
Supports Firefox automation using persistent real user profile, VisionService screen awareness fusion, and state tracking.
Includes step-by-step debug logging and deadlock protection.
"""

from __future__ import annotations

import asyncio
import traceback
from pathlib import Path
from typing import Any, Dict, Optional

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

    def open_website(self, url: str) -> str:
        """Navigates current active Firefox tab to the specified URL."""
        if not url.startswith(("http://", "https://")):
            url = f"https://{url}"

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

        title, current_url = self.manager.run_async(_action(), timeout=90.0)
        self.state.update_active_tab(current_url, title)
        self.state.log_action("open_website", {"url": url}, title)
        self.state.save_persistent_state()
        return f"Successfully opened {current_url} — '{title}' in Firefox"

    def search_web(self, query: str) -> str:
        """Executes a Google search in Firefox."""
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

        title = self.manager.run_async(_action())
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

        title = self.manager.run_async(_action())
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
            if ctx and ctx.window_title and ("Firefox" in ctx.window_title or "Mozilla" in ctx.window_title):
                if ctx.ocr_text and len(ctx.ocr_text) > 100:
                    return f"Extracted via Screen Vision ({ctx.window_title}):\n{ctx.ocr_text[:1200]}"
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

        content, title, url = self.manager.run_async(_action())
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
            saved_file = self.manager.run_async(_action())
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

        title, url = self.manager.run_async(_action())
        self.state.update_active_tab(url, title)
        return f"Navigated ({action}) — '{title}' ({url})"

    def capture_page(self) -> bytes:
        """Captures current active Firefox page screenshot as PNG bytes."""

        async def _action():
            try:
                _, context = await self.manager.async_get_or_create_browser()
                page = await context.get_current_page()
                return await page.screenshot(type="png", full_page=False)
            except Exception as e:
                print(f"[BROWSER_ACTION ERROR] Page capture failed: {e}")
                traceback.print_exc()
                raise

        png_bytes = self.manager.run_async(_action())
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
            result = self.manager.run_async(_run_agent(), timeout=180.0)
            return f"Autonomous Task Finished: {result}"
        except Exception as e:
            return f"Autonomous task status: {e}"

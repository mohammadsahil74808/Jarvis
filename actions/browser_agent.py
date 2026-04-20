import asyncio
import threading
import concurrent.futures
import platform
import shutil
import time
from pathlib import Path
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeout

class BrowserAgent:
    def __init__(self):
        self._loop = None
        self._thread = None
        self._ready = threading.Event()
        self._playwright = None
        self._browser = None
        self._context = None
        self._page = None
        self._headless = False # Default to visible for agent tasks usually, but can be toggled

    def start(self):
        if self._thread and self._thread.is_alive():
            return
        self._thread = threading.Thread(
            target=self._run_loop, daemon=True, name="BrowserAgentThread"
        )
        self._thread.start()
        if not self._ready.wait(timeout=20):
            raise RuntimeError("BrowserAgent failed to start within timeout.")

    def _run_loop(self):
        self._loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self._loop)
        self._loop.run_until_complete(self._init_playwright())
        self._ready.set()
        self._loop.run_forever()

    async def suicide(self):
        """Internal cleanup."""
        if self._browser:
            await self._browser.close()
        if self._playwright:
            await self._playwright.stop()
        self._loop.stop()

    async def _init_playwright(self):
        self._playwright = await async_playwright().start()

    def run(self, coro, timeout: int = 60):
        if not self._loop:
            self.start()
        future = asyncio.run_coroutine_threadsafe(coro, self._loop)
        return future.result(timeout=timeout)

    async def _launch_if_needed(self, headless: bool = None):
        target_headless = headless if headless is not None else self._headless
        
        # If browser exists but headless mode changed, close and restart
        if self._browser:
            # We don't easily check current headless state from browser object, 
            # so we assume it matches self._headless from last launch.
            if target_headless != self._headless:
                await self._browser.close()
                self._browser = None
                self._context = None
                self._page = None

        if self._browser and self._browser.is_connected():
            return

        self._headless = target_headless
        
        # Try to find Edge or Chrome
        system = platform.system()
        channel = "msedge" if system == "Windows" else "chrome"
        
        try:
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless,
                channel=channel,
                args=["--start-maximized"] if not self._headless else []
            )
        except Exception as e:
            print(f"[BrowserAgent] ⚠️ Failed to launch {channel}: {e}. Falling back to default chromium.")
            self._browser = await self._playwright.chromium.launch(
                headless=self._headless
            )
            
        print(f"[BrowserAgent] ✅ Browser launched (headless={self._headless})")

    async def _get_page(self, headless: bool = None):
        await self._launch_if_needed(headless=headless)
        if self._context is None:
            self._context = await self._browser.new_context(
                viewport=None if not self._headless else {'width': 1920, 'height': 1080},
                user_agent="Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36 Edg/120.0.0.0"
            )
        if self._page is None or self._page.is_closed():
            self._page = await self._context.new_page()
        return self._page

    # Actions

    async def go_to(self, url: str, headless: bool = None) -> str:
        if not url.startswith("http"):
            url = "https://" + url
        page = await self._get_page(headless=headless)
        try:
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            return f"Successfully navigated to: {page.url}"
        except PlaywrightTimeout:
            return f"Timeout reached while loading: {url}"
        except Exception as e:
            return f"Navigation error: {e}"

    async def search_google(self, query: str, headless: bool = None) -> str:
        url = f"https://www.google.com/search?q={query.replace(' ', '+')}"
        return await self.go_to(url, headless=headless)

    async def click_element(self, selector: str = None, text: str = None, description: str = None, headless: bool = None) -> str:
        page = await self._get_page(headless=headless)
        try:
            if selector:
                await page.click(selector, timeout=10000)
                return f"Clicked element with selector: {selector}"
            elif text:
                # Try exact then partial
                try:
                    await page.get_by_text(text, exact=True).first.click(timeout=5000)
                    return f"Clicked element with exact text: '{text}'"
                except:
                    await page.get_by_text(text, exact=False).first.click(timeout=5000)
                    return f"Clicked element with partial text: '{text}'"
            elif description:
                # Intelligent role-based search
                for role in ["button", "link", "searchbox", "checkbox", "menuitem"]:
                    try:
                        await page.get_by_role(role, name=description, exact=False).first.click(timeout=2000)
                        return f"Found and clicked {role}: '{description}'"
                    except:
                        continue
                return f"Could not find element matching description: '{description}'"
            return "No identifier provided for click."
        except Exception as e:
            return f"Click failed: {e}"

    async def type_text(self, text: str, selector: str = None, description: str = None, press_enter: bool = False, headless: bool = None) -> str:
        page = await self._get_page(headless=headless)
        try:
            locator = None
            if selector:
                locator = page.locator(selector).first
            elif description:
                # Look for labels or placeholders
                for find_method in [page.get_by_placeholder, page.get_by_label, page.get_by_role]:
                    try:
                        if find_method == page.get_by_role:
                            target = find_method("textbox", name=description, exact=False).first
                        else:
                            target = find_method(description, exact=False).first
                        if await target.is_visible(timeout=1000):
                            locator = target
                            break
                    except:
                        continue
            
            if not locator:
                # Fallback to focused element
                locator = page.locator(":focus")

            await locator.fill(text)
            if press_enter:
                await page.keyboard.press("Enter")
            return "Text entered successfully."
        except Exception as e:
            return f"Typing failed: {e}"

    async def scroll(self, direction: str = "down", amount: int = 500, headless: bool = None) -> str:
        page = await self._get_page(headless=headless)
        try:
            y = amount if direction.lower() == "down" else -amount
            await page.mouse.wheel(0, y)
            return f"Scrolled {direction} by {amount} pixels."
        except Exception as e:
            return f"Scroll failed: {e}"

    async def extract_text(self, selector: str = "body", headless: bool = None) -> str:
        page = await self._get_page(headless=headless)
        try:
            text = await page.locator(selector).inner_text(timeout=5000)
            return text.strip() or "No text found in selected element."
        except Exception as e:
            return f"Extraction failed: {e}"

    async def fill_form(self, data: dict, headless: bool = None) -> str:
        page = await self._get_page(headless=headless)
        results = []
        for key, value in data.items():
            # key can be selector or description
            try:
                # Attempt to type using intelligent helper
                res = await self.type_text(str(value), description=key, headless=headless)
                if "failed" in res.lower():
                    # Try as selector
                    res = await self.type_text(str(value), selector=key, headless=headless)
                results.append(f"{key}: {'Success' if 'success' in res.lower() else 'Failed'}")
            except:
                results.append(f"{key}: Error")
        return "Form filled: " + ", ".join(results)

    async def login_helper(self, url: str, timeout: int = 120) -> str:
        # Strictly visible mode for login helper
        page = await self._get_page(headless=False)
        await page.goto(url)
        print(f"[BrowserAgent] 🔐 Login Helper started for: {url}")
        print(f"[BrowserAgent] Sir, please log in manually. I will wait for {timeout} seconds.")
        
        # We wait until the user closes the page or timeout
        start_time = time.time()
        while time.time() - start_time < timeout:
            if page.is_closed():
                return "Browser page closed by user. Login helper finished."
            await asyncio.sleep(2)
        
        return "Login helper timed out. I assume you have logged in or finished the task."

    async def close(self) -> str:
        if self._browser:
            await self._browser.close()
            self._browser = None
            self._context = None
            self._page = None
            return "Browser closed."
        return "Browser was not open."

# Singleton instance
_agent = BrowserAgent()

def browser_agent(parameters: dict, **kwargs) -> str:
    """
    Advanced Browser Agent powered by Playwright.
    
    Actions:
        go_to: (url) Navigate to a website.
        search: (query) Search Google.
        click: (selector|text|description) Click an element.
        type: (text, selector|description, press_enter) Type text.
        scroll: (direction, amount) Scroll the page.
        extract: (selector) Get text from the page.
        fill_form: (data: dict) Fill multiple fields.
        login_helper: (url, timeout) Manual login mode.
        close: Close the browser.
        
    Parameters:
        action (str): The action to perform.
        headless (bool): Run in background (default depends on action).
        ... action specific parameters.
    """
    action = parameters.get("action", "").lower()
    headless = parameters.get("headless", None)
    
    try:
        if action == "go_to":
            return _agent.run(_agent.go_to(parameters.get("url"), headless=headless))
        elif action == "search":
            return _agent.run(_agent.search_google(parameters.get("query"), headless=headless))
        elif action == "click":
            return _agent.run(_agent.click_element(
                selector=parameters.get("selector"),
                text=parameters.get("text"),
                description=parameters.get("description"),
                headless=headless
            ))
        elif action == "type":
            return _agent.run(_agent.type_text(
                text=parameters.get("text"),
                selector=parameters.get("selector"),
                description=parameters.get("description"),
                press_enter=parameters.get("press_enter", False),
                headless=headless
            ))
        elif action == "scroll":
            return _agent.run(_agent.scroll(
                direction=parameters.get("direction", "down"),
                amount=parameters.get("amount", 800),
                headless=headless
            ))
        elif action == "extract":
            return _agent.run(_agent.extract_text(
                selector=parameters.get("selector", "body"),
                headless=headless
            ))
        elif action == "fill_form":
            return _agent.run(_agent.fill_form(
                data=parameters.get("data", {}),
                headless=headless
            ))
        elif action == "login_helper":
            return _agent.run(_agent.login_helper(
                url=parameters.get("url"),
                timeout=parameters.get("timeout", 180)
            ))
        elif action == "close":
            return _agent.run(_agent.close())
        else:
            return f"Unknown action: {action}"
    except Exception as e:
        return f"BrowserAgent Error: {str(e)}"

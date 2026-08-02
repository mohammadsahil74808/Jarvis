# actions/browser_control.py
"""
Direct JARVIS action connecting Browser Use engine.
Allows JARVIS main loop, ToolExecutor, and Voice Assistant to directly trigger
Playwright browser automation and autonomous Agent tasks in Google Chrome.
Enforces real Google Chrome usage, DevTools Protocol session reuse, and clear profile lock reporting.
"""

from __future__ import annotations

from jarvis.browser.browser_adapter import get_browser_adapter


def browser_control(parameters: dict, **kwargs) -> str:
    """
    Main action entry point for Browser Use in JARVIS.
    Supports: open_website, search_web, click_element, type_text, fill_form,
              extract_data, download_file, navigate, capture_page, perform_task, get_status.
    """
    params = parameters or {}
    action = str(params.get("action", "open_website")).lower().strip()

    print(f"\n[BROWSER_CONTROL] Entered action: '{action}' | Params: {params}")
    print(f"[BROWSER_MANAGER] Accessing persistent Google Chrome context adapter...")
    adapter = get_browser_adapter()

    try:
        if action == "open_website" or action == "go_to":
            url = str(params.get("url") or "https://google.com")
            print(f"[CHROME] Opening URL: {url}")
            res = adapter.open_website(url)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "search_web" or action == "search":
            query = str(params.get("query") or "")
            print(f"[CHROME] Searching web for: '{query}'")
            res = adapter.search_web(query)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "click_element" or action == "click":
            target = str(params.get("target") or params.get("selector") or params.get("text") or params.get("description") or "")
            print(f"[CHROME] Clicking element: '{target}'")
            res = adapter.click_element(target)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "type_text" or action == "type" or action == "smart_type":
            target = str(params.get("target") or params.get("selector") or params.get("description") or "")
            text = str(params.get("text") or "")
            print(f"[CHROME] Typing text into '{target}'")
            res = adapter.type_text(target, text)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "fill_form":
            fields = params.get("fields") or {}
            print(f"[CHROME] Filling form fields: {fields}")
            res = adapter.fill_form(fields)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "extract_data" or action == "get_text":
            query = str(params.get("query") or "main text content")
            print(f"[CHROME] Extracting page data for query: '{query}'")
            res = adapter.extract_data(query)
            print(f"[TASK COMPLETED] Extracted data length: {len(res)} chars")
            return res

        elif action == "download_file":
            url = str(params.get("url") or "")
            print(f"[CHROME] Downloading file from: {url}")
            res = adapter.download_file(url)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "navigate":
            nav_action = str(params.get("action") or "reload")
            print(f"[CHROME] Navigating ({nav_action})")
            res = adapter.navigate(nav_action)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "capture_page":
            png_bytes = adapter.capture_page()
            print(f"[CHROME] Page snapshot captured: {len(png_bytes)} bytes")
            return f"Captured webpage snapshot in Google Chrome ({len(png_bytes)} bytes)"

        elif action == "perform_task" or action == "autonomous_task":
            task_desc = str(params.get("task_description") or params.get("task") or params.get("text") or params.get("query") or "")
            print(f"[BROWSER_USE_AGENT] Launching Browser Use autonomous engine for task: '{task_desc}'")
            res = adapter.perform_task(task_desc)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "get_status":
            status = adapter.get_status()
            print(f"[CHROME STATUS] {status}")
            return f"Google Chrome status: {status}"

        elif action == "scroll":
            direction = str(params.get("direction", "down"))
            amount = int(params.get("amount", 500))
            print(f"[CHROME] Scrolling {direction} by {amount}")
            res = adapter.scroll(direction, amount)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "list_tabs":
            res = adapter.list_tabs()
            return res

        elif action == "switch_tab":
            idx = int(params.get("index", 0))
            res = adapter.switch_tab(idx)
            return res

        elif action == "close_tab":
            idx = int(params.get("index", -1))
            res = adapter.close_tab(idx)
            return res

        elif action == "execute_js":
            script = str(params.get("script", ""))
            res = adapter.execute_js(script)
            return res

        elif action == "go_back":
            res = adapter.go_back()
            return res

        elif action == "go_forward":
            res = adapter.go_forward()
            return res

        elif action == "close":
            adapter.shutdown()
            return "Browser closed."

        else:
            return f"Unknown browser action '{action}' requested."

    except Exception as e:
        err_msg = str(e)
        print(f"[BROWSER_CONTROL ERROR] {err_msg}")
        return f"Browser action error: {err_msg}"

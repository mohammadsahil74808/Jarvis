# actions/browser_use_action.py
"""
Direct JARVIS action connecting Browser Use engine (integrations/browser_use).
Allows JARVIS main loop, ToolExecutor, and Voice Assistant to directly trigger
Playwright browser automation and autonomous Agent tasks in Firefox.
Enforces real Firefox persistent profile usage, session reuse, and clear profile lock reporting.
"""

from __future__ import annotations

from typing import Any
from jarvis.browser import get_browser_adapter


def browser_use_action(parameters: dict, **kwargs) -> str:
    """
    Main action entry point for Browser Use in JARVIS.
    Supports: open_website, search_web, click_element, type_text, fill_form,
              extract_data, download_file, navigate, capture_page, perform_task, get_status.
    """
    params = parameters or {}
    action = str(params.get("action", "open_website")).lower().strip()

    print(f"\n[BROWSER_USE_ACTION] Entered action: '{action}' | Params: {params}")
    print(f"[BROWSER_MANAGER] Accessing persistent Firefox context adapter...")
    adapter = get_browser_adapter()

    try:
        if action == "open_website":
            url = str(params.get("url") or "https://google.com")
            print(f"[FIREFOX] Opening URL: {url}")
            res = adapter.open_website(url)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "search_web":
            query = str(params.get("query") or "")
            print(f"[FIREFOX] Searching web for: '{query}'")
            res = adapter.search_web(query)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "click_element":
            target = str(params.get("target") or "")
            print(f"[FIREFOX] Clicking element: '{target}'")
            res = adapter.click_element(target)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "type_text":
            target = str(params.get("target") or "")
            text = str(params.get("text") or "")
            print(f"[FIREFOX] Typing text into '{target}'")
            res = adapter.type_text(target, text)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "fill_form":
            fields = params.get("fields") or {}
            print(f"[FIREFOX] Filling form fields: {fields}")
            res = adapter.fill_form(fields)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "extract_data":
            query = str(params.get("query") or "main text content")
            print(f"[FIREFOX] Extracting page data for query: '{query}'")
            res = adapter.extract_data(query)
            print(f"[TASK COMPLETED] Extracted data length: {len(res)} chars")
            return res

        elif action == "download_file":
            url = str(params.get("url") or "")
            print(f"[FIREFOX] Downloading file from: {url}")
            res = adapter.download_file(url)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "navigate":
            nav_action = str(params.get("action") or "reload")
            print(f"[FIREFOX] Navigating ({nav_action})")
            res = adapter.navigate(nav_action)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "capture_page":
            png_bytes = adapter.capture_page()
            print(f"[FIREFOX] Page snapshot captured: {len(png_bytes)} bytes")
            return f"Captured webpage snapshot in Firefox ({len(png_bytes)} bytes)"

        elif action == "perform_task":
            task_desc = str(params.get("task_description") or params.get("query") or "")
            print(f"[BROWSER_USE_AGENT] Launching Browser Use autonomous engine for task: '{task_desc}'")
            res = adapter.perform_task(task_desc)
            print(f"[TASK COMPLETED] Result: {res}")
            return res

        elif action == "get_status":
            status = adapter.get_status()
            print(f"[FIREFOX STATUS] {status}")
            return f"Firefox persistent status: {status}"

        else:
            return f"Unknown browser action '{action}' requested."

    except Exception as e:
        err_msg = str(e)
        print(f"[BROWSER_USE_ACTION ERROR] {err_msg}")
        return f"Browser Use action error: {err_msg}"

# jarvis/browser/__init__.py
"""
Upstream Browser Use Adapter Package for J.A.R.V.I.S.
Exposes a production-grade, thread-safe, Firefox-only browser automation interface.
"""

from .browser_adapter import BrowserUseAdapter, get_browser_adapter

__all__ = ["BrowserUseAdapter", "get_browser_adapter"]

# jarvis/browser/__init__.py
"""
Upstream Browser Use Adapter Package for J.A.R.V.I.S.
Exposes a production-grade, thread-safe, Google Chrome DevTools Protocol browser automation interface.
"""

from .browser_adapter import get_browser_adapter

__all__ = ["get_browser_adapter"]

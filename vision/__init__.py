"""Persistent screen understanding services for JARVIS."""

from .context import ScreenContext
from .context_store import get_screen_context, get_screen_context_prompt, update_screen_context

__all__ = ["ScreenContext", "VisionService", "get_screen_context", "get_screen_context_prompt", "update_screen_context"]


def __getattr__(name):
    if name == "VisionService":
        from .service import VisionService
        return VisionService
    raise AttributeError(name)

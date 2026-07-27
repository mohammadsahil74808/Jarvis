from __future__ import annotations

from threading import RLock

from .context import ScreenContext

_lock = RLock()
_latest = ScreenContext.empty()


def update_screen_context(context: ScreenContext) -> None:
    """Publish the latest ScreenContext for models, tools, and services."""
    global _latest
    with _lock:
        _latest = context


def get_screen_context() -> ScreenContext:
    """Return the latest compact screen context without triggering capture."""
    with _lock:
        return _latest


def get_screen_context_prompt() -> str:
    return get_screen_context().to_prompt()

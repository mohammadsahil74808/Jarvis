# vision/memory.py
"""Temporal screen memory and semantic desktop event log for JARVIS.

Tracks semantic events (e.g. app switching, error dialog popups, build completions,
terminal output updates) so JARVIS maintains temporal awareness of what happened on
the screen over time.
"""

from __future__ import annotations

import collections
import threading
import time
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from .context import ScreenContext


@dataclass(slots=True)
class ScreenEvent:
    """A single semantic desktop event recorded in temporal memory."""

    timestamp: float = field(default_factory=time.time)
    iso_time: str = ""
    event_type: str = "SCREEN_CHANGE"
    summary: str = ""
    app: str | None = None
    window_title: str | None = None
    details: dict[str, Any] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if not self.iso_time:
            self.iso_time = datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z")

    def time_ago_str(self) -> str:
        delta = max(0.0, time.time() - self.timestamp)
        if delta < 60.0:
            return f"{int(delta)}s ago"
        elif delta < 3600.0:
            return f"{int(delta // 60)}m ago"
        else:
            return f"{int(delta // 3600)}h ago"

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["time_ago"] = self.time_ago_str()
        return d


class ScreenMemory:
    """Thread-safe rolling temporal memory buffer for semantic desktop events."""

    def __init__(self, max_events: int = 30) -> None:
        self.max_events = max_events
        self._events: collections.deque[ScreenEvent] = collections.deque(maxlen=max_events)
        self._lock = threading.RLock()

    def add_event(self, event: ScreenEvent) -> None:
        with self._lock:
            self._events.append(event)

    def get_recent_events(self, limit: int = 10, max_age_sec: float | None = None) -> list[ScreenEvent]:
        with self._lock:
            now = time.time()
            res = []
            for ev in reversed(self._events):
                if max_age_sec is not None and (now - ev.timestamp) > max_age_sec:
                    continue
                res.append(ev)
                if len(res) >= limit:
                    break
            return res

    def detect_and_record_events(
        self, prev_ctx: ScreenContext | None, curr_ctx: ScreenContext
    ) -> list[ScreenEvent]:
        """Compares previous context with current context and records any semantic events."""
        if prev_ctx is None or curr_ctx.status != "ok":
            return []

        new_events: list[ScreenEvent] = []
        now = time.time()

        # 1. Active Application or Window Title Changed
        if (
            curr_ctx.active_application != prev_ctx.active_application
            or curr_ctx.active_window_title != prev_ctx.active_window_title
        ):
            if curr_ctx.active_application or curr_ctx.active_window_title:
                ev = ScreenEvent(
                    timestamp=now,
                    event_type="ACTIVE_APP_CHANGED",
                    summary=f"Switched focus to {curr_ctx.active_application or 'window'}: '{curr_ctx.active_window_title or ''}'",
                    app=curr_ctx.active_application,
                    window_title=curr_ctx.active_window_title,
                )
                new_events.append(ev)

        # 2. Error Dialog Opened / New Error Popups
        new_errors = [e for e in curr_ctx.error_popups if e not in prev_ctx.error_popups]
        if new_errors:
            ev = ScreenEvent(
                timestamp=now,
                event_type="ERROR_DIALOG_OPENED",
                summary=f"Error detected: '{new_errors[0]}'",
                app=curr_ctx.active_application,
                window_title=curr_ctx.active_window_title,
                details={"errors": new_errors},
            )
            new_events.append(ev)

        # 3. Build / Compilation Status Changed
        text_lower = curr_ctx.visible_text.lower()
        prev_text_lower = prev_ctx.visible_text.lower()
        if "build succeeded" in text_lower and "build succeeded" not in prev_text_lower:
            new_events.append(
                ScreenEvent(
                    timestamp=now,
                    event_type="BUILD_FINISHED",
                    summary="Build completed successfully",
                    app=curr_ctx.active_application,
                    window_title=curr_ctx.active_window_title,
                    details={"status": "success"},
                )
            )
        elif ("build failed" in text_lower or "compilation failed" in text_lower) and (
            "build failed" not in prev_text_lower and "compilation failed" not in prev_text_lower
        ):
            new_events.append(
                ScreenEvent(
                    timestamp=now,
                    event_type="BUILD_FINISHED",
                    summary="Build failed with errors",
                    app=curr_ctx.active_application,
                    window_title=curr_ctx.active_window_title,
                    details={"status": "failed"},
                )
            )

        # 4. Terminal Output Updated
        if curr_ctx.terminals and curr_ctx.visible_text != prev_ctx.visible_text:
            if any(w in text_lower for w in ("error", "exception", "failed", "traceback")):
                new_events.append(
                    ScreenEvent(
                        timestamp=now,
                        event_type="TERMINAL_OUTPUT_CHANGED",
                        summary=f"Terminal command output updated in {curr_ctx.active_application or 'terminal'}",
                        app=curr_ctx.active_application,
                        window_title=curr_ctx.active_window_title,
                    )
                )

        # 5. Browser Tab Changed
        if curr_ctx.browser_pages and curr_ctx.active_window_title != prev_ctx.active_window_title:
            new_events.append(
                ScreenEvent(
                    timestamp=now,
                    event_type="BROWSER_TAB_CHANGED",
                    summary=f"Browser tab changed to '{curr_ctx.active_window_title}'",
                    app=curr_ctx.active_application,
                    window_title=curr_ctx.active_window_title,
                )
            )

        # 6. Download Completed
        if "download complete" in text_lower and "download complete" not in prev_text_lower:
            new_events.append(
                ScreenEvent(
                    timestamp=now,
                    event_type="DOWNLOAD_COMPLETED",
                    summary="File download completed",
                    app=curr_ctx.active_application,
                    window_title=curr_ctx.active_window_title,
                )
            )

        with self._lock:
            for ev in new_events:
                self._events.append(ev)

        return new_events

    def to_prompt(self, limit: int = 5) -> str:
        events = self.get_recent_events(limit=limit)
        if not events:
            return ""
        lines = ["Recent Desktop Timeline:"]
        for ev in events:
            lines.append(f"- [{ev.time_ago_str()}] {ev.event_type}: {ev.summary}")
        return "\n".join(lines)

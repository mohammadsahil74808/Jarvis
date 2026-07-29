from __future__ import annotations

import hashlib
import logging
import importlib.util
import os
import re
import threading
import time
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Callable

logger = logging.getLogger(__name__)

from .context import ScreenContext
from .context_store import update_screen_context

ERROR_WORDS = ("error", "failed", "exception", "traceback", "critical", "fatal", "not found", "denied")
TERMINAL_HINTS = ("terminal", "cmd", "powershell", "bash", "zsh", "windows terminal")
CODE_HINTS = ("visual studio code", "vscode", "pycharm", "sublime", "notepad++", ".py", ".js", ".ts")
BROWSER_HINTS = ("chrome", "edge", "firefox", "brave", "browser")
EXPLORER_HINTS = ("explorer", "file explorer", "downloads", "documents")


_DEPS: tuple[Any, Any, Any, Any] | None = None


def _vision_deps() -> tuple[Any, Any, Any, Any]:
    """Import heavy desktop vision dependencies only when the service is running."""
    global _DEPS
    if _DEPS is None:
        import cv2
        import mss
        import numpy as np
        import pytesseract

        _DEPS = (cv2, mss, np, pytesseract)
    return _DEPS


class VisionService:
    """Continuously maintains a lightweight ScreenContext in a daemon thread."""

    def __init__(self, config: dict | None = None, on_context: Callable[[ScreenContext], None] | None = None):
        cfg = config or {}
        self.enabled = bool(cfg.get("vision_context_enabled", True))
        self.continuous = bool(cfg.get("vision_continuous_polling", False))
        self.min_interval = float(cfg.get("vision_min_interval_sec", 2.0))
        self.max_interval = float(cfg.get("vision_max_interval_sec", 15.0))
        self.change_threshold = float(cfg.get("vision_change_threshold", 0.018))
        self.ocr_every_n_changes = int(cfg.get("vision_ocr_every_n_changes", 1))
        self.max_ocr_chars = int(cfg.get("vision_max_ocr_chars", 2500))
        self.privacy_excluded_apps = {str(x).lower() for x in cfg.get("vision_privacy_excluded_apps", [])}
        self.on_context = on_context
        self._lock = threading.RLock()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._context = ScreenContext.empty()
        self._last_fingerprint: str | None = None
        self._last_small: Any | None = None
        self._change_count = 0
        self._interval = self.min_interval

    def start(self) -> None:
        if not self.enabled or not self.continuous or (self._thread and self._thread.is_alive()):
            return
        self._thread = threading.Thread(target=self._loop, name="VisionService", daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()

    def latest(self) -> ScreenContext:
        with self._lock:
            return self._context

    def latest_prompt(self) -> str:
        return self.latest().to_prompt()

    def _loop(self) -> None:
        while not self._stop.is_set():
            started = time.monotonic()
            try:
                updated = self._observe_once()
                self._interval = self.min_interval if updated else min(self.max_interval, self._interval * 1.35)
            except Exception as exc:
                self._set_context(ScreenContext.empty(status="degraded"), error=str(exc)[:200])
                self._interval = min(self.max_interval, max(self._interval * 1.5, 5.0))
            elapsed = time.monotonic() - started
            self._stop.wait(max(0.2, self._interval - elapsed))

    def _observe_once(self) -> bool:
        active_app, title = self._active_window()
        if active_app and active_app.lower() in self.privacy_excluded_apps:
            ctx = ScreenContext.empty(status="privacy_redacted")
            ctx.active_application = active_app
            ctx.active_window_title = title
            return self._set_context(ctx)

        frame = self._capture_small()
        change_score = self._change_score(frame)
        fingerprint = hashlib.blake2b(frame.tobytes(), digest_size=12).hexdigest()
        meta_changed = self.latest().active_window_title != title or self.latest().active_application != active_app
        if fingerprint == self._last_fingerprint or (change_score < self.change_threshold and not meta_changed):
            self._last_small = frame
            self._last_fingerprint = fingerprint
            return False

        self._change_count += 1
        text = ""
        if self._change_count % max(1, self.ocr_every_n_changes) == 0:
            text = self._ocr(frame)
        ctx = self._build_context(active_app, title, text[: self.max_ocr_chars], frame, change_score)
        self._last_small = frame
        self._last_fingerprint = fingerprint
        return self._set_context(ctx)

    def _capture_small(self) -> Any:
        cv2, mss, np, _pytesseract = _vision_deps()
        with mss.mss() as sct:
            if len(sct.monitors) < 2:
                raise RuntimeError("No primary monitor available for screen capture.")
            mon = sct.monitors[1]
            shot = sct.grab(mon)
        img = cv2.cvtColor(np.array(shot), cv2.COLOR_BGRA2BGR)
        return cv2.resize(img, (640, 360), interpolation=cv2.INTER_AREA)

    def _change_score(self, frame: Any) -> float:
        cv2, _mss, np, _pytesseract = _vision_deps()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if self._last_small is None:
            return 1.0
        prev = cv2.cvtColor(self._last_small, cv2.COLOR_BGR2GRAY)
        return float(np.mean(cv2.absdiff(gray, prev)) / 255.0)

    def _ocr(self, frame: Any) -> str:
        cv2, _mss, _np, pytesseract = _vision_deps()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
        return pytesseract.image_to_string(gray).strip()

    def _build_context(self, app: str | None, title: str | None, text: str, frame: Any, score: float) -> ScreenContext:
        app_l = (app or "").lower(); title_l = (title or "").lower(); text_l = text.lower()
        ctx = ScreenContext(
            timestamp=datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
            active_application=app,
            active_window_title=title,
            visible_text=text,
            visible_buttons=self._detect_buttons(frame, text),
            progress_bars=self._detect_progress_bars(frame),
            change_score=score,
            status="ok",
        )
        if any(w in text_l for w in ERROR_WORDS):
            ctx.error_popups = self._extract_lines(text, ERROR_WORDS, limit=4)
        if "dialog" in text_l or any(w in text_l for w in ("ok", "cancel", "yes", "no")):
            ctx.dialogs = self._extract_lines(text, ("ok", "cancel", "yes", "no", "dialog"), limit=4)
        if any(h in app_l or h in title_l for h in TERMINAL_HINTS):
            ctx.terminals = [title or app or "terminal"]
        if any(h in app_l or h in title_l for h in CODE_HINTS):
            ctx.code_editors = [title or app or "code editor"]
            self._add_git_context(ctx, title)
        if any(h in app_l or h in title_l for h in BROWSER_HINTS):
            ctx.browser_pages = [title or app or "browser"]
        if any(h in app_l or h in title_l for h in EXPLORER_HINTS):
            ctx.file_explorers = [title or app or "file explorer"]
        ctx.notifications = self._extract_lines(text, ("notification", "update available", "completed"), limit=3)
        return ctx

    def _detect_buttons(self, frame: Any, text: str) -> list[dict]:
        cv2, _mss, _np, _pytesseract = _vision_deps()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
        contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        buttons = []
        labels = re.findall(r"\b(OK|Cancel|Yes|No|Apply|Save|Run|Build|Retry|Close|Next|Back)\b", text, re.I)
        for cnt in contours[:400]:
            x, y, w, h = cv2.boundingRect(cnt)
            if 30 < w < 360 and 14 < h < 80 and 1.2 < (w / max(h, 1)) < 10:
                buttons.append({"type": "button", "box": [int(x), int(y), int(x + w), int(y + h)], "confidence": 0.55})
                if len(buttons) >= 20:
                    break
        for i, label in enumerate(labels[:8]):
            if i < len(buttons):
                buttons[i]["label"] = label
            else:
                buttons.append({"type": "button", "label": label, "confidence": 0.65})
        return buttons

    def _detect_progress_bars(self, frame: Any) -> list[dict]:
        cv2, _mss, _np, _pytesseract = _vision_deps()
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        edges = cv2.Canny(gray, 80, 160)
        contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        bars = []
        for cnt in contours:
            x, y, w, h = cv2.boundingRect(cnt)
            if 80 < w < 620 and 5 <= h <= 30 and w / max(h, 1) > 5:
                bars.append({"box": [int(x), int(y), int(x + w), int(y + h)], "confidence": 0.5})
                if len(bars) >= 5:
                    break
        return bars

    def _active_window(self) -> tuple[str | None, str | None]:
        if importlib.util.find_spec("pygetwindow") is None:
            return None, None
        import pygetwindow as gw
        win = gw.getActiveWindow()
        title = getattr(win, "title", None) if win else None
        app = title.split(" - ")[-1] if title and " - " in title else None
        return app, title

    def _add_git_context(self, ctx: ScreenContext, title: str | None) -> None:
        cwd = Path(os.getcwd())
        ctx.current_project = cwd.name
        head = cwd / ".git" / "HEAD"
        if head.exists():
            raw = head.read_text(encoding="utf-8", errors="ignore").strip()
            ctx.git_branch = raw.rsplit("/", 1)[-1] if raw.startswith("ref:") else raw[:8]
        newest: tuple[float, Path] | None = None
        ignored = {".git", "node_modules", "venv", ".venv", "__pycache__", "models"}
        scanned = 0

        for root, dirs, files in os.walk(cwd):
            if Path(root) != cwd:
                dirs[:] = []
            else:
                dirs[:] = [d for d in dirs if d not in ignored]
                
            if scanned >= 1500:
                break
            for file in files:
                if file in ignored:
                    continue
                path = Path(root) / file
                scanned += 1
                try:
                    mtime = path.stat().st_mtime
                    if newest is None or mtime > newest[0]:
                        newest = (mtime, path)
                except Exception as e:
                    logger.debug(f"Failed to stat {path}: {e}")
                if scanned >= 1500:
                    break
        if newest:
            ctx.recently_modified_file = str(newest[1].relative_to(cwd))

    def _extract_lines(self, text: str, words: tuple[str, ...], limit: int) -> list[str]:
        out = []
        for line in text.splitlines():
            clean = line.strip()
            low = clean.lower()
            if clean and any(w in low for w in words):
                out.append(clean[:180])
            if len(out) >= limit:
                break
        return out

    def _set_context(self, ctx: ScreenContext, error: str | None = None) -> bool:
        if error:
            ctx.error = error
        with self._lock:
            previous = self._context.to_prompt() if self._context else ""
            self._context = ctx
        update_screen_context(ctx)
        if self.on_context and ctx.to_prompt() != previous:
            self.on_context(ctx)
        return True

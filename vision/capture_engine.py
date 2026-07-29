# vision/capture_engine.py
"""
Unified, thread-safe screen capture & frame caching engine for JARVIS.

Provides a singleton MSS instance, monitor selection, region capture,
image resizing, frame caching, grayscale buffer reuse, and adaptive JPEG encoding.
"""

from __future__ import annotations

import hashlib
import io
import threading
import time

import cv2
import mss
import mss.tools
import numpy as np

try:
    import PIL.Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False


class CaptureEngine:
    """Thread-safe singleton engine managing desktop frame capture and caching."""

    _instance: CaptureEngine | None = None
    _class_lock = threading.RLock()

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._sct: mss.MSS | None = None
        self._last_raw_frame: np.ndarray | None = None
        self._last_gray_frame: np.ndarray | None = None
        self._last_hash: str | None = None
        self._last_timestamp: float = 0.0
        self._monitor_index: int = 1

    @classmethod
    def get_instance(cls) -> CaptureEngine:
        with cls._class_lock:
            if cls._instance is None:
                cls._instance = cls()
            return cls._instance

    def _get_sct(self) -> mss.MSS:
        if self._sct is None:
            if hasattr(mss, "MSS"):
                self._sct = mss.MSS()
            else:
                self._sct = mss.mss()
        return self._sct

    def get_monitors(self) -> list[dict[str, int]]:
        with self._lock:
            try:
                sct = self._get_sct()
                return [dict(m) for m in sct.monitors]
            except Exception:
                return [{"top": 0, "left": 0, "width": 1920, "height": 1080}]

    def set_monitor(self, index: int) -> None:
        with self._lock:
            self._monitor_index = index

    def capture_frame(self, monitor_index: int | None = None, region: dict[str, int] | None = None) -> np.ndarray:
        """Captures screen or region as a BGR numpy array (H, W, 3)."""
        with self._lock:
            try:
                sct = self._get_sct()
                if region:
                    shot = sct.grab(region)
                else:
                    idx = monitor_index if monitor_index is not None else self._monitor_index
                    if idx >= len(sct.monitors):
                        idx = 1 if len(sct.monitors) > 1 else 0
                    try:
                        shot = sct.grab(sct.monitors[idx])
                    except Exception:
                        shot = sct.grab(sct.monitors[0])

                arr = np.array(shot)
                bgr = cv2.cvtColor(arr, cv2.COLOR_BGRA2BGR)
            except Exception:
                # Fallback to PIL ImageGrab or synthetic frame if OS graphics context is restricted
                try:
                    import PIL.ImageGrab
                    pil_img = PIL.ImageGrab.grab(bbox=(region["left"], region["top"], region["left"] + region["width"], region["top"] + region["height"]) if region else None)
                    rgb = np.array(pil_img)
                    bgr = cv2.cvtColor(rgb, cv2.COLOR_RGB2BGR)
                except Exception:
                    bgr = np.zeros((360, 640, 3), dtype=np.uint8)

            if not region:
                self._last_raw_frame = bgr
                self._last_gray_frame = None
                self._last_timestamp = time.time()
                self._last_hash = hashlib.blake2b(bgr.tobytes(), digest_size=12).hexdigest()

            return bgr

    def capture_gray(self, monitor_index: int | None = None, region: dict[str, int] | None = None) -> np.ndarray:
        """Returns grayscale frame, reusing cached frame if available."""
        with self._lock:
            if not region and self._last_gray_frame is not None and (time.time() - self._last_timestamp < 0.2):
                return self._last_gray_frame
            bgr = self.capture_frame(monitor_index, region)
            gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
            if not region:
                self._last_gray_frame = gray
            return gray

    def capture_resized(
        self,
        target_w: int = 640,
        target_h: int = 360,
        monitor_index: int | None = None,
        region: dict[str, int] | None = None,
    ) -> np.ndarray:
        """Captures and downsamples frame to target dimensions (BGR array)."""
        bgr = self.capture_frame(monitor_index, region)
        return cv2.resize(bgr, (target_w, target_h), interpolation=cv2.INTER_AREA)

    def capture_png_bytes(self, monitor_index: int | None = None, region: dict[str, int] | None = None) -> bytes:
        """Captures screen as raw PNG bytes."""
        with self._lock:
            try:
                sct = self._get_sct()
                if region:
                    shot = sct.grab(region)
                else:
                    idx = monitor_index if monitor_index is not None else self._monitor_index
                    if idx >= len(sct.monitors):
                        idx = 1 if len(sct.monitors) > 1 else 0
                    try:
                        shot = sct.grab(sct.monitors[idx])
                    except Exception:
                        shot = sct.grab(sct.monitors[0])
                result = mss.tools.to_png(shot.rgb, shot.size)
                return result if result is not None else b""
            except Exception:
                bgr = self.capture_frame(monitor_index, region)
                ret, buf = cv2.imencode(".png", bgr)
                return buf.tobytes() if ret else b""

    def capture_jpeg_adaptive(
        self,
        max_w: int = 640,
        max_h: int = 360,
        target_bytes: int = 100000,
        qualities: tuple[int, ...] = (70, 40, 20),
    ) -> bytes:
        """Captures, resizes, and adaptively compresses frame to JPEG under target_bytes."""
        bgr = self.capture_frame()
        if _PIL_OK:
            rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)
            img = PIL.Image.fromarray(rgb)
            img.thumbnail((max_w, max_h), PIL.Image.Resampling.LANCZOS)
            for q in qualities:
                buf = io.BytesIO()
                img.save(buf, format="JPEG", quality=q, optimize=True)
                data = buf.getvalue()
                if len(data) < target_bytes or q == qualities[-1]:
                    return data

        resized = cv2.resize(bgr, (max_w, max_h), interpolation=cv2.INTER_AREA)
        for q in qualities:
            ret, buf = cv2.imencode(".jpg", resized, [cv2.IMWRITE_JPEG_QUALITY, q])
            if ret:
                b = buf.tobytes()
                if len(b) < target_bytes or q == qualities[-1]:
                    return b
        return b""

    def get_latest_cached_frame(self) -> tuple[np.ndarray | None, float, str | None]:
        with self._lock:
            return self._last_raw_frame, self._last_timestamp, self._last_hash

    def close(self) -> None:
        with self._lock:
            if self._sct is not None:
                try:
                    self._sct.close()
                except Exception:
                    pass
                self._sct = None


def get_capture_engine() -> CaptureEngine:
    return CaptureEngine.get_instance()


def capture_screen(region: dict[str, int] | None = None) -> np.ndarray:
    return get_capture_engine().capture_frame(region=region)


def capture_screenshot_bytes() -> bytes:
    return get_capture_engine().capture_jpeg_adaptive()

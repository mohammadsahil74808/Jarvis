# tests/test_vision_system.py
"""Unit tests for JARVIS screen capture engine, VisionService, privacy masking, and temporal screen memory."""

import pytest
import numpy as np
from vision.capture_engine import CaptureEngine, get_capture_engine, capture_screen, capture_screenshot_bytes
from vision.context import ScreenContext
from vision.privacy import mask_secrets, is_app_excluded
from vision.memory import ScreenMemory
from vision.ui_analyzer import analyze_ui_elements


@pytest.fixture
def capture_engine():
    return get_capture_engine()


class TestCaptureEngine:
    def test_singleton_instance(self, capture_engine):
        inst2 = CaptureEngine.get_instance()
        assert capture_engine is inst2

    def test_monitors_detection(self, capture_engine):
        monitors = capture_engine.get_monitors()
        assert isinstance(monitors, list)
        assert len(monitors) > 0

    def test_capture_frame(self):
        frame = capture_screen()
        assert isinstance(frame, np.ndarray)
        assert len(frame.shape) == 3  # H, W, BGR channels
        assert frame.shape[2] == 3

    def test_capture_resized(self, capture_engine):
        resized = capture_engine.capture_resized(320, 180)
        assert isinstance(resized, np.ndarray)
        assert resized.shape[0] == 180
        assert resized.shape[1] == 320

    def test_capture_jpeg_adaptive(self):
        jpeg_bytes = capture_screenshot_bytes()
        assert isinstance(jpeg_bytes, bytes)
        assert len(jpeg_bytes) > 0
        assert len(jpeg_bytes) < 200000  # Compressed under ~200KB

    def test_frame_caching(self, capture_engine):
        frame1 = capture_engine.capture_frame()
        cached_frame, timestamp, last_hash = capture_engine.get_latest_cached_frame()
        assert cached_frame is not None
        assert last_hash is not None
        assert timestamp > 0.0


class TestPrivacyAndSecretMasking:
    def test_groq_key_masking(self):
        raw = "My API key is gsk_123456789012345678901234567890 for Groq"
        masked = mask_secrets(raw)
        assert "gsk_123456789012345678901234567890" not in masked
        assert "[REDACTED_GROQ_KEY]" in masked

    def test_bearer_token_masking(self):
        raw = "Authorization: Bearer secret_token_abcdef1234567890"
        masked = mask_secrets(raw)
        assert "secret_token_abcdef1234567890" not in masked
        assert "[REDACTED_BEARER_TOKEN]" in masked

    def test_app_exclusion(self):
        excluded = {"bitwarden", "1password", "keepass"}
        assert is_app_excluded("Bitwarden - Vault", excluded)
        assert not is_app_excluded("Visual Studio Code", excluded)


class TestScreenMemoryAndEvents:
    def test_event_detection_and_timeline(self):
        memory = ScreenMemory()

        ctx1 = ScreenContext.empty(status="ok")
        ctx1.active_application = "PowerShell"
        ctx1.active_window_title = "Terminal"

        ctx2 = ScreenContext.empty(status="ok")
        ctx2.active_application = "Visual Studio Code"
        ctx2.active_window_title = "main.py - Jarvis"
        ctx2.error_popups = ["SyntaxError: invalid syntax line 4"]

        events = memory.detect_and_record_events(ctx1, ctx2)
        assert len(events) > 0

        event_types = [e.event_type for e in events]
        assert "ACTIVE_APP_CHANGED" in event_types
        assert "ERROR_DIALOG_OPENED" in event_types

        prompt_timeline = memory.to_prompt()
        assert "Recent Desktop Timeline:" in prompt_timeline
        assert "ACTIVE_APP_CHANGED" in prompt_timeline


class TestUIElementAnalyzer:
    def test_ui_element_classification(self):
        gray = np.zeros((360, 640), dtype=np.uint8)
        import cv2
        cv2.rectangle(gray, (10, 10), (100, 50), 200, -1)
        elements = analyze_ui_elements(gray, "OK Cancel")
        assert isinstance(elements, dict)

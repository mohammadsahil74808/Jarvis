# tests/test_vision_system.py
"""Unit tests for JARVIS screen capture engine, VisionService, privacy masking, and temporal screen memory."""

import unittest
import time
import numpy as np
from vision.capture_engine import CaptureEngine, get_capture_engine, capture_screen, capture_screenshot_bytes
from vision.context import ScreenContext
from vision.service import VisionService
from vision.privacy import mask_secrets, is_app_excluded
from vision.memory import ScreenMemory, ScreenEvent
from vision.ui_analyzer import analyze_ui_elements


class TestCaptureEngine(unittest.TestCase):
    def setUp(self):
        self.engine = get_capture_engine()

    def test_singleton_instance(self):
        inst1 = get_capture_engine()
        inst2 = CaptureEngine.get_instance()
        self.assertIs(inst1, inst2)

    def test_monitors_detection(self):
        monitors = self.engine.get_monitors()
        self.assertIsInstance(monitors, list)
        self.assertGreater(len(monitors), 0)

    def test_capture_frame(self):
        frame = capture_screen()
        self.assertIsInstance(frame, np.ndarray)
        self.assertEqual(len(frame.shape), 3)  # H, W, BGR channels
        self.assertEqual(frame.shape[2], 3)

    def test_capture_resized(self):
        resized = self.engine.capture_resized(320, 180)
        self.assertIsInstance(resized, np.ndarray)
        self.assertEqual(resized.shape[0], 180)
        self.assertEqual(resized.shape[1], 320)

    def test_capture_jpeg_adaptive(self):
        jpeg_bytes = capture_screenshot_bytes()
        self.assertIsInstance(jpeg_bytes, bytes)
        self.assertGreater(len(jpeg_bytes), 0)
        self.assertLess(len(jpeg_bytes), 200000)  # Compressed under ~200KB

    def test_frame_caching(self):
        frame1 = self.engine.capture_frame()
        cached_frame, timestamp, last_hash = self.engine.get_latest_cached_frame()
        self.assertIsNotNone(cached_frame)
        self.assertIsNotNone(last_hash)
        self.assertGreater(timestamp, 0.0)


class TestPrivacyAndSecretMasking(unittest.TestCase):
    def test_groq_key_masking(self):
        raw = "My API key is gsk_123456789012345678901234567890 for Groq"
        masked = mask_secrets(raw)
        self.assertNotIn("gsk_123456789012345678901234567890", masked)
        self.assertIn("[REDACTED_GROQ_KEY]", masked)

    def test_bearer_token_masking(self):
        raw = "Authorization: Bearer secret_token_abcdef1234567890"
        masked = mask_secrets(raw)
        self.assertNotIn("secret_token_abcdef1234567890", masked)
        self.assertIn("[REDACTED_BEARER_TOKEN]", masked)

    def test_app_exclusion(self):
        excluded = {"bitwarden", "1password", "keepass"}
        self.assertTrue(is_app_excluded("Bitwarden - Vault", excluded))
        self.assertFalse(is_app_excluded("Visual Studio Code", excluded))


class TestScreenMemoryAndEvents(unittest.TestCase):
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
        self.assertGreater(len(events), 0)

        event_types = [e.event_type for e in events]
        self.assertIn("ACTIVE_APP_CHANGED", event_types)
        self.assertIn("ERROR_DIALOG_OPENED", event_types)

        prompt_timeline = memory.to_prompt()
        self.assertIn("Recent Desktop Timeline:", prompt_timeline)
        self.assertIn("ACTIVE_APP_CHANGED", prompt_timeline)


class TestUIElementAnalyzer(unittest.TestCase):
    def test_ui_element_classification(self):
        gray = np.zeros((360, 640), dtype=np.uint8)
        # Draw a mock button rectangle
        gray[100:140, 200:350] = 255
        res = analyze_ui_elements(gray, "Click OK to submit")
        self.assertIn("buttons", res)
        self.assertIn("textboxes", res)
        self.assertIn("progress_bars", res)


class TestVisionServiceOptimizations(unittest.TestCase):
    def test_context_creation(self):
        ctx = ScreenContext.empty(status="ok")
        self.assertEqual(ctx.status, "ok")
        prompt = ctx.to_prompt()
        self.assertIn("Status: ok", prompt)

    def test_adaptive_polling_and_ocr_skipping(self):
        events = []
        def _on_ctx(c):
            events.append(c)

        service = VisionService(
            config={
                "vision_context_enabled": True,
                "vision_min_interval_sec": 0.5,
                "vision_max_interval_sec": 2.0,
                "vision_change_threshold": 0.018,
            },
            on_context=_on_ctx,
        )

        gray = np.zeros((360, 640), dtype=np.uint8)
        score1 = service._compute_change_score(gray)
        self.assertEqual(score1, 1.0)

        service._last_gray = gray
        score2 = service._compute_change_score(gray)
        self.assertEqual(score2, 0.0)

    def test_project_metadata_caching(self):
        service = VisionService()
        ctx = ScreenContext.empty()
        service._add_git_context(ctx, "VSCode")
        self.assertIsNotNone(ctx.current_project)
        t1 = service._project_meta_time
        service._add_git_context(ctx, "VSCode")
        self.assertEqual(service._project_meta_time, t1)


if __name__ == "__main__":
    unittest.main()

import sys
import os
import asyncio
from pathlib import Path
import unittest
from unittest.mock import Mock, patch

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import JarvisLive
from core.utils import retry, async_retry

class MockUI:
    def __init__(self):
        self.muted = False
    def set_state(self, state): pass
    def write_log(self, text): pass
    def root(self): pass

class TestSelfHealing(unittest.TestCase):

    def test_retry_decorator(self):
        print("Testing retry decorator...")
        self.count = 0
        
        @retry(max_attempts=3, delay=0.1)
        def failing_func():
            self.count += 1
            if self.count < 3:
                raise ValueError("Temporary failure")
            return "Success"

        result = failing_func()
        self.assertEqual(result, "Success")
        self.assertEqual(self.count, 3)
        print("[PASS] retry decorator passed.")

    def test_async_retry_decorator(self):
        print("Testing async_retry decorator...")
        self.async_count = 0
        
        @async_retry(max_attempts=3, delay=0.1)
        async def async_failing_func():
            self.async_count += 1
            if self.async_count < 3:
                raise ValueError("Temporary async failure")
            return "Async Success"

        result = asyncio.run(async_failing_func())
        self.assertEqual(result, "Async Success")
        self.assertEqual(self.async_count, 3)
        print("[PASS] async_retry decorator passed.")

    @patch("main.open_app")
    def test_execute_tool_retry_and_suggestion(self, mock_open_app):
        print("Testing _execute_tool retry and fallback suggestion...")
        ui = MockUI()
        jarvis = JarvisLive(ui)
        
        # Make open_app fail consistently
        mock_open_app.side_effect = Exception("Hard failure")
        
        class MockFC:
            def __init__(self):
                self.name = "open_app"
                self.args = {"app_name": "BrokenApp"}
                self.id = "123"

        async def run_test():
            # This should try 2 times (as per main.py implementation) and then return an error with suggestion
            fc = MockFC()
            result_obj = await jarvis._execute_tool(fc)
            result_text = result_obj.response["result"]
            
            print(f"Result text: {result_text}")
            self.assertIn("failed after 2 attempts", result_text)
            self.assertIn("[SELF-HEALING SUGGESTION]", result_text)
            self.assertIn("Try using 'web_search'", result_text)

        asyncio.run(run_test())
        print("[PASS] _execute_tool self-healing logic passed.")

if __name__ == "__main__":
    unittest.main()

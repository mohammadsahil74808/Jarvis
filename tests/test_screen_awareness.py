import sys
import os
import asyncio
from pathlib import Path
from unittest.mock import Mock, patch

# Add project root to sys.path
sys.path.append(str(Path(__file__).resolve().parent.parent))

from main import JarvisLive
from actions.computer_control import computer_control

class MockUI:
    def __init__(self):
        self.muted = False
    def set_state(self, state): pass
    def write_log(self, text): 
        print(f"[UI LOG] {text}")
    def root(self): pass

@patch("actions.screen_processor._capture_screenshot")
@patch("google.genai.Client")
async def test_capture_screen_context(mock_client, mock_capture):
    print("Testing capture_screen_context tool...")
    ui = MockUI()
    jarvis = JarvisLive(ui)
    
    # Mock screenshot
    mock_capture.return_value = b"fake_image_bytes"
    
    # Mock Gemini response
    mock_response = Mock()
    mock_response.text = "Active Window: VS Code\n- OK Button at (800, 200)"
    mock_model = Mock()
    mock_model.generate_content.return_value = mock_response
    mock_genai_client = Mock()
    mock_genai_client.models.get.return_value = mock_model
    mock_client.return_value = mock_genai_client

    class MockFC:
        def __init__(self):
            self.name = "capture_screen_context"
            self.args = {}
            self.id = "456"

    await jarvis._execute_tool(MockFC())
    
    print(f"Captured context: {jarvis.screen_context}")
    assert "VS Code" in jarvis.screen_context
    assert "800, 200" in jarvis.screen_context
    print("[PASS] capture_screen_context passed.")

@patch("pyautogui.size")
@patch("pyautogui.click")
@patch("pyautogui.moveTo")
def test_click_normalized(mock_move, mock_click, mock_size):
    print("Testing click_normalized action...")
    mock_size.return_value = (1920, 1080)
    
    # Click at (500, 500) -> should be (960, 540)
    params = {"action": "click_normalized", "x_norm": 500, "y_norm": 500}
    result = computer_control(params)
    
    print(f"Result: {result}")
    # Verify coordinates passed to _click (via mock_click)
    # computer_control calls _click(x=960, y=540, ...)
    mock_click.assert_called_with(960, 540, button="left", clicks=1)
    print("[PASS] click_normalized passed.")

if __name__ == "__main__":
    asyncio.run(test_capture_screen_context())
    test_click_normalized()
    print("\nAll screen awareness tests passed!")

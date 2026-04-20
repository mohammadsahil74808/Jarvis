import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from actions.screen_vision import screen_vision

def test_screen_vision():
    print("--- Testing ScreenVision ---")
    
    # 1. Test Analyze (OCR + Detect)
    print("1. Testing analyze action...")
    result = screen_vision({
        "action": "analyze"
    })
    print(f"Result: {result}")
    
    # 2. Test OCR only
    print("\n2. Testing ocr action...")
    result = screen_vision({
        "action": "ocr"
    })
    print(f"OCR result: {result}")
    
    # 3. Test Detect only
    print("\n3. Testing detect action...")
    result = screen_vision({
        "action": "detect"
    })
    print(f"Detect result: {result}")
    
    print("\n--- Verification Complete ---")

if __name__ == "__main__":
    test_screen_vision()

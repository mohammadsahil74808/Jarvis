import sys
import os
from pathlib import Path

# Add project root to sys.path
sys.path.append(str(Path(__file__).parent.parent))

from actions.screen_vision import screen_vision, ocr_screen, capture_screen, detect_ui_elements
import pytesseract

def diagnose():
    print("--- ScreenVision Diagnostic ---")
    
    # 1. Check pytesseract version and command
    print(f"Pytesseract commanded: {pytesseract.pytesseract.tesseract_cmd}")
    try:
        ver = pytesseract.get_tesseract_version()
        print(f"Tesseract Version: {ver}")
    except Exception as e:
        print(f"Tesseract Error: {e}")
        
    # 2. Test Screenshot Capture
    try:
        img = capture_screen()
        print(f"Screenshot Capture: OK (Size: {img.shape})")
    except Exception as e:
        print(f"Screenshot Capture: FAILED ({e})")
        return

    # 3. Test OCR
    try:
        txt = ocr_screen(img)
        print(f"OCR Test: OK (Extracted {len(txt)} chars)")
    except Exception as e:
        print(f"OCR Test: FAILED ({e})")

    # 4. Test Detection
    try:
        el = detect_ui_elements(img)
        print(f"UI Detection Test: OK (Found {len(el)} elements)")
    except Exception as e:
        print(f"UI Detection Test: FAILED ({e})")

if __name__ == "__main__":
    diagnose()

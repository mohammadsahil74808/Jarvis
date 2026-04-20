import mss
import mss.tools
import cv2
import numpy as np
import pytesseract
from PIL import Image
import io
import json
import os
from pathlib import Path

# Tesseract path configuration (Common for Windows)
TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
if os.path.exists(TESSERACT_EXE):
    pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE

def capture_screen(region=None):
    """Captures the screen or a specific region."""
    with mss.mss() as sct:
        if region:
            # region: {'top': 0, 'left': 0, 'width': 100, 'height': 100}
            shot = sct.grab(region)
        else:
            shot = sct.grab(sct.monitors[1])
        
        # Convert to numpy array for OpenCV
        img = np.array(shot)
        # Convert from BGRA to BGR
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

def detect_ui_elements(img):
    """Detects potential buttons and UI elements using OpenCV."""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Thresholding to find contours
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    elements = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        # Filter by aspect ratio and size (typical for buttons)
        aspect_ratio = float(w) / h
        if 1.2 < aspect_ratio < 10.0 and 30 < w < 600 and 15 < h < 150:
            elements.append({
                "type": "potential_button",
                "box": [x, y, x + w, y + h],
                "confidence": 0.6
            })
    return elements

def ocr_screen(img):
    """Extracts text from the image using Tesseract."""
    # Preprocessing for better OCR
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    # Scale up for better OCR on small text
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    
    text = pytesseract.image_to_string(gray)
    return text.strip()

def screen_vision(parameters: dict, **kwargs) -> str:
    """
    Analyzes the screen to extract text and detect UI elements.
    
    Actions:
        analyze: (default) Full analysis (OCR + Button Detection)
        ocr: Just extract text.
        detect: Just detect buttons.
    
    Parameters:
        action (str): analyze | ocr | detect
        region (dict): Optional {'top', 'left', 'width', 'height'}
    """
    action = parameters.get("action", "analyze").lower()
    region = parameters.get("region")
    
    try:
        img = capture_screen(region)
        
        results = {
            "text": "",
            "elements": [],
            "status": "success"
        }
        
        if action in ["analyze", "ocr"]:
            results["text"] = ocr_screen(img)
            
        if action in ["analyze", "detect"]:
            results["elements"] = detect_ui_elements(img)
            
        # Check for errors in text
        error_keywords = ["error", "failed", "exception", "not found", "critical"]
        found_errors = [word for word in error_keywords if word in results["text"].lower()]
        if found_errors:
            results["alerts"] = f"Potential errors detected: {', '.join(found_errors)}"

        # Format output as a nice string for JARVIS
        output = []
        if results["text"]:
            output.append(f"Screen Text: {results['text'][:500]}...")
        if results["elements"]:
            output.append(f"Detected {len(results['elements'])} UI elements.")
        if "alerts" in results:
            output.append(f"WARNING: {results['alerts']}")
            
        if not output:
            return "Sir, I analyzed the screen but couldn't find any significant text or UI elements."
            
        return "\n".join(output)

    except Exception as e:
        return f"Screen Vision Error: {str(e)}"

if __name__ == "__main__":
    # Quick test
    res = screen_vision({"action": "analyze"})
    print(res)

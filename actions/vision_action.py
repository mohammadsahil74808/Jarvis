# actions/vision_action.py
import io
import json
import cv2
import mss
import mss.tools
import numpy as np

try:
    import PIL.Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from google.genai import types
from core.config import API_CONFIG_PATH, get_gemini_client
import os

try:
    import pytesseract
    TESSERACT_EXE = r"C:\Program Files\Tesseract-OCR\tesseract.exe"
    if os.path.exists(TESSERACT_EXE):
        pytesseract.pytesseract.tesseract_cmd = TESSERACT_EXE
except ImportError:
    pytesseract = None

# Configuration
IMG_MAX_W = 640
IMG_MAX_H = 360
VISION_MODEL = "gemini-2.0-flash"

SYSTEM_PROMPT = (
    "You are JARVIS from Iron Man movies. "
    "Analyze images with technical precision and intelligence. "
    "Help the user in a way they can understand — don't be overly complex. "
    "Be concise, smart, and helpful like Tony Stark's AI assistant. "
    "Respond in maximum 2 short sentences. Speed is priority. "
    "Address the user as 'sir' for a tone of respect. "
    "Ask if the user needs any further help with their problem."
)

def _get_camera_index() -> int:
    try:
        if API_CONFIG_PATH.exists():
            with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
                cfg = json.load(f)
            if "camera_index" in cfg:
                return int(cfg["camera_index"])
    except Exception:
        pass

    print("[Camera] 🔍 Auto-detecting camera...")
    best_index = 0
    for idx in range(4):
        cap = cv2.VideoCapture(idx, cv2.CAP_DSHOW)
        if cap.isOpened():
            best_index = idx
            cap.release()
            break
    return best_index

def _adaptive_compress(img) -> bytes:
    for q in [70, 40, 20]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q, optimize=True)
        data = buf.getvalue()
        if len(data) < 100000 or q == 20:
            return data
    return b""

def _capture_screenshot_bytes() -> bytes:
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)
    if _PIL_OK:
        img = PIL.Image.open(io.BytesIO(png_bytes)).convert("RGB")
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.LANCZOS)
        return _adaptive_compress(img)
    return png_bytes

def _capture_screenshot_cv2(region=None):
    with mss.mss() as sct:
        if region:
            shot = sct.grab(region)
        else:
            shot = sct.grab(sct.monitors[1])
        img = np.array(shot)
        img = cv2.cvtColor(img, cv2.COLOR_BGRA2BGR)
        return img

def _capture_camera_bytes() -> bytes:
    index = _get_camera_index()
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")
    
    for _ in range(5): cap.read()
    ret, frame = cap.read()
    cap.release()
    
    if not ret or frame is None:
        raise RuntimeError("Failed to capture frame.")
        
    if _PIL_OK:
        rgb = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        img = PIL.Image.fromarray(rgb)
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.LANCZOS)
        return _adaptive_compress(img)
        
    ret, buf = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 50])
    return buf.tobytes()

def _detect_ui_elements(img):
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    _, thresh = cv2.threshold(gray, 200, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    
    elements = []
    for cnt in contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect_ratio = float(w) / h
        if 1.2 < aspect_ratio < 10.0 and 30 < w < 600 and 15 < h < 150:
            elements.append({
                "type": "potential_button",
                "box": [x, y, x + w, y + h],
                "confidence": 0.6
            })
    return elements

def _ocr_screen(img):
    if not pytesseract:
        return ""
    gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
    gray = cv2.resize(gray, None, fx=1.5, fy=1.5, interpolation=cv2.INTER_CUBIC)
    text = pytesseract.image_to_string(gray)
    return text.strip()

def vision_action(parameters: dict, player=None, **kwargs) -> str:
    """
    Unified entry point for Vision requests.
    Supports actions: 'analyze' (QA via Gemini), 'ocr' (Tesseract), 'detect' (OpenCV Buttons), 'context' (Gemini structured extraction)
    """
    action = parameters.get("action", "analyze").lower()
    angle = parameters.get("angle", "screen").lower().strip()
    user_text = parameters.get("query") or parameters.get("text") or parameters.get("user_text", "What do you see?")
    
    print(f"[Vision Action] Executing: {action} on {angle}")

    try:
        if action == "analyze":
            if angle == "camera":
                image_bytes = _capture_camera_bytes()
            else:
                image_bytes = _capture_screenshot_bytes()
                
            client = get_gemini_client()
            res = client.models.generate_content(
                model=VISION_MODEL,
                config=types.GenerateContentConfig(
                    system_instruction=SYSTEM_PROMPT,
                    max_output_tokens=150,
                    temperature=0.4
                ),
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    user_text
                ]
            )
            analysis = res.text.strip()
            if player:
                player.write_log(f"Jarvis (Vision): {analysis}")
            return analysis

        elif action == "context":
            image_bytes = _capture_screenshot_bytes()
            client = get_gemini_client()
            prompt = (
                "Analyze this screenshot. Describe: 1. The active window. "
                "2. Important buttons/text visible. 3. Their approximate coordinates (0-1000 scale, e.g. center is 500,500). "
                "Be concise. Format as a bulleted list."
            )
            res = client.models.generate_content(
                model=VISION_MODEL,
                contents=[
                    types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
                    prompt
                ]
            )
            return res.text.strip()

        elif action in ["ocr", "detect", "local_vision"]:
            img = _capture_screenshot_cv2(parameters.get("region"))
            results = {"text": "", "elements": [], "status": "success"}
            
            if action in ["ocr", "local_vision"]:
                results["text"] = _ocr_screen(img)
                
            if action in ["detect", "local_vision"]:
                results["elements"] = _detect_ui_elements(img)
                
            error_keywords = ["error", "failed", "exception", "not found", "critical"]
            found_errors = [word for word in error_keywords if word in results["text"].lower()]
            if found_errors:
                results["alerts"] = f"Potential errors detected: {', '.join(found_errors)}"

            output = []
            if results["text"]: output.append(f"Screen Text: {results['text'][:500]}...")
            if results["elements"]: output.append(f"Detected {len(results['elements'])} UI elements.")
            if "alerts" in results: output.append(f"WARNING: {results['alerts']}")
                
            if not output:
                return "Sir, I analyzed the screen but couldn't find any significant text or UI elements."
            return "\n".join(output)

        else:
            return f"Unknown vision action: {action}"

    except Exception as e:
        error_msg = f"Vision system error: {str(e)}"
        print(f"[Vision] ❌ {error_msg}")
        return error_msg

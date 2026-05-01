# actions/screen_processor.py
import base64
import io
import json
import re
import os
import cv2
import mss
import mss.tools
import numpy as np
from pathlib import Path

try:
    import PIL.Image
    _PIL_OK = True
except ImportError:
    _PIL_OK = False

from google.genai import types
from core.config import get_api_key, API_CONFIG_PATH, get_gemini_client

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
    """Compresses PIL image to target <100KB for faster API transfer."""
    for q in [70, 40, 20]:
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=q, optimize=True)
        data = buf.getvalue()
        if len(data) < 100000 or q == 20:
            return data
    return b""

def _capture_screenshot() -> bytes:
    with mss.mss() as sct:
        shot = sct.grab(sct.monitors[1])
        png_bytes = mss.tools.to_png(shot.rgb, shot.size)
    if _PIL_OK:
        img = PIL.Image.open(io.BytesIO(png_bytes)).convert("RGB")
        img.thumbnail([IMG_MAX_W, IMG_MAX_H], PIL.Image.LANCZOS)
        return _adaptive_compress(img)
    return png_bytes

def _capture_camera() -> bytes:
    index = _get_camera_index()
    cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
    if not cap.isOpened():
        raise RuntimeError("Could not open camera.")
    
    # Warm up
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

def screen_process(
    parameters: dict,
    response: str | None = None,
    player=None,
    session_memory=None,
) -> str:
    """
    Main entry point for vision analysis.
    Captures an image and analyzes it using Gemini 2.0 Flash.
    """
    user_text = (parameters or {}).get("text") or (parameters or {}).get("user_text", "What do you see?")
    angle = (parameters or {}).get("angle", "screen").lower().strip()
    
    print(f"[Vision] Processing {angle} analysis request...")
    
    try:
        # 1. Capture Image
        if angle == "camera":
            image_bytes = _capture_camera()
        else:
            image_bytes = _capture_screenshot()
            
        # 2. Call Gemini
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
        print(f"[Vision] Result: {analysis[:100]}...")
        
        if player:
            player.write_log(f"Jarvis (Vision): {analysis}")
            
        return analysis
        
    except Exception as e:
        error_msg = f"Vision system error: {str(e)}"
        print(f"[Vision] ❌ {error_msg}")
        return error_msg

if __name__ == "__main__":
    print("Testing Screen Processor (Stateless Mode)...")
    result = screen_process({"angle": "screen", "text": "What is on my screen right now?"})
    print("-" * 30)
    print(result)

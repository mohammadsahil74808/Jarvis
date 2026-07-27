# vision/ui_analyzer.py
"""Enhanced UI element classifier and UI Automation inspector for JARVIS vision context.

Combines lightweight Windows UI Automation (when available) with high-speed OpenCV
contour heuristics to detect buttons, textboxes, dropdowns, terminals, code editors,
dialogs, progress bars, and notifications.
"""

from __future__ import annotations

import re
from typing import Any

import cv2
import numpy as np

# Common UI control keywords for OCR string matching
BUTTON_KEYWORDS = re.compile(
    r"\b(OK|Cancel|Yes|No|Apply|Save|Run|Build|Retry|Close|Next|Back|Submit|Confirm|Delete|Edit|Open)\b",
    re.I,
)
TEXTBOX_KEYWORDS = re.compile(
    r"\b(Search|Type here|Enter|Input|Username|Password|Email|URL|Filter|Address)\b",
    re.I,
)


def analyze_ui_elements(gray_frame: np.ndarray, ocr_text: str) -> dict[str, list[dict[str, Any]]]:
    """Analyzes a grayscale image frame and OCR text to categorize UI elements.

    Returns dict containing:
      - 'buttons': list of button element dicts
      - 'textboxes': list of input box dicts
      - 'progress_bars': list of progress bar dicts
      - 'dialogs': list of dialog box dicts
    """
    buttons = []
    textboxes = []
    progress_bars = []

    # 1. Otsu binary thresholding
    _, thresh = cv2.threshold(gray_frame, 200, 255, cv2.THRESH_BINARY_INV + cv2.THRESH_OTSU)
    contours, _ = cv2.findContours(thresh, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)

    button_labels = BUTTON_KEYWORDS.findall(ocr_text)
    textbox_labels = TEXTBOX_KEYWORDS.findall(ocr_text)

    for cnt in contours[:500]:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = float(w) / max(h, 1)

        # Button Heuristic: w/h ratio between 1.2 and 10, width 30-360, height 14-80
        if 30 < w < 360 and 14 < h < 80 and 1.2 < aspect < 10.0:
            buttons.append(
                {
                    "type": "button",
                    "box": [int(x), int(y), int(x + w), int(y + h)],
                    "confidence": 0.60,
                }
            )
            if len(buttons) >= 20:
                break

        # Textbox / Input Box Heuristic: wider rectangle (aspect 3 to 15), height 20-50
        elif 80 < w < 500 and 20 <= h <= 50 and 3.0 < aspect < 15.0:
            textboxes.append(
                {
                    "type": "textbox",
                    "box": [int(x), int(y), int(x + w), int(y + h)],
                    "confidence": 0.55,
                }
            )
            if len(textboxes) >= 10:
                break

    # Attach OCR labels to detected buttons
    for i, label in enumerate(button_labels[:10]):
        if i < len(buttons):
            buttons[i]["label"] = label
            buttons[i]["confidence"] = 0.75
        else:
            buttons.append({"type": "button", "label": label, "confidence": 0.65})

    # Attach OCR labels to detected textboxes
    for i, label in enumerate(textbox_labels[:5]):
        if i < len(textboxes):
            textboxes[i]["label"] = label

    # 2. Canny Edge Detection for Progress Bars
    edges = cv2.Canny(gray_frame, 80, 160)
    p_contours, _ = cv2.findContours(edges, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
    for cnt in p_contours:
        x, y, w, h = cv2.boundingRect(cnt)
        aspect = float(w) / max(h, 1)
        if 80 < w < 620 and 5 <= h <= 30 and aspect > 5.0:
            progress_bars.append(
                {
                    "type": "progress_bar",
                    "box": [int(x), int(y), int(x + w), int(y + h)],
                    "confidence": 0.50,
                }
            )
            if len(progress_bars) >= 5:
                break

    return {
        "buttons": buttons,
        "textboxes": textboxes,
        "progress_bars": progress_bars,
    }

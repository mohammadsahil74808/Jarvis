"""
Optimizes captured screen images for local OCR.
Inspired by NormCap's enhancement pipeline.
"""
import logging
from collections import Counter
import cv2
import numpy as np
from PIL import Image

logger = logging.getLogger(__name__)

def _get_edge_pixels(image: np.ndarray, num_samples=400) -> list[tuple]:
    """Heuristically find edge colors for padding."""
    h, w = image.shape[:2]
    # top, bottom, left, right edges
    points = [(x, 0) for x in range(w)] + \
             [(x, h - 1) for x in range(w)] + \
             [(0, y) for y in range(h)] + \
             [(w - 1, y) for y in range(h)]
    
    # Cap sample size to save compute
    sample_size = min(len(points), num_samples)
    import random
    points = random.sample(points, sample_size)
    
    edge_pixels = []
    for x, y in points:
        pixel = tuple(image[y, x])
        edge_pixels.append(pixel)
        
    return edge_pixels

def add_padding(image: np.ndarray, padding: int = 80) -> np.ndarray:
    """Pad the image with the most frequent edge color."""
    edge_pixels = _get_edge_pixels(image)
    if not edge_pixels:
        return image
        
    color_count = Counter(edge_pixels)
    bg_color = color_count.most_common(1)[0][0]
    
    # Check if grayscale or color
    if len(image.shape) == 2:
        bg_color = bg_color[0] if isinstance(bg_color, tuple) else bg_color
        padded = cv2.copyMakeBorder(image, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=bg_color)
    else:
        # Convert bg_color to scalar format expected by cv2
        bg_color = [int(c) for c in bg_color]
        padded = cv2.copyMakeBorder(image, padding, padding, padding, padding, cv2.BORDER_CONSTANT, value=bg_color)
        
    return padded

def resize_image(image: np.ndarray, factor: float = 2.0) -> np.ndarray:
    """Resize image to simulate ~300 DPI for Tesseract."""
    width = int(image.shape[1] * factor)
    height = int(image.shape[0] * factor)
    return cv2.resize(image, (width, height), interpolation=cv2.INTER_CUBIC)

def binarize_image(image: np.ndarray) -> np.ndarray:
    """Convert to grayscale and binarize for optimal OCR."""
    if len(image.shape) == 3:
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
    else:
        gray = image
        
    # Apply Otsu's thresholding after Gaussian filtering
    blur = cv2.GaussianBlur(gray, (5, 5), 0)
    _, binary = cv2.threshold(blur, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
    return binary

def enhance_for_ocr(pil_img: Image.Image, resize_factor: float = 2.0, padding: int = 80) -> Image.Image:
    """
    Main pipeline: Resize -> Pad -> Binarize -> Return PIL Image.
    """
    # Convert PIL to cv2 (numpy array)
    cv_img = np.array(pil_img)
    if len(cv_img.shape) == 3 and cv_img.shape[2] == 3:
        # RGB to BGR
        cv_img = cv_img[:, :, ::-1].copy()
    elif len(cv_img.shape) == 3 and cv_img.shape[2] == 4:
        # RGBA to BGR
        cv_img = cv2.cvtColor(cv_img, cv2.COLOR_RGBA2BGR)
        
    # Pipeline
    if resize_factor:
        cv_img = resize_image(cv_img, factor=resize_factor)
    if padding:
        cv_img = add_padding(cv_img, padding=padding)
        
    cv_img = binarize_image(cv_img)
    
    # Back to PIL
    return Image.fromarray(cv_img)

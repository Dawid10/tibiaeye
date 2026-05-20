"""Chat extractors - OCR text extraction from chat lines."""
from typing import List

import cv2
import numpy as np

from .config import GrayImage


def _crop_text_region(line_image: GrayImage) -> GrayImage:
    """Crop to only the columns containing visible text (pixel > 80)."""
    mask = line_image > 80
    cols_with_text = np.any(mask, axis=0)
    if not cols_with_text.any():
        return line_image
    first = np.min(np.where(cols_with_text))
    last = np.max(np.where(cols_with_text))
    return line_image[:, first:last + 1]


def preprocess_for_ocr(line_image: GrayImage) -> GrayImage:
    """Preprocess a chat line image for Tesseract OCR.

    Steps: crop text region, threshold at 100, scale up 3x.
    Chat text is light gray on dark background.
    """
    cropped = _crop_text_region(line_image)
    _, binary = cv2.threshold(cropped, 100, 255, cv2.THRESH_BINARY)
    scaled = cv2.resize(binary, None, fx=3, fy=3, interpolation=cv2.INTER_CUBIC)
    return scaled


def extract_line_text(line_image: GrayImage) -> str:
    """Extract text from a chat line image using Tesseract OCR.

    Returns extracted text string, or empty string on failure.
    """
    try:
        import pytesseract
    except ImportError:
        return ""

    preprocessed = preprocess_for_ocr(line_image)

    try:
        text = pytesseract.image_to_string(preprocessed, config="--psm 7")
        return text.strip()
    except Exception as e:
        print(f"[Chat] OCR extraction failed: {e}")
        return ""


def extract_all_loot_texts(loot_lines: list) -> List[str]:
    """Extract text from all loot line images.

    Args:
        loot_lines: List of (line_image, bbox) tuples from locators.

    Returns:
        List of extracted text strings.
    """
    texts = []
    for line_image, _bbox in loot_lines:
        text = extract_line_text(line_image)
        if text:
            texts.append(text)
    return texts

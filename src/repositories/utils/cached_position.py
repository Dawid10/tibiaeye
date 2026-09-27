"""Check that a remembered UI element is still where we cached it."""
import cv2
import numpy as np

from ...core.constants import CONFIDENCE_UI_DEFAULT


def is_template_at(screenshot: np.ndarray, template: np.ndarray, position,
                   confidence: float = CONFIDENCE_UI_DEFAULT) -> bool:
    """
    One match at the cached spot. Cheap, and catches a switch between window and
    full-screen capture (positions shift ~30px) that a bounds check alone misses.
    """
    x, y, w, h = position
    if x < 0 or y < 0 or y + h > screenshot.shape[0] or x + w > screenshot.shape[1]:
        return False
    patch = screenshot[y:y + h, x:x + w]
    if patch.shape != template.shape:
        return False
    return float(cv2.matchTemplate(patch, template, cv2.TM_CCOEFF_NORMED).max()) >= confidence

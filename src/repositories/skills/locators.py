"""
Skills Locators - Find skills window position.
"""
from typing import Optional, Tuple
import cv2
import numpy as np

from .config import images, hashit
from ...core.constants import CONFIDENCE_UI_DEFAULT

# Cache for skills icon position
_skills_icon_cache = {
    'position': None,
    'hash': None
}


def locate(screenshot: np.ndarray, template: np.ndarray, confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[Tuple[int, int, int, int]]:
    """Locate template in screenshot. Returns (x, y, w, h) or None."""
    if template is None or screenshot is None:
        return None
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        return None

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


def get_skills_icon_position(screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Find the Skills window icon position with AGGRESSIVE caching.

    CPU OPTIMIZATION: The skills icon position NEVER changes during gameplay.
    Once found, we cache it permanently and skip all template matching.
    """
    global _skills_icon_cache

    # OPTIMIZATION: If we have a cached position, use it directly!
    # The icon position doesn't change, so no need to verify with hash every tick.
    if _skills_icon_cache['position'] is not None:
        pos = _skills_icon_cache['position']
        # Only verify bounds (very fast check)
        if (pos[1] + pos[3] <= screenshot.shape[0] and
            pos[0] + pos[2] <= screenshot.shape[1]):
            return _skills_icon_cache['position']
        # Bounds failed = screen changed, clear cache
        _skills_icon_cache['position'] = None

    # Find skills icon (only happens once per session)
    skills_icon = images['icons'].get('skills')
    if skills_icon is None:
        return None

    position = locate(screenshot, skills_icon)
    if position is not None:
        _skills_icon_cache['position'] = position
        print(f"[Skills] Icon found at {position} - cached permanently")

    return position

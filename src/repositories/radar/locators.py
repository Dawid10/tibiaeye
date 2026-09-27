"""
Radar locators - Find radar UI elements on screen.

PyTibia style with caching.
"""
from typing import Optional, Tuple
import cv2
import numpy as np

from . import config as _cfg
from .config import dimensions
from ..utils.cached_position import is_template_at
from ...core.constants import CONFIDENCE_UI_DEFAULT


# Position cache
_radar_tools_pos_cache = None


def get_radar_tools_position(screenshot: np.ndarray, use_cache: bool = True) -> Optional[Tuple[int, int, int, int]]:
    """
    Find radar tools position on screen.

    The radar tools are the buttons below the minimap (center, +/- zoom).

    Args:
        screenshot: Grayscale screenshot
        use_cache: Whether to use cached position

    Returns:
        (x, y, width, height) or None if not found
    """
    global _radar_tools_pos_cache

    _cfg._ensure_loaded()

    template = _cfg.images.get('tools')
    if template is None:
        return None

    # Cached spot is re-checked with one tiny match (capture mode or window may have moved)
    if use_cache and _radar_tools_pos_cache is not None:
        if is_template_at(screenshot, template, _radar_tools_pos_cache):
            return _radar_tools_pos_cache
        _radar_tools_pos_cache = None

    # Template matching
    try:
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val >= CONFIDENCE_UI_DEFAULT:
            pos = (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
            _radar_tools_pos_cache = pos
            return pos
    except cv2.error:
        pass

    return None


def clear_cache():
    """Clear position cache."""
    global _radar_tools_pos_cache
    _radar_tools_pos_cache = None


def clear_all_radar_caches():
    """Clear ALL radar caches (position + coordinates)."""
    global _radar_tools_pos_cache
    _radar_tools_pos_cache = None

    # Also clear the coordinate cache from config
    from .config import coordinates
    coordinates.clear()
    print("[Radar] All caches cleared")

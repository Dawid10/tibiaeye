"""BattleList extractors - content region extraction from screenshot."""
from typing import Optional

import numpy as np

from .typings import BBox, GrayImage
from .config import CONTENT_WIDTH
from .locators import get_icon_position, get_bottom_bar_position

try:
    from numba import njit

    @njit(cache=True)
    def get_creatures_names_images(content: np.ndarray, slot_count: int,
                                   slot_height: int, name_start_x: int,
                                   name_width: int) -> np.ndarray:
        """JIT-optimized extraction of name rows from all slots at once."""
        result = np.zeros((slot_count, name_width), dtype=np.uint8)
        for i in range(slot_count):
            y = 11 + i * slot_height
            if y >= content.shape[0]:
                break
            x_end = min(content.shape[1], name_start_x + name_width)
            width = x_end - name_start_x
            if width <= 0:
                break
            for j in range(width):
                result[i, j] = content[y, name_start_x + j]
        return result

    _dummy = np.zeros((220, 156), dtype=np.uint8)
    get_creatures_names_images(_dummy, 1, 22, 23, 115)
    NUMBA_EXTRACTORS_AVAILABLE = True
except ImportError:
    NUMBA_EXTRACTORS_AVAILABLE = False

    def get_creatures_names_images(content: np.ndarray, slot_count: int,
                                   slot_height: int, name_start_x: int,
                                   name_width: int) -> np.ndarray:
        """Pure-Python fallback for name row extraction."""
        result = np.zeros((slot_count, name_width), dtype=np.uint8)
        for i in range(slot_count):
            y = 11 + i * slot_height
            if y >= content.shape[0]:
                break
            x_end = min(content.shape[1], name_start_x + name_width)
            width = x_end - name_start_x
            if width <= 0:
                break
            result[i, :width] = content[y, name_start_x:x_end]
        return result


def get_content(screenshot: GrayImage,
                icon_image: Optional[GrayImage],
                bottom_bar_image: Optional[GrayImage],
                cache: dict,
                confidence: float) -> Optional[GrayImage]:
    """Extract battlelist content region between icon and bottom bar."""
    icon_pos = get_icon_position(screenshot, icon_image, cache, confidence)
    if icon_pos is None:
        return None

    x, y, w, h = icon_pos
    content_x = x - 1
    content_y = y + h + 1

    if content_y >= screenshot.shape[0] or content_x < 0:
        return None

    content = screenshot[content_y:, content_x:content_x + CONTENT_WIDTH]

    bottom_pos = get_bottom_bar_position(content, bottom_bar_image, confidence)
    if bottom_pos is None:
        return content[:220, :]

    content_end = bottom_pos[1] - 11
    if content_end <= 0:
        return None
    return content[:content_end, :]

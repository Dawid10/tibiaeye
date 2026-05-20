"""BattleList locators - find icon and bottom bar positions via template matching."""
from typing import Dict, Optional

import cv2

from .typings import BBox, GrayImage
from ...core.constants import CONFIDENCE_UI_DEFAULT


def locate(screenshot: GrayImage, template: GrayImage,
           confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[BBox]:
    """Locate template in screenshot via matchTemplate."""
    if template is None or screenshot is None:
        return None
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        return None

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val < confidence:
        return None
    return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])


def get_icon_position(screenshot: GrayImage,
                      icon_image: Optional[GrayImage],
                      cache: Dict[str, object],
                      confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[BBox]:
    """Get battlelist icon position with permanent cache."""
    if icon_image is None:
        return None

    cached_pos = cache.get('icon_pos')
    if cached_pos is not None:
        x, y, w, h = cached_pos
        if y + h <= screenshot.shape[0] and x + w <= screenshot.shape[1]:
            return cached_pos
        cache['icon_pos'] = None

    pos = locate(screenshot, icon_image, confidence)
    if pos is not None:
        cache['icon_pos'] = pos
        print(f"[BattleList] Icon found at {pos} - cached permanently")
    return pos


def get_bottom_bar_position(content: GrayImage,
                            bottom_bar_image: Optional[GrayImage],
                            confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[BBox]:
    """Find bottom bar in content region."""
    return locate(content, bottom_bar_image, confidence)

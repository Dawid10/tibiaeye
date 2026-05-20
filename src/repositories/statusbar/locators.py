from typing import Optional, Tuple

import cv2
import numpy as np

from ...core.constants import CONFIDENCE_UI_DEFAULT
from ...utils.hash import cache_object_position
from .config import images


def locate(screenshot: np.ndarray, template: np.ndarray,
           confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[Tuple[int, int, int, int]]:
    if template is None or screenshot is None:
        return None
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        return None

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


@cache_object_position
def get_hp_icon_position(screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    pos = locate(screenshot, images['icons']['hp'])
    if pos is not None:
        return pos
    return locate(screenshot, images['icons']['hp_macos'])


@cache_object_position
def get_mana_icon_position(screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    return locate(screenshot, images['icons']['mana'])

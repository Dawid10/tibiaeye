"""Chase Opponent button state, read from the combat controls next to the minimap."""
from typing import Optional, Tuple

import numpy as np

from ..core.constants import (
    CHASE_BUTTON_OFFSET_FROM_RADAR_TOOLS, CHASE_BUTTON_BOX,
    CHASE_BUTTON_MIN_GREEN_PIXELS, CHASE_BUTTON_GREEN_MARGIN,
)


def count_chase_button_green(screenshot_bgr: np.ndarray,
                             radar_tools_pos: Tuple[int, int, int, int]) -> Optional[int]:
    """Green pixels on the running-figure button (it turns green when chase is on)."""
    center_x = radar_tools_pos[0] + CHASE_BUTTON_OFFSET_FROM_RADAR_TOOLS[0]
    center_y = radar_tools_pos[1] + CHASE_BUTTON_OFFSET_FROM_RADAR_TOOLS[1]
    half = CHASE_BUTTON_BOX // 2
    box = screenshot_bgr[center_y - half:center_y + half + 1, center_x - half:center_x + half + 1]
    if box.size == 0:
        return None
    pixels = box.reshape(-1, 3).astype(np.int16)
    blue, green, red = pixels[:, 0], pixels[:, 1], pixels[:, 2]
    is_green = (green > red + CHASE_BUTTON_GREEN_MARGIN) & (green > blue + CHASE_BUTTON_GREEN_MARGIN)
    return int(np.count_nonzero(is_green))


def is_chase_mode_on(green_pixels: int) -> bool:
    return green_pixels >= CHASE_BUTTON_MIN_GREEN_PIXELS

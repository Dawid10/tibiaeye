from typing import Tuple

import numpy as np

from .config import BAR_SIZE


def get_hp_bar(screenshot: np.ndarray, icon_pos: Tuple[int, int, int, int]) -> np.ndarray:
    y = icon_pos[1] + 5
    x = icon_pos[0] + 13
    return screenshot[y, x:x + BAR_SIZE]


def get_mana_bar(screenshot: np.ndarray, icon_pos: Tuple[int, int, int, int]) -> np.ndarray:
    y = icon_pos[1] + 5
    x = icon_pos[0] + 13
    return screenshot[y, x:x + BAR_SIZE]

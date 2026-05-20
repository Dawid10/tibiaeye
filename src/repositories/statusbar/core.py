from typing import Optional, Tuple

import numpy as np

from ..core import PlayerStatus, get_screen_capture
from .config import BAR_SIZE
from .extractors import get_hp_bar, get_mana_bar
from .locators import get_hp_icon_position, get_mana_icon_position


# Adaptive bar reading: uses the reference brightness of the first filled pixels
# to find where the bar transitions to empty. Works across capture card and
# screen capture (different color spaces) without needing a fixed color list.
_DROP_THRESHOLD = 12


def get_filled_percentage(bar) -> int:
    """Calculate filled percentage using adaptive threshold.

    Uses pixels 5-10 as reference (always filled), then finds where
    3 consecutive pixels drop below reference - _DROP_THRESHOLD.
    """
    bar_len = len(bar)
    if bar_len < 10:
        return 0

    ref_sum = 0
    for i in range(5, 11):
        ref_sum += int(bar[i])
    ref_mean = ref_sum / 6
    threshold = ref_mean - _DROP_THRESHOLD

    last_filled = bar_len - 1
    for i in range(5, bar_len - 2):
        if int(bar[i]) < threshold and int(bar[i + 1]) < threshold and int(bar[i + 2]) < threshold:
            last_filled = i - 1
            break

    result = (last_filled + 1) * 100 // bar_len
    if result > 100:
        return 100
    return result


def get_hp_percentage(screenshot: np.ndarray) -> Optional[int]:
    pos = get_hp_icon_position(screenshot)
    if pos is None:
        return None
    bar = get_hp_bar(screenshot, pos)
    return get_filled_percentage(bar)


def get_mana_percentage(screenshot: np.ndarray) -> Optional[int]:
    pos = get_mana_icon_position(screenshot)
    if pos is None:
        return None
    bar = get_mana_bar(screenshot, pos)
    return get_filled_percentage(bar)


class StatusBarRepository:

    def __init__(self):
        self._screen = get_screen_capture()
        self._last_hp: float = 100.0
        self._last_mp: float = 100.0

    def get_hp_percentage(self, screenshot: np.ndarray = None) -> float:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        result = get_hp_percentage(screenshot)
        if result is None:
            return self._last_hp
        self._last_hp = float(result)
        return self._last_hp

    def get_mp_percentage(self, screenshot: np.ndarray = None) -> float:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        result = get_mana_percentage(screenshot)
        if result is None:
            return self._last_mp
        self._last_mp = float(result)
        return self._last_mp

    def get_status(self, screenshot: np.ndarray = None) -> PlayerStatus:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        return PlayerStatus(
            hp_percent=self.get_hp_percentage(screenshot),
            mp_percent=self.get_mp_percentage(screenshot),
        )

    def get_both_percentages(self, screenshot: np.ndarray = None) -> Tuple[float, float]:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        return (
            self.get_hp_percentage(screenshot),
            self.get_mp_percentage(screenshot),
        )

    def is_hp_below(self, threshold: float, screenshot: np.ndarray = None) -> bool:
        return self.get_hp_percentage(screenshot) < threshold

    def is_mp_below(self, threshold: float, screenshot: np.ndarray = None) -> bool:
        return self.get_mp_percentage(screenshot) < threshold

    def is_critical(self, hp_threshold: float = 30.0, screenshot: np.ndarray = None) -> bool:
        return self.is_hp_below(hp_threshold, screenshot)

    def needs_heal(self, hp_threshold: float = 70.0, screenshot: np.ndarray = None) -> bool:
        return self.is_hp_below(hp_threshold, screenshot)

    def needs_mana(self, mp_threshold: float = 50.0, screenshot: np.ndarray = None) -> bool:
        return self.is_mp_below(mp_threshold, screenshot)

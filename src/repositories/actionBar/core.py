"""
Action Bar Repository - extracts item counts from action bar slots.

Uses the PyTibia algorithm: hash-based matching with 1x4 pixel columns.
"""
import math
import pathlib
from typing import Dict, Optional, Tuple

import cv2
import numpy as np
try:
    from farmhash import hash64 as farmhash64
except ImportError:
    import hashlib
    def farmhash64(data) -> int:
        return int(hashlib.md5(data).hexdigest()[:16], 16)

from ..core import get_screen_capture
from ...core.constants import CONFIDENCE_UI_DEFAULT
from ...utils.image_resolver import resolve_image, glob_images


# Paths relative to this file
CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
ACTIONBAR_IMAGES_PATH = CURRENT_PATH / "images"


def _hashit(arr: np.ndarray) -> int:
    """Create a hash from numpy array."""
    return farmhash64(np.ascontiguousarray(arr))


def _load_gray_image(path: str) -> Optional[np.ndarray]:
    """Load image as grayscale."""
    if not pathlib.Path(path).exists():
        return None
    img = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
    return img


def _locate(img: np.ndarray, template: np.ndarray, confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[Tuple[int, int, int, int]]:
    """Locate template in image. Returns (x, y, w, h) or None."""
    if template is None or img is None:
        return None
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return None

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


class ActionBarRepository:
    """
    Repository for reading item counts from action bar slots.

    Uses PyTibia's algorithm: hash-based matching with 1x4 pixel column templates.
    """

    # Slot dimensions (from PyTibia)
    SLOT_WIDTH = 34
    SLOT_SPACING = 2

    def __init__(self):
        self._screen = get_screen_capture()

        # Load arrow templates
        self._left_arrows = _load_gray_image(str(resolve_image(ACTIONBAR_IMAGES_PATH, "arrows/left.png")))
        self._right_arrows = _load_gray_image(str(resolve_image(ACTIONBAR_IMAGES_PATH, "arrows/right.png")))

        # Build digit hash lookup table (hash -> digit value)
        self._digit_hashes: Dict[int, int] = {}
        self._load_digit_hashes()

        # Position cache
        self._left_arrows_pos: Optional[Tuple[int, int, int, int]] = None

        if self._left_arrows is not None:
            print(f"ActionBar: Loaded {len(self._digit_hashes)} digit hashes from {ACTIONBAR_IMAGES_PATH}")
        else:
            print(f"ActionBar: WARNING - Arrow templates not found at {arrows_path}")

    def _load_digit_hashes(self) -> None:
        """Load digit templates (1x4 columns) and build hash lookup."""
        for digit in range(10):
            # Load main template
            img = _load_gray_image(str(resolve_image(ACTIONBAR_IMAGES_PATH, f"digits/{digit}.png")))
            if img is not None:
                img_hash = _hashit(img)
                self._digit_hashes[img_hash] = digit

            # Load alternate templates (e.g., 9_alt1.png, 9_alt2.png)
            for alt_file in glob_images(ACTIONBAR_IMAGES_PATH, "digits", f"{digit}_alt*.png"):
                img = _load_gray_image(str(alt_file))
                if img is not None:
                    img_hash = _hashit(img)
                    self._digit_hashes[img_hash] = digit

    def _get_left_arrows_position(self, screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
        """Find left arrows position with caching."""
        if self._left_arrows is None:
            return None

        if self._left_arrows_pos is not None:
            return self._left_arrows_pos

        pos = _locate(screenshot, self._left_arrows, confidence=CONFIDENCE_UI_DEFAULT)
        if pos is not None:
            self._left_arrows_pos = pos

        return pos

    def get_slot_count(self, screenshot: np.ndarray, slot: int) -> Optional[int]:
        """
        Get item count from an action bar slot.

        Uses PyTibia's exact algorithm:
        1. Find left arrows position
        2. Calculate slot X position
        3. Extract 34x34 slot image
        4. Extract digits region [24:32, 2:32]
        5. Read digits right-to-left using hash lookup

        Args:
            screenshot: Grayscale screenshot
            slot: Slot number (1-based, 1 = first slot)

        Returns:
            Item count or None if not detected
        """
        left_pos = self._get_left_arrows_position(screenshot)
        if left_pos is None:
            return None

        # Calculate slot X position (from PyTibia formula)
        # x0 = leftSideArrowsPos[0] + leftSideArrowsPos[2] + (slot * 2) + ((slot - 1) * 34)
        x0 = left_pos[0] + left_pos[2] + (slot * self.SLOT_SPACING) + ((slot - 1) * self.SLOT_WIDTH)
        y0 = left_pos[1]

        # Bounds check
        if x0 < 0 or y0 < 0:
            return None
        if y0 + self.SLOT_WIDTH > screenshot.shape[0]:
            return None
        if x0 + self.SLOT_WIDTH > screenshot.shape[1]:
            return None

        # Extract slot image (34x34)
        slot_image = screenshot[y0:y0 + self.SLOT_WIDTH, x0:x0 + self.SLOT_WIDTH]

        # Extract digits region (from PyTibia: [24:32, 2:32])
        digits = slot_image[24:32, 2:32]

        # Read digits right to left (units, tens, hundreds, etc.)
        count = 0
        for i in range(5):  # Max 5 digits (99999)
            # Position of digit column (from PyTibia formula)
            x = ((6 * (5 - i)) - 3)
            if x < 0 or x >= digits.shape[1]:
                continue

            # Extract single digit column (4 rows, 1 column) - from PyTibia: digits[2:6, x:x+1]
            digit_col = digits[2:6, x:x + 1]

            # Look up hash in digit dictionary
            col_hash = _hashit(digit_col)
            number = self._digit_hashes.get(col_hash, None)

            if number is None:
                continue

            # Add to count (rightmost digit is ones, then tens, etc.)
            count += int(number * math.pow(10, i))

        return count if count > 0 else None

    def get_health_potions(self, screenshot: np.ndarray = None) -> Optional[int]:
        """Get health potion count (slot 1 by default)."""
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        return self.get_slot_count(screenshot, 1)

    def get_mana_potions(self, screenshot: np.ndarray = None) -> Optional[int]:
        """Get mana potion count (slot 2 by default)."""
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)
        return self.get_slot_count(screenshot, 2)

    def clear_cache(self) -> None:
        """Clear position cache to force re-detection."""
        self._left_arrows_pos = None

    @property
    def is_configured(self) -> bool:
        """Check if arrow templates are loaded."""
        return self._left_arrows is not None and len(self._digit_hashes) > 0



import pathlib

import numpy as np

from ...utils.hash import load_gray_image
from ...utils.image_resolver import resolve_image


CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"

BAR_SIZE = 94

# Base colors for HP/mana bars (exact values from macOS/direct capture)
_HP_BASE = [79, 118, 121, 110, 62]
_MANA_BASE = [68, 95, 97, 89, 52]

# Expand each base color with ±tolerance to handle capture card color distortion
_COLOR_TOLERANCE = 15

def _expand_colors(base_colors, tolerance):
    expanded = set()
    for c in base_colors:
        for offset in range(-tolerance, tolerance + 1):
            val = c + offset
            if 0 <= val <= 255:
                expanded.add(val)
    return np.array(sorted(expanded), dtype=np.uint8)

HP_BAR_COLORS = _expand_colors(_HP_BASE, _COLOR_TOLERANCE)
MANA_BAR_COLORS = _expand_colors(_MANA_BASE, _COLOR_TOLERANCE)

images = {
    'icons': {
        'hp': load_gray_image(str(resolve_image(IMAGES_PATH, "heart.png"))),
        'hp_macos': load_gray_image(str(resolve_image(IMAGES_PATH, "heart_macos.png"))),
        'mana': load_gray_image(str(resolve_image(IMAGES_PATH, "mana.png"))),
    }
}

"""GameWindow configuration - images, resolutions, constants."""
import pathlib
from typing import Dict, Optional

import cv2
import numpy as np

from ...utils.image_resolver import resolve_image


CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"

GAME_WINDOW_SIZES = {
    720: (480, 352),
    1080: (960, 704)
}

RESOLUTIONS = {
    720: {'slotWidth': 32},
    1080: {'slotWidth': 64},
}

GRID_WIDTH = 15
GRID_HEIGHT = 11
PLAYER_SLOT_X = 7
PLAYER_SLOT_Y = 5

BAR_WIDTH = 27
BAR_HEIGHT = 4
BLACK_THRESHOLD = 30
BAR_MIN_DARK_RATIO = 0.80  # 80% of bar border pixels must be dark (tolerates capture card blur)
BAR_MIN_VERTICAL_GAP = 16  # min pixels between bars vertically (real bars are 32-64px apart, lava noise is 1-3px)
BAR_MIN_INTERIOR_CONTRAST = 20  # min brightness difference between interior and border rows

NAME_HEIGHT = 13
NAME_LEFT_OFFSET = 50
NAME_RIGHT_OFFSET = 90

UNDER_ROOF_PIXEL_VALUE = 192

IGNORED_PIXEL_VALUES = (0, 113, 29, 57, 91, 152, 170, 192)

# OCR constants
CHAR_ATLAS_DIR = "char_atlas"
CHAR_ATLAS_FILE = "char_atlas.json"
OCR_BINARIZE_THRESHOLD = 120
OCR_CORE_ROWS = (3, 9)
OCR_MERGE_GAP = 1
OCR_MIN_CHAR_WIDTH = 2
OCR_GLYPH_HEIGHT = 6
OCR_SPACE_GAP = 4


def load_gray_image(path: str) -> Optional[np.ndarray]:
    if not pathlib.Path(path).exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def load_arrow_images() -> Dict[str, np.ndarray]:
    arrows = {}

    arrow_names = [
        'leftGameWindow00', 'leftGameWindow01', 'leftGameWindow10', 'leftGameWindow11',
        'rightGameWindow00', 'rightGameWindow01', 'rightGameWindow10', 'rightGameWindow11'
    ]

    for name in arrow_names:
        img = load_gray_image(str(resolve_image(IMAGES_PATH, f"arrows/{name}.png")))
        if img is not None:
            arrows[name] = img

    return arrows


def load_monster_templates(monsters_folder: str = None) -> Dict[str, np.ndarray]:
    folder = pathlib.Path(monsters_folder or str(IMAGES_PATH / "monsters"))
    if not folder.exists():
        return {}

    templates = {}
    for img_path in folder.glob("*.png"):
        name = img_path.stem
        img = load_gray_image(str(img_path))
        if img is not None:
            templates[name] = img

    if templates:
        print(f"[GameWindow] Loaded {len(templates)} monster templates")

    return templates

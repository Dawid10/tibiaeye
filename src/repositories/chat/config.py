"""Chat repository configuration - paths, constants, template loading."""
import pathlib
from typing import Dict, Optional

import cv2
import numpy as np

from ...utils.image_resolver import resolve_image, glob_images

GrayImage = np.ndarray

# ============================================
# PATH CONSTANTS
# ============================================
IMAGES_PATH = pathlib.Path(__file__).parent / "images"

# ============================================
# CHAT LAYOUT CONSTANTS
# ============================================
LOOT_LINE_HEIGHT = 14
CHAT_TAB_WIDTH = 92
LOOT_OF_PREFIX = "Loot of "


def load_gray_image(path: pathlib.Path) -> Optional[GrayImage]:
    """Load image as grayscale. Returns None if not found."""
    if not path.exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def load_loot_of_template() -> Optional[GrayImage]:
    """Load 'Loot of' text template for matching."""
    return load_gray_image(resolve_image(IMAGES_PATH, "loot_of_text.png"))


def load_nothing_template() -> Optional[GrayImage]:
    """Load 'nothing' text template for filtering empty loot."""
    return load_gray_image(resolve_image(IMAGES_PATH, "nothing_text.png"))


def load_tab_templates() -> Dict[str, GrayImage]:
    """Load loot tab template images."""
    tabs = {}
    for img_path in glob_images(IMAGES_PATH, "tabs"):
        img = load_gray_image(img_path)
        if img is not None:
            tabs[img_path.stem] = img
    return tabs

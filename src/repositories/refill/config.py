"""
Refill Repository Config - Constants and paths.
"""
import pathlib

import cv2
import numpy as np

from ...utils.image_resolver import resolve_image, glob_images


CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"

# Trade window dimensions
# Note: New Tibia UI has wider trade window (~450+ pixels)
TRADE_WINDOW_WIDTH = 500
TRADE_WINDOW_HEIGHT = 14  # Height of the title bar

# Item list configuration
ITEM_HEIGHT = 20  # Height of each item row
ITEM_START_Y = 22  # Y offset from trade window top to first item
MAX_VISIBLE_ITEMS = 8  # Maximum visible items in trade window

# Amount input position (relative to trade window)
AMOUNT_INPUT_X = 90
AMOUNT_INPUT_Y = 200

# Buy button position (relative to trade window)
BUY_BUTTON_X = 50
BUY_BUTTON_Y = 220


def load_gray_image(path: str) -> np.ndarray:
    """Load image as grayscale."""
    if not pathlib.Path(path).exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def load_color_image(path: str) -> np.ndarray:
    """Load image in BGR color."""
    if not pathlib.Path(path).exists():
        return None
    return cv2.imread(str(path))


# Pre-load UI templates
images = {
    'ui': {},
    'potions': {}
}


def _load_ui(name, key):
    path = resolve_image(IMAGES_PATH, f"ui/{name}")
    if path.exists():
        images['ui'][key] = load_gray_image(str(path))
        print(f"Refill: Loaded {name}")


_load_ui("npcTradeBar.png", "tradeBar")
_load_ui("npcTradeOk.png", "okButton")
_load_ui("npcTradeSearch.png", "searchBox")
_load_ui("npcTradeAmount.png", "amountInput")
_load_ui("npcTradeBuy.png", "buyButton")

# Load potion templates
for potion_file in glob_images(IMAGES_PATH, "potions"):
    potion_name = potion_file.stem
    images['potions'][potion_name] = load_gray_image(str(potion_file))

print(f"Refill config loaded: {len(images['potions'])} potion templates")

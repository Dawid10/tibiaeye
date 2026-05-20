"""
Inventory Repository Config - Constants and paths.
"""
import pathlib

import cv2
import numpy as np

from ...utils.image_resolver import glob_images


CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"

# Container window dimensions
CONTAINER_HEADER_HEIGHT = 14
CONTAINER_WIDTH = 176
SLOT_SIZE = 32
SLOT_SPACING = 2
SLOTS_PER_ROW = 4

# Container expansion
CONTAINER_EXPANDED_HEIGHT = 208  # Height in pixels when container shows all 20 slots (5 rows)

# Container offsets
CONTAINER_CONTENT_Y = 22  # Y offset from container top to first slot
CLOSE_BUTTON_OFFSET_X = -12  # X offset from right edge
CLOSE_BUTTON_OFFSET_Y = 3


def load_gray_image(path: str) -> np.ndarray:
    """Load image as grayscale."""
    if not pathlib.Path(path).exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


# Pre-load container templates
images = {
    'containers': {},
    'slots': {},
    'ui': {}
}

# Load container title bar templates
for container_file in glob_images(IMAGES_PATH, "containers"):
    container_name = container_file.stem.lower()
    images['containers'][container_name] = load_gray_image(str(container_file))

# Load slot item templates (backpack icons, stash, etc.)
for slot_file in glob_images(IMAGES_PATH, "slots"):
    slot_name = slot_file.stem.lower()
    images['slots'][slot_name] = load_gray_image(str(slot_file))

# Load UI elements (close button, depot icon, etc.)
for ui_file in glob_images(IMAGES_PATH, "ui"):
    ui_name = ui_file.stem.lower()
    images['ui'][ui_name] = load_gray_image(str(ui_file))

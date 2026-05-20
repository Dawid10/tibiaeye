"""BattleList configuration - paths, constants, image/hash loading."""
import json
import pathlib
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .typings import GrayImage
from ..utils.hash import hashit, normalize_text_pixels, CreatureHashTable
from ..utils.hash_tracker import record_hash_learned

from ...utils.image_resolver import resolve_image, glob_images

# ============================================
# PATH CONSTANTS
# ============================================
IMAGES_PATH = pathlib.Path(__file__).parent / "images"
MONSTERS_PATH = str(IMAGES_PATH / "monsters")
SKULLS_PATH = IMAGES_PATH / "skulls"
LEARNED_HASHES_PATH = IMAGES_PATH / "learned_hashes.json"

# ============================================
# SLOT LAYOUT CONSTANTS
# ============================================
SLOT_HEIGHT = 22
CONTENT_WIDTH = 156
SLOT_START_Y = 11
NAME_START_X = 23
NAME_WIDTH = 115

# ============================================
# PIXEL VALUES
# ============================================
TEXT_PIXEL_VALUES = (192, 247)
TEXT_PIXEL_THRESHOLD = 150  # Pixel > threshold = text (capture card tolerant)
ATTACK_PIXEL_VALUES = (76, 166)
ATTACK_PIXEL_TOLERANCE = 15


def load_gray_image(path: pathlib.Path) -> Optional[GrayImage]:
    """Load image as grayscale."""
    if not path.exists():
        print(f"Warning: Image not found: {path}")
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def load_icon_image() -> Optional[GrayImage]:
    """Load battlelist icon image."""
    return load_gray_image(resolve_image(IMAGES_PATH, "icons/battleList.png"))


def load_bottom_bar_image() -> Optional[GrayImage]:
    """Load bottom bar image."""
    return load_gray_image(resolve_image(IMAGES_PATH, "containers/bottomBar.png"))


def load_skull_images() -> Dict[str, GrayImage]:
    """Load all skull template images from skulls directory."""
    skulls = {}
    for img_path in glob_images(IMAGES_PATH, "skulls"):
        img = load_gray_image(img_path)
        if img is not None:
            skulls[img_path.stem] = img
    return skulls


def extract_name_row_from_image(img: GrayImage) -> Optional[np.ndarray]:
    """Extract normalized name row from creature name image."""
    if img.shape[0] < 9:
        return None
    width = min(img.shape[1], NAME_WIDTH)
    row = img[8, 0:width]
    return normalize_text_pixels(row, NAME_WIDTH)


def build_name_hash_table(monsters_folder: str) -> Tuple[Dict[int, str], set]:
    """Build hash table mapping FarmHash64 -> creature name.

    Returns (name_hashes, collided_hashes) where collided_hashes contains
    hashes that map to multiple creature names. These must use template
    matching fallback instead of hash lookup.
    """
    monsters_path = pathlib.Path(monsters_folder)
    if not monsters_path.exists():
        return {}, set()

    name_hashes: Dict[int, str] = {}
    collided_hashes: set = set()
    for img_path in monsters_path.glob("*.png"):
        name = img_path.stem
        img = load_gray_image(img_path)
        if img is None or img.shape[0] < 9:
            continue
        name_row = extract_name_row_from_image(img)
        if name_row is not None:
            name_hash = hashit(name_row)
            if name_hash in name_hashes and name_hashes[name_hash] != name:
                collided_hashes.add(name_hash)
                print(f"[BattleList] Hash collision: '{name}' and '{name_hashes[name_hash]}' "
                      f"share hash {name_hash} — will use template matching")
            name_hashes[name_hash] = name

    if name_hashes:
        print(f"[BattleList] Built hash table with {len(name_hashes)} creatures"
              f"{f' ({len(collided_hashes)} collisions)' if collided_hashes else ''}")
    return name_hashes, collided_hashes


def load_learned_hashes(name_hashes: Dict[int, str],
                        path: pathlib.Path = LEARNED_HASHES_PATH) -> None:
    """Load learned hashes from JSON and merge into name_hashes dict."""
    if not path.exists():
        return
    try:
        with open(path, 'r') as f:
            learned = json.load(f)
        count = 0
        for hash_str, name in learned.items():
            hash_int = int(hash_str)
            if hash_int not in name_hashes:
                name_hashes[hash_int] = name
                count += 1
        if count > 0:
            print(f"[BattleList] Loaded {count} learned hashes from screen captures")
    except Exception as e:
        print(f"[BattleList] Warning: Could not load learned hashes: {e}")


def save_learned_hash(hash_value: int, name: str,
                      path: pathlib.Path = LEARNED_HASHES_PATH) -> None:
    """Save a learned hash to the JSON file."""
    try:
        learned = {}
        if path.exists():
            with open(path, 'r') as f:
                learned = json.load(f)

        hash_str = str(hash_value)
        if hash_str in learned:
            return

        learned[hash_str] = name
        with open(path, 'w') as f:
            json.dump(learned, f, indent=2)

        record_hash_learned(name, 'BL')
        print(f"[BattleList] Learned new hash for '{name}' - next time will be O(1)!")
    except Exception:
        pass


def load_templates(monsters_folder: str) -> List[dict]:
    """Load monster template images for fallback matching."""
    monsters_path = pathlib.Path(monsters_folder)
    if not monsters_path.exists():
        return []

    templates = []
    for img_path in monsters_path.glob("*.png"):
        name = img_path.stem
        img = load_gray_image(img_path)
        if img is not None:
            templates.append({'name': name, 'image': img})
    return templates

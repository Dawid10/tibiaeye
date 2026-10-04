"""
Battle List Repository - PyTibia style with auto-detection and FarmHash64.

Pure functions at module level + thin BattleListRepository facade class.
"""
import pathlib
from typing import Dict, Iterator, List, Optional, Tuple

import cv2
import numpy as np

from .typings import GrayImage, BBox
from .config import (
    IMAGES_PATH, MONSTERS_PATH, LEARNED_HASHES_PATH,
    SLOT_HEIGHT, CONTENT_WIDTH, SLOT_START_Y, NAME_START_X, NAME_WIDTH,
    TEXT_PIXEL_VALUES, TEXT_PIXEL_THRESHOLD, ATTACK_PIXEL_VALUES, ATTACK_PIXEL_TOLERANCE,
    load_gray_image, load_icon_image, load_bottom_bar_image,
    load_skull_images, extract_name_row_from_image,
    build_name_hash_table, load_learned_hashes, save_learned_hash,
    load_templates,
)
from .locators import locate, get_icon_position, get_bottom_bar_position
from .extractors import get_content
from ..core import (
    Creature,
    CreatureType,
    HPColor,
    get_screen_capture
)
from ..utils.hash import hashit, normalize_text_pixels, CreatureHashTable, FARMHASH_AVAILABLE
from ...core.constants import CONFIDENCE_CREATURE, CONFIDENCE_UI_DEFAULT, UNIDENTIFIED_CREATURE_NAME


# ============================================
# JIT-optimized functions
# ============================================
try:
    from numba import njit

    @njit(cache=True)
    def _count_filled_slots_jit(content: np.ndarray, slot_height: int,
                                 slot_start_y: int, name_start_x: int,
                                 text_val_1: int, text_val_2: int) -> int:
        """JIT-optimized slot counting. Speedup: 2-4x over pure Python."""
        max_slots = len(content) // slot_height
        filled = 0
        for slot_idx in range(max_slots):
            y_base = slot_height * slot_idx
            check_offsets = np.array([11, 10, 4, 5], dtype=np.int32)
            found = False
            for i in range(4):
                check_y = y_base + check_offsets[i]
                if check_y >= len(content):
                    break
                if name_start_x >= content.shape[1]:
                    break
                # Check a small horizontal range for text pixels (not just 1 pixel)
                for dx in range(0, 10):
                    cx = name_start_x + dx
                    if cx >= content.shape[1]:
                        break
                    pixel = content[check_y, cx]
                    if pixel >= text_val_1:
                        found = True
                        break
                if found:
                    break
            if found:
                filled += 1
            else:
                break
        return filled

    @njit(cache=True)
    def get_being_attacked_creatures_jit(content: np.ndarray,
                                          slot_count: int,
                                          slot_height: int,
                                          attack_val_1: int,
                                          attack_val_2: int) -> np.ndarray:
        """JIT-optimized attack detection. Returns bool array, early exit after first."""
        result = np.zeros(slot_count, dtype=np.bool_)
        for slot_idx in range(slot_count):
            y = slot_idx * slot_height
            corners_y = np.array([y, y, y + 19, y + 19], dtype=np.int32)
            corners_x = np.array([0, 19, 0, 19], dtype=np.int32)
            attacked = True
            for c in range(4):
                cy = corners_y[c]
                cx = corners_x[c]
                if cy >= content.shape[0] or cx >= content.shape[1]:
                    attacked = False
                    break
                pixel = content[cy, cx]
                if pixel != attack_val_1 and pixel != attack_val_2:
                    attacked = False
                    break
            if attacked:
                result[slot_idx] = True
                break
        return result

    _jit_warmed_up = False

    def _warmup_jit():
        global _jit_warmed_up
        if _jit_warmed_up:
            return
        _dummy = np.zeros((220, 156), dtype=np.uint8)
        _count_filled_slots_jit(_dummy, 22, 11, 23, 150, 247)
        get_being_attacked_creatures_jit(_dummy, 1, 22, 76, 166)
        _jit_warmed_up = True

    NUMBA_BATTLELIST_AVAILABLE = True
except ImportError:
    NUMBA_BATTLELIST_AVAILABLE = False


# ============================================
# Module-level pure functions
# ============================================

def get_filled_slots_count(content: GrayImage,
                           slot_height: int = SLOT_HEIGHT,
                           slot_start_y: int = SLOT_START_Y,
                           name_start_x: int = NAME_START_X,
                           text_pixel_values: Tuple[int, int] = TEXT_PIXEL_VALUES) -> int:
    """Count filled slots in battle list content."""
    if content is None:
        return 0

    if NUMBA_BATTLELIST_AVAILABLE:
        _warmup_jit()
        return _count_filled_slots_jit(
            content, slot_height, slot_start_y,
            name_start_x, TEXT_PIXEL_THRESHOLD, text_pixel_values[1]
        )

    max_slots = len(content) // slot_height
    filled = 0
    for slot_idx in range(max_slots):
        y = slot_height * slot_idx
        check_positions = [y + 11, y + 10, y + 4, y + 5]
        found = False
        for check_y in check_positions:
            if check_y >= len(content):
                break
            if name_start_x >= content.shape[1]:
                break
            # Check a small horizontal range for text pixels
            for dx in range(10):
                cx = name_start_x + dx
                if cx >= content.shape[1]:
                    break
                pixel = content[check_y, cx]
                if pixel >= text_pixel_values[0]:
                    found = True
                    break
            if found:
                break
        if found:
            filled += 1
        else:
            break
    return filled


_attack_diag_tick = 0

ATTACK_RED_EXCESS_THRESHOLD = 15  # Min avg (R - max(G,B)) across border sample


def is_slot_being_attacked_color(color_content: np.ndarray, slot_idx: int,
                                  slot_height: int = SLOT_HEIGHT,
                                  debug: bool = False) -> bool:
    """Detect attack border via R-channel excess in the color (BGR) content.

    Tibia's attack border is red/orange. In BGR, the attacked border has
    R >> G and R >> B. Non-attacked borders are neutral gray (R ~ G ~ B).
    This works reliably across capture card NV12 color shifts.
    """
    global _attack_diag_tick
    y = slot_idx * slot_height
    if y + 19 >= color_content.shape[0] or color_content.shape[1] < 20:
        return False

    # Sample border pixels: top row, bottom row, left col, right col
    # Skip x=1 (dark gap) and icon interior — use the outer border
    top_row = color_content[y, 0:20]        # (20, 3) BGR
    bot_row = color_content[y + 19, 0:20]
    left_col = color_content[y:y + 20, 0]   # (20, 3)
    right_col = color_content[y:y + 20, 19]

    samples = np.vstack([top_row, bot_row, left_col, right_col])  # (80, 3)
    r = samples[:, 2].astype(np.int16)
    g = samples[:, 1].astype(np.int16)
    b = samples[:, 0].astype(np.int16)

    red_excess = r - np.maximum(g, b)
    avg_excess = float(red_excess.mean())

    attacked = avg_excess > ATTACK_RED_EXCESS_THRESHOLD

    if debug and _attack_diag_tick % 200 == 0:
        print(f"[BL-Color] slot={slot_idx} R_excess={avg_excess:.1f} "
              f"(thresh={ATTACK_RED_EXCESS_THRESHOLD}) -> {'ATTACK' if attacked else 'no'}")

    _attack_diag_tick += 1
    return attacked


def is_slot_being_attacked(content: GrayImage, slot_idx: int,
                           slot_height: int = SLOT_HEIGHT,
                           attack_pixel_values: Tuple[int, int] = ATTACK_PIXEL_VALUES,
                           debug: bool = False) -> bool:
    """Check if creature in slot is being attacked by corner pixels (grayscale fallback)."""
    global _attack_diag_tick
    y = slot_idx * slot_height
    corners = [
        (y, 0), (y, 19),
        (y + 19, 0), (y + 19, 19),
    ]
    pixel_values = []
    all_match = True
    for cy, cx in corners:
        if cy >= content.shape[0] or cx >= content.shape[1]:
            return False
        pixel = content[cy, cx]
        pixel_values.append(int(pixel))
        if not any(abs(int(pixel) - int(v)) <= ATTACK_PIXEL_TOLERANCE for v in attack_pixel_values):
            all_match = False

    if debug and _attack_diag_tick % 200 == 0:
        expected = f"{attack_pixel_values} +-{ATTACK_PIXEL_TOLERANCE}"
        status = "ATTACK" if all_match else "no"
        print(f"[BL-Diag] slot={slot_idx} corners={pixel_values} expected={expected} -> {status}")

    _attack_diag_tick += 1
    return all_match


def get_slot_name_hash(content: GrayImage, slot_index: int,
                       slot_start_y: int = SLOT_START_Y,
                       slot_height: int = SLOT_HEIGHT,
                       name_start_x: int = NAME_START_X,
                       name_width: int = NAME_WIDTH) -> Optional[int]:
    """Fingerprint of the name in one battle list slot (what learned_hashes.json stores)."""
    y = slot_start_y + (slot_index * slot_height)
    x_end = min(content.shape[1], name_start_x + name_width)
    if y >= content.shape[0] or x_end <= name_start_x:
        return None
    return hashit(normalize_text_pixels(content[y, name_start_x:x_end], name_width))


def get_creature_name_by_hash(content: GrayImage, slot_index: int,
                               name_hashes: Dict[int, str],
                               slot_start_y: int = SLOT_START_Y,
                               slot_height: int = SLOT_HEIGHT,
                               name_start_x: int = NAME_START_X,
                               name_width: int = NAME_WIDTH) -> Optional[str]:
    """Hash lookup for creature name. Returns name or None."""
    y = slot_start_y + (slot_index * slot_height)
    if y >= content.shape[0]:
        return None

    x_end = min(content.shape[1], name_start_x + name_width)
    if x_end <= name_start_x:
        return None

    row = content[y, name_start_x:x_end]
    normalized = normalize_text_pixels(row, name_width)
    name_hash = hashit(normalized)
    return name_hashes.get(name_hash)


def get_creature_name_by_template(content: GrayImage, slot_index: int,
                                   templates: List[dict],
                                   slot_height: int = SLOT_HEIGHT,
                                   target_names: List[str] = None,
                                   log_failure: bool = True) -> str:
    """Template matching fallback for creature name identification."""
    if not templates:
        return 'Unknown'

    y_start = slot_index * slot_height
    y_end = y_start + slot_height
    x_start = 20
    x_end = min(content.shape[1], 155)

    if y_end > content.shape[0]:
        return 'Unknown'

    slot_area = content[y_start:y_end, x_start:x_end]

    best_match = None
    best_confidence = CONFIDENCE_CREATURE
    best_score = 0.0
    best_name_for_log = None

    templates_to_check = templates
    if target_names is not None and len(target_names) > 0:
        templates_to_check = [t for t in templates if t['name'].lower() in target_names]

    for template in templates_to_check:
        img = template['image']
        if img.shape[0] > slot_area.shape[0] or img.shape[1] > slot_area.shape[1]:
            continue

        result = cv2.matchTemplate(slot_area, img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        if max_val > best_score:
            best_score = max_val
            best_name_for_log = template['name']

        if max_val > best_confidence:
            best_confidence = max_val
            best_match = template['name']

    if best_match is None and log_failure:
        if best_name_for_log is not None:
            print(f"[BattleList] Template match FAILED: best='{best_name_for_log}' "
                  f"score={best_score:.2f} (need {CONFIDENCE_CREATURE:.2f})")
        else:
            print(f"[BattleList] Template match FAILED: no templates matched at all")

    return best_match if best_match else 'Unknown'


def has_skull(content: GrayImage, slot_index: int,
              skull_images: Dict[str, GrayImage],
              slot_height: int = SLOT_HEIGHT,
              confidence: float = 0.85) -> Optional[str]:
    """Check if creature in slot has a skull. Returns skull color or None."""
    if not skull_images:
        return None

    y_start = slot_index * slot_height
    y_end = y_start + slot_height
    x_start = 0
    x_end = 20

    if y_end > content.shape[0]:
        return None

    slot_area = content[y_start:y_end, x_start:x_end]

    for skull_name, skull_img in skull_images.items():
        if skull_img.shape[0] > slot_area.shape[0] or skull_img.shape[1] > slot_area.shape[1]:
            continue
        result = cv2.matchTemplate(slot_area, skull_img, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        if max_val >= confidence:
            return skull_name
    return None


def is_attacking_some_creature(creatures: List[Creature]) -> bool:
    """Check if any creature in the list is being attacked."""
    for creature in creatures:
        if creature.is_being_attacked:
            return True
    return False


def get_creatures_names(content: GrayImage, slot_count: int,
                        name_hashes: Dict[int, str],
                        slot_start_y: int = SLOT_START_Y,
                        slot_height: int = SLOT_HEIGHT,
                        name_start_x: int = NAME_START_X,
                        name_width: int = NAME_WIDTH) -> Iterator[Optional[str]]:
    """Generator yielding creature names via hash lookup for each slot."""
    for slot_index in range(slot_count):
        yield get_creature_name_by_hash(
            content, slot_index, name_hashes,
            slot_start_y, slot_height, name_start_x, name_width
        )


# ============================================
# BattleListRepository facade
# ============================================

class BattleListRepository:
    """Thin facade delegating to pure functions and config/locators/extractors."""

    # Class-level constants for test compatibility
    SLOT_HEIGHT = SLOT_HEIGHT
    CONTENT_WIDTH = CONTENT_WIDTH
    SLOT_START_Y = SLOT_START_Y
    NAME_START_X = NAME_START_X
    NAME_WIDTH = NAME_WIDTH
    TEXT_PIXEL_VALUES = TEXT_PIXEL_VALUES
    ATTACK_PIXEL_VALUES = ATTACK_PIXEL_VALUES

    def __init__(self,
                 region=None,
                 detection_mode: str = "auto",
                 monsters_folder: str = None,
                 template_confidence: float = CONFIDENCE_UI_DEFAULT,
                 blacklist: List[str] = None):
        self._detection_mode = detection_mode
        self._template_confidence = template_confidence
        self._blacklist = [b.lower() for b in (blacklist or [])]

        self._screen = get_screen_capture()

        self._icon_image = load_icon_image()
        self._bottom_bar_image = load_bottom_bar_image()
        self._skull_images = load_skull_images()

        self._monsters_folder = monsters_folder or MONSTERS_PATH
        self._images_path = IMAGES_PATH

        # Cache dict passed to locator functions
        self._cache: Dict[str, object] = {}

        # FarmHash64 creature name recognition
        self._creature_hash_table = CreatureHashTable(self._monsters_folder)
        self._creature_hash_table.load()

        self._name_hashes, self._collided_hashes = build_name_hash_table(self._monsters_folder)
        load_learned_hashes(self._name_hashes)

        self._learned_hashes_path = LEARNED_HASHES_PATH
        self._unknown_hashes: set = set()  # fingerprints no template matched; skipped until taught

        # Logging dedup
        self._logged_hash_lookups: set = set()
        self._logged_template_matches: set = set()
        self._logged_no_templates_warning: bool = False

        # Monster templates
        self._templates: List[dict] = load_templates(self._monsters_folder)
        self._templates_loaded = True

    # ------------------------------------------
    # Private thin wrappers (test compatibility)
    # ------------------------------------------

    def _load_gray_image(self, path: pathlib.Path) -> Optional[GrayImage]:
        return load_gray_image(path)

    def _hashit(self, arr: np.ndarray) -> int:
        return hashit(arr)

    def _build_name_hash_table(self) -> None:
        self._name_hashes, self._collided_hashes = build_name_hash_table(self._monsters_folder)

    def _load_learned_hashes(self) -> None:
        load_learned_hashes(self._name_hashes, self._learned_hashes_path)

    def _save_learned_hash(self, hash_value: int, name: str) -> None:
        save_learned_hash(hash_value, name, self._learned_hashes_path)

    def _extract_name_row_from_image(self, img: GrayImage) -> Optional[np.ndarray]:
        return extract_name_row_from_image(img)

    def _locate(self, screenshot: GrayImage, template: GrayImage,
                confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[BBox]:
        return locate(screenshot, template, confidence)

    def _get_icon_position(self, screenshot: GrayImage) -> Optional[BBox]:
        cache = getattr(self, '_cache', None)
        if cache is None:
            cache = {}
            # Migrate legacy _cached_icon_pos into new cache dict
            legacy_pos = getattr(self, '_cached_icon_pos', None)
            if legacy_pos is not None:
                cache['icon_pos'] = legacy_pos
            self._cache = cache
        return get_icon_position(
            screenshot, self._icon_image, cache, self._template_confidence
        )

    def _get_bottom_bar_position(self, content: GrayImage) -> Optional[BBox]:
        return get_bottom_bar_position(content, self._bottom_bar_image, self._template_confidence)

    def _get_content(self, screenshot: GrayImage) -> Optional[GrayImage]:
        cache = getattr(self, '_cache', None)
        if cache is None:
            cache = {}
            self._cache = cache
        return get_content(
            screenshot, self._icon_image, self._bottom_bar_image,
            cache, self._template_confidence
        )

    def _get_filled_slots_count(self, content: GrayImage) -> int:
        return get_filled_slots_count(
            content, self.SLOT_HEIGHT, self.SLOT_START_Y,
            self.NAME_START_X, self.TEXT_PIXEL_VALUES
        )

    def _is_slot_being_attacked(self, content: GrayImage, slot_idx: int,
                                color_content: Optional[np.ndarray] = None) -> bool:
        if color_content is not None:
            return is_slot_being_attacked_color(
                color_content, slot_idx, self.SLOT_HEIGHT, debug=True
            )
        return is_slot_being_attacked(
            content, slot_idx, self.SLOT_HEIGHT, self.ATTACK_PIXEL_VALUES,
            debug=True
        )

    def _get_creature_name_by_hash(self, content: GrayImage, slot_index: int,
                                     target_names: List[str] = None) -> str:
        name = get_creature_name_by_hash(
            content, slot_index, self._name_hashes,
            self.SLOT_START_Y, self.SLOT_HEIGHT, self.NAME_START_X, self.NAME_WIDTH
        )

        logged_hash = getattr(self, '_logged_hash_lookups', None)
        if logged_hash is None:
            logged_hash = set()
            self._logged_hash_lookups = logged_hash

        # Skip hash result for collided hashes — force template matching
        if name is not None:
            y = self.SLOT_START_Y + (slot_index * self.SLOT_HEIGHT)
            x_end = min(content.shape[1], self.NAME_START_X + self.NAME_WIDTH)
            row = content[y, self.NAME_START_X:x_end]
            normalized = normalize_text_pixels(row, self.NAME_WIDTH)
            name_hash = hashit(normalized)
            if name_hash in self._collided_hashes:
                name = None
            else:
                if name not in logged_hash:
                    print(f"[BattleList] Hash lookup: '{name}' (O(1))")
                    logged_hash.add(name)
                return name

        # A name that already failed every template stays unknown until taught: skip ~1300 matches per tick
        name_hash = get_slot_name_hash(content, slot_index)
        unknown_hashes = self.__dict__.setdefault('_unknown_hashes', set())
        if name_hash in unknown_hashes:
            return 'Unknown'

        template_name = self._get_creature_name_by_template(content, slot_index, target_names)
        if template_name == 'Unknown' and name_hash is not None and not target_names:
            unknown_hashes.add(name_hash)
            print(f"[BattleList] Unknown name in row {slot_index + 1} - ignored like a player. If it is a monster, "
                  f"name it in Targeting > Unknown Monsters (teach names)")

        logged_tmpl = getattr(self, '_logged_template_matches', None)
        if logged_tmpl is None:
            logged_tmpl = set()
            self._logged_template_matches = logged_tmpl

        if template_name != 'Unknown':
            if template_name not in logged_tmpl:
                print(f"[BattleList] Template matching: '{template_name}' (learning...)")
                logged_tmpl.add(template_name)

            y = self.SLOT_START_Y + (slot_index * self.SLOT_HEIGHT)
            x_end = min(content.shape[1], self.NAME_START_X + self.NAME_WIDTH)
            row = content[y, self.NAME_START_X:x_end]
            normalized = normalize_text_pixels(row, self.NAME_WIDTH)
            name_hash = hashit(normalized)
            # Don't learn collided hashes — would overwrite and cause misidentification
            if name_hash not in self._collided_hashes:
                self._name_hashes[name_hash] = template_name
                self._save_learned_hash(name_hash, template_name)

        return template_name

    def _load_templates(self) -> None:
        if self._templates_loaded:
            return
        self._templates = load_templates(self._monsters_folder)
        self._templates_loaded = True

    def _get_creature_name_by_template(self, content: GrayImage, slot_index: int,
                                        target_names: List[str] = None) -> str:
        warned = getattr(self, '_logged_no_templates_warning', False)

        if not self._templates:
            if target_names and not warned:
                print(f"[BattleList] NO templates found for whitelist: {list(target_names)[:5]}")
                self._logged_no_templates_warning = True
            return 'Unknown'

        templates_to_check = self._templates
        if target_names is not None and len(target_names) > 0:
            templates_to_check = [t for t in self._templates if t['name'].lower() in target_names]
            if len(templates_to_check) == 0 and not warned:
                print(f"[BattleList] NO templates found for whitelist: {list(target_names)[:5]}")
                self._logged_no_templates_warning = True

        return get_creature_name_by_template(
            content, slot_index, templates_to_check, self.SLOT_HEIGHT, log_failure=False
        )

    # ------------------------------------------
    # Public API (unchanged signatures)
    # ------------------------------------------

    def _capture_gray(self) -> GrayImage:
        img = self._screen.capture()
        return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    def get_creatures(self, img: Optional[np.ndarray] = None,
                       target_names: List[str] = None,
                       color_img: Optional[np.ndarray] = None) -> List[Creature]:
        if img is None:
            screenshot = self._capture_gray()
        elif len(img.shape) == 3:
            screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            screenshot = img

        content = self._get_content(screenshot)
        if content is None:
            return []

        # Extract color content for attack detection (R-channel method)
        color_content = None
        if color_img is not None and len(color_img.shape) == 3:
            cached_icon_pos = self._cache.get('icon_pos')
            if cached_icon_pos:
                x, y, w, h = cached_icon_pos
                cx = x - 1
                cy = y + h + 1
                if cy < color_img.shape[0] and cx >= 0:
                    color_content = color_img[cy:cy + content.shape[0],
                                              cx:cx + CONTENT_WIDTH]

        slot_count = self._get_filled_slots_count(content)
        if slot_count == 0:
            return []

        creatures = []

        target_set = None
        if target_names is not None and len(target_names) > 0:
            target_set = set(n.lower() for n in target_names)

        cached_icon_pos = self._cache.get('icon_pos')

        for slot_idx in range(slot_count):
            is_attacked = self._is_slot_being_attacked(content, slot_idx, color_content)
            creature_name = self._get_creature_name_by_hash(content, slot_idx, target_set)

            if cached_icon_pos:
                screen_x = cached_icon_pos[0]
                screen_y = cached_icon_pos[1] + cached_icon_pos[3] + 1 + (slot_idx * self.SLOT_HEIGHT)
            else:
                screen_x = 0
                screen_y = slot_idx * self.SLOT_HEIGHT

            creature_type = CreatureType.MONSTER
            if creature_name == 'Unknown':
                creature_name = UNIDENTIFIED_CREATURE_NAME
                creature_type = CreatureType.PLAYER

            creature = Creature(
                name=creature_name,
                x=screen_x,
                y=screen_y,
                width=self.CONTENT_WIDTH,
                height=self.SLOT_HEIGHT,
                creature_type=creature_type,
                confidence=1.0 if creature_name != UNIDENTIFIED_CREATURE_NAME else 0.5,
                is_being_attacked=is_attacked
            )
            creatures.append(creature)

        return creatures

    def get_unknown_slots(self, screenshot: GrayImage) -> List[Tuple[int, int, GrayImage]]:
        """Battle list rows whose name isn't recognised: (slot_index, name_hash, row_image)."""
        content = self._get_content(screenshot)
        if content is None:
            return []
        unknown = []
        for slot_idx in range(self._get_filled_slots_count(content)):
            if self._get_creature_name_by_hash(content, slot_idx) != 'Unknown':
                continue
            name_hash = get_slot_name_hash(content, slot_idx)
            top = slot_idx * self.SLOT_HEIGHT
            unknown.append((slot_idx, name_hash, content[top:top + self.SLOT_HEIGHT].copy()))
        return unknown

    def get_slot_hash(self, screenshot: GrayImage, slot_index: int) -> Optional[int]:
        content = self._get_content(screenshot)
        if content is None or slot_index >= self._get_filled_slots_count(content):
            return None
        return get_slot_name_hash(content, slot_index)

    def learn_name(self, name_hash: int, name: str) -> None:
        """Recognise this fingerprint as `name` from now on (this instance + learned_hashes.json)."""
        self._name_hashes[name_hash] = name
        self._collided_hashes.discard(name_hash)
        self.__dict__.setdefault('_unknown_hashes', set()).discard(name_hash)
        save_learned_hash(name_hash, name, overwrite=True)

    def is_attacking(self, img: Optional[np.ndarray] = None) -> bool:
        creatures = self.get_creatures(img)
        return is_attacking_some_creature(creatures)

    def get_being_attacked_creature(self, creatures: List[Creature] = None) -> Optional[Creature]:
        if creatures is None:
            creatures = self.get_creatures()
        for creature in creatures:
            if creature.is_being_attacked:
                return creature
        return None

    def get_creature_hp_color(self, creature: Creature) -> HPColor:
        return HPColor.GREEN

    def is_blacklisted(self, name: str) -> bool:
        name_lower = name.lower()
        return any(blocked in name_lower for blocked in self._blacklist)

    def get_valid_targets(self, creatures: List[Creature] = None) -> List[Creature]:
        if creatures is None:
            creatures = self.get_creatures()
        return [c for c in creatures if not self.is_blacklisted(c.name)]

    def get_best_target(self, creatures: List[Creature] = None) -> Optional[Creature]:
        targets = self.get_valid_targets(creatures)
        if not targets:
            return None
        for target in targets:
            if target.is_being_attacked:
                return target
        return targets[0]

    def get_creature_count(self, img: Optional[np.ndarray] = None) -> int:
        if img is None:
            screenshot = self._capture_gray()
        elif len(img.shape) == 3:
            screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            screenshot = img

        content = self._get_content(screenshot)
        if content is None:
            return 0
        return self._get_filled_slots_count(content)

    def capture_template(self, creature_name: str, slot_index: int = 0,
                         screenshot: np.ndarray = None) -> bool:
        if screenshot is None:
            screenshot = self._capture_gray()
        elif len(screenshot.shape) == 3:
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)

        content = self._get_content(screenshot)
        if content is None:
            print(f"[BattleList] capture_template: Could not find battlelist")
            return False

        y_start = slot_index * self.SLOT_HEIGHT
        y_end = y_start + self.SLOT_HEIGHT
        x_start = self.NAME_START_X
        x_end = min(content.shape[1], x_start + self.NAME_WIDTH)

        if y_end > content.shape[0]:
            print(f"[BattleList] capture_template: Slot {slot_index} out of bounds")
            return False

        name_region = content[y_start:y_end, x_start:x_end]

        template_path = pathlib.Path(self._monsters_folder) / f"{creature_name}.png"
        cv2.imwrite(str(template_path), name_region)

        row = content[y_start + 11, x_start:x_end]
        normalized = normalize_text_pixels(row, self.NAME_WIDTH)
        name_hash = hashit(normalized)

        self._name_hashes[name_hash] = creature_name
        self._save_learned_hash(name_hash, creature_name)

        print(f"[BattleList] Template captured: '{creature_name}' -> {template_path}")
        print(f"[BattleList] Hash learned: {name_hash} -> '{creature_name}'")
        return True

    @property
    def is_detected(self) -> bool:
        screenshot = self._capture_gray()
        return self._get_icon_position(screenshot) is not None

    @property
    def template_count(self) -> int:
        return len(self._name_hashes)

    @property
    def template_names(self) -> List[str]:
        return list(self._name_hashes.values())

    @property
    def uses_farmhash(self) -> bool:
        return FARMHASH_AVAILABLE

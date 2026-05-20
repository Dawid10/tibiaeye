"""
Character-level OCR for game window creature name identification.

Two-tier name recognition:
  Tier 1: Whole-name hash (fast path, ~0.1ms) - covers 95%+ after learning
  Tier 2: Character-level OCR (fallback, ~0.5ms) - for never-seen creatures

Both tiers auto-learn from battlelist identifications during gameplay.
"""
import json
import pathlib
import time
from typing import Dict, List, Optional, Tuple

import numpy as np

from ...utils.hash import hashit
from .config import (
    OCR_BINARIZE_THRESHOLD,
    OCR_CORE_ROWS,
    OCR_MERGE_GAP,
    OCR_MIN_CHAR_WIDTH,
    OCR_GLYPH_HEIGHT,
    OCR_SPACE_GAP,
    CHAR_ATLAS_DIR,
    CHAR_ATLAS_FILE,
    IMAGES_PATH,
)
from ...utils.image_resolver import resolve_directory


# ---------------------------------------------------------------------------
# Binarization
# ---------------------------------------------------------------------------

def binarize_name_region(name_region: np.ndarray, threshold: int = OCR_BINARIZE_THRESHOLD) -> np.ndarray:
    """Convert grayscale name region to binary (0/255).

    Text pixels in Tibia creature names are bright (192, 247+).
    Everything below threshold becomes 0 (background), above becomes 255 (text).
    """
    if name_region is None or name_region.size == 0:
        return np.zeros((0, 0), dtype=np.uint8)
    binary = np.zeros_like(name_region, dtype=np.uint8)
    binary[name_region >= threshold] = 255
    return binary


def auto_detect_threshold(name_region: np.ndarray) -> int:
    """Detect binarization threshold using Otsu's method."""
    if name_region is None or name_region.size == 0:
        return OCR_BINARIZE_THRESHOLD
    import cv2
    threshold, _ = cv2.threshold(name_region, 0, 255, cv2.THRESH_BINARY | cv2.THRESH_OTSU)
    return int(threshold)


# ---------------------------------------------------------------------------
# Tier 1: Whole-name hash
# ---------------------------------------------------------------------------

def normalize_name_image(binary: np.ndarray) -> np.ndarray:
    """Crop binary name image to text bounding box and pad to fixed height.

    Returns a canonical representation for hashing: tight-cropped text
    padded to OCR_GLYPH_HEIGHT rows on the vertical axis.
    """
    if binary is None or binary.size == 0:
        return np.zeros((OCR_GLYPH_HEIGHT, 0), dtype=np.uint8)

    rows_with_text = np.any(binary > 0, axis=1)
    cols_with_text = np.any(binary > 0, axis=0)

    if not np.any(rows_with_text) or not np.any(cols_with_text):
        return np.zeros((OCR_GLYPH_HEIGHT, 0), dtype=np.uint8)

    row_indices = np.where(rows_with_text)[0]
    col_indices = np.where(cols_with_text)[0]

    cropped = binary[row_indices[0]:row_indices[-1] + 1,
                     col_indices[0]:col_indices[-1] + 1]

    h, w = cropped.shape
    if h == OCR_GLYPH_HEIGHT:
        return cropped
    if h > OCR_GLYPH_HEIGHT:
        return cropped[:OCR_GLYPH_HEIGHT, :]

    padded = np.zeros((OCR_GLYPH_HEIGHT, w), dtype=np.uint8)
    padded[:h, :] = cropped
    return padded


def hash_name_image(normalized: np.ndarray) -> int:
    """Hash a normalized binary name image for Tier 1 lookup."""
    if normalized is None or normalized.size == 0:
        return 0
    return hashit(normalized)


# ---------------------------------------------------------------------------
# Tier 2: Character segmentation + OCR
# ---------------------------------------------------------------------------

def segment_characters(core_binary: np.ndarray,
                       min_width: int = OCR_MIN_CHAR_WIDTH,
                       merge_gap: int = OCR_MERGE_GAP,
                       space_gap: int = OCR_SPACE_GAP) -> List[Tuple[int, int]]:
    """Segment binary image into character column ranges.

    Returns list of (start_col, end_col) tuples. Space markers are (-1, -1).
    """
    if core_binary is None or core_binary.size == 0:
        return []

    col_sums = core_binary.sum(axis=0)

    segments = []
    in_char = False
    start = 0

    for x in range(len(col_sums)):
        if col_sums[x] > 0 and not in_char:
            start = x
            in_char = True
        elif col_sums[x] == 0 and in_char:
            segments.append((start, x))
            in_char = False

    if in_char:
        segments.append((start, len(col_sums)))

    if not segments:
        return []

    merged = [segments[0]]
    for seg in segments[1:]:
        gap = seg[0] - merged[-1][1]
        if gap <= merge_gap:
            merged[-1] = (merged[-1][0], seg[1])
        elif gap >= space_gap:
            merged.append((-1, -1))
            merged.append(seg)
        else:
            merged.append(seg)

    return [(s, e) for s, e in merged if (e - s >= min_width) or s == -1]


def extract_glyph(binary: np.ndarray, col_start: int, col_end: int,
                  core_rows: Tuple[int, int] = OCR_CORE_ROWS,
                  height: int = OCR_GLYPH_HEIGHT) -> np.ndarray:
    """Extract a single glyph from binary image, normalized to fixed height."""
    row_start = min(core_rows[0], binary.shape[0])
    row_end = min(core_rows[1], binary.shape[0])

    if row_start >= row_end or col_start >= col_end:
        return np.zeros((height, 0), dtype=np.uint8)

    glyph = binary[row_start:row_end, col_start:col_end]

    h, w = glyph.shape
    if h == height:
        return glyph.copy()
    if h > height:
        return glyph[:height, :].copy()

    padded = np.zeros((height, w), dtype=np.uint8)
    padded[:h, :] = glyph
    return padded


def read_name_by_ocr(binary: np.ndarray, glyph_atlas: Dict[str, str],
                     core_rows: Tuple[int, int] = OCR_CORE_ROWS) -> Optional[str]:
    """Read creature name from binary image using character-level OCR.

    Args:
        binary: Binarized name region image
        glyph_atlas: Dict mapping glyph hash (str) -> character (str)
        core_rows: (start_row, end_row) for character body extraction

    Returns:
        Recognized name string, or None if any glyph is unknown
    """
    row_start = min(core_rows[0], binary.shape[0])
    row_end = min(core_rows[1], binary.shape[0])

    if row_start >= row_end:
        return None

    core = binary[row_start:row_end, :]
    segments = segment_characters(core)

    if not segments:
        return None

    chars = []
    for start, end in segments:
        if start == -1:
            chars.append(' ')
            continue

        glyph = extract_glyph(binary, start, end, core_rows)
        if glyph.size == 0:
            return None

        glyph_hash = str(hashit(glyph))
        char = glyph_atlas.get(glyph_hash)
        if char is None:
            return None
        chars.append(char)

    return ''.join(chars) if chars else None


def fuzzy_match_name(ocr_result: str, known_names: List[str],
                     max_distance: int = 2) -> Optional[str]:
    """Match OCR result against known creature names with tolerance.

    First tries exact match, then case-insensitive, then edit distance.
    """
    if not ocr_result or not known_names:
        return None

    if ocr_result in known_names:
        return ocr_result

    lower = ocr_result.lower()
    for name in known_names:
        if name.lower() == lower:
            return name

    if max_distance > 0:
        best_name = None
        best_dist = max_distance + 1

        for name in known_names:
            dist = _levenshtein(ocr_result.lower(), name.lower())
            if dist < best_dist:
                best_dist = dist
                best_name = name

        if best_name is not None and best_dist <= max_distance:
            return best_name

    return None


def _levenshtein(s1: str, s2: str) -> int:
    """Compute Levenshtein edit distance between two strings."""
    if len(s1) < len(s2):
        return _levenshtein(s2, s1)

    if len(s2) == 0:
        return len(s1)

    previous_row = list(range(len(s2) + 1))
    for i, c1 in enumerate(s1):
        current_row = [i + 1]
        for j, c2 in enumerate(s2):
            insertions = previous_row[j + 1] + 1
            deletions = current_row[j] + 1
            substitutions = previous_row[j] + (c1 != c2)
            current_row.append(min(insertions, deletions, substitutions))
        previous_row = current_row

    return previous_row[-1]


# ---------------------------------------------------------------------------
# Learning (BL teaches GW)
# ---------------------------------------------------------------------------

def learn_name_hash(binary: np.ndarray, creature_name: str,
                    name_hashes: Dict[str, str]) -> bool:
    """Learn whole-name hash from a successfully identified creature.

    Returns True if a new hash was learned.
    """
    normalized = normalize_name_image(binary)
    if normalized.size == 0:
        return False

    name_hash = str(hash_name_image(normalized))
    if name_hash == '0':
        return False

    if name_hash in name_hashes:
        return False

    name_hashes[name_hash] = creature_name
    return True


def learn_glyphs_from_name(binary: np.ndarray, creature_name: str,
                           glyph_atlas: Dict[str, str],
                           core_rows: Tuple[int, int] = OCR_CORE_ROWS) -> int:
    """Learn character glyphs from a successfully identified creature name.

    Segments the binary name image and labels each glyph with the
    corresponding character from creature_name.

    Returns number of new glyphs learned.
    """
    row_start = min(core_rows[0], binary.shape[0])
    row_end = min(core_rows[1], binary.shape[0])

    if row_start >= row_end:
        return 0

    core = binary[row_start:row_end, :]
    segments = segment_characters(core)

    if not segments:
        return 0

    text_segments = [(s, e) for s, e in segments if s != -1]
    name_chars = list(creature_name.replace(' ', ''))

    if len(text_segments) != len(name_chars):
        return 0

    new_count = 0
    for (start, end), char in zip(text_segments, name_chars):
        glyph = extract_glyph(binary, start, end, core_rows)
        if glyph.size == 0:
            continue

        glyph_hash = str(hashit(glyph))
        if glyph_hash not in glyph_atlas:
            glyph_atlas[glyph_hash] = char
            new_count += 1

    return new_count


# ---------------------------------------------------------------------------
# Atlas persistence
# ---------------------------------------------------------------------------

def get_atlas_path(images_path: pathlib.Path = None) -> pathlib.Path:
    """Get platform-aware atlas directory path."""
    if images_path is None:
        images_path = IMAGES_PATH
    atlas_dir = resolve_directory(images_path, CHAR_ATLAS_DIR)
    return atlas_dir / CHAR_ATLAS_FILE


def load_char_atlas(images_path: pathlib.Path = None) -> dict:
    """Load character atlas from disk.

    Returns dict with keys: metadata, glyphs, name_hashes
    """
    atlas_path = get_atlas_path(images_path)

    default_atlas = {
        'metadata': {
            'platform': __import__('sys').platform,
            'threshold': OCR_BINARIZE_THRESHOLD,
            'core_rows': list(OCR_CORE_ROWS),
            'version': 1,
        },
        'glyphs': {},
        'name_hashes': {},
    }

    if not atlas_path.exists():
        return default_atlas

    try:
        with open(atlas_path, 'r') as f:
            data = json.load(f)
        for key in ('metadata', 'glyphs', 'name_hashes'):
            if key not in data:
                data[key] = default_atlas[key]
        return data
    except (json.JSONDecodeError, OSError):
        return default_atlas


def save_char_atlas(atlas: dict, images_path: pathlib.Path = None) -> bool:
    """Save character atlas to disk. Returns True on success."""
    atlas_path = get_atlas_path(images_path)

    try:
        atlas_path.parent.mkdir(parents=True, exist_ok=True)
        with open(atlas_path, 'w') as f:
            json.dump(atlas, f, indent=2)
        return True
    except OSError as e:
        print(f"[OCR] Failed to save atlas: {e}")
        return False


# ---------------------------------------------------------------------------
# Atlas manager (stateful, used by facade)
# ---------------------------------------------------------------------------

class CharAtlasManager:
    """Manages character atlas loading, learning, and periodic persistence.

    This is the only stateful component — tracks dirty flag and save interval.
    """

    SAVE_INTERVAL = 30.0

    def __init__(self, images_path: pathlib.Path = None):
        self._images_path = images_path
        self._atlas = load_char_atlas(images_path)
        self._dirty = False
        self._last_save_time = time.time()
        self._learned_names = set()

        glyph_count = len(self._atlas.get('glyphs', {}))
        hash_count = len(self._atlas.get('name_hashes', {}))
        if glyph_count > 0 or hash_count > 0:
            print(f"[OCR] Loaded atlas: {glyph_count} glyphs, {hash_count} name hashes")

    @property
    def atlas(self) -> dict:
        return self._atlas

    @property
    def glyphs(self) -> Dict[str, str]:
        return self._atlas.get('glyphs', {})

    @property
    def name_hashes(self) -> Dict[str, str]:
        return self._atlas.get('name_hashes', {})

    @property
    def threshold(self) -> int:
        return self._atlas.get('metadata', {}).get('threshold', OCR_BINARIZE_THRESHOLD)

    @property
    def core_rows(self) -> Tuple[int, int]:
        rows = self._atlas.get('metadata', {}).get('core_rows', list(OCR_CORE_ROWS))
        return (rows[0], rows[1])

    def identify_name(self, name_region: np.ndarray,
                      available_names: List[str]) -> Optional[str]:
        """Try to identify creature name using OCR (Tier 1 then Tier 2).

        Args:
            name_region: Grayscale name region above HP bar
            available_names: Creature names from battlelist that haven't been matched yet

        Returns:
            Matched creature name or None
        """
        if name_region is None or name_region.size == 0:
            return None
        if not available_names:
            return None

        binary = binarize_name_region(name_region, self.threshold)

        # Tier 1: whole-name hash (fast)
        normalized = normalize_name_image(binary)
        if normalized.size > 0:
            name_hash = str(hash_name_image(normalized))
            matched = self.name_hashes.get(name_hash)
            if matched and matched in available_names:
                return matched

        # Tier 2: character-level OCR (slow but learns)
        ocr_result = read_name_by_ocr(binary, self.glyphs, self.core_rows)
        if ocr_result:
            matched = fuzzy_match_name(ocr_result, available_names)
            if matched:
                return matched

        return None

    def learn_from_creature(self, name_region: np.ndarray,
                            creature_name: str) -> None:
        """Learn name hash and glyphs from a BL-identified creature."""
        if name_region is None or name_region.size == 0:
            return
        if not creature_name or creature_name == 'Player':
            return

        binary = binarize_name_region(name_region, self.threshold)

        if learn_name_hash(binary, creature_name, self._atlas['name_hashes']):
            self._dirty = True
            if creature_name not in self._learned_names:
                print(f"[OCR] Name hash learned: {creature_name}")
                self._learned_names.add(creature_name)

        new_glyphs = learn_glyphs_from_name(
            binary, creature_name, self._atlas['glyphs'], self.core_rows
        )
        if new_glyphs > 0:
            self._dirty = True

    def maybe_save(self) -> None:
        """Save atlas to disk if dirty and enough time has passed."""
        if not self._dirty:
            return
        if time.time() - self._last_save_time < self.SAVE_INTERVAL:
            return

        if save_char_atlas(self._atlas, self._images_path):
            self._dirty = False
            self._last_save_time = time.time()
            glyph_count = len(self._atlas.get('glyphs', {}))
            hash_count = len(self._atlas.get('name_hashes', {}))
            print(f"[OCR] Atlas saved: {glyph_count} glyphs, {hash_count} name hashes")

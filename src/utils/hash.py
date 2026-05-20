"""
FarmHash64-based image hashing utilities.

Based on PyTibia's implementation for ultra-fast image recognition.
Uses FarmHash64 for O(1) lookups instead of expensive template matching.

Performance comparison:
- Template matching: ~0.5-2ms per comparison
- Hash lookup: ~0.0001ms (5000-20000x faster)
"""
import pathlib
from typing import Callable, Dict, Optional, Tuple, Union

import cv2
import numpy as np

# Try to import farmhash for ultra-fast hashing
try:
    from farmhash import hash64 as FarmHash64
    FARMHASH_AVAILABLE = True
except ImportError:
    FARMHASH_AVAILABLE = False
    import hashlib

# Type aliases
GrayImage = np.ndarray
BBox = Tuple[int, int, int, int]

# Text pixel values used for creature name detection (PyTibia style)
TEXT_PIXEL_VALUES = np.array([192, 247], dtype=np.uint8)


def normalize_text_pixels(row: np.ndarray, width: int = 115) -> np.ndarray:
    """
    Vectorized normalization of text pixels for hash computation.

    Replaces slow Python loop:
        for i in range(len(row)):
            if row[i] in TEXT_PIXEL_VALUES or row[i] > 150:
                normalized[i] = 192

    With O(n) NumPy vectorized operation.

    Args:
        row: 1D array of pixel values
        width: Target width for normalized output (default 115 for name region)

    Returns:
        Normalized array where text pixels = 192, others = 0
    """
    # Pad or truncate to target width
    if len(row) < width:
        padded = np.zeros(width, dtype=np.uint8)
        padded[:len(row)] = row
        row = padded
    else:
        row = row[:width]

    # Vectorized: pixels in TEXT_PIXEL_VALUES OR > 150 become 192
    mask = np.isin(row, TEXT_PIXEL_VALUES) | (row > 150)
    result = np.where(mask, np.uint8(192), np.uint8(0))
    return result.astype(np.uint8)


def hashit(arr: np.ndarray) -> int:
    """
    Fast hash of numpy array using FarmHash64.

    This is the core function used throughout PyTibia for:
    - Creature name recognition (O(1) lookup)
    - Floor level detection
    - Coordinate caching
    - Position caching

    Args:
        arr: Numpy array (usually grayscale image)

    Returns:
        64-bit integer hash
    """
    if FARMHASH_AVAILABLE:
        return FarmHash64(np.ascontiguousarray(arr))
    else:
        # Fallback to MD5 if farmhash not available
        return int(hashlib.md5(np.ascontiguousarray(arr)).hexdigest()[:16], 16)


def load_gray_image(path: str) -> Optional[GrayImage]:
    """Load image as grayscale."""
    if not pathlib.Path(path).exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def cache_object_position(func: Callable) -> Callable:
    """
    Decorator to cache object position based on image hash.

    PyTibia's cacheObjectPosition pattern - avoids redundant
    template matching when the object hasn't moved.

    Usage:
        @cache_object_position
        def find_icon(screenshot):
            # expensive template matching
            return (x, y, w, h)
    """
    lastX: Optional[int] = None
    lastY: Optional[int] = None
    lastW: Optional[int] = None
    lastH: Optional[int] = None
    lastImgHash: Optional[int] = None

    def inner(screenshot: GrayImage) -> Optional[BBox]:
        nonlocal lastX, lastY, lastW, lastH, lastImgHash

        # Check if cached position still valid
        if lastX is not None and lastY is not None and lastW is not None and lastH is not None:
            # Verify bounds
            if (lastY + lastH <= screenshot.shape[0] and
                lastX + lastW <= screenshot.shape[1]):
                cached_region = screenshot[lastY:lastY + lastH, lastX:lastX + lastW]
                if hashit(cached_region) == lastImgHash:
                    return (lastX, lastY, lastW, lastH)

        # Cache miss - run the actual function
        res = func(screenshot)
        if res is None:
            return None

        lastX, lastY, lastW, lastH = res
        lastImgHash = hashit(screenshot[lastY:lastY + lastH, lastX:lastX + lastW])
        return res

    def clear_cache():
        nonlocal lastX, lastY, lastW, lastH, lastImgHash
        lastX = lastY = lastW = lastH = lastImgHash = None

    inner.clear_cache = clear_cache
    return inner


class CreatureHashTable:
    """
    Hash table for O(1) creature name recognition.

    PyTibia's approach: pre-compute hash of a single row of pixels
    from each creature name image. At runtime, extract same row from
    battle list and lookup hash directly.

    Performance:
    - Pre-computation: ~10ms per creature (done once at startup)
    - Runtime lookup: ~0.0001ms per creature (vs ~2ms template matching)
    """

    # Battle list name region: row 8, columns 0-115
    NAME_ROW = 8
    NAME_WIDTH = 115

    # Text pixel values in battle list
    TEXT_PIXEL_VALUES = (192, 247)

    def __init__(self, monsters_folder: str):
        """
        Initialize creature hash table.

        Args:
            monsters_folder: Path to folder with monster name PNG images
        """
        self._hash_to_name: Dict[int, str] = {}
        self._name_to_image: Dict[str, GrayImage] = {}
        self._monsters_folder = pathlib.Path(monsters_folder)
        self._loaded = False

    def load(self) -> int:
        """
        Load all monster images and pre-compute hashes.

        Returns:
            Number of creatures loaded
        """
        if self._loaded:
            return len(self._hash_to_name)

        if not self._monsters_folder.exists():
            self._loaded = True
            return 0

        count = 0
        for img_path in self._monsters_folder.glob("*.png"):
            name = img_path.stem
            img = load_gray_image(str(img_path))

            if img is None:
                continue

            self._name_to_image[name] = img

            # Extract single row for hash (PyTibia method)
            # The creature name images should have text at row 8
            if img.shape[0] > self.NAME_ROW:
                # Extract row and normalize text pixels
                name_row = self._extract_name_row(img)
                if name_row is not None:
                    name_hash = hashit(name_row)
                    self._hash_to_name[name_hash] = name
                    count += 1

        self._loaded = True
        print(f"[CreatureHashTable] Loaded {count} creature hashes")
        return count

    def _extract_name_row(self, img: GrayImage) -> Optional[np.ndarray]:
        """
        Extract normalized name row from image.

        PyTibia normalizes text pixels to consistent value (192)
        for reliable hashing.

        Optimized: Uses vectorized NumPy operation instead of Python loop.
        """
        if img.shape[0] <= self.NAME_ROW:
            return None

        # Get row 8, up to 115 pixels wide
        width = min(img.shape[1], self.NAME_WIDTH)
        row = img[self.NAME_ROW, 0:width]

        # Vectorized normalization (O(n) instead of Python loop)
        return normalize_text_pixels(row, self.NAME_WIDTH)

    def lookup(self, name_image: GrayImage) -> str:
        """
        Lookup creature name from image using hash.

        Args:
            name_image: Grayscale image of creature name row

        Returns:
            Creature name or 'Unknown'
        """
        if not self._loaded:
            self.load()

        name_hash = hashit(name_image)
        return self._hash_to_name.get(name_hash, 'Unknown')

    def lookup_from_slot(self, content: GrayImage, slot_index: int) -> str:
        """
        Lookup creature name from battle list slot.

        Args:
            content: Battle list content image
            slot_index: Slot index (0-based)

        Returns:
            Creature name or 'Unknown'

        Optimized: Uses vectorized NumPy operation instead of Python loop.
        """
        if not self._loaded:
            self.load()

        # Extract name row from slot (PyTibia method)
        y = 11 + (slot_index * 22)  # 11px offset, 22px per slot
        if y >= content.shape[0]:
            return 'Unknown'

        # Get row at y position, columns 23-138 (115px)
        if y + 1 > content.shape[0] or 138 > content.shape[1]:
            return 'Unknown'

        row = content[y, 23:138] if 138 <= content.shape[1] else content[y, 23:]

        # Vectorized normalization (O(n) instead of Python loop)
        normalized = normalize_text_pixels(row, self.NAME_WIDTH)

        name_hash = hashit(normalized)
        return self._hash_to_name.get(name_hash, 'Unknown')

    def get_image(self, name: str) -> Optional[GrayImage]:
        """Get full image for creature name (for template matching fallback)."""
        if not self._loaded:
            self.load()
        return self._name_to_image.get(name)

    @property
    def creature_count(self) -> int:
        """Number of creatures in hash table."""
        if not self._loaded:
            self.load()
        return len(self._hash_to_name)

    @property
    def creature_names(self) -> list:
        """List of creature names."""
        if not self._loaded:
            self.load()
        return list(self._name_to_image.keys())


class FloorHashTable:
    """
    Hash table for O(1) floor level detection.

    Pre-computes hash of floor level indicator images.
    """

    def __init__(self, floor_images_folder: str):
        """
        Initialize floor hash table.

        Args:
            floor_images_folder: Path to folder with floor-*.png images
        """
        self._hash_to_floor: Dict[int, int] = {}
        self._floor_images_folder = pathlib.Path(floor_images_folder)
        self._loaded = False

    def load(self) -> int:
        """Load floor images and pre-compute hashes."""
        if self._loaded:
            return len(self._hash_to_floor)

        if not self._floor_images_folder.exists():
            self._loaded = True
            return 0

        count = 0
        for floor in range(16):  # Floors 0-15
            img_path = self._floor_images_folder / f"floor-{floor}.png"
            if not img_path.exists():
                img_path = self._floor_images_folder / f"{floor}.png"

            if not img_path.exists():
                continue

            img = load_gray_image(str(img_path))
            if img is not None:
                floor_hash = hashit(img)
                self._hash_to_floor[floor_hash] = floor
                count += 1

        self._loaded = True
        return count

    def lookup(self, floor_image: GrayImage) -> Optional[int]:
        """
        Lookup floor level from image using hash.

        Args:
            floor_image: Grayscale image of floor indicator

        Returns:
            Floor level (0-15) or None
        """
        if not self._loaded:
            self.load()

        floor_hash = hashit(floor_image)
        return self._hash_to_floor.get(floor_hash)


class ArrowHashTable:
    """
    Hash table for O(1) arrow position detection.

    Pre-computes hash of game window arrow images.
    """

    def __init__(self, arrows_folder: str):
        """
        Initialize arrow hash table.

        Args:
            arrows_folder: Path to folder with arrow PNG images
        """
        self._hash_to_name: Dict[int, str] = {}
        self._arrows_folder = pathlib.Path(arrows_folder)
        self._loaded = False

    def load(self) -> int:
        """Load arrow images and pre-compute hashes."""
        if self._loaded:
            return len(self._hash_to_name)

        if not self._arrows_folder.exists():
            self._loaded = True
            return 0

        count = 0
        arrow_names = [
            'leftGameWindow00', 'leftGameWindow01', 'leftGameWindow10', 'leftGameWindow11',
            'rightGameWindow00', 'rightGameWindow01', 'rightGameWindow10', 'rightGameWindow11'
        ]

        for name in arrow_names:
            img_path = self._arrows_folder / f"{name}.png"
            if not img_path.exists():
                continue

            img = load_gray_image(str(img_path))
            if img is not None:
                arrow_hash = hashit(img)
                self._hash_to_name[arrow_hash] = name
                count += 1

        self._loaded = True
        return count

    def lookup(self, arrow_image: GrayImage) -> Optional[str]:
        """
        Lookup arrow name from image using hash.

        Returns:
            Arrow name or None
        """
        if not self._loaded:
            self.load()

        arrow_hash = hashit(arrow_image)
        return self._hash_to_name.get(arrow_hash)


# Singleton instances
_creature_hash_table: Optional[CreatureHashTable] = None
_floor_hash_table: Optional[FloorHashTable] = None


def get_creature_hash_table(monsters_folder: str = "monsters") -> CreatureHashTable:
    """Get singleton CreatureHashTable instance."""
    global _creature_hash_table
    if _creature_hash_table is None:
        _creature_hash_table = CreatureHashTable(monsters_folder)
    return _creature_hash_table


def get_floor_hash_table(floor_images_folder: str = None) -> FloorHashTable:
    """Get singleton FloorHashTable instance."""
    global _floor_hash_table
    if _floor_hash_table is None:
        folder = floor_images_folder or str(pathlib.Path(__file__).parent.parent / "repositories" / "radar" / "images" / "floorLevels")
        _floor_hash_table = FloorHashTable(folder)
    return _floor_hash_table

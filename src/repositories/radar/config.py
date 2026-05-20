"""
Radar config - Configuration and pre-loaded data.

PyTibia style: loads floor images, walkable matrices, and floor level indicators.
Heavy data (images, walkable matrices) is lazy-loaded on first use via _ensure_loaded().
"""
import pathlib
import numpy as np
import cv2

from ...core.constants import CONFIDENCE_RADAR_FLOORS
from ...utils.image_resolver import resolve_image

CURRENT_PATH = pathlib.Path(__file__).parent.resolve()
IMAGES_PATH = CURRENT_PATH / "images"

# Radar dimensions (from PyTibia)
dimensions = {
    'width': 106,
    'height': 109,
    'halfWidth': 53,
    'halfHeight': 54,
}

# Tibia coordinate system offsets
COORDINATE_OFFSET_X = 31744
COORDINATE_OFFSET_Y = 30976

# Floor levels (0 = highest sky, 7 = ground, 15 = deepest underground)
floors = list(range(16))
FLOOR_GROUND = 7
FLOOR_MIN = 0
FLOOR_MAX = 15

# Floor detection confidence thresholds (from constants)
floorsConfidence = CONFIDENCE_RADAR_FLOORS


def _load_gray_image(path: str) -> np.ndarray:
    """Load image as grayscale."""
    if not pathlib.Path(path).exists():
        return None
    img = cv2.imread(str(path))
    if img is None:
        return None
    return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)


def _hashit(arr: np.ndarray) -> int:
    """Create hash from numpy array using FarmHash64 (same as core.py)."""
    if arr is None:
        return 0
    try:
        from farmhash import hash64 as FarmHash64
        return FarmHash64(np.ascontiguousarray(arr))
    except ImportError:
        import hashlib
        return int(hashlib.md5(np.ascontiguousarray(arr)).hexdigest()[:16], 16)


# Coordinate cache (hash -> coordinate)
coordinates = {}

# Pixel color values (terrain types)
pixelsColorsValues = {
    'accessPoint': 226,
    'caveFloor': 111,
    'caveWall': 76,
    'commonFloorOrStreet': 1,
    'grassOrRockyGround': 120,
    'ice': 240,
    'lava': 136,
    'mountainOrStone': 102,
    'sand': 213,
    'snow': 255,
    'swamp': 207,
    'treesOrBushes': 60,
    'wall': 106,
    'water': 93,
    'vacuumOrUndiscoveredArea': 0
}

# Non-walkable pixel colors
nonWalkablePixelsColors = np.array([
    pixelsColorsValues['caveWall'],
    pixelsColorsValues['lava'],
    pixelsColorsValues['mountainOrStone'],
    pixelsColorsValues['swamp'],
    pixelsColorsValues['treesOrBushes'],
    pixelsColorsValues['wall'],
    pixelsColorsValues['water'],
    pixelsColorsValues['vacuumOrUndiscoveredArea'],
])

# Tile friction values
availableTilesFrictions = np.array([70, 90, 95, 100, 110, 125, 140, 150, 160, 200, 250])

# Movement speed by breakpoint
breakpointTileMovementSpeed = {
    1: 850, 2: 800, 3: 750, 4: 700, 5: 650, 6: 600, 7: 550, 8: 500,
    9: 450, 10: 400, 11: 350, 12: 300, 13: 250, 14: 200, 15: 150, 16: 100, 17: 50,
}

# Tile frictions with breakpoints (from PyTibia)
tilesFrictionsWithBreakpoints = {
    70:  np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 111, 142, 200, 342, 1070]),
    90:  np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 120, 147, 192, 278, 499, 1842]),
    95:  np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 127, 157, 205, 299, 543, 2096]),
    100: np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 113, 135, 167, 219, 321, 592, 2382]),
    110: np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 126, 150, 187, 248, 367, 696, 3060]),
    125: np.array([0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 146, 175, 219, 293, 444, 876, 4419]),
    140: np.array([0, 0, 0, 0, 0, 0, 0, 111, 125, 143, 167, 201, 254, 344, 531, 1092, 6341]),
    150: np.array([0, 0, 0, 0, 0, 0, 0, 120, 135, 155, 181, 219, 278, 380, 595, 1258, 8036]),
    160: np.array([0, 0, 0, 0, 0, 0, 116, 129, 145, 167, 196, 238, 304, 419, 663, 1443, 10167]),
    200: np.array([0, 0, 0, 114, 124, 135, 149, 167, 190, 219, 261, 322, 419, 597, 998, 2444, 25761]),
    250: np.array([117, 126, 135, 146, 160, 175, 195, 220, 252, 295, 356, 446, 598, 884, 1591, 4557, 81351]),
}

# Heavy data — declared None, populated by _ensure_loaded()
floorsImgs = None
floorsPathsImgs = None
floorsLevelsImgs = None
floorsLevelsImgsHashes = None
walkableFloorsSqms = None
floorsPathsSqms = None
images = None

_loaded = False


def _ensure_loaded():
    """Load heavy data (floor images, walkable matrices) on first call."""
    global _loaded, floorsImgs, floorsPathsImgs, floorsLevelsImgs
    global floorsLevelsImgsHashes, walkableFloorsSqms, floorsPathsSqms, images

    if _loaded:
        return

    print("Loading radar data...")

    # Load floor images (for coordinate detection)
    floorsImgs = []
    loaded_floors = 0
    for floor in floors:
        img = _load_gray_image(str(IMAGES_PATH / f"floor-{floor}.png"))
        floorsImgs.append(img)
        if img is not None:
            loaded_floors += 1
    print(f"  Floor images: {loaded_floors}/16 loaded")

    # Load floor path images (for walkability)
    floorsPathsImgs = []
    for floor in floors:
        img = _load_gray_image(str(IMAGES_PATH / "paths" / f"floor-{floor}.png"))
        floorsPathsImgs.append(img)

    # Load floor level indicator images (for floor detection)
    floorsLevelsImgs = []
    loaded_levels = 0
    for floor in floors:
        img = _load_gray_image(str(resolve_image(IMAGES_PATH, f"floorLevels/{floor}.png")))
        floorsLevelsImgs.append(img)
        if img is not None:
            loaded_levels += 1

    # Create floor level hashes
    floorsLevelsImgsHashes = {}
    for floor in floors:
        if floorsLevelsImgs[floor] is not None:
            h = _hashit(floorsLevelsImgs[floor])
            floorsLevelsImgsHashes[h] = floor
    print(f"  Floor level indicators: {loaded_levels}/16 loaded, {len(floorsLevelsImgsHashes)} hashes")

    # Load radar tools image
    images = {
        'tools': _load_gray_image(str(resolve_image(IMAGES_PATH, "buttons/radarTools.png")))
    }
    if images['tools'] is None:
        print("  WARNING: radarTools.png not found!")
    else:
        print(f"  Radar tools template: {images['tools'].shape[1]}x{images['tools'].shape[0]}")

    # Load or create walkable floor matrices
    floorsPathsSqms = None
    npy_path = CURRENT_PATH / "npys" / "floorsPathsSqms.npy"
    if npy_path.exists():
        try:
            floorsPathsSqms = np.load(str(npy_path))
        except Exception:
            floorsPathsSqms = None

    # Generate walkableFloorsSqms from floor path IMAGES (like PyTibia does!)
    NON_WALKABLE_PIXEL_VALUES = [105, 226]
    walkableFloorsSqms = np.ndarray(shape=(16, 2048, 2560), dtype=np.uint8)

    floors_with_data = 0
    for floor_idx in floors:
        floor_img = floorsPathsImgs[floor_idx]
        if floor_img is not None:
            walkableFloorsSqms[floor_idx] = np.where(
                np.isin(floor_img, NON_WALKABLE_PIXEL_VALUES), 0, 1).astype(np.uint8)
            floors_with_data += 1
        else:
            walkableFloorsSqms[floor_idx] = np.zeros((2048, 2560), dtype=np.uint8)

    print(f"  Walkable matrix: {floors_with_data}/16 floors")

    _loaded = True
    print("Radar data loaded!")

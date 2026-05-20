"""
Radar core - Main functions for coordinate detection and navigation.

PyTibia style implementation.
"""
from typing import Optional, Union, List
import numpy as np
import cv2
from scipy.spatial import distance

from .typings import Coordinate, CoordinateList, FloorLevel, TileFriction, WaypointList
from . import config as _cfg
from .config import (
    COORDINATE_OFFSET_X,
    COORDINATE_OFFSET_Y,
    dimensions,
    availableTilesFrictions,
    breakpointTileMovementSpeed,
    tilesFrictionsWithBreakpoints,
    nonWalkablePixelsColors,
    coordinates,
    floorsConfidence,
)
from .locators import get_radar_tools_position
from .extractors import get_radar_image
from ...utils.hash import hashit as _farmhash
from ...core.constants import CONFIDENCE_UI_DEFAULT

# Capture card detection: color distortion lowers template matching scores
# Floor maps have 15 discrete terrain colors; capture card produces ~140+ blended values
# TM_CCOEFF_NORMED still finds the correct location, just at lower confidence
_CAPTURE_CARD_MODE = False

def set_capture_card_mode(enabled: bool):
    global _CAPTURE_CARD_MODE
    _CAPTURE_CARD_MODE = enabled

CAPTURE_CARD_FULL_SEARCH_CONFIDENCE = 0.35
CAPTURE_CARD_LOCAL_SEARCH_CONFIDENCE = 0.35


def _hashit(arr: np.ndarray) -> int:
    """
    Create hash from numpy array using FarmHash64.

    Optimized: Uses FarmHash64 instead of Python's hash(tobytes()) for
    ~10x faster hashing without memory allocation.
    """
    if arr is None:
        return 0
    return _farmhash(arr)


# GPU Acceleration: Check if OpenCL is available for faster template matching
_OPENCL_AVAILABLE = False
try:
    if cv2.ocl.haveOpenCL():
        cv2.ocl.setUseOpenCL(True)
        _OPENCL_AVAILABLE = cv2.ocl.useOpenCL()
        if _OPENCL_AVAILABLE:
            print("[Radar] OpenCL GPU acceleration enabled for template matching")
except Exception:
    pass


def _locate_gpu(img: np.ndarray, template: np.ndarray, confidence: float = CONFIDENCE_UI_DEFAULT):
    """
    GPU-accelerated template matching using OpenCL via cv2.UMat.

    CPU OPTIMIZATION: Uses GPU for template matching on LARGE images only.
    For small images, GPU overhead (transfer time) is worse than CPU.

    Threshold: Only use GPU if image > 500x500 pixels.
    """
    if img is None or template is None:
        return None
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return None

    # Only use GPU for large images (overhead not worth it for small ones)
    MIN_SIZE_FOR_GPU = 500 * 500
    if img.shape[0] * img.shape[1] < MIN_SIZE_FOR_GPU:
        return _locate(img, template, confidence)

    try:
        # Convert to UMat for GPU processing
        img_gpu = cv2.UMat(img)
        template_gpu = cv2.UMat(template)

        # Template matching on GPU
        result = cv2.matchTemplate(img_gpu, template_gpu, cv2.TM_CCOEFF_NORMED)

        # Get result back to CPU for analysis
        result_cpu = result.get()
        _, max_val, _, max_loc = cv2.minMaxLoc(result_cpu)

        if max_val >= confidence:
            return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    except Exception:
        # Fallback to CPU
        return _locate(img, template, confidence)

    return None


def check_radar_zoom(screenshot: np.ndarray = None) -> tuple:
    """
    Check if radar/minimap is at correct zoom level.

    The radar must be at default zoom (106x109 pixels) for coordinate
    detection to work correctly.

    Args:
        screenshot: Grayscale screenshot (captures new if None)

    Returns:
        (ok: bool, message: str)
    """
    from ...core import get_screen_capture

    if screenshot is None:
        screen = get_screen_capture()
        img = screen.capture()
        screenshot = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

    # Find radar tools
    tools_pos = get_radar_tools_position(screenshot, use_cache=False)
    if tools_pos is None:
        return (False, "Radar tools not found. Make sure the minimap is visible.")

    # Try to extract radar image
    radar_img = get_radar_image(screenshot, tools_pos)
    if radar_img is None:
        return (False, "Could not extract radar image. Check minimap position.")

    # Check size
    expected_h, expected_w = dimensions['height'], dimensions['width']
    actual_h, actual_w = radar_img.shape[:2]

    if actual_h != expected_h or actual_w != expected_w:
        return (False, f"Radar size incorrect: {actual_w}x{actual_h}, expected {expected_w}x{expected_h}. "
                       "Reset minimap zoom to default (click the center button).")

    # Try to detect coordinate to verify it's working
    coord = get_coordinate(screenshot)
    if coord is None:
        return (False, "Radar detected but could not read coordinates. "
                       "Make sure minimap zoom is at DEFAULT level (not zoomed in/out).")

    return (True, f"Radar OK - Current position: {coord}")


def _locate(img: np.ndarray, template: np.ndarray, confidence: float = CONFIDENCE_UI_DEFAULT):
    """Template matching. Returns (x, y, w, h) or None."""
    if img is None or template is None:
        return None
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return None

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


def get_pixel_from_coordinate(coordinate: Coordinate) -> tuple:
    """Convert Tibia coordinate to pixel coordinate."""
    return (coordinate[0] - COORDINATE_OFFSET_X, coordinate[1] - COORDINATE_OFFSET_Y)


def get_coordinate_from_pixel(pixel: tuple, floor: int = 7) -> Coordinate:
    """Convert pixel coordinate to Tibia coordinate."""
    return (pixel[0] + COORDINATE_OFFSET_X, pixel[1] + COORDINATE_OFFSET_Y, floor)


def get_coordinate(screenshot: np.ndarray, previous_coordinate: Coordinate = None) -> Optional[Coordinate]:
    """
    Get current coordinate from radar using template matching.

    PyTibia style implementation:
    1. Find radar tools position
    2. Extract radar image (106x109)
    3. Mask player position (center pixels)
    4. Get floor level
    5. Template match against floor image
    6. Return coordinate

    Args:
        screenshot: Grayscale screenshot
        previous_coordinate: Previous coordinate for faster local search

    Returns:
        (x, y, z) coordinate or None if not detected
    """
    _cfg._ensure_loaded()

    # Find radar tools position
    radar_tools_pos = get_radar_tools_position(screenshot)
    if radar_tools_pos is None:
        return None

    # Extract radar image
    radar_image = get_radar_image(screenshot, radar_tools_pos)
    if radar_image is None:
        return None

    # Check coordinate cache
    radar_hash = _hashit(radar_image)
    cached_coord = coordinates.get(radar_hash)
    if cached_coord is not None:
        return cached_coord

    # Get floor level
    floor_level = get_floor_level(screenshot)
    if floor_level is None:
        return None

    # Mask player position (center of radar) - PyTibia style
    # These are the pixels where the player icon appears
    radar_image[52, 53] = 128
    radar_image[52, 54] = 128
    radar_image[53, 53] = 128
    radar_image[53, 54] = 128
    radar_image[54, 51] = 128
    radar_image[54, 52] = 128
    radar_image[55, 51] = 128
    radar_image[55, 52] = 128
    radar_image[54, 53] = 128
    radar_image[54, 54] = 128
    radar_image[55, 53] = 128
    radar_image[55, 54] = 128
    radar_image[54, 55] = 128
    radar_image[54, 56] = 128
    radar_image[55, 55] = 128
    radar_image[55, 56] = 128
    radar_image[56, 53] = 128
    radar_image[56, 54] = 128
    radar_image[57, 53] = 128
    radar_image[57, 54] = 128

    # Get floor image
    floor_img = _cfg.floorsImgs[floor_level]
    if floor_img is None:
        return None

    # If we have previous coordinate, search locally first (MUCH faster)
    # CPU OPTIMIZATION: Increased padding from 5 to 20 to handle faster movement
    # and avoid falling back to expensive full search
    if previous_coordinate is not None:
        prev_pixel = get_pixel_from_coordinate(previous_coordinate)
        padding = 20  # Increased from 5 - handles faster movement without full search

        y_start = prev_pixel[1] - (dimensions['halfHeight'] + padding)
        y_end = prev_pixel[1] + (dimensions['halfHeight'] + 1 + padding)
        x_start = prev_pixel[0] - (dimensions['halfWidth'] + padding)
        x_end = prev_pixel[0] + (dimensions['halfWidth'] + padding)

        # Bounds check
        if y_start >= 0 and x_start >= 0 and y_end <= floor_img.shape[0] and x_end <= floor_img.shape[1]:
            area_img = floor_img[y_start:y_end, x_start:x_end]
            local_conf = CAPTURE_CARD_LOCAL_SEARCH_CONFIDENCE if _CAPTURE_CARD_MODE else 0.9
            found = _locate(area_img, radar_image, confidence=local_conf)

            if found:
                current_x_pixel = prev_pixel[0] - padding + found[0]
                current_y_pixel = prev_pixel[1] - padding + found[1]
                coord = get_coordinate_from_pixel((current_x_pixel, current_y_pixel), floor_level)

                # Cache the result
                coordinates[radar_hash] = coord
                return coord

    # Full search on floor image
    full_conf = CAPTURE_CARD_FULL_SEARCH_CONFIDENCE if _CAPTURE_CARD_MODE else floorsConfidence[floor_level]
    found = _locate(floor_img, radar_image, confidence=full_conf)
    if found is None:
        return None

    x_pixel = found[0] + dimensions['halfWidth']
    y_pixel = found[1] + dimensions['halfHeight']
    coord = get_coordinate_from_pixel((x_pixel, y_pixel), floor_level)

    # Cache the result
    coordinates[radar_hash] = coord
    return coord


def get_floor_level(screenshot: np.ndarray) -> Optional[FloorLevel]:
    """
    Get current floor level from radar floor indicator.

    PyTibia style: uses hash matching for O(1) floor detection.

    Args:
        screenshot: Grayscale screenshot

    Returns:
        Floor level (0-15) or None if not detected
    """
    _cfg._ensure_loaded()

    radar_tools_pos = get_radar_tools_position(screenshot)
    if radar_tools_pos is None:
        return None

    left, top, width, height = radar_tools_pos

    # Floor indicator is to the right of radar tools
    indicator_left = left + width + 8
    indicator_top = top - 7
    indicator_height = 67
    indicator_width = 2

    try:
        floor_img = screenshot[indicator_top:indicator_top + indicator_height,
                               indicator_left:indicator_left + indicator_width]

        # Try exact hash match first (fast, works on macOS/direct capture)
        floor_hash = _hashit(floor_img)
        floor = _cfg.floorsLevelsImgsHashes.get(floor_hash)
        if floor is not None:
            return floor

        # Fallback: correlation match (handles capture card pixel jitter)
        best_floor = None
        best_score = 0.0
        for f_idx in _cfg.floors:
            f_img = _cfg.floorsLevelsImgs[f_idx]
            if f_img is None or f_img.shape != floor_img.shape:
                continue
            diff = np.mean(np.abs(f_img.astype(np.int16) - floor_img.astype(np.int16)))
            score = 1.0 - diff / 255.0
            if score > best_score:
                best_score = score
                best_floor = f_idx

        if best_floor is not None and best_score > 0.95:
            return best_floor

        return None

    except IndexError:
        return None


def get_tile_friction_by_coordinate(coordinate: Coordinate) -> TileFriction:
    """Get tile friction for a coordinate."""
    _cfg._ensure_loaded()

    x_pixel, y_pixel = get_pixel_from_coordinate(coordinate)
    floor = coordinate[2]

    try:
        return _cfg.floorsPathsSqms[floor, y_pixel, x_pixel]
    except IndexError:
        return 110


def is_coordinate_walkable(coordinate: Coordinate) -> bool:
    """Check if a coordinate is walkable."""
    _cfg._ensure_loaded()

    x_pixel, y_pixel = get_pixel_from_coordinate(coordinate)
    floor = coordinate[2]

    try:
        return _cfg.walkableFloorsSqms[floor, y_pixel, x_pixel] == 1
    except IndexError:
        return True


def get_closest_waypoint_index(coordinate: Coordinate, waypoints: WaypointList) -> Optional[int]:
    """Get index of closest waypoint on same floor."""
    closest_index = None
    closest_distance = float('inf')

    for i, waypoint in enumerate(waypoints):
        wp_coord = waypoint.get('coordinate')
        if wp_coord is None:
            continue

        if wp_coord[2] != coordinate[2]:
            continue

        dist = distance.euclidean(
            (coordinate[0], coordinate[1]),
            (wp_coord[0], wp_coord[1])
        )

        if dist < closest_distance:
            closest_distance = dist
            closest_index = i

    return closest_index


def get_breakpoint_tile_movement_speed(char_speed: int, tile_friction: TileFriction) -> int:
    """Get movement speed for a tile based on character speed and friction."""
    if tile_friction not in tilesFrictionsWithBreakpoints:
        closest = np.flatnonzero(availableTilesFrictions > tile_friction)
        if len(closest) > 0:
            tile_friction = availableTilesFrictions[closest[0]]
        else:
            tile_friction = 250

    breakpoints = tilesFrictionsWithBreakpoints[tile_friction]
    available_indexes = np.flatnonzero(char_speed >= breakpoints)

    if len(available_indexes) == 0:
        return breakpointTileMovementSpeed[1]

    return breakpointTileMovementSpeed.get(available_indexes[-1] + 1, 1000)


def is_non_walkable_pixel_color(pixel_color: int) -> bool:
    """Check if a pixel color represents non-walkable terrain."""
    return np.isin(pixel_color, nonWalkablePixelsColors)


def get_direction_between_coordinates(coord1: Coordinate, coord2: Coordinate) -> Optional[str]:
    """Get direction from coord1 to coord2."""
    if coord1[0] < coord2[0]:
        return 'right'
    if coord2[0] < coord1[0]:
        return 'left'
    if coord1[1] < coord2[1]:
        return 'down'
    if coord2[1] < coord1[1]:
        return 'up'
    return None


def get_around_pixels_coordinates(pixel_coord: tuple) -> np.ndarray:
    """Get 8 surrounding pixel coordinates."""
    offsets = np.array([
        [-1, -1], [0, -1], [1, -1],
        [-1, 0], [1, 0],
        [-1, 1], [0, 1], [1, 1]
    ])
    return np.add(offsets, pixel_coord)


def get_available_around_coordinates(coordinate: Coordinate, walkable_floor: np.ndarray) -> CoordinateList:
    """Get walkable coordinates around a position."""
    pixel = get_pixel_from_coordinate(coordinate)
    around = get_around_pixels_coordinates(pixel)

    walkable = []
    for px, py in around:
        try:
            if walkable_floor[int(py), int(px)] == 1:
                walkable.append((
                    int(px) + COORDINATE_OFFSET_X,
                    int(py) + COORDINATE_OFFSET_Y,
                    coordinate[2]
                ))
        except IndexError:
            continue

    return walkable


def get_closest_coordinate(coordinate: Coordinate, coordinates: CoordinateList) -> Optional[Coordinate]:
    """
    Get closest coordinate from a list.

    Args:
        coordinate: Reference coordinate
        coordinates: List of coordinates to search

    Returns:
        Closest coordinate or None if list is empty
    """
    if not coordinates:
        return None

    coord_xy = (coordinate[0], coordinate[1])
    coords_xy = [(c[0], c[1]) for c in coordinates]

    distances = distance.cdist([coord_xy], coords_xy)[0]
    closest_idx = np.argsort(distances)[0]

    return coordinates[closest_idx]


def manhattan_distance(a: Coordinate, b: Coordinate) -> int:
    """Calculate Manhattan distance between two coordinates."""
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


def euclidean_distance(a: Coordinate, b: Coordinate) -> float:
    """Calculate Euclidean distance between two coordinates."""
    return distance.euclidean((a[0], a[1]), (b[0], b[1]))


def is_adjacent(a: Coordinate, b: Coordinate) -> bool:
    """Check if two coordinates are adjacent (including diagonals)."""
    return (
        abs(a[0] - b[0]) <= 1 and
        abs(a[1] - b[1]) <= 1 and
        a[2] == b[2]
    )


def is_same_floor(a: Coordinate, b: Coordinate) -> bool:
    """Check if two coordinates are on the same floor."""
    return a[2] == b[2]

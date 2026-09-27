"""
Radar extractors - Extract radar data from screenshots.

PyTibia style: radar is LEFT of the tools, not right.
"""
from typing import Optional, Tuple
import numpy as np

from .config import dimensions


def get_radar_bbox(radar_tools_pos: Tuple[int, int, int, int]) -> Tuple[int, int, int, int]:
    """Minimap (x, y, w, h): it sits to the LEFT of the radar tools (PyTibia style)."""
    tools_x, tools_y, _, _ = radar_tools_pos
    return (tools_x - dimensions['width'] - 11, tools_y - 50, dimensions['width'], dimensions['height'])


def get_minimap_pixel(radar_tools_pos, current, goal, margin):
    """Screen pixel of goal on the minimap (1 px per sqm, player at the center), or None if off the minimap."""
    x0, y0, width, height = get_radar_bbox(radar_tools_pos)
    px = dimensions['halfWidth'] + goal[0] - current[0]
    py = dimensions['halfHeight'] + goal[1] - current[1]
    if not (margin <= px < width - margin and margin <= py < height - margin):
        return None
    return (x0 + px, y0 + py)


def get_radar_image(screenshot: np.ndarray, radar_tools_pos: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """
    Extract radar image from screenshot.

    PyTibia style:
    - Radar is to the LEFT of the tools (not right!)
    - x0 = tools.x - radar.width - 11
    - y0 = tools.y - 50

    Args:
        screenshot: Grayscale screenshot
        radar_tools_pos: (x, y, width, height) of radar tools

    Returns:
        Radar image (106x109 pixels) or None
    """
    if radar_tools_pos is None:
        return None

    x0, y0, width, height = get_radar_bbox(radar_tools_pos)
    x1 = x0 + width
    y1 = y0 + height

    try:
        # Bounds check
        if x0 < 0 or y0 < 0:
            return None
        if y1 > screenshot.shape[0] or x1 > screenshot.shape[1]:
            return None

        radar_image = screenshot[y0:y1, x0:x1]

        # Verify size
        if radar_image.shape != (dimensions['height'], dimensions['width']):
            return None

        return radar_image.copy()  # Return copy to allow modification

    except (IndexError, ValueError):
        return None


def get_floor_level_image(screenshot: np.ndarray, radar_tools_pos: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    """
    Extract floor level indicator from screenshot.

    The floor indicator is to the RIGHT of the radar tools.

    Args:
        screenshot: Grayscale screenshot
        radar_tools_pos: (x, y, width, height) of radar tools

    Returns:
        Floor level indicator image or None
    """
    if radar_tools_pos is None:
        return None

    left, top, width, height = radar_tools_pos

    # Floor indicator is to the right of radar tools
    indicator_left = left + width + 8
    indicator_top = top - 7
    indicator_height = 67
    indicator_width = 2

    try:
        return screenshot[
            indicator_top:indicator_top + indicator_height,
            indicator_left:indicator_left + indicator_width
        ]
    except IndexError:
        return None

"""
Radar Repository - PyTibia style coordinate detection and navigation.
"""
from .core import (
    get_coordinate,
    get_floor_level,
    get_tile_friction_by_coordinate,
    is_coordinate_walkable,
    get_closest_waypoint_index,
    get_breakpoint_tile_movement_speed,
    check_radar_zoom,
    get_pixel_from_coordinate,
    get_coordinate_from_pixel,
    get_direction_between_coordinates,
    get_around_pixels_coordinates,
    get_available_around_coordinates,
    get_closest_coordinate,
    manhattan_distance,
    euclidean_distance,
    is_adjacent,
    is_same_floor,
)
from .config import (
    COORDINATE_OFFSET_X,
    COORDINATE_OFFSET_Y,
)
from .typings import Coordinate, CoordinateList, XYCoordinate, FloorLevel, TileFriction

__all__ = [
    # Core detection
    'get_coordinate',
    'get_floor_level',
    'get_tile_friction_by_coordinate',
    'is_coordinate_walkable',
    'get_closest_waypoint_index',
    'get_breakpoint_tile_movement_speed',
    'check_radar_zoom',
    # Coordinate utilities
    'get_pixel_from_coordinate',
    'get_coordinate_from_pixel',
    'get_direction_between_coordinates',
    'get_around_pixels_coordinates',
    'get_available_around_coordinates',
    'get_closest_coordinate',
    'manhattan_distance',
    'euclidean_distance',
    'is_adjacent',
    'is_same_floor',
    # Constants
    'COORDINATE_OFFSET_X',
    'COORDINATE_OFFSET_Y',
    # Types
    'Coordinate',
    'CoordinateList',
    'XYCoordinate',
    'FloorLevel',
    'TileFriction',
]

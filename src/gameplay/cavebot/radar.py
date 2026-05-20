"""
Cavebot Radar - Re-exports from repositories/radar and gameplay/core/waypoint.

This module provides backwards-compatible imports for cavebot navigation.
"""
# Re-export from repositories/radar
from ...repositories.radar import (
    get_coordinate,
    get_floor_level,
    get_tile_friction_by_coordinate,
    is_coordinate_walkable,
    get_closest_waypoint_index,
    get_breakpoint_tile_movement_speed,
    Coordinate,
    FloorLevel,
    TileFriction,
)

from ...repositories.radar.core import (
    get_direction_between_coordinates,
    get_pixel_from_coordinate,
    get_coordinate_from_pixel,
    get_around_pixels_coordinates,
    get_available_around_coordinates,
)

# Re-export from gameplay/core/waypoint
from ..core.waypoint import (
    generate_floor_walkpoints,
    generate_global_walkpoints,
    resolve_goal_coordinate,
    resolve_floor_coordinate,
    resolve_move_down_coordinate,
    resolve_move_up_coordinate,
    resolve_use_shovel_coordinate,
    resolve_use_rope_coordinate,
    resolve_use_hole_coordinate,
    resolve_use_teleport_coordinate,
    Checkpoint,
)

# Aliases for backwards compatibility
get_direction_between_coords = get_direction_between_coordinates


__all__ = [
    # Radar functions
    'get_coordinate',
    'get_floor_level',
    'get_tile_friction_by_coordinate',
    'is_coordinate_walkable',
    'get_closest_waypoint_index',
    'get_breakpoint_tile_movement_speed',
    'get_direction_between_coordinates',
    'get_direction_between_coords',
    'get_pixel_from_coordinate',
    'get_coordinate_from_pixel',
    'get_around_pixels_coordinates',
    'get_available_around_coordinates',

    # Waypoint functions
    'generate_floor_walkpoints',
    'generate_global_walkpoints',
    'resolve_goal_coordinate',
    'resolve_floor_coordinate',
    'resolve_move_down_coordinate',
    'resolve_move_up_coordinate',
    'resolve_use_shovel_coordinate',
    'resolve_use_rope_coordinate',
    'resolve_use_hole_coordinate',
    'resolve_use_teleport_coordinate',

    # Types
    'Coordinate',
    'FloorLevel',
    'TileFriction',
    'Checkpoint',
]

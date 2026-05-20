"""
Utilities module - helper functions and tools.
"""
from .input import (
    safe_click,
    safe_press,
    type_text,
    move_mouse_human
)

from .timing import (
    Timer,
    rate_limiter
)

# Coordinate utilities - re-export from radar for backwards compatibility
from ..repositories.radar import (
    get_pixel_from_coordinate,
    get_coordinate_from_pixel,
    get_direction_between_coordinates,
    get_around_pixels_coordinates,
    get_closest_coordinate,
    manhattan_distance,
    euclidean_distance,
    is_adjacent,
    is_same_floor,
    Coordinate,
    CoordinateList,
    COORDINATE_OFFSET_X,
    COORDINATE_OFFSET_Y,
)

from .hash import (
    hashit,
    load_gray_image,
    cache_object_position,
    CreatureHashTable,
    FloorHashTable,
    ArrowHashTable,
    get_creature_hash_table,
    get_floor_hash_table,
    FARMHASH_AVAILABLE,
)

from .alerts import (
    AlertSystem,
    get_alert_system,
    play_stuck_alert,
    play_alert,
)

__all__ = [
    'safe_click',
    'safe_press',
    'type_text',
    'move_mouse_human',
    'Timer',
    'rate_limiter',
    # Coordinate utils (from radar)
    'get_pixel_from_coordinate',
    'get_coordinate_from_pixel',
    'get_direction_between_coordinates',
    'get_around_pixels_coordinates',
    'get_closest_coordinate',
    'manhattan_distance',
    'euclidean_distance',
    'is_adjacent',
    'is_same_floor',
    'Coordinate',
    'CoordinateList',
    'COORDINATE_OFFSET_X',
    'COORDINATE_OFFSET_Y',
    # Hash utils (FarmHash64)
    'hashit',
    'load_gray_image',
    'cache_object_position',
    'CreatureHashTable',
    'FloorHashTable',
    'ArrowHashTable',
    'get_creature_hash_table',
    'get_floor_hash_table',
    'FARMHASH_AVAILABLE',
    # Alert utils
    'AlertSystem',
    'get_alert_system',
    'play_stuck_alert',
    'play_alert',
]

"""
Core module - fundamental components for the tibia bot.
"""
from .screen import (
    ScreenCapture,
    Region,
    PositionCache,
    cache_position,
    get_screen_capture,
    clear_position_cache,
    compute_image_hash
)

from .types import (
    Direction,
    CreatureType,
    HPColor,
    TaskStatus,
    BotMode,
    Coordinate,
    Creature,
    Marker,
    PlayerStatus,
    GameContext
)

__all__ = [
    # Screen capture
    'ScreenCapture',
    'Region',
    'PositionCache',
    'cache_position',
    'get_screen_capture',
    'clear_position_cache',
    'compute_image_hash',

    # Types
    'Direction',
    'CreatureType',
    'HPColor',
    'TaskStatus',
    'BotMode',
    'Coordinate',
    'Creature',
    'Marker',
    'PlayerStatus',
    'GameContext',
]

"""
Bridge module - re-exports from src/core for backwards compatibility.

This module allows repositories submodules to use relative imports like:
    from ..core import Creature, get_screen_capture

Instead of absolute imports.
"""
from ..core import (
    # Screen capture
    ScreenCapture,
    Region,
    PositionCache,
    cache_position,
    get_screen_capture,
    clear_position_cache,
    compute_image_hash,

    # Types
    Direction,
    CreatureType,
    HPColor,
    TaskStatus,
    BotMode,
    Coordinate,
    Creature,
    Marker,
    PlayerStatus,
    GameContext,
)

__all__ = [
    # Screen
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

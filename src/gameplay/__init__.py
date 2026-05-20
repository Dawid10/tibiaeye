"""
Gameplay module - PyTibia style game loop and task system.
"""
from .context import get_context, create_context
from .gameloop import GameLoop
from .cavebot import handle_cavebot, load_waypoints_from_file
from .resolvers import (
    resolve_tasks_by_waypoint,
    resolve_cavebot_tasks,
    get_current_waypoint,
    has_creatures_to_attack,
)

__all__ = [
    # Context
    'get_context',
    'create_context',

    # Game Loop
    'GameLoop',

    # Cavebot
    'handle_cavebot',
    'load_waypoints_from_file',

    # Resolvers
    'resolve_tasks_by_waypoint',
    'resolve_cavebot_tasks',
    'get_current_waypoint',
    'has_creatures_to_attack',
]

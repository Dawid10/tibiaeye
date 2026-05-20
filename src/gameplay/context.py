"""
Global Context - PyTibia style state management.

All game state is stored in a single dictionary that flows through
the middleware pipeline and task system.
Initial defaults for configurable fields come from src.core.defaults.
"""
from typing import Any, Dict, List, Optional, Tuple
import numpy as np

from ..core.defaults import get_default


def create_context() -> Dict[str, Any]:
    """
    Create a fresh context with default values.

    This is the central state object that flows through:
    1. Middlewares (data extraction)
    2. Task orchestrator (action execution)
    3. Healing observers (reactive healing)
    """
    return {
        # Screenshot (updated every frame)
        'screenshot': None,  # np.ndarray grayscale

        # Radar/Minimap
        'radar': {
            'coordinate': None,  # (x, y, z) current position
            'previousCoordinate': None,
            'lastCoordinateVisited': None,
        },

        # Battle List
        'battleList': {
            'creatures': [],  # List of creatures in battle list
            'beingAttackedCreatureCategory': None,
        },

        # Game Window
        'gameWindow': {
            'coordinate': None,  # Game window position on screen
            'image': None,  # Game window screenshot
            'monsters': [],  # Monsters visible in game window
            'players': [],
            'creatures': [],  # All creatures
            'previousMonsters': [],  # Previous tick monsters (for loot detection)
            'monstersBars': [],  # HP bars detected
        },

        # Player Status
        'statusBar': {
            'hp': 0,
            'hpPercentage': 100,
            'mana': 0,
            'manaPercentage': 100,
        },

        # Player Speed (for tile friction calculations)
        'playerSpeed': 110,  # Default base speed

        # Cavebot
        'cavebot': {
            'enabled': False,
            'waypoints': {
                'items': [],  # List of waypoints
                'currentIndex': 0,
                'indexBeforeCombat': None,  # Saved index before entering combat
            },
            'targetCreature': None,
            'closestCreature': None,
            'isAttackingSomeCreature': False,
            # Dynamic obstacles (PyTibia style)
            'holesOrStairs': [],  # Coordinates of holes/stairs to avoid
            'nonWalkableCoordinates': [],  # Dynamic obstacles (creatures, etc.)
            # Stuck detection (defaults from core.defaults; overwritten by GUI at start)
            'stuckAlert': {
                'enabled': get_default('general.enableStuckAlert'),
                'timeoutSeconds': get_default('general.stuckAlertTimeout'),
            },
        },

        # Healing
        'healing': {
            'enabled': False,
            'spells': [],  # Healing spell configs
            'potions': [],  # Potion configs
            'highPriority': {
                'enabled': False,
                'hpPercentageLessThanOrEqual': 30,
                'manaPercentageGreaterThanOrEqual': 10,
            },
            'eatFood': {
                'enabled': False,
                'hotkey': None,
            },
        },

        # Spell Attack (offensive spell casting)
        'spellAttack': {
            'enabled': False,
            'manaReservePercent': 30,
            'groups': [],
            'lastCastSpell': None,
            'lastCastTime': 0,
        },

        # Loot
        'loot': {
            'enabled': False,
            'hotkey': 'g',
            'corpsesToLoot': [],
        },

        # Targeting
        'targeting': {
            'enabled': True,
            'creatures': {},  # Creature targeting settings
        },

        # Pause state
        'pause': True,

        # Task orchestrator (set at runtime)
        'tasksOrchestrator': None,

        # Deposit
        'deposit': {
            'lockerCoordinate': None,
        },

        # Chat
        'chat': {
            'tabs': [],
            'lootMessages': [],  # New loot messages detected this tick
        },

        # GUI Logger (set at runtime by GUI)
        'gui_logger': None,  # Callable: (message: str, level: str) -> None

        # Reconnect
        'reconnect': {
            'enabled': False,
            'state': 'CONNECTED',
            'retryCount': 0,
        },

        # Resolution/Window
        'resolution': (1920, 1080),
        'window': {
            'x': 0,
            'y': 0,
            'width': 0,
            'height': 0,
        },

        # License and Telemetry (optional)
        'license': None,       # LicenseValidator instance
        'telemetry': None,     # TelemetryClient instance
        'character_id': None,  # UUID from dashboard
    }


# Global context instance
context: Dict[str, Any] = create_context()


def get_context() -> Dict[str, Any]:
    """Get the global context."""
    return context

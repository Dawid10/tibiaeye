"""Trap Detector - detects when character is surrounded by creatures and can't attack."""
import math
import time
from typing import Any, Dict, Optional, Tuple

from ..core.constants import TRAP_DELAY_MOVING, TRAP_FALLBACK_TIMEOUT


def is_trapped(context: Dict[str, Any]) -> bool:
    """True if creatures exist in battle list but no reachable creature (closestCreature is None)."""
    creatures = context.get('battleList', {}).get('creatures', [])
    closest = context.get('cavebot', {}).get('closestCreature')
    return len(creatures) > 0 and closest is None


def get_closest_trapped_creature(context: Dict[str, Any]):
    """Select closest monster by euclidean distance to game window center (no pathfinding)."""
    monsters = context.get('gameWindow', {}).get('monsters', [])
    if not monsters:
        return None
    gw_image = context.get('gameWindow', {}).get('image')
    if gw_image is None:
        return None
    center_y, center_x = gw_image.shape[0] // 2, gw_image.shape[1] // 2
    return min(monsters, key=lambda c: _euclidean(c.game_window_coordinate, (center_x, center_y)))


def _euclidean(a: Tuple[int, int], b: Tuple[int, int]) -> float:
    dx = a[0] - b[0]
    dy = a[1] - b[1]
    return math.sqrt(dx * dx + dy * dy)


class TrapDetector:
    """Detects when character is surrounded and triggers anti-trap attack."""

    def __init__(self):
        self._trap_start_time: float = 0
        self._last_position: Optional[Tuple] = None
        self._is_stationary: bool = False

    def should_engage(self, context: Dict[str, Any]) -> bool:
        """Return True when trap condition is met and delay has passed.

        - Stationary (position unchanged): engage immediately
        - Moving (position changed recently): wait TRAP_DELAY_MOVING seconds
        """
        if not is_trapped(context):
            self._trap_start_time = 0
            return False

        current_pos = context.get('radar', {}).get('coordinate')
        if current_pos is None:
            return False

        now = time.time()

        # Track position changes
        if self._last_position is None:
            self._last_position = current_pos
            self._trap_start_time = now
            return False

        if current_pos != self._last_position:
            self._last_position = current_pos
            self._is_stationary = False
            self._trap_start_time = now
            return False

        self._is_stationary = True
        self._last_position = current_pos

        if self._trap_start_time == 0:
            self._trap_start_time = now
            return False

        # Stationary: engage immediately (0s delay)
        if self._is_stationary:
            delay = 0
        else:
            delay = TRAP_DELAY_MOVING

        return (now - self._trap_start_time) >= delay

    def reset(self) -> None:
        """Reset trap state after successful engagement."""
        self._trap_start_time = 0

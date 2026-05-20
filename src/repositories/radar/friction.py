"""
Tile Friction Calculator - Calculates movement time based on tile type and player speed.

Tibia uses different friction values for different terrain types, affecting
how fast the character can move across them.
"""
from typing import Optional
import numpy as np

from . import config as _cfg
from .config import (
    availableTilesFrictions,
    tilesFrictionsWithBreakpoints,
    breakpointTileMovementSpeed,
)
from .typings import Coordinate


DEFAULT_FRICTION = 110
DEFAULT_MOVEMENT_TIME_MS = 450
DEFAULT_PLAYER_SPEED = 110


def _find_closest_friction(friction: int) -> int:
    """Find the closest available friction value."""
    differences = np.abs(availableTilesFrictions - friction)
    closest_index = np.argmin(differences)
    return int(availableTilesFrictions[closest_index])


def _calculate_speed_tier(speed: int, friction: int) -> int:
    """Calculate the speed tier based on player speed and tile friction."""
    breakpoints = tilesFrictionsWithBreakpoints[friction]
    tier = np.sum(speed >= breakpoints)
    return max(1, int(tier))


class TileFrictionCalculator:
    """
    Calculates movement time based on tile friction and player speed.

    Tile friction affects how fast a character can move across different
    terrain types (grass, sand, ice, etc.).
    """

    def get_movement_time(self, player_speed: int, tile_friction: int) -> float:
        """
        Calculate movement time in milliseconds for a single tile.

        Args:
            player_speed: Character's current speed (e.g., 110, 150, 200)
            tile_friction: Tile's friction value (e.g., 100 for grass)

        Returns:
            Movement time in milliseconds
        """
        if player_speed <= 0:
            return DEFAULT_MOVEMENT_TIME_MS

        normalized_friction = self._normalize_friction(tile_friction)
        tier = _calculate_speed_tier(player_speed, normalized_friction)
        return breakpointTileMovementSpeed.get(tier, DEFAULT_MOVEMENT_TIME_MS)

    def get_movement_time_seconds(self, player_speed: int, tile_friction: int) -> float:
        """
        Calculate movement time in seconds for a single tile.

        Args:
            player_speed: Character's current speed
            tile_friction: Tile's friction value

        Returns:
            Movement time in seconds
        """
        return self.get_movement_time(player_speed, tile_friction) / 1000.0

    def _normalize_friction(self, friction: int) -> int:
        """Normalize friction to an available value."""
        if friction in tilesFrictionsWithBreakpoints:
            return friction
        return _find_closest_friction(friction)

    def get_tile_friction(self, coordinate: Coordinate) -> int:
        """
        Get the friction value for a coordinate.

        Args:
            coordinate: (x, y, z) world coordinate

        Returns:
            Friction value for the tile (defaults to 110 if not found)
        """
        if coordinate is None:
            return DEFAULT_FRICTION

        _cfg._ensure_loaded()

        if _cfg.floorsPathsSqms is None:
            return DEFAULT_FRICTION

        x, y, z = coordinate
        pixel_x = x - 31744
        pixel_y = y - 30976

        try:
            friction_value = _cfg.floorsPathsSqms[z, pixel_y, pixel_x]
            return self._map_pixel_to_friction(friction_value)
        except (IndexError, TypeError):
            return DEFAULT_FRICTION

    def _map_pixel_to_friction(self, pixel_value: int) -> int:
        """Map pixel value from path image to friction value."""
        friction_map = {
            0: 100,     # Unexplored/void - normal
            1: 100,     # Common floor/street
            60: 125,    # Trees/bushes
            76: 140,    # Cave wall
            93: 200,    # Water
            102: 140,   # Mountain/stone
            105: 250,   # Blocked terrain
            106: 250,   # Wall
            111: 100,   # Cave floor
            120: 100,   # Grass/rocky ground
            136: 200,   # Lava
            207: 160,   # Swamp
            213: 150,   # Sand
            226: 100,   # Access point
            240: 70,    # Ice
            255: 125,   # Snow
        }
        return friction_map.get(pixel_value, DEFAULT_FRICTION)

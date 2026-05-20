"""Pathfinding detectors — extract walkable grid and BFS path from GameWindow data."""
import time
from typing import Optional, Tuple

import numpy as np


GRID_WIDTH = 15
GRID_HEIGHT = 11
PLAYER_SLOT_X = 7
PLAYER_SLOT_Y = 5


def detect_walkable_grid(gw_result: dict, coordinate: Optional[Tuple[int, int, int]] = None) -> dict:
    """Extract walkable grid from GameWindow detection.

    Retrieves the 11x15 walkable matrix from the radar/walkable data,
    given the player coordinate from the radar result.

    Returns dict with:
        walkable_grid   — numpy int32 array (11, 15) or None
        walkable_count  — int
        timing_ms       — float
        diagnostics     — dict
    """
    t0 = time.perf_counter()

    walkable_grid = None
    walkable_count = 0

    if coordinate is not None:
        try:
            from src.repositories.radar.config import (
                walkableFloorsSqms, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y
            )

            floor = coordinate[2]
            pixel_x = coordinate[0] - COORDINATE_OFFSET_X
            pixel_y = coordinate[1] - COORDINATE_OFFSET_Y

            y_start = pixel_y - PLAYER_SLOT_Y
            y_end = pixel_y + (GRID_HEIGHT - PLAYER_SLOT_Y)
            x_start = pixel_x - PLAYER_SLOT_X
            x_end = pixel_x + (GRID_WIDTH - PLAYER_SLOT_X)

            if (y_start >= 0 and y_end <= walkableFloorsSqms.shape[1]
                    and x_start >= 0 and x_end <= walkableFloorsSqms.shape[2]
                    and 0 <= floor < walkableFloorsSqms.shape[0]):
                walkable_grid = walkableFloorsSqms[floor, y_start:y_end, x_start:x_end].copy().astype(np.int32)
                walkable_count = int(np.sum(walkable_grid > 0))

        except Exception as e:
            pass

    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "walkable_count": walkable_count,
        "grid_shape": list(walkable_grid.shape) if walkable_grid is not None else None,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "walkable_grid": walkable_grid,
        "walkable_count": walkable_count,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_bfs_path(gw_result: dict, target, coordinate: Optional[Tuple[int, int, int]] = None) -> dict:
    """Get BFS path distance from player to target creature.

    Uses the same BFS logic as get_closest_creature() to compute
    the shortest path distance from player slot to target creature slot.

    Returns dict with:
        path_slots      — list of (x, y) slot coords along the BFS path or []
        distance        — int or None
        path_exists     — bool
        timing_ms       — float
        diagnostics     — dict
    """
    t0 = time.perf_counter()

    path_slots = []
    distance = None
    path_exists = False

    if target is None or coordinate is None:
        timing_ms = (time.perf_counter() - t0) * 1000
        return {
            "path_slots": path_slots,
            "distance": distance,
            "path_exists": path_exists,
            "timing_ms": timing_ms,
            "diagnostics": {"reason": "no target or coordinate", "time_ms": 0.0},
        }

    try:
        from src.repositories.radar.config import (
            walkableFloorsSqms, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y
        )
        from src.repositories.gamewindow.creatures import bfs_flood_fill

        floor = coordinate[2]
        pixel_x = coordinate[0] - COORDINATE_OFFSET_X
        pixel_y = coordinate[1] - COORDINATE_OFFSET_Y

        y_start = pixel_y - PLAYER_SLOT_Y
        y_end = pixel_y + (GRID_HEIGHT - PLAYER_SLOT_Y)
        x_start = pixel_x - PLAYER_SLOT_X
        x_end = pixel_x + (GRID_WIDTH - PLAYER_SLOT_X)

        if not (y_start >= 0 and y_end <= walkableFloorsSqms.shape[1]
                and x_start >= 0 and x_end <= walkableFloorsSqms.shape[2]
                and 0 <= floor < walkableFloorsSqms.shape[0]):
            raise ValueError("coordinate out of walkable bounds")

        local_walkable = walkableFloorsSqms[floor, y_start:y_end, x_start:x_end].copy().astype(np.int32)

        monsters = gw_result.get("monsters", [])
        creature_slots = set()
        for c in monsters:
            sx, sy = c.slot
            if 0 <= sx < GRID_WIDTH and 0 <= sy < GRID_HEIGHT:
                if not (sx == PLAYER_SLOT_X and sy == PLAYER_SLOT_Y):
                    creature_slots.add((sx, sy))

        distances = bfs_flood_fill(local_walkable, PLAYER_SLOT_Y, PLAYER_SLOT_X, creature_slots)

        target_slot_x, target_slot_y = target.slot

        if not (0 <= target_slot_x < GRID_WIDTH and 0 <= target_slot_y < GRID_HEIGHT):
            raise ValueError("target slot out of grid bounds")

        # Check adjacent tiles for the minimum distance (creature itself blocks BFS)
        min_dist = float('inf')
        best_tile = None
        for dy in range(-1, 2):
            for dx in range(-1, 2):
                if dy == 0 and dx == 0:
                    continue
                ny, nx = target_slot_y + dy, target_slot_x + dx
                if (ny, nx) in distances:
                    d = distances[(ny, nx)]
                    if d < min_dist:
                        min_dist = d
                        best_tile = (nx, ny)

        # Also check if the creature's tile itself is reachable
        if (target_slot_y, target_slot_x) in distances:
            d = distances[(target_slot_y, target_slot_x)]
            if d < min_dist:
                min_dist = d
                best_tile = (target_slot_x, target_slot_y)

        if min_dist < float('inf') and best_tile is not None:
            path_exists = True
            distance = int(min_dist)
            # Reconstruct a simple path: just start and end slots
            path_slots = [(PLAYER_SLOT_X, PLAYER_SLOT_Y), best_tile, (target_slot_x, target_slot_y)]

    except Exception as e:
        pass

    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "path_exists": path_exists,
        "distance": distance,
        "path_length": len(path_slots),
        "target_slot": list(target.slot) if target is not None else None,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "path_slots": path_slots,
        "distance": distance,
        "path_exists": path_exists,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }

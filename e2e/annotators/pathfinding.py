"""Pathfinding annotators — draw walkable grid and BFS path overlays."""
import cv2
import numpy as np

from e2e.config import (
    COLOR_BLOCKED,
    COLOR_BFS_PATH,
    COLOR_PLAYER,
    COLOR_WALKABLE,
    FONT,
    FONT_SCALE_LABEL,
    GRID_OVERLAY_ALPHA,
)


GRID_WIDTH = 15
GRID_HEIGHT = 11
PLAYER_SLOT_X = 7
PLAYER_SLOT_Y = 5


def annotate_walkable_grid(image: np.ndarray, gw_result: dict, pf_walkable: dict) -> None:
    """Draw semi-transparent walkable grid overlay on the game window area.

    Green = walkable tile, Red = blocked tile, Blue = player position.
    Only draws if the game window position is known.
    """
    walkable_grid = pf_walkable.get("walkable_grid")
    gw_pos = gw_result.get("game_window_position")

    if walkable_grid is None or gw_pos is None:
        return

    gx, gy, gw, gh = gw_pos
    slot_w = gw // GRID_WIDTH
    slot_h = gh // GRID_HEIGHT

    overlay = image.copy()

    for row in range(GRID_HEIGHT):
        for col in range(GRID_WIDTH):
            tile_x = gx + col * slot_w
            tile_y = gy + row * slot_h
            tile_x2 = tile_x + slot_w
            tile_y2 = tile_y + slot_h

            if col == PLAYER_SLOT_X and row == PLAYER_SLOT_Y:
                color = COLOR_PLAYER
            elif walkable_grid[row, col] > 0:
                color = COLOR_WALKABLE
            else:
                color = COLOR_BLOCKED

            cv2.rectangle(overlay, (tile_x, tile_y), (tile_x2, tile_y2), color, -1)

    cv2.addWeighted(overlay, GRID_OVERLAY_ALPHA, image, 1 - GRID_OVERLAY_ALPHA, 0, image)


def annotate_bfs_path(image: np.ndarray, gw_result: dict, pf_path: dict) -> None:
    """Draw BFS path line from player slot to target creature slot.

    Yellow line connecting player -> intermediate -> target slots.
    Only draws if path_exists is True and game window position is known.
    """
    if not pf_path.get("path_exists"):
        return

    gw_pos = gw_result.get("game_window_position")
    path_slots = pf_path.get("path_slots", [])

    if gw_pos is None or len(path_slots) < 2:
        return

    gx, gy, gw, gh = gw_pos
    slot_w = gw // GRID_WIDTH
    slot_h = gh // GRID_HEIGHT

    def slot_center(slot_x, slot_y):
        cx = gx + slot_x * slot_w + slot_w // 2
        cy = gy + slot_y * slot_h + slot_h // 2
        return (cx, cy)

    points = [slot_center(sx, sy) for sx, sy in path_slots]

    for i in range(len(points) - 1):
        cv2.line(image, points[i], points[i + 1], COLOR_BFS_PATH, 2)

    for pt in points:
        cv2.circle(image, pt, 4, COLOR_BFS_PATH, -1)

    distance = pf_path.get("distance")
    if distance is not None and points:
        label = f"BFS:{distance}"
        cv2.putText(image, label, (points[0][0] + 5, points[0][1] - 8),
                    FONT, FONT_SCALE_LABEL, COLOR_BFS_PATH, 1)

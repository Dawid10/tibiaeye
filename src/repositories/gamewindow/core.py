"""
Game Window core - arrow detection, capture, slot utilities.

Pure functions for game window positioning and interaction.
"""
import pathlib
from typing import Optional, Tuple

import cv2
import numpy as np

from ..core import Region, get_screen_capture
from ...core.constants import (
    CONFIDENCE_UI_DEFAULT, CONFIDENCE_UI_BUTTON, CONFIDENCE_DEPOT,
    CONFIDENCE_ARROW_HIGH, CONFIDENCE_ARROW_MED, CONFIDENCE_ARROW_LOW,
)
from ..utils.cached_position import is_template_at
from .config import (
    IMAGES_PATH, load_gray_image,
    MAP_TOP_DEFAULT_OFFSET, MAP_TOP_SEARCH_ROWS, MAP_FRAME_DARK_MAX, MAP_FRAME_UNIFORM_MAX_STD,
    MAP_FRAME_BEVEL_MIN_CONTRAST, MAP_TEXTURE_MIN_STD, MAP_TEXTURE_CHECK_ROWS, MAP_TOP_MAX_ATTEMPTS,
)


def locate(img: np.ndarray, template: np.ndarray,
           confidence: float = CONFIDENCE_UI_DEFAULT) -> Optional[Tuple[int, int, int, int]]:
    if template is None or img is None:
        return None
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return None

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


def _cached_arrow_still_there(screenshot: np.ndarray, arrow_images: dict, cache: dict) -> bool:
    template = arrow_images.get(cache.get('arrow'))
    if cache.get('position') is None or template is None:
        return False
    return is_template_at(screenshot, template, cache['position'], CONFIDENCE_ARROW_LOW)


def find_left_arrow(screenshot: np.ndarray, arrow_images: dict,
                    cache: dict) -> Optional[Tuple[int, int, int, int]]:
    if _cached_arrow_still_there(screenshot, arrow_images, cache):
        return cache['position']
    cache['position'] = None

    for conf in [CONFIDENCE_ARROW_HIGH, CONFIDENCE_ARROW_MED, CONFIDENCE_ARROW_LOW]:
        for name in ['leftGameWindow01', 'leftGameWindow11', 'leftGameWindow10', 'leftGameWindow00']:
            if name not in arrow_images:
                continue
            pos = locate(screenshot, arrow_images[name], confidence=conf)
            if pos is None:
                continue
            cache['arrow'] = name
            cache['position'] = pos
            print(f"[GameWindow] Left arrow found at {pos}")
            return pos

    return None


def find_right_arrow(screenshot: np.ndarray, arrow_images: dict,
                     cache: dict) -> Optional[Tuple[int, int, int, int]]:
    if _cached_arrow_still_there(screenshot, arrow_images, cache):
        return cache['position']
    cache['position'] = None

    for conf in [CONFIDENCE_ARROW_HIGH, CONFIDENCE_ARROW_MED, CONFIDENCE_ARROW_LOW]:
        for name in ['rightGameWindow01', 'rightGameWindow11', 'rightGameWindow10', 'rightGameWindow00']:
            if name not in arrow_images:
                continue
            pos = locate(screenshot, arrow_images[name], confidence=conf)
            if pos is None:
                continue
            cache['arrow'] = name
            cache['position'] = pos
            print(f"[GameWindow] Right arrow found at {pos}")
            return pos

    return None


def _is_map_top_frame(screenshot: np.ndarray, x: int, y: int, width: int, height: int) -> bool:
    top = screenshot[y, x:x + width]
    bottom = screenshot[y + height + 1, x:x + width]
    if top.mean() >= MAP_FRAME_DARK_MAX or top.std() >= MAP_FRAME_UNIFORM_MAX_STD:
        return False
    if bottom.std() >= MAP_FRAME_UNIFORM_MAX_STD:
        return False
    if bottom.mean() < top.mean() + MAP_FRAME_BEVEL_MIN_CONTRAST:
        return False
    below = screenshot[y + 1:y + 1 + MAP_TEXTURE_CHECK_ROWS, x:x + width]
    return below.std(axis=1).mean() >= MAP_TEXTURE_MIN_STD


def find_map_top(screenshot: np.ndarray, x: int, arrow_y: int,
                 width: int = 960, height: int = 704) -> Optional[int]:
    """First row of the map, found by its beveled frame below the side arrows."""
    for y in range(arrow_y, arrow_y + MAP_TOP_SEARCH_ROWS):
        if y + height + 1 >= screenshot.shape[0]:
            return None
        if _is_map_top_frame(screenshot, x, y, width, height):
            return y + 1
    return None


def _get_map_top_offset(screenshot: np.ndarray, x: int, arrow_y: int, top_cache: dict) -> int:
    """Offset from arrows to the map top; learned once, like the arrow positions."""
    if top_cache.get('offset') is not None:
        return top_cache['offset']
    if top_cache.get('attempts', 0) >= MAP_TOP_MAX_ATTEMPTS:
        return MAP_TOP_DEFAULT_OFFSET

    top_cache['attempts'] = top_cache.get('attempts', 0) + 1
    top = find_map_top(screenshot, x, arrow_y)
    if top is None:
        if top_cache['attempts'] == MAP_TOP_MAX_ATTEMPTS:
            print("[GameWindow] WARNING: map frame of 960x704 not found. If the map looks smaller than usual "
                  "(taller chat / smaller window), clicks will miss - drag the chat smaller until the map is full size")
        return MAP_TOP_DEFAULT_OFFSET

    top_cache['offset'] = top - arrow_y
    print(f"[GameWindow] Map top found {top_cache['offset']}px below the side arrows")
    return top_cache['offset']


def get_game_window_position(screenshot: np.ndarray, arrow_images: dict,
                             left_cache: dict,
                             right_cache: dict,
                             top_cache: Optional[dict] = None) -> Optional[Tuple[int, int, int, int]]:
    left_pos = find_left_arrow(screenshot, arrow_images, left_cache)
    if left_pos is None:
        return None

    right_pos = find_right_arrow(screenshot, arrow_images, right_cache)
    if right_pos is None:
        return None

    x = ((left_pos[0] + 7 + right_pos[0]) // 2) - 480
    if top_cache is None:
        top_cache = {}
    y = left_pos[1] + _get_map_top_offset(screenshot, x, left_pos[1], top_cache)
    width = 960
    height = 704

    return (x, y, width, height)


def capture_game_window(screenshot: np.ndarray,
                        game_window_position: Tuple[int, int, int, int]) -> Optional[np.ndarray]:
    if game_window_position is None:
        return None
    x, y, w, h = game_window_position
    return screenshot[y:y + h, x:x + w]


def get_slot_from_coordinate(player_coord: Tuple[int, int, int],
                             target_coord: Tuple[int, int, int]) -> Optional[Tuple[int, int]]:
    diff_x = target_coord[0] - player_coord[0]
    diff_y = target_coord[1] - player_coord[1]

    if abs(diff_x) > 7 or abs(diff_y) > 5:
        return None

    return (7 + diff_x, 5 + diff_y)


def get_slot_screen_position(slot: Tuple[int, int],
                             game_window_position: Tuple[int, int, int, int]) -> Optional[Tuple[int, int]]:
    if game_window_position is None:
        return None

    gw_x, gw_y, gw_w, gw_h = game_window_position
    slot_x, slot_y = slot

    slot_width = gw_w // 15
    slot_height = gw_h // 11

    screen_x = gw_x + (slot_x * slot_width) + (slot_width // 2)
    screen_y = gw_y + (slot_y * slot_height) + (slot_height // 2)

    return (screen_x, screen_y)


def click_slot(slot: Tuple[int, int],
               game_window_position: Tuple[int, int, int, int]) -> bool:
    import pyautogui

    pos = get_slot_screen_position(slot, game_window_position)
    if pos is None:
        return False

    pyautogui.click(pos[0], pos[1])
    return True


def right_click_slot(slot: Tuple[int, int],
                     game_window_position: Tuple[int, int, int, int]) -> bool:
    import pyautogui

    pos = get_slot_screen_position(slot, game_window_position)
    if pos is None:
        return False

    pyautogui.rightClick(pos[0], pos[1])
    return True


def find_depot_locker(screenshot: np.ndarray,
                      game_window_position: Tuple[int, int, int, int]) -> Optional[Tuple[int, int, int, int]]:
    if game_window_position is None:
        return None

    depot_template_path = IMAGES_PATH.parent / "inventory" / "images" / "gamewindow" / "depot_locker.png"
    if not depot_template_path.exists():
        depot_template_path = IMAGES_PATH / "depot_locker.png"

    depot_template = load_gray_image(str(depot_template_path)) if depot_template_path.exists() else None
    if depot_template is None:
        return None

    gw_x, gw_y, gw_w, gw_h = game_window_position
    game_window = screenshot[gw_y:gw_y + gw_h, gw_x:gw_x + gw_w]

    pos = locate(game_window, depot_template, confidence=CONFIDENCE_UI_BUTTON)
    if pos is not None:
        return (gw_x + pos[0], gw_y + pos[1], pos[2], pos[3])

    return None

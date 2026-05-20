"""
Inventory Core - Container detection and manipulation.

Based on PyTibia's approach for container/backpack management.
"""
import time
from typing import Optional, Tuple, Dict

import cv2
import numpy as np
import pyautogui

from .config import (
    images,
    CONTAINER_WIDTH,
    CONTAINER_HEADER_HEIGHT,
    CONTAINER_CONTENT_Y,
    SLOT_SIZE,
    SLOT_SPACING,
    SLOTS_PER_ROW,
    CLOSE_BUTTON_OFFSET_X,
    CLOSE_BUTTON_OFFSET_Y,
)
from ...core.constants import CONFIDENCE_UI_DEFAULT, CONFIDENCE_DEPOT, CONFIDENCE_UI_BUTTON
from ...utils.jitter import jitter


def _locate(
    img: np.ndarray,
    template: np.ndarray,
    confidence: float = CONFIDENCE_UI_DEFAULT
) -> Optional[Tuple[int, int, int, int]]:
    """Locate template in image. Returns (x, y, w, h) or None."""
    if template is None or img is None:
        return None
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return None

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


def _locate_all(
    img: np.ndarray,
    template: np.ndarray,
    confidence: float = CONFIDENCE_UI_DEFAULT
) -> list:
    """Locate all occurrences of template in image."""
    if template is None or img is None:
        return []
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return []

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= confidence)

    matches = []
    for pt in zip(*locations[::-1]):
        matches.append((pt[0], pt[1], template.shape[1], template.shape[0]))

    return matches


# Cache for container positions
_container_cache: Dict[str, Tuple[int, int, int, int]] = {}

# Common container aliases
CONTAINER_ALIASES = {
    'main': ['backpack bottom', 'dragon backpack', 'crown backpack', 'backpack'],
    'loot': ['brocade backpack', 'fur backpack', 'beach backpack'],
    'depot': ['locker'],
}


def _find_container_template(container_name: str):
    """Find template by name or alias."""
    container_key = container_name.lower()

    # Direct match
    if container_key in images['containers']:
        return images['containers'][container_key]

    # Try aliases
    if container_key in CONTAINER_ALIASES:
        for alias in CONTAINER_ALIASES[container_key]:
            if alias in images['containers']:
                return images['containers'][alias]

    # Partial match (e.g., "dragon" matches "dragon backpack")
    for name, template in images['containers'].items():
        if container_key in name or name in container_key:
            return template

    return None


def get_container_position(
    screenshot: np.ndarray,
    container_name: str
) -> Optional[Tuple[int, int, int, int]]:
    """
    Find a container window position by name.

    Args:
        screenshot: Grayscale screenshot
        container_name: Name of container (e.g., 'backpack', 'depot', 'loot', 'main')

    Returns:
        (x, y, w, h) tuple or None if not found
    """
    global _container_cache

    container_key = container_name.lower()
    template = _find_container_template(container_name)

    if template is None:
        return None

    # Try cached position first
    if container_key in _container_cache:
        cached = _container_cache[container_key]
        x, y, w, h = cached
        if (y + h <= screenshot.shape[0] and x + w <= screenshot.shape[1]):
            region = screenshot[y:y+h, x:x+w]
            if region.shape == template.shape:
                match = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
                if cv2.minMaxLoc(match)[1] >= 0.9:
                    return cached

    # Search for container
    # Use lower confidence for depot/locker (templates may not match perfectly)
    is_depot = container_key in ['locker', 'depot']
    confidence = CONFIDENCE_DEPOT if is_depot else CONFIDENCE_UI_DEFAULT
    pos = _locate(screenshot, template, confidence=confidence)
    if pos is not None:
        _container_cache[container_key] = pos

    return pos


def is_container_open(screenshot: np.ndarray, container_name: str) -> bool:
    """Check if a container is currently open."""
    return get_container_position(screenshot, container_name) is not None


def get_slot_position(
    container_pos: Tuple[int, int, int, int],
    slot_index: int
) -> Tuple[int, int]:
    """
    Get the center position of a slot in a container.

    Args:
        container_pos: (x, y, w, h) of container window
        slot_index: 0-based slot index (left to right, top to bottom)

    Returns:
        (x, y) center position of slot
    """
    row = slot_index // SLOTS_PER_ROW
    col = slot_index % SLOTS_PER_ROW

    x = container_pos[0] + 4 + col * (SLOT_SIZE + SLOT_SPACING) + SLOT_SIZE // 2
    y = container_pos[1] + CONTAINER_CONTENT_Y + row * (SLOT_SIZE + SLOT_SPACING) + SLOT_SIZE // 2

    return (x, y)


def open_container(screenshot: np.ndarray, container_name: str) -> bool:
    """
    Open a container by right-clicking on it.

    Tries two strategies:
    1. Find by container title bar (containersbars template)
    2. Find by slot icon (slots template) - for items in inventory/containers

    Args:
        screenshot: Grayscale screenshot
        container_name: Name of container to open

    Returns:
        True if click was performed
    """
    container_key = container_name.lower()

    template = _find_container_template(container_name)
    if template is not None:
        pos = _locate(screenshot, template, confidence=CONFIDENCE_UI_BUTTON)
        if pos is not None:
            center_x = pos[0] + pos[2] // 2
            center_y = pos[1] + pos[3] // 2
            pyautogui.rightClick(center_x, center_y)
            return True

    slot_template = images['slots'].get(container_key)
    if slot_template is None:
        return False

    pos = _locate(screenshot, slot_template, confidence=CONFIDENCE_UI_BUTTON)
    if pos is None:
        return False

    center_x = pos[0] + pos[2] // 2
    center_y = pos[1] + pos[3] // 2
    pyautogui.rightClick(center_x, center_y)
    return True


def close_container(screenshot: np.ndarray, container_name: str) -> bool:
    """
    Close a container by clicking its X button.

    Args:
        screenshot: Grayscale screenshot
        container_name: Name of container to close

    Returns:
        True if click was performed
    """
    pos = get_container_position(screenshot, container_name)
    if pos is None:
        return False

    # Click close button (X) in top right
    close_x = pos[0] + CONTAINER_WIDTH + CLOSE_BUTTON_OFFSET_X
    close_y = pos[1] + CLOSE_BUTTON_OFFSET_Y
    pyautogui.click(close_x, close_y)

    # Clear cache
    _container_cache.pop(container_name.lower(), None)

    return True


def drag_item(
    from_pos: Tuple[int, int],
    to_pos: Tuple[int, int],
    duration: float = 0.3
) -> None:
    """
    Drag an item from one position to another.

    Args:
        from_pos: (x, y) source position
        to_pos: (x, y) destination position
        duration: Drag duration in seconds
    """
    pyautogui.moveTo(from_pos[0], from_pos[1])
    time.sleep(jitter(0.05))
    pyautogui.mouseDown()
    time.sleep(jitter(0.05))
    pyautogui.moveTo(to_pos[0], to_pos[1], duration=duration)
    time.sleep(jitter(0.05))
    pyautogui.mouseUp()


def is_depot_open(screenshot: np.ndarray) -> bool:
    """Check if depot chest is currently open."""
    # Use lower confidence for depot/locker (templates may not match perfectly)
    DEPOT_CONFIDENCE = 0.70

    # Check for depot chest container or locker
    depot_template = images['containers'].get('depot')
    if depot_template is not None:
        if _locate(screenshot, depot_template, confidence=DEPOT_CONFIDENCE) is not None:
            return True

    # Check for depot locker
    locker_template = images['containers'].get('locker')
    if locker_template is not None:
        if _locate(screenshot, locker_template, confidence=DEPOT_CONFIDENCE) is not None:
            return True

    return False


def open_depot_slot(screenshot: np.ndarray) -> bool:
    """
    Open the depot container by right-clicking the depot icon in the locker.

    Args:
        screenshot: Grayscale screenshot

    Returns:
        True if click was performed
    """
    slot_template = images['slots'].get('depot')
    if slot_template is None:
        return False

    pos = _locate(screenshot, slot_template, confidence=CONFIDENCE_UI_BUTTON)
    if pos is None:
        return False

    center_x = pos[0] + pos[2] // 2
    center_y = pos[1] + pos[3] // 2
    pyautogui.rightClick(center_x, center_y)
    return True


def open_depot_chest(
    screenshot: np.ndarray,
    chest_index: int = 0
) -> bool:
    """
    Open a specific depot chest by right-clicking its icon.

    Args:
        screenshot: Grayscale screenshot
        chest_index: Which depot chest to open (1-4)

    Returns:
        True if click was performed
    """
    chest_key = f'depot chest {chest_index + 1}'
    slot_template = images['slots'].get(chest_key)
    if slot_template is None:
        return False

    pos = _locate(screenshot, slot_template, confidence=CONFIDENCE_UI_BUTTON)
    if pos is None:
        return False

    center_x = pos[0] + pos[2] // 2
    center_y = pos[1] + pos[3] // 2
    pyautogui.rightClick(center_x, center_y)
    return True


def clear_container_cache() -> None:
    """Clear the container position cache."""
    global _container_cache
    _container_cache.clear()

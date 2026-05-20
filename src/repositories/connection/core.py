"""Connection repository - pure functions for disconnect/login screen detection."""
from typing import Optional, Tuple

import cv2
import numpy as np

from ...core.constants import (
    CONFIDENCE_RECONNECT,
    RECONNECT_CHAR_LIST_FIRST_ROW_OFFSET,
    RECONNECT_CHAR_LIST_ROW_HEIGHT,
    RECONNECT_CHAR_LIST_MAX_ROWS,
)
from .config import images


def _locate(screenshot: np.ndarray, template: Optional[np.ndarray],
            confidence: float = CONFIDENCE_RECONNECT) -> Optional[Tuple[int, int, int, int]]:
    """Locate template in screenshot. Returns (x, y, w, h) or None."""
    if template is None or screenshot is None:
        return None
    if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
        return None

    result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


def _get_center(box: Tuple[int, int, int, int]) -> Tuple[int, int]:
    """Get center point of a bounding box (x, y, w, h)."""
    return (box[0] + box[2] // 2, box[1] + box[3] // 2)


def is_disconnected(screenshot: np.ndarray) -> bool:
    """Check if the disconnect dialog is visible."""
    return _locate(screenshot, images['disconnectDialog']) is not None


def is_login_screen(screenshot: np.ndarray) -> bool:
    """Check if the login screen is visible."""
    return _locate(screenshot, images['loginScreen']) is not None


def is_character_list(screenshot: np.ndarray) -> bool:
    """Check if the character list is visible."""
    return _locate(screenshot, images['characterList']) is not None


def is_game_loaded(screenshot: np.ndarray) -> bool:
    """Check if the game is loaded by looking for HP icon."""
    from ..statusbar.locators import get_hp_icon_position
    return get_hp_icon_position(screenshot) is not None


def get_ok_button_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """Get center position of the OK button on disconnect dialog."""
    box = _locate(screenshot, images['okButton'])
    if box is None:
        return None
    return _get_center(box)


def get_login_button_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """Get center position of the Login button."""
    box = _locate(screenshot, images['loginButton'])
    if box is None:
        return None
    return _get_center(box)


def get_email_field_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """Get center position of the email field."""
    box = _locate(screenshot, images['emailField'])
    if box is None:
        return None
    return _get_center(box)


def get_password_field_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """Get center position of the password field."""
    box = _locate(screenshot, images['passwordField'])
    if box is None:
        return None
    return _get_center(box)


def get_character_row_positions(screenshot: np.ndarray) -> list:
    """Get click positions for all character rows in the list.

    Returns list of (x, y) tuples for each row, calculated from
    the 'Select Character' header position with fixed row height.
    """
    box = _locate(screenshot, images['characterList'])
    if box is None:
        return []
    header_bottom = box[1] + box[3]
    center_x = box[0] + box[2] // 2
    positions = []
    for i in range(RECONNECT_CHAR_LIST_MAX_ROWS):
        y = header_bottom + RECONNECT_CHAR_LIST_FIRST_ROW_OFFSET + (i * RECONNECT_CHAR_LIST_ROW_HEIGHT)
        positions.append((center_x, y))
    return positions


def get_enter_game_button_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """Get center position of the Enter Game button."""
    box = _locate(screenshot, images['enterGameButton'])
    if box is None:
        return None
    return _get_center(box)


class ConnectionRepository:
    """Thin facade over pure functions (PyTibia pattern)."""

    def is_disconnected(self, screenshot: np.ndarray) -> bool:
        return is_disconnected(screenshot)

    def is_login_screen(self, screenshot: np.ndarray) -> bool:
        return is_login_screen(screenshot)

    def is_character_list(self, screenshot: np.ndarray) -> bool:
        return is_character_list(screenshot)

    def is_game_loaded(self, screenshot: np.ndarray) -> bool:
        return is_game_loaded(screenshot)

    def get_ok_button_position(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        return get_ok_button_position(screenshot)

    def get_login_button_position(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        return get_login_button_position(screenshot)

    def get_email_field_position(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        return get_email_field_position(screenshot)

    def get_password_field_position(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        return get_password_field_position(screenshot)

    def get_character_row_positions(self, screenshot: np.ndarray) -> list:
        return get_character_row_positions(screenshot)

    def get_enter_game_button_position(self, screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
        return get_enter_game_button_position(screenshot)

"""
Input utilities - safe mouse and keyboard functions.

Automatically adjusts mouse coordinates by the ScreenCapture region offset
so that image-relative positions become absolute screen positions.
"""
import random
import time
from typing import Optional, Tuple

import pyautogui


# ---------------------------------------------------------------------------
# Screen offset: when ScreenCapture uses a sub-region (e.g. Tibia window),
# all detected positions are image-relative.  pyautogui needs absolute
# screen coordinates.  We patch click/rightClick/moveTo once at import time
# so every call site is fixed transparently.
# ---------------------------------------------------------------------------

_cached_offset = (0, 0)


def _get_screen_offset() -> Tuple[int, int]:
    """Return cached capture region offset."""
    return _cached_offset


def refresh_screen_offset() -> None:
    """Re-read capture region offset from ScreenCapture. Call after refresh_capture_region()."""
    global _cached_offset
    try:
        from ..core.screen import get_screen_capture
        region = get_screen_capture().get_capture_region()
        _cached_offset = (region.x, region.y) if region else (0, 0)
    except Exception:
        _cached_offset = (0, 0)


_original_click = pyautogui.click
_original_moveTo = pyautogui.moveTo
_original_rightClick = pyautogui.rightClick


def _offset_click(x=None, y=None, *args, **kwargs):
    if x is not None and y is not None:
        ox, oy = _get_screen_offset()
        x += ox
        y += oy
    return _original_click(x, y, *args, **kwargs)


def _offset_moveTo(x=None, y=None, *args, **kwargs):
    if x is not None and y is not None:
        ox, oy = _get_screen_offset()
        x += ox
        y += oy
    return _original_moveTo(x, y, *args, **kwargs)


def _offset_rightClick(x=None, y=None, **kwargs):
    if x is not None and y is not None:
        ox, oy = _get_screen_offset()
        x += ox
        y += oy
    return _original_rightClick(x, y, **kwargs)


# Patch click, moveTo and rightClick with offset wrappers.
# rightClick must be patched separately (not rely on internal click() call)
# because Arduino patch replaces _original_click with a different signature.
pyautogui.click = _offset_click
pyautogui.moveTo = _offset_moveTo
pyautogui.rightClick = _offset_rightClick


# ---------------------------------------------------------------------------
# Public utilities
# ---------------------------------------------------------------------------

def safe_click(x: int, y: int,
               restore_position: bool = True,
               delay_after: float = 0.0,
               random_offset: int = 0) -> Tuple[int, int]:
    """
    Safely click at position with optional mouse restoration.

    Args:
        x: X coordinate (image-relative, offset applied automatically).
        y: Y coordinate (image-relative, offset applied automatically).
        restore_position: Restore mouse to original position.
        delay_after: Delay after click in seconds.
        random_offset: Random offset range for more natural clicks.

    Returns:
        Actual click position (x, y).
    """
    if random_offset > 0:
        x += random.randint(-random_offset, random_offset)
        y += random.randint(-random_offset, random_offset)

    # Skip position save/restore when hardware input is active
    # (Arduino HID cannot track the current mouse position)
    if restore_position:
        try:
            from ..hardware import is_hardware_input
            if is_hardware_input():
                restore_position = False
        except ImportError:
            pass

    original = pyautogui.position() if restore_position else None

    pyautogui.click(x, y)

    if original:
        _original_moveTo(*original)

    if delay_after > 0:
        time.sleep(delay_after)

    return (x, y)


def safe_press(key: str, delay_after: float = 0.0) -> None:
    """
    Safely press a key.

    Args:
        key: Key to press.
        delay_after: Delay after press in seconds.
    """
    pyautogui.press(key)

    if delay_after > 0:
        time.sleep(delay_after)


def type_text(text: str,
              interval: float = 0.02,
              press_enter: bool = False) -> None:
    """
    Type text with natural timing.

    Args:
        text: Text to type.
        interval: Delay between characters.
        press_enter: Press enter after typing.
    """
    pyautogui.typewrite(text, interval=interval)

    if press_enter:
        pyautogui.press('enter')


def move_mouse_human(x: int, y: int,
                     duration: float = 0.2,
                     tween: str = 'easeInOutQuad') -> None:
    """
    Move mouse with human-like motion.

    Args:
        x: Target X coordinate (image-relative, offset applied automatically).
        y: Target Y coordinate (image-relative, offset applied automatically).
        duration: Movement duration in seconds.
        tween: Easing function name.
    """
    tween_func = getattr(pyautogui, tween, pyautogui.easeInOutQuad)

    pyautogui.moveTo(x, y, duration=duration, tween=tween_func)

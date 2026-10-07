"""
Input utilities - safe mouse and keyboard functions.

Automatically adjusts mouse coordinates by the ScreenCapture region offset
so that image-relative positions become absolute screen positions.
"""
import os
import random
import time
import traceback
from typing import Optional, Tuple

import pyautogui

from ..core.constants import CLICK_GUARD_REFRESH
from .focus_watch import remember_input


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


def get_screen_offset() -> Tuple[int, int]:
    """Top-left of the captured region on screen (screenshot pixel + offset = screen pixel)."""
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


# ---------------------------------------------------------------------------
# Click guard: a click that lands outside Tibia (Dock, menu bar, another app)
# takes the focus away, and every key press after it goes to the wrong app
# until the player clicks Tibia again. Refuse those clicks and say who asked.
# ---------------------------------------------------------------------------

_tibia_regions_cache: Tuple[list, float] = ([], 0.0)


def _tibia_regions() -> list:
    global _tibia_regions_cache
    regions, read_at = _tibia_regions_cache
    now = time.time()
    if now - read_at < CLICK_GUARD_REFRESH:
        return regions
    try:
        from .window import get_tibia_windows
        regions = [window['region'] for window in get_tibia_windows()]
    except Exception:
        regions = []  # no Quartz (capture card PC, other OS): can't tell, let clicks through
    _tibia_regions_cache = (regions, now)
    return regions


def is_inside_tibia(x: int, y: int) -> bool:
    """Absolute screen point inside a Tibia window. True when no Tibia window can be found."""
    regions = _tibia_regions()
    if not regions:
        return True
    return any(r.x <= x < r.x + r.width and r.y <= y < r.y + r.height for r in regions)


def _caller() -> str:
    """file:line of the code that asked for the click (outside this module and pyautogui)."""
    for frame in reversed(traceback.extract_stack()[:-1]):
        name = os.path.basename(frame.filename)
        if name != 'input.py' and 'pyautogui' not in frame.filename:
            return f"{name}:{frame.lineno}"
    return "?"


def _refused(action: str, x: int, y: int) -> bool:
    if is_inside_tibia(x, y):
        return False
    print(f"[Input] Refused {action} at ({x}, {y}) - outside the Tibia window (asked by {_caller()})")
    return True


_original_click = pyautogui.click
_original_moveTo = pyautogui.moveTo
_original_rightClick = pyautogui.rightClick


def _offset_click(x=None, y=None, *args, **kwargs):
    if x is not None and y is not None:
        ox, oy = _get_screen_offset()
        x += ox
        y += oy
        if _refused('click', x, y):
            return None
        remember_input(f"click ({x}, {y})")
    return _original_click(x, y, *args, **kwargs)


def _offset_moveTo(x=None, y=None, *args, **kwargs):
    if x is not None and y is not None:
        ox, oy = _get_screen_offset()
        x += ox
        y += oy
        remember_input(f"moveTo ({x}, {y})")
    return _original_moveTo(x, y, *args, **kwargs)


def _offset_rightClick(x=None, y=None, **kwargs):
    if x is not None and y is not None:
        ox, oy = _get_screen_offset()
        x += ox
        y += oy
        if _refused('right click', x, y):
            return None
        remember_input(f"rightClick ({x}, {y})")
    return _original_rightClick(x, y, **kwargs)


# Patch click, moveTo and rightClick with offset wrappers.
# rightClick must be patched separately (not rely on internal click() call)
# because Arduino patch replaces _original_click with a different signature.
pyautogui.click = _offset_click
pyautogui.moveTo = _offset_moveTo
pyautogui.rightClick = _offset_rightClick


def _recording(name, original):
    def send(*args, **kwargs):
        remember_input(f"{name} {args[0] if args else ''}".strip())
        return original(*args, **kwargs)
    return send


# Keys too, so the focus watchdog can list everything the bot sent before Tibia lost the input
for _name in ('press', 'keyDown', 'keyUp', 'hotkey'):
    setattr(pyautogui, _name, _recording(_name, getattr(pyautogui, _name)))


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


def alt_click(x: int, y: int) -> None:
    """
    Alt+Click (attack in Tibia). Option is released even if the click fails: a stuck Option
    turns the next click on another app into "switch to it and hide Tibia" on macOS.
    """
    pyautogui.keyDown('alt')
    try:
        pyautogui.click(x, y)
    finally:
        pyautogui.keyUp('alt')


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

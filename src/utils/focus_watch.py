"""
Focus watchdog (macOS): notice the moment Tibia stops getting the bot's input, and log the
bot's last inputs so the one that caused it can be found.

Reported symptom: while walking, a random Dock icon (Discord, WhatsApp...) turns grey with its
name shown, the bot stalls, then carries on. Three ways that can happen, all checked here:
- the mouse is outside the Tibia window (a click/move landed on the Dock),
- another app is in front,
- the Dock holds keyboard focus (then W/A/S/D jump between apps by first letter: d -> Discord).
"""
import os
import time
import traceback
from collections import deque
from typing import Optional

from ..core.constants import FOCUS_WATCH_INTERVAL, FOCUS_WATCH_HISTORY

_recent_inputs: deque = deque(maxlen=FOCUS_WATCH_HISTORY)


def _caller() -> str:
    """file:line of the bot code that sent the input (skips this package's wrappers and pyautogui)."""
    for frame in reversed(traceback.extract_stack()[:-2]):
        name = os.path.basename(frame.filename)
        if name in ('input.py', 'focus_watch.py') or 'pyautogui' in frame.filename:
            continue
        return f"{name}:{frame.lineno}"
    return "?"


def remember_input(action: str) -> None:
    _recent_inputs.append((time.time(), action, _caller()))


def recent_inputs_text(now: float) -> str:
    if not _recent_inputs:
        return "  (none)"
    return "\n".join(f"  {now - at:4.1f}s ago  {action:<24} from {caller}"
                     for at, action, caller in _recent_inputs)


def _front_app_name() -> Optional[str]:
    from AppKit import NSWorkspace
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    return app.localizedName() if app is not None else None


def _dock_focused_item() -> Optional[str]:
    """Title of the Dock item holding keyboard focus, or None when the Dock isn't focused."""
    from AppKit import NSRunningApplication
    from ApplicationServices import AXUIElementCreateApplication, AXUIElementCopyAttributeValue
    docks = NSRunningApplication.runningApplicationsWithBundleIdentifier_('com.apple.dock')
    if not docks:
        return None
    dock = AXUIElementCreateApplication(docks[0].processIdentifier())
    error, element = AXUIElementCopyAttributeValue(dock, 'AXFocusedUIElement', None)
    if error != 0 or element is None:
        return None
    error, title = AXUIElementCopyAttributeValue(element, 'AXTitle', None)
    return str(title) if error == 0 and title else "?"


def find_focus_problem() -> Optional[str]:
    """What is keeping input away from Tibia right now, or None if nothing."""
    import pyautogui
    from .input import is_inside_tibia

    dock_item = _dock_focused_item()
    if dock_item is not None:
        return f"the Dock has keyboard focus (on '{dock_item}')"
    front = _front_app_name()
    if front is not None and 'tibia' not in front.lower():
        return f"'{front}' is the front app, not Tibia"
    position = pyautogui.position()
    if not is_inside_tibia(position.x, position.y):
        return f"the mouse is at ({position.x}, {position.y}), outside the Tibia window"
    return None


class FocusWatch:
    """Checks every FOCUS_WATCH_INTERVAL; logs once when focus is lost and once when it's back."""

    def __init__(self):
        self._last_check = 0.0
        self._problem: Optional[str] = None
        self._problem_since = 0.0
        self._broken = False

    def check(self) -> None:
        now = time.time()
        if self._broken or now - self._last_check < FOCUS_WATCH_INTERVAL:
            return
        self._last_check = now
        try:
            problem = find_focus_problem()
        except Exception as error:  # no AppKit/AX (other OS, capture card PC): stay out of the way
            self._broken = True
            print(f"[Focus] Watchdog off: {error}")
            return
        self._report(problem, now)

    def _report(self, problem: Optional[str], now: float) -> None:
        if problem is None:
            if self._problem is not None:
                print(f"[Focus] Tibia has the input again after {now - self._problem_since:.1f}s")
            self._problem = None
            return
        if self._problem is not None:
            return
        self._problem = problem
        self._problem_since = now
        print(f"[Focus] TIBIA LOST THE INPUT: {problem}. Last bot inputs (newest last):\n"
              f"{recent_inputs_text(now)}")

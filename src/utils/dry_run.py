"""
Dry run: every keyboard/mouse call is printed instead of sent.

Swaps the same targets as the Arduino patch (src/hardware/patch.py):
the low-level _original_* functions behind the offset wrappers in input.py,
plus the pyautogui functions called directly elsewhere. Logged click/move
coordinates are therefore absolute screen positions.
"""
import pyautogui

from . import input as input_module


DIRECT_INPUT_FUNCTIONS = (
    'press', 'keyDown', 'keyUp', 'mouseDown', 'mouseUp',
    'scroll', 'typewrite', 'write', 'hotkey',
)

_enabled = False


def _format_call(name, args, kwargs):
    parts = [repr(arg) for arg in args] + [f"{key}={value!r}" for key, value in kwargs.items()]
    return f"{name}({', '.join(parts)})"


def _make_logger(name):
    def log_call(*args, **kwargs):
        print(f"[DRY RUN] {_format_call(name, args, kwargs)}")
    return log_call


def enable_dry_run():
    global _enabled
    input_module._original_click = _make_logger('click')
    input_module._original_moveTo = _make_logger('moveTo')
    input_module._original_rightClick = _make_logger('rightClick')
    for name in DIRECT_INPUT_FUNCTIONS:
        setattr(pyautogui, name, _make_logger(name))
    _enabled = True
    print("DRY RUN: keyboard and mouse input is logged, not sent")


def is_dry_run():
    return _enabled

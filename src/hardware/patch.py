"""
Monkey-patching for hardware backends.

Replaces pyautogui functions with Arduino equivalents so that
all existing call sites (40+ files) work without modification.
"""
import pyautogui

from . import arduino


_patched = False

# Saved originals for unpatch
_saved_originals = {}


def patch_for_arduino() -> None:
    """Replace pyautogui functions with Arduino HID equivalents.

    Preserves the offset wrappers in input.py by swapping
    _original_click/_original_moveTo instead of pyautogui.click/moveTo.
    """
    global _patched
    if _patched:
        return

    import src.utils.input as input_module

    # Save originals
    _saved_originals['input._original_click'] = input_module._original_click
    _saved_originals['input._original_moveTo'] = input_module._original_moveTo
    _saved_originals['input._original_rightClick'] = input_module._original_rightClick
    _saved_originals['pyautogui.press'] = pyautogui.press
    _saved_originals['pyautogui.keyDown'] = pyautogui.keyDown
    _saved_originals['pyautogui.keyUp'] = pyautogui.keyUp
    _saved_originals['pyautogui.mouseDown'] = pyautogui.mouseDown
    _saved_originals['pyautogui.mouseUp'] = pyautogui.mouseUp
    _saved_originals['pyautogui.scroll'] = pyautogui.scroll
    _saved_originals['pyautogui.typewrite'] = pyautogui.typewrite
    _saved_originals['pyautogui.write'] = pyautogui.write
    _saved_originals['pyautogui.hotkey'] = pyautogui.hotkey

    # Swap the low-level targets used by _offset_click / _offset_moveTo / _offset_rightClick
    input_module._original_click = arduino.click
    input_module._original_moveTo = arduino.moveTo
    input_module._original_rightClick = arduino.rightClick

    # Swap functions that are called directly on pyautogui elsewhere
    pyautogui.press = arduino.press
    pyautogui.keyDown = arduino.keyDown
    pyautogui.keyUp = arduino.keyUp
    pyautogui.mouseDown = arduino.mouseDown
    pyautogui.mouseUp = arduino.mouseUp
    pyautogui.scroll = arduino.scroll
    pyautogui.typewrite = arduino.typewrite
    pyautogui.write = arduino.write
    pyautogui.hotkey = arduino.hotkey

    # Give Arduino the original OS-level moveTo for precise cursor positioning.
    # Arduino HID button events + OS API positioning avoids macOS acceleration.
    arduino.set_os_moveTo(_saved_originals['input._original_moveTo'])

    _patched = True


def unpatch() -> None:
    """Restore all original pyautogui functions."""
    global _patched
    if not _patched:
        return

    import src.utils.input as input_module

    input_module._original_click = _saved_originals['input._original_click']
    input_module._original_moveTo = _saved_originals['input._original_moveTo']
    input_module._original_rightClick = _saved_originals['input._original_rightClick']
    pyautogui.press = _saved_originals['pyautogui.press']
    pyautogui.keyDown = _saved_originals['pyautogui.keyDown']
    pyautogui.keyUp = _saved_originals['pyautogui.keyUp']
    pyautogui.mouseDown = _saved_originals['pyautogui.mouseDown']
    pyautogui.mouseUp = _saved_originals['pyautogui.mouseUp']
    pyautogui.scroll = _saved_originals['pyautogui.scroll']
    pyautogui.typewrite = _saved_originals['pyautogui.typewrite']
    pyautogui.write = _saved_originals['pyautogui.write']
    pyautogui.hotkey = _saved_originals['pyautogui.hotkey']

    arduino.set_os_moveTo(None)
    _saved_originals.clear()
    _patched = False


def is_patched() -> bool:
    """Return True if Arduino patch is active."""
    return _patched


class use_software_input:
    """Context manager: temporarily restore original pyautogui functions.

    Used by reconnect detector so login typing goes through OS-level
    input (pyautogui/Quartz) instead of Arduino HID, which drops
    shifted characters on macOS with non-US input sources.

    Usage:
        from src.hardware.patch import use_software_input

        with use_software_input():
            pyautogui.click(x, y)
            pyautogui.write("email@test.com")
    """

    def __enter__(self):
        if _patched:
            unpatch()
            self._was_patched = True
        else:
            self._was_patched = False
        return self

    def __exit__(self, *exc):
        if self._was_patched:
            patch_for_arduino()
        return False

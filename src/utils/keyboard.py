"""
Keyboard utilities - Simple wrapper around pyautogui.

Note: Arrow keys cause issues on macOS with CGEvent, so we use WASD for movement.
"""
import pyautogui


def press(key: str):
    """Press and release a key."""
    pyautogui.press(key)


def keyDown(key: str):
    """Hold a key down."""
    pyautogui.keyDown(key)


def keyUp(key: str):
    """Release a key."""
    pyautogui.keyUp(key)


def hotkey(*keys):
    """Press multiple keys together (e.g., hotkey('ctrl', 'a'))."""
    pyautogui.hotkey(*keys)

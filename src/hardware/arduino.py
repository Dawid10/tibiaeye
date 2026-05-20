"""
Arduino HID backend - serial communication with Arduino Leonardo.

Mirrors pyautogui API so monkey-patching is transparent.
Protocol: one text line per command over serial (115200 baud).
"""
import time
from typing import Optional

from .constants import (
    ARDUINO_BAUD_RATE,
    ARDUINO_SERIAL_TIMEOUT,
    ARDUINO_COMMAND_DELAY,
    ARDUINO_CLICK_PRESS_DURATION,
    ARDUINO_CLICK_INTERVAL,
)

try:
    import serial
    SERIAL_AVAILABLE = True
except ImportError:
    SERIAL_AVAILABLE = False


_serial_connection = None
_debug = False
_os_moveTo = None


def set_debug(enabled: bool) -> None:
    """Enable/disable command logging. Shows every command sent to Arduino."""
    global _debug
    _debug = enabled


def set_os_moveTo(fn) -> None:
    """Set OS-level moveTo for precise cursor positioning.

    When set, click() and moveTo() use this for positioning (OS API)
    while button events still go through Arduino HID.
    This avoids macOS mouse acceleration mangling firmware-based moves.
    """
    global _os_moveTo
    _os_moveTo = fn




def connect(port: str) -> bool:
    """Connect to Arduino on given serial port. Returns True on success."""
    global _serial_connection

    if not SERIAL_AVAILABLE:
        print("pyserial not installed. Run: pip install pyserial")
        return False

    try:
        _serial_connection = serial.Serial(
            port,
            ARDUINO_BAUD_RATE,
            timeout=ARDUINO_SERIAL_TIMEOUT,
        )
        # Wait for Arduino reset after serial open
        time.sleep(2.0)

        # Read handshake
        _serial_connection.reset_input_buffer()
        _serial_connection.write(b"PING\n")
        time.sleep(0.1)
        response = _serial_connection.readline().decode("utf-8", errors="ignore").strip()

        if "TIBIAEYE_READY" in response or "PONG" in response:
            print(f"Arduino connected on {port}")
            return True

        print(f"Arduino handshake failed (got: '{response}')")
        disconnect()
        return False

    except Exception as e:
        print(f"Arduino connection error: {e}")
        _serial_connection = None
        return False


def disconnect() -> None:
    """Close serial connection."""
    global _serial_connection

    if _serial_connection and _serial_connection.is_open:
        _serial_connection.close()
    _serial_connection = None


def is_connected() -> bool:
    """Check if Arduino is connected and port is open."""
    return _serial_connection is not None and _serial_connection.is_open


def _send_command(cmd: str) -> None:
    """Send a command line to Arduino. No-op if disconnected."""
    if not is_connected():
        return
    try:
        if _debug:
            print(f"[Arduino HID] {cmd}")
        _serial_connection.write(f"{cmd}\n".encode("utf-8"))
        time.sleep(ARDUINO_COMMAND_DELAY)
    except Exception as e:
        print(f"[Arduino] Serial write failed: {e}")


# ---------------------------------------------------------------------------
# pyautogui-compatible API
# ---------------------------------------------------------------------------

def press(key, **kwargs) -> None:
    """Press and release a key."""
    _send_command(f"PRESS {key}")


def keyDown(key, **kwargs) -> None:
    """Hold a key down."""
    _send_command(f"KEYDOWN {key}")


def keyUp(key, **kwargs) -> None:
    """Release a key."""
    _send_command(f"KEYUP {key}")


def click(x=None, y=None, clicks=1, interval=0.0, button='left', **kwargs) -> None:
    """Click at position. Moves first if x/y given.

    When _os_moveTo is set, uses OS API for positioning and Arduino HID
    for button events (avoids macOS mouse acceleration on firmware moves).
    """
    if _os_moveTo and x is not None and y is not None:
        _os_moveTo(int(x), int(y))
        for i in range(clicks):
            if i > 0:
                time.sleep(ARDUINO_CLICK_INTERVAL)
            _send_command(f"MOUSEDOWN {button}")
            time.sleep(ARDUINO_CLICK_PRESS_DURATION)
            _send_command(f"MOUSEUP {button}")
        return

    if x is not None and y is not None:
        parts = [f"CLICK {int(x)} {int(y)}"]
        if button == 'right':
            parts.append("RIGHT")
        if clicks > 1:
            parts.append(str(clicks))
        _send_command(" ".join(parts))
        return

    for i in range(clicks):
        if i > 0:
            time.sleep(ARDUINO_CLICK_INTERVAL)
        _send_command(f"MOUSEDOWN {button}")
        time.sleep(ARDUINO_CLICK_PRESS_DURATION)
        _send_command(f"MOUSEUP {button}")


def rightClick(x=None, y=None, **kwargs) -> None:
    """Right-click at position."""
    click(x=x, y=y, button='right')


def moveTo(x=None, y=None, duration=0, **kwargs) -> None:
    """Move mouse to absolute position.

    When _os_moveTo is set, delegates to OS API for precision.
    """
    if x is None or y is None:
        return
    if _os_moveTo:
        _os_moveTo(int(x), int(y), duration=duration, **kwargs)
        return
    duration_ms = int(duration * 1000) if duration else 0
    cmd = f"MOVETO {int(x)} {int(y)}"
    if duration_ms > 0:
        cmd += f" {duration_ms}"
    _send_command(cmd)


def mouseDown(button='left', **kwargs) -> None:
    """Press mouse button down."""
    _send_command(f"MOUSEDOWN {button}")


def mouseUp(button='left', **kwargs) -> None:
    """Release mouse button."""
    _send_command(f"MOUSEUP {button}")


def scroll(amount, x=None, y=None, **kwargs) -> None:
    """Scroll wheel."""
    cmd = f"SCROLL {int(amount)}"
    if x is not None and y is not None:
        cmd += f" {int(x)} {int(y)}"
    _send_command(cmd)


def typewrite(text, interval=0.02, **kwargs) -> None:
    """Type text character by character via PRESS commands."""
    for i, char in enumerate(text):
        if i > 0 and interval > 0:
            time.sleep(interval)
        _send_command(f"PRESS {'space' if char == ' ' else char}")


def write(text, interval=0.02, **kwargs) -> None:
    """Alias for typewrite."""
    typewrite(text, interval=interval)


def hotkey(*keys, **kwargs) -> None:
    """Press key combination (e.g. hotkey('ctrl', 'c'))."""
    _send_command(f"HOTKEY {' '.join(keys)}")

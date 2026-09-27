"""
Hardware abstraction layer.

Provides transparent switching between software (pyautogui + mss),
Arduino HID, and full hardware (Arduino + capture card) modes.

Usage:
    from src.hardware import init_hardware, shutdown_hardware

    init_hardware("software")           # default, no changes
    init_hardware("arduino", "/dev/tty.usbmodem14101")
    init_hardware("full_hardware", "/dev/tty.usbmodem14101", 0)
"""
from typing import Optional

from .constants import MODE_SOFTWARE, MODE_ARDUINO, MODE_FULL_HARDWARE, MODE_CAPTURE_CARD


_active_mode = MODE_SOFTWARE


def init_hardware(mode: str = MODE_SOFTWARE,
                  arduino_port: str = "",
                  capture_device: int = 0,
                  debug: bool = False) -> None:
    """Initialize hardware backend.

    Args:
        mode: One of "software", "arduino", "full_hardware".
        arduino_port: Serial port for Arduino (e.g. "/dev/tty.usbmodem14101").
                      Empty string triggers auto-detection.
        capture_device: OpenCV device index for capture card.
        debug: Log every command sent to Arduino.
    """
    global _active_mode

    if mode == MODE_SOFTWARE:
        _active_mode = MODE_SOFTWARE
        print("Hardware mode: software (pyautogui + mss)")
        return

    if mode == MODE_CAPTURE_CARD:
        from . import capture
        if not capture.connect(capture_device):
            print("Capture card failed. Falling back to software mode.")
            _active_mode = MODE_SOFTWARE
            return

        from ..core.screen import get_screen_capture
        screen = get_screen_capture()
        screen.set_capture_backend("capture_card", capture.capture_frame)

        # Enable capture card mode in radar (lowers confidence thresholds)
        from ..repositories.radar.core import set_capture_card_mode
        set_capture_card_mode(True)

        _active_mode = MODE_CAPTURE_CARD
        print("Hardware mode: capture_card (pyautogui + capture card)")
        return

    from ..utils.dry_run import is_dry_run
    if is_dry_run():
        print("Dry run active: skipping Arduino input (would replace the dry-run loggers).")
        _active_mode = MODE_SOFTWARE
        return

    # Arduino modes need a serial connection
    port = arduino_port or _auto_detect_arduino()
    if not port:
        print("No Arduino port specified and auto-detect failed. Falling back to software mode.")
        _active_mode = MODE_SOFTWARE
        return

    from . import arduino, patch

    arduino.set_debug(debug)

    if not arduino.connect(port):
        print("Arduino connection failed. Falling back to software mode.")
        _active_mode = MODE_SOFTWARE
        return

    patch.patch_for_arduino()

    if mode == MODE_FULL_HARDWARE:
        from . import capture
        if not capture.connect(capture_device):
            print("Capture card failed. Using Arduino input + mss screenshots.")
            _active_mode = MODE_ARDUINO
            return

        # Wire capture card into ScreenCapture
        from ..core.screen import get_screen_capture
        screen = get_screen_capture()
        screen.set_capture_backend("capture_card", capture.capture_frame)

        from ..repositories.radar.core import set_capture_card_mode
        set_capture_card_mode(True)

        _active_mode = MODE_FULL_HARDWARE
        print("Hardware mode: full_hardware (Arduino HID + capture card)")
    else:
        _active_mode = MODE_ARDUINO
        print("Hardware mode: arduino (Arduino HID + mss)")


def shutdown_hardware() -> None:
    """Disconnect all hardware and restore software mode."""
    global _active_mode

    from . import capture

    if _active_mode in (MODE_ARDUINO, MODE_FULL_HARDWARE):
        from . import arduino, patch
        patch.unpatch()
        arduino.disconnect()

    capture.disconnect()

    # Remove capture backend from ScreenCapture
    try:
        from ..core.screen import get_screen_capture
        get_screen_capture().set_capture_backend(None, None)
    except Exception:
        pass

    _active_mode = MODE_SOFTWARE


def get_active_mode() -> str:
    """Return the currently active hardware mode."""
    return _active_mode


def is_hardware_input() -> bool:
    """Return True if input goes through hardware (Arduino)."""
    return _active_mode in (MODE_ARDUINO, MODE_FULL_HARDWARE)


def _auto_detect_arduino() -> Optional[str]:
    """Try to find an Arduino Leonardo serial port.

    Scans common port patterns on macOS and Linux.
    Returns first matching port or None.
    """
    try:
        import serial.tools.list_ports

        for port_info in serial.tools.list_ports.comports():
            desc = (port_info.description or "").lower()
            vid = port_info.vid

            # Arduino Leonardo VID:PID = 2341:8036
            if vid == 0x2341:
                return port_info.device

            if "arduino" in desc or "leonardo" in desc:
                return port_info.device

        return None
    except ImportError:
        return None

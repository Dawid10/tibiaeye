"""
Capture card backend - video capture via OpenCV.

Provides screen capture from an external capture card (e.g. Elgato)
as an alternative to MSS when the game blocks software screenshots.
"""
from typing import Optional

import cv2
import numpy as np

from .constants import CAPTURE_DEVICE_INDEX


_capture_device: Optional[cv2.VideoCapture] = None


def connect(device_index: int = CAPTURE_DEVICE_INDEX) -> bool:
    """Open capture device. Returns True on success."""
    global _capture_device

    _capture_device = cv2.VideoCapture(device_index)

    if not _capture_device.isOpened():
        print(f"Failed to open capture device {device_index}")
        _capture_device = None
        return False

    _capture_device.set(cv2.CAP_PROP_FRAME_WIDTH, 1920)
    _capture_device.set(cv2.CAP_PROP_FRAME_HEIGHT, 1080)

    actual_w = int(_capture_device.get(cv2.CAP_PROP_FRAME_WIDTH))
    actual_h = int(_capture_device.get(cv2.CAP_PROP_FRAME_HEIGHT))
    print(f"Capture card connected (device {device_index}, {actual_w}x{actual_h})")
    return True


def disconnect() -> None:
    """Release capture device."""
    global _capture_device

    if _capture_device is not None:
        _capture_device.release()
    _capture_device = None


def is_connected() -> bool:
    """Check if capture device is open."""
    return _capture_device is not None and _capture_device.isOpened()


def capture_frame(grayscale: bool = False) -> Optional[np.ndarray]:
    """Capture a full frame from the device. Returns BGR or grayscale array."""
    if not is_connected():
        return None

    ret, frame = _capture_device.read()
    if not ret:
        return None

    if grayscale:
        return cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)

    return frame


def capture_region(x: int, y: int, width: int, height: int,
                   grayscale: bool = False) -> Optional[np.ndarray]:
    """Capture a sub-region from the device frame."""
    frame = capture_frame(grayscale=False)
    if frame is None:
        return None

    region = frame[y:y + height, x:x + width]

    if grayscale:
        return cv2.cvtColor(region, cv2.COLOR_BGR2GRAY)

    return region

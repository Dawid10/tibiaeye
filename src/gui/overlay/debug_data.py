"""Thread-safe shared state for debug overlay data.

The gameloop thread writes debug data via update_debug_data(),
the GUI thread reads it via get_debug_data().
"""
import threading

_lock = threading.Lock()
_data = {}
_enabled = False


def set_debug_overlay_enabled(enabled):
    global _enabled
    _enabled = enabled


def is_debug_overlay_enabled():
    return _enabled


def update_debug_data(data):
    global _data
    with _lock:
        _data = data


def get_debug_data():
    with _lock:
        return _data.copy() if _data else {}

"""Overlay controller for Windows - tkinter Toplevel with color-key transparency."""
import ctypes
import ctypes.wintypes
import time
import tkinter as tk

import cv2

from ...core.screen import get_screen_capture
from .config import (
    POSITION_UPDATE_MS,
    ANIMATION_INTERVAL_MS,
    BORDER_WIDTH,
    OPACITY_MIN,
    OPACITY_MAX,
    PADDING,
)
from .animation import compute_pulse_opacity
from .positions import get_overlay_regions

TRANSPARENT_COLOR = '#000000'
COLOR_DARK = (0, 0x4d, 0)
COLOR_BRIGHT = (0, 0xff, 0)

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.windll.user32


def _is_tibia_active():
    hwnd = user32.GetForegroundWindow()
    if not hwnd:
        return False
    length = user32.GetWindowTextLengthW(hwnd)
    if length == 0:
        return False
    buf = ctypes.create_unicode_buffer(length + 1)
    user32.GetWindowTextW(hwnd, buf, length + 1)
    return 'tibia' in buf.value.lower()


def _lerp_color(t):
    """Interpolate between COLOR_DARK and COLOR_BRIGHT. t in [0, 1]."""
    r = int(COLOR_DARK[0] + (COLOR_BRIGHT[0] - COLOR_DARK[0]) * t)
    g = int(COLOR_DARK[1] + (COLOR_BRIGHT[1] - COLOR_DARK[1]) * t)
    b = int(COLOR_DARK[2] + (COLOR_BRIGHT[2] - COLOR_DARK[2]) * t)
    return f'#{r:02x}{g:02x}{b:02x}'


def _apply_capture_offset(regions, screen_capture):
    """Convert image-relative coords to screen coords."""
    for region in regions:
        bbox = region.get('bbox')
        if bbox is None:
            continue
        x, y, w, h = bbox
        sx, sy = screen_capture.to_screen_coords(x, y)
        region['bbox'] = (sx, sy, w, h)


class OverlayControllerTk:

    def __init__(self, tk_root):
        self._root = tk_root
        self._overlay = None
        self._canvas = None
        self._active = False
        self._visible = False
        self._start_time = 0.0
        self._position_timer_id = None
        self._animation_timer_id = None
        self._screen = None
        self._current_color = _lerp_color(0.5)
        self._regions = []

    def start(self):
        if self._active:
            return
        self._active = True
        self._visible = False
        self._start_time = time.time()
        self._screen = get_screen_capture()
        self._create_overlay()
        self._schedule_position_update()
        self._schedule_animation_update()

    def stop(self):
        if not self._active:
            return
        self._active = False

        if self._position_timer_id is not None:
            self._root.after_cancel(self._position_timer_id)
            self._position_timer_id = None

        if self._animation_timer_id is not None:
            self._root.after_cancel(self._animation_timer_id)
            self._animation_timer_id = None

        if self._overlay is not None:
            self._overlay.destroy()
            self._overlay = None
            self._canvas = None

        self._visible = False
        self._regions = []

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def _create_overlay(self):
        if self._overlay is not None:
            self._overlay.destroy()

        self._overlay = tk.Toplevel(self._root)
        self._overlay.title('TibiaVision Overlay')
        self._overlay.overrideredirect(True)
        self._overlay.attributes('-topmost', True)
        self._overlay.attributes('-transparentcolor', TRANSPARENT_COLOR)

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        self._overlay.geometry(f'{screen_w}x{screen_h}+0+0')

        self._canvas = tk.Canvas(
            self._overlay,
            width=screen_w,
            height=screen_h,
            bg=TRANSPARENT_COLOR,
            highlightthickness=0,
        )
        self._canvas.pack(fill='both', expand=True)

        self._overlay.update_idletasks()
        self._apply_click_through()

    def _apply_click_through(self):
        hwnd = self._get_overlay_hwnd()
        if hwnd is None:
            return
        style = user32.GetWindowLongW(hwnd, GWL_EXSTYLE)
        style |= WS_EX_TRANSPARENT | WS_EX_LAYERED | WS_EX_TOOLWINDOW
        user32.SetWindowLongW(hwnd, GWL_EXSTYLE, style)

    def _get_overlay_hwnd(self):
        if self._overlay is None:
            return None
        try:
            return int(self._overlay.wm_frame(), 16)
        except Exception:
            return None

    def _show(self):
        if not self._visible and self._overlay is not None:
            self._overlay.deiconify()
            self._overlay.lift()
            self._visible = True

    def _hide(self):
        if self._visible and self._overlay is not None:
            self._overlay.withdraw()
            self._visible = False

    def _redraw(self):
        if self._canvas is None:
            return
        self._canvas.delete('all')
        for region in self._regions:
            bbox = region.get('bbox')
            if bbox is None:
                continue
            x, y, w, h = bbox
            x1 = x - PADDING
            y1 = y - PADDING
            x2 = x + w + PADDING
            y2 = y + h + PADDING
            self._canvas.create_rectangle(
                x1, y1, x2, y2,
                outline=self._current_color,
                width=BORDER_WIDTH,
            )

    def _schedule_position_update(self):
        if not self._active:
            return

        try:
            if _is_tibia_active():
                self._screen.refresh_capture_region()
                self._show()

                img = self._screen.capture()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                regions = get_overlay_regions(gray)
                _apply_capture_offset(regions, self._screen)

                self._regions = regions
                self._redraw()
            else:
                self._hide()
        except Exception:
            pass

        self._position_timer_id = self._root.after(
            POSITION_UPDATE_MS, self._schedule_position_update
        )

    def _schedule_animation_update(self):
        if not self._active:
            return

        try:
            if self._visible:
                elapsed = time.time() - self._start_time
                opacity = compute_pulse_opacity(elapsed)
                t = (opacity - OPACITY_MIN) / (OPACITY_MAX - OPACITY_MIN)
                self._current_color = _lerp_color(t)
                self._redraw()
        except Exception:
            pass

        self._animation_timer_id = self._root.after(
            ANIMATION_INTERVAL_MS, self._schedule_animation_update
        )

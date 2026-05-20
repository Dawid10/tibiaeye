"""Overlay controller - orchestrates window, view, animation, and position updates."""
import time

import cv2
from AppKit import NSWorkspace

from ...core.screen import get_screen_capture
from .config import POSITION_UPDATE_MS, ANIMATION_INTERVAL_MS
from .animation import compute_pulse_opacity
from .window import create_overlay_window, get_screen_for_mss_region, _get_primary_screen
from .view import OverlayView
from .positions import get_overlay_regions

TIBIA_BUNDLE_ID = "com.cipsoft.tibia"
TIBIA_APP_NAME = "Tibia"


def _is_tibia_active() -> bool:
    app = NSWorkspace.sharedWorkspace().frontmostApplication()
    if app is None:
        return False
    bundle_id = app.bundleIdentifier() or ""
    name = app.localizedName() or ""
    return TIBIA_BUNDLE_ID in bundle_id or TIBIA_APP_NAME in name


def _apply_capture_offset(regions, capture_region):
    """Offset bboxes from image-relative to absolute Quartz points.

    MSS on macOS captures at logical resolution (1 pixel = 1 Quartz point),
    so no scale conversion is needed — just add the capture region origin.
    """
    if capture_region is None:
        return
    for region in regions:
        bbox = region.get('bbox')
        if bbox is None:
            continue
        x, y, w, h = bbox
        region['bbox'] = (
            capture_region.x + x,
            capture_region.y + y,
            w,
            h,
        )


class OverlayController:

    def __init__(self, tk_root):
        self._root = tk_root
        self._window = None
        self._view = None
        self._active = False
        self._visible = False
        self._start_time = 0.0
        self._position_timer_id = None
        self._animation_timer_id = None
        self._screen = None
        self._overlay_screen = None

    def start(self):
        if self._active:
            return

        self._active = True
        self._visible = False
        self._start_time = time.time()
        self._screen = get_screen_capture()

        self._create_overlay_on_screen(_get_primary_screen())

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

        if self._window is not None:
            self._window.orderOut_(None)
            self._window = None
            self._view = None

        self._overlay_screen = None
        self._visible = False

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def _create_overlay_on_screen(self, target_screen):
        """Create (or recreate) the overlay window on the given NSScreen."""
        was_visible = self._visible

        if self._window is not None:
            self._window.orderOut_(None)
            self._visible = False

        self._overlay_screen = target_screen
        self._window = create_overlay_window(target_screen)
        frame = self._window.frame()
        self._view = OverlayView.alloc().initWithFrame_(frame)
        self._window.setContentView_(self._view)

        if was_visible:
            self._window.orderFrontRegardless()
            self._visible = True

    def _ensure_correct_screen(self, capture_region):
        """Move overlay to the screen containing the capture region if needed."""
        if capture_region is None:
            target = _get_primary_screen()
        else:
            target = get_screen_for_mss_region(
                capture_region.x, capture_region.y,
                capture_region.width, capture_region.height,
            )

        if target is None:
            target = _get_primary_screen()

        if self._overlay_screen != target:
            self._create_overlay_on_screen(target)

    def _show(self):
        if not self._visible and self._window is not None:
            self._window.orderFrontRegardless()
            self._visible = True

    def _hide(self):
        if self._visible and self._window is not None:
            self._window.orderOut_(None)
            self._visible = False

    def _schedule_position_update(self):
        if not self._active:
            return

        try:
            if _is_tibia_active():
                self._screen.refresh_capture_region()
                capture_region = self._screen.get_capture_region()
                self._ensure_correct_screen(capture_region)

                self._show()
                img = self._screen.capture()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                regions = get_overlay_regions(gray)

                _apply_capture_offset(regions, capture_region)

                if self._view is not None:
                    self._view.update_regions(regions)
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
                if self._view is not None:
                    self._view.update_opacity(opacity)
        except Exception:
            pass

        self._animation_timer_id = self._root.after(
            ANIMATION_INTERVAL_MS, self._schedule_animation_update
        )

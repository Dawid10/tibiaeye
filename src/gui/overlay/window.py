"""NSWindow factory for transparent click-through overlay (macOS only)."""
from typing import Optional

from AppKit import (
    NSWindow,
    NSScreen,
    NSColor,
    NSBorderlessWindowMask,
    NSFloatingWindowLevel,
)


def _get_primary_screen():
    """Primary screen (with menu bar) = Cocoa global coordinate origin."""
    screens = NSScreen.screens()
    if screens and len(screens) > 0:
        return screens[0]
    return NSScreen.mainScreen()


def get_scale_factor() -> float:
    screen = _get_primary_screen()
    if screen is None:
        return 2.0
    return screen.backingScaleFactor()


def get_screen_for_mss_region(mss_x, mss_y, mss_w, mss_h):
    """Find the NSScreen that contains the center of an MSS-coordinate region."""
    primary = _get_primary_screen()
    if primary is None:
        return None

    scale = primary.backingScaleFactor()
    primary_h = primary.frame().size.height

    # Convert MSS center point (top-left origin, pixels) to Cocoa global (bottom-left origin, points)
    center_px = mss_x + mss_w / 2
    center_py = mss_y + mss_h / 2
    cocoa_x = center_px / scale
    cocoa_y = primary_h - center_py / scale

    for screen in NSScreen.screens():
        frame = screen.frame()
        if (frame.origin.x <= cocoa_x < frame.origin.x + frame.size.width and
                frame.origin.y <= cocoa_y < frame.origin.y + frame.size.height):
            return screen

    return primary


def create_overlay_window(target_screen=None) -> NSWindow:
    """Create overlay window on the given screen (defaults to primary)."""
    screen = target_screen or _get_primary_screen()
    frame = screen.frame()

    window = NSWindow.alloc().initWithContentRect_styleMask_backing_defer_(
        frame,
        NSBorderlessWindowMask,
        2,  # NSBackingStoreBuffered
        False,
    )
    window.setBackgroundColor_(NSColor.clearColor())
    window.setOpaque_(False)
    window.setLevel_(NSFloatingWindowLevel + 1)
    window.setIgnoresMouseEvents_(True)
    window.setHasShadow_(False)
    window.setSharingType_(0)  # NSWindowSharingNone - exclude from screen capture
    window.setCollectionBehavior_(1 << 4)  # NSWindowCollectionBehaviorStationary

    return window

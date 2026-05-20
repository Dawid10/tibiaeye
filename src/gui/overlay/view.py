"""NSView subclass that draws green pulsing rectangles over detected regions."""
import objc
from AppKit import NSView, NSColor, NSBezierPath

from .config import BORDER_WIDTH, COLOR_RGB, PADDING
from .window import _get_primary_screen


class OverlayView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(OverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._regions = []
        self._opacity = 0.5
        return self

    def isFlipped(self):
        return False

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(self.bounds())

        if not self._regions:
            return

        primary = _get_primary_screen()
        if primary is None:
            return
        primary_h = primary.frame().size.height

        # Get the screen this view's window is on
        window = self.window()
        screen = window.screen() if window else primary
        if screen is None:
            screen = primary
        screen_origin = screen.frame().origin

        r, g, b = COLOR_RGB
        color = NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, self._opacity)
        color.set()

        for region in self._regions:
            bbox = region.get('bbox')
            if bbox is None:
                continue

            # bbox is in absolute Quartz points (top-left origin).
            # MSS on macOS captures at logical resolution (1 pixel = 1 point).
            qx, qy, qw, qh = bbox

            # Apply padding in points (draw OUTSIDE the detection region)
            qx -= PADDING
            qy -= PADDING
            qw += PADDING * 2
            qh += PADDING * 2

            # Quartz points (top-left origin) → Cocoa view-local points (bottom-left origin)
            # 1. Flip Y: cocoa_y = primary_h - quartz_bottom
            # 2. View-local: subtract the overlay screen's Cocoa origin
            view_x = qx - screen_origin.x
            view_y = (primary_h - qy - qh) - screen_origin.y
            view_w = qw
            view_h = qh

            path = NSBezierPath.bezierPathWithRect_(
                ((view_x, view_y), (view_w, view_h))
            )
            path.setLineWidth_(BORDER_WIDTH)
            path.stroke()

    def update_regions(self, regions):
        self._regions = regions

    def update_opacity(self, opacity):
        self._opacity = opacity
        self.setNeedsDisplay_(True)

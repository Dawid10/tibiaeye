"""Debug overlay for macOS - transparent click-through grid + creature markers.

Uses NSWindow + NSView (same pattern as the screen overlay controller.py).
Replaces the Windows-only tkinter + ctypes approach.
"""
import objc
from AppKit import NSView, NSColor, NSBezierPath, NSFont, NSString, NSMutableDictionary
from Foundation import NSMakeRect, NSMakePoint

from .debug_data import get_debug_data, set_debug_overlay_enabled
from .window import create_overlay_window, _get_primary_screen, get_screen_for_mss_region
from ...core.screen import get_screen_capture

DEBUG_UPDATE_MS = 80

# Colors (r, g, b, a) in 0.0-1.0 range
COLOR_GRID = (0.1, 0.29, 0.1, 0.8)
COLOR_WALKABLE_DOT = (0.05, 0.3, 0.05, 1.0)
COLOR_BLOCKED = (0.3, 0.05, 0.05, 1.0)
COLOR_PLAYER = (0.27, 0.53, 1.0, 1.0)
COLOR_TARGET = (1.0, 1.0, 0.0, 1.0)
COLOR_CREATURE = (0.0, 0.87, 0.0, 1.0)
COLOR_ATTACKING = (1.0, 0.53, 0.0, 1.0)
COLOR_INFO_BG = (0.04, 0.04, 0.04, 0.85)
COLOR_INFO_TEXT = (0.8, 0.8, 0.8, 1.0)

FONT_SIZE_LABEL = 9.0
FONT_SIZE_LABEL_BOLD = 10.0
FONT_SIZE_INFO = 10.0
FONT_SIZE_DIST = 8.0


def _nscolor(r, g, b, a=1.0):
    return NSColor.colorWithCalibratedRed_green_blue_alpha_(r, g, b, a)


def _make_font(size, bold=False):
    if bold:
        return NSFont.boldSystemFontOfSize_(size)
    return NSFont.monospacedSystemFontOfSize_weight_(size, 0.0)


def _draw_text(text, x, y, color_tuple, font, anchor_center=True):
    """Draw text at position. Cocoa coords (bottom-left origin)."""
    attrs = NSMutableDictionary.dictionary()
    attrs['NSFont'] = font
    attrs['NSColor'] = _nscolor(*color_tuple)
    ns_str = NSString.stringWithString_(text)
    size = ns_str.sizeWithAttributes_(attrs)
    if anchor_center:
        x -= size.width / 2
        y -= size.height / 2
    ns_str.drawAtPoint_withAttributes_(NSMakePoint(x, y), attrs)


class DebugOverlayView(NSView):

    def initWithFrame_(self, frame):
        self = objc.super(DebugOverlayView, self).initWithFrame_(frame)
        if self is None:
            return None
        self._debug_data = {}
        self._screen_offset = (0, 0)
        self._primary_h = 0.0
        self._screen_origin = (0.0, 0.0)
        return self

    def isFlipped(self):
        return False

    def setDebugData_offset_primaryH_screenOrigin_(self, data, offset, primary_h, screen_origin):
        self._debug_data = data
        self._screen_offset = offset
        self._primary_h = primary_h
        self._screen_origin = screen_origin
        self.setNeedsDisplay_(True)

    def _to_view(self, qx, qy):
        """Convert quartz coords (top-left origin, points) to view-local (bottom-left origin)."""
        view_x = qx - self._screen_origin[0]
        view_y = (self._primary_h - qy) - self._screen_origin[1]
        return view_x, view_y

    def drawRect_(self, rect):
        NSColor.clearColor().set()
        NSBezierPath.fillRect_(self.bounds())

        data = self._debug_data
        if not data:
            return

        gw_pos = data.get('gw_position')
        if not gw_pos:
            return

        ox, oy = self._screen_offset
        gw_qx = ox + gw_pos[0]
        gw_qy = oy + gw_pos[1]
        gw_w = gw_pos[2]
        gw_h = gw_pos[3]
        slot_w = data.get('slot_width', 64)

        creatures = data.get('creatures', [])

        walkable = data.get('walkable')
        bfs_distances = data.get('bfs_distances')
        if walkable is not None:
            self._draw_walkable(gw_qx, gw_qy, slot_w, walkable, bfs_distances, creatures)

        self._draw_grid(gw_qx, gw_qy, gw_w, gw_h, slot_w)
        self._draw_creatures(gw_qx, gw_qy, slot_w, creatures)
        self._draw_player(gw_qx, gw_qy, slot_w)
        self._draw_info(gw_qx, gw_qy, gw_w, data)

    def _draw_grid(self, gw_qx, gw_qy, gw_w, gw_h, slot_w):
        _nscolor(*COLOR_GRID).set()
        for col in range(16):
            x = gw_qx + col * slot_w
            vx, vy_top = self._to_view(x, gw_qy)
            _, vy_bot = self._to_view(x, gw_qy + gw_h)
            path = NSBezierPath.bezierPath()
            path.moveToPoint_(NSMakePoint(vx, vy_top))
            path.lineToPoint_(NSMakePoint(vx, vy_bot))
            path.setLineWidth_(1.0)
            path.stroke()
        for row in range(12):
            y = gw_qy + row * slot_w
            vx_left, vy = self._to_view(gw_qx, y)
            vx_right, _ = self._to_view(gw_qx + gw_w, y)
            path = NSBezierPath.bezierPath()
            path.moveToPoint_(NSMakePoint(vx_left, vy))
            path.lineToPoint_(NSMakePoint(vx_right, vy))
            path.setLineWidth_(1.0)
            path.stroke()

    def _draw_walkable(self, gw_qx, gw_qy, slot_w, walkable, bfs_distances, creatures=None):
        rows, cols = walkable.shape[:2]

        detail_tiles = set()
        if creatures:
            for c in creatures:
                slot = c.get('slot')
                if not slot:
                    continue
                sc, sr = slot
                for dr in range(-2, 3):
                    for dc in range(-2, 3):
                        detail_tiles.add((sr + dr, sc + dc))

        font_dist = _make_font(FONT_SIZE_DIST)

        for row in range(min(rows, 11)):
            for col in range(min(cols, 15)):
                if row == 5 and col == 7:
                    continue

                is_walkable = walkable[row, col] > 0
                qx = gw_qx + col * slot_w + slot_w // 2
                qy = gw_qy + row * slot_w + slot_w // 2
                vx, vy = self._to_view(qx, qy)

                if not is_walkable:
                    _nscolor(*COLOR_BLOCKED).set()
                    NSBezierPath.fillRect_(NSMakeRect(vx - 3, vy - 3, 6, 6))
                    continue

                if not bfs_distances:
                    continue

                dist = bfs_distances.get((row, col))
                if dist is None or dist == 0:
                    continue

                intensity = max(50, 255 - int((dist / 20) * 200)) / 255.0

                if (row, col) in detail_tiles:
                    _nscolor(0.0, intensity, 0.0, 1.0).set()
                    path = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(vx - 4, vy - 4, 8, 8))
                    path.fill()
                    _draw_text(str(dist), vx, vy, (0.67, 0.93, 0.67, 1.0), font_dist)
                else:
                    _nscolor(0.0, intensity, 0.0, 1.0).set()
                    path = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(vx - 2, vy - 2, 4, 4))
                    path.fill()

    def _draw_creatures(self, gw_qx, gw_qy, slot_w, creatures):
        font_label = _make_font(FONT_SIZE_LABEL)
        font_bold = _make_font(FONT_SIZE_LABEL_BOLD, bold=True)

        for c in creatures:
            slot = c.get('slot')
            if not slot:
                continue
            col, row = slot
            qx = gw_qx + col * slot_w + slot_w // 2
            qy = gw_qy + row * slot_w + slot_w // 2
            vx, vy = self._to_view(qx, qy)

            name = c.get('name', '?')
            method = c.get('id_method', '')
            bfs_dist = c.get('bfs_distance')
            is_target = c.get('is_target', False)
            is_attacking = c.get('is_attacking', False)

            dist_str = f" d={bfs_dist}" if bfs_dist is not None else ""

            if is_target:
                self._draw_target_marker(vx, vy, name, font_bold)
            elif is_attacking:
                _nscolor(*COLOR_ATTACKING).set()
                path = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(vx - 10, vy - 10, 20, 20))
                path.setLineWidth_(2.0)
                path.stroke()
                _draw_text(f"{name} ({method}){dist_str}", vx, vy + 18, COLOR_ATTACKING, font_label)
            else:
                _nscolor(*COLOR_CREATURE).set()
                path = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(vx - 6, vy - 6, 12, 12))
                path.setLineWidth_(2.0)
                path.stroke()
                _draw_text(f"{name} ({method}){dist_str}", vx, vy + 14, COLOR_CREATURE, font_label)

    def _draw_target_marker(self, vx, vy, name, font):
        _nscolor(*COLOR_TARGET).set()
        size = 14
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(NSMakePoint(vx - size, vy))
        path.lineToPoint_(NSMakePoint(vx + size, vy))
        path.setLineWidth_(2.0)
        path.stroke()
        path = NSBezierPath.bezierPath()
        path.moveToPoint_(NSMakePoint(vx, vy - size))
        path.lineToPoint_(NSMakePoint(vx, vy + size))
        path.setLineWidth_(2.0)
        path.stroke()
        oval = NSBezierPath.bezierPathWithOvalInRect_(NSMakeRect(vx - 10, vy - 10, 20, 20))
        oval.setLineWidth_(2.0)
        oval.stroke()
        _draw_text(f"TARGET: {name}", vx, vy + 20, COLOR_TARGET, font)

    def _draw_player(self, gw_qx, gw_qy, slot_w):
        qx = gw_qx + 7 * slot_w + slot_w // 2
        qy = gw_qy + 5 * slot_w + slot_w // 2
        vx, vy = self._to_view(qx, qy)
        _nscolor(*COLOR_PLAYER).set()
        NSBezierPath.strokeRect_(NSMakeRect(vx - 8, vy - 8, 16, 16))
        font_bold = _make_font(FONT_SIZE_LABEL_BOLD, bold=True)
        _draw_text('YOU', vx, vy + 14, COLOR_PLAYER, font_bold)

    def _draw_info(self, gw_qx, gw_qy, gw_w, data):
        hp = data.get('hp_percent', -1)
        mana = data.get('mana_percent', -1)
        target = data.get('target_name', 'None')
        task = data.get('task_name', 'idle')
        tick = data.get('tick_count', 0)
        coord = data.get('coordinate')
        is_attacking = data.get('is_attacking', False)
        creature_count = len(data.get('creatures', []))

        coord_str = f"({coord[0]},{coord[1]},{coord[2]})" if coord else "N/A"

        lines = [
            f"Tick: {tick}  |  HP: {hp}%  |  Mana: {mana}%",
            f"Coord: {coord_str}  |  Target: {target}",
            f"Task: {task}  |  Attacking: {is_attacking}  |  Creatures: {creature_count}",
        ]

        line_h = 15
        panel_h = line_h * len(lines) + 8
        panel_qy = gw_qy - panel_h - 4

        vx_left, vy_top = self._to_view(gw_qx, panel_qy)
        vx_right, vy_bot = self._to_view(gw_qx + gw_w, panel_qy + panel_h)

        _nscolor(*COLOR_INFO_BG).set()
        NSBezierPath.fillRect_(NSMakeRect(vx_left, vy_bot, vx_right - vx_left, vy_top - vy_bot))
        _nscolor(*COLOR_GRID).set()
        NSBezierPath.strokeRect_(NSMakeRect(vx_left, vy_bot, vx_right - vx_left, vy_top - vy_bot))

        font_info = _make_font(FONT_SIZE_INFO)
        for i, line in enumerate(lines):
            text_qy = panel_qy + 4 + i * line_h + line_h // 2
            _, text_vy = self._to_view(0, text_qy)
            _draw_text(line, vx_left + 6, text_vy, COLOR_INFO_TEXT, font_info, anchor_center=False)


class DebugOverlayController:

    def __init__(self, tk_root):
        self._root = tk_root
        self._window = None
        self._view = None
        self._active = False
        self._timer_id = None
        self._screen = None
        self._overlay_screen = None

    @property
    def is_active(self):
        return self._active

    def start(self):
        if self._active:
            return
        self._active = True
        set_debug_overlay_enabled(True)
        self._screen = get_screen_capture()
        self._create_overlay_on_screen(_get_primary_screen())
        self._schedule_update()

    def stop(self):
        if not self._active:
            return
        self._active = False
        set_debug_overlay_enabled(False)
        if self._timer_id is not None:
            self._root.after_cancel(self._timer_id)
            self._timer_id = None
        if self._window is not None:
            self._window.orderOut_(None)
            self._window = None
            self._view = None
        self._overlay_screen = None

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    def _create_overlay_on_screen(self, target_screen):
        if self._window is not None:
            self._window.orderOut_(None)

        self._overlay_screen = target_screen
        self._window = create_overlay_window(target_screen)
        frame = self._window.frame()
        self._view = DebugOverlayView.alloc().initWithFrame_(frame)
        self._window.setContentView_(self._view)
        self._window.orderFrontRegardless()

    def _ensure_correct_screen(self, capture_region):
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

    def _schedule_update(self):
        if not self._active:
            return
        try:
            self._redraw()
        except Exception:
            pass
        self._timer_id = self._root.after(DEBUG_UPDATE_MS, self._schedule_update)

    def _get_screen_offset(self):
        if self._screen is None:
            return (0, 0)
        region = self._screen.get_capture_region()
        if region is None:
            return (0, 0)
        return (region.x, region.y)

    def _redraw(self):
        if self._view is None:
            return

        data = get_debug_data()
        if not data:
            return

        if self._screen is not None:
            capture_region = self._screen.get_capture_region()
            self._ensure_correct_screen(capture_region)

        primary = _get_primary_screen()
        primary_h = primary.frame().size.height if primary else 0.0

        screen_origin = (0.0, 0.0)
        if self._window is not None:
            screen = self._window.screen()
            if screen is not None:
                origin = screen.frame().origin
                screen_origin = (origin.x, origin.y)

        offset = self._get_screen_offset()
        self._view.setDebugData_offset_primaryH_screenOrigin_(data, offset, primary_h, screen_origin)

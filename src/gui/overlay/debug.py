"""Debug overlay - transparent click-through grid + creature markers over game window.

Shows on top of Tibia:
- 15x11 grid dividing the game window into slots
- Walkable/blocked tile indicators (green dot / red square)
- BFS distance heatmap (brighter green = closer to player)
- Creature markers with names, ID method, and BFS distance
- Target crosshair on closest creature
- Player marker at center (7, 5)
- Info panel: HP, Mana, Target, Task, Tick, Coordinate
"""
import ctypes
import tkinter as tk

from .debug_data import get_debug_data, set_debug_overlay_enabled
from ...core.screen import get_screen_capture

GWL_EXSTYLE = -20
WS_EX_TRANSPARENT = 0x00000020
WS_EX_LAYERED = 0x00080000
WS_EX_TOOLWINDOW = 0x00000080

user32 = ctypes.windll.user32

# Use a non-black color key (existing overlay uses #000000)
TRANSPARENT_COLOR = '#010101'

DEBUG_UPDATE_MS = 80

# Colors
COLOR_GRID = '#1a4a1a'
COLOR_WALKABLE_DOT = '#0d4d0d'
COLOR_BLOCKED = '#4d0d0d'
COLOR_PLAYER = '#4488ff'
COLOR_TARGET = '#ffff00'
COLOR_CREATURE = '#00dd00'
COLOR_ATTACKING = '#ff8800'
COLOR_HP_BAR = '#00cccc'
COLOR_INFO_BG = '#0a0a0a'
COLOR_INFO_TEXT = '#cccccc'

FONT_LABEL = ('Consolas', 8)
FONT_LABEL_BOLD = ('Consolas', 9, 'bold')
FONT_INFO = ('Consolas', 9)
FONT_DIST = ('Consolas', 7)


class DebugOverlayController:

    def __init__(self, tk_root):
        self._root = tk_root
        self._overlay = None
        self._canvas = None
        self._active = False
        self._timer_id = None
        self._screen = None

    @property
    def is_active(self):
        return self._active

    def start(self):
        if self._active:
            return
        self._active = True
        set_debug_overlay_enabled(True)
        self._screen = get_screen_capture()
        self._create_overlay()
        self._schedule_update()

    def stop(self):
        if not self._active:
            return
        self._active = False
        set_debug_overlay_enabled(False)
        if self._timer_id is not None:
            self._root.after_cancel(self._timer_id)
            self._timer_id = None
        if self._overlay is not None:
            self._overlay.destroy()
            self._overlay = None
            self._canvas = None

    def toggle(self):
        if self._active:
            self.stop()
        else:
            self.start()

    # -- window setup --

    def _create_overlay(self):
        self._overlay = tk.Toplevel(self._root)
        self._overlay.title('TibiaVision Debug')
        self._overlay.overrideredirect(True)
        self._overlay.attributes('-topmost', True)
        self._overlay.attributes('-transparentcolor', TRANSPARENT_COLOR)

        screen_w = user32.GetSystemMetrics(0)
        screen_h = user32.GetSystemMetrics(1)
        self._overlay.geometry(f'{screen_w}x{screen_h}+0+0')

        self._canvas = tk.Canvas(
            self._overlay,
            width=screen_w, height=screen_h,
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

    # -- update loop --

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

    # -- main draw --

    def _redraw(self):
        if self._canvas is None:
            return
        self._canvas.delete('all')

        data = get_debug_data()
        if not data:
            return

        gw_pos = data.get('gw_position')
        if not gw_pos:
            return

        ox, oy = self._get_screen_offset()
        gw_x = ox + gw_pos[0]
        gw_y = oy + gw_pos[1]
        gw_w = gw_pos[2]
        gw_h = gw_pos[3]
        slot_w = data.get('slot_width', 64)

        creatures = data.get('creatures', [])

        walkable = data.get('walkable')
        bfs_distances = data.get('bfs_distances')
        if walkable is not None:
            self._draw_walkable(gw_x, gw_y, slot_w, walkable, bfs_distances, creatures)

        self._draw_grid(gw_x, gw_y, gw_w, gw_h, slot_w)

        bars = data.get('bars', [])
        if bars:
            self._draw_bars(gw_x, gw_y, bars)

        self._draw_creatures(gw_x, gw_y, slot_w, creatures)

        self._draw_player(gw_x, gw_y, slot_w)

        self._draw_info(gw_x, gw_y, gw_w, data)

    # -- grid --

    def _draw_grid(self, gw_x, gw_y, gw_w, gw_h, slot_w):
        for col in range(16):
            x = gw_x + col * slot_w
            self._canvas.create_line(x, gw_y, x, gw_y + gw_h, fill=COLOR_GRID, width=1)
        for row in range(12):
            y = gw_y + row * slot_w
            self._canvas.create_line(gw_x, y, gw_x + gw_w, y, fill=COLOR_GRID, width=1)

    # -- walkable tiles --

    def _draw_walkable(self, gw_x, gw_y, slot_w, walkable, bfs_distances, creatures=None):
        rows, cols = walkable.shape[:2]

        # Build set of tiles near creatures (radius 2) for detailed BFS text
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

        create_oval = self._canvas.create_oval
        create_rect = self._canvas.create_rectangle
        create_text = self._canvas.create_text

        for row in range(min(rows, 11)):
            for col in range(min(cols, 15)):
                if row == 5 and col == 7:
                    continue

                is_walkable = walkable[row, col] > 0

                if not is_walkable:
                    cx = gw_x + col * slot_w + slot_w // 2
                    cy = gw_y + row * slot_w + slot_w // 2
                    create_rect(cx - 3, cy - 3, cx + 3, cy + 3,
                                fill=COLOR_BLOCKED, outline='')
                    continue

                if not bfs_distances:
                    continue

                dist = bfs_distances.get((row, col))
                if dist is None or dist == 0:
                    continue

                cx = gw_x + col * slot_w + slot_w // 2
                cy = gw_y + row * slot_w + slot_w // 2
                intensity = max(50, 255 - int((dist / 20) * 200))
                color = f'#00{intensity:02x}00'

                if (row, col) in detail_tiles:
                    create_oval(cx - 4, cy - 4, cx + 4, cy + 4,
                                fill=color, outline='')
                    create_text(cx, cy, text=str(dist),
                                fill='#aaeeaa', font=FONT_DIST)
                else:
                    create_oval(cx - 2, cy - 2, cx + 2, cy + 2,
                                fill=color, outline='')

    # -- HP bars --

    def _draw_bars(self, gw_x, gw_y, bars):
        from ...repositories.gamewindow.config import BAR_WIDTH
        for bx, by in bars:
            sx = gw_x + bx
            sy = gw_y + by
            self._canvas.create_rectangle(
                sx, sy - 1, sx + BAR_WIDTH, sy + 3,
                outline=COLOR_HP_BAR, width=1,
            )

    # -- creatures --

    def _draw_creatures(self, gw_x, gw_y, slot_w, creatures):
        for c in creatures:
            slot = c.get('slot')
            if not slot:
                continue
            col, row = slot
            cx = gw_x + col * slot_w + slot_w // 2
            cy = gw_y + row * slot_w + slot_w // 2

            name = c.get('name', '?')
            method = c.get('id_method', '')
            bfs_dist = c.get('bfs_distance')
            is_target = c.get('is_target', False)
            is_attacking = c.get('is_attacking', False)

            if is_target:
                self._draw_target_marker(cx, cy, name)
            elif is_attacking:
                self._canvas.create_oval(
                    cx - 10, cy - 10, cx + 10, cy + 10,
                    outline=COLOR_ATTACKING, width=2,
                )
                dist_str = f" d={bfs_dist}" if bfs_dist is not None else ""
                self._canvas.create_text(
                    cx, cy - 18, text=f"{name} ({method}){dist_str}",
                    fill=COLOR_ATTACKING, font=FONT_LABEL,
                )
            else:
                self._canvas.create_oval(
                    cx - 6, cy - 6, cx + 6, cy + 6,
                    outline=COLOR_CREATURE, width=2,
                )
                dist_str = f" d={bfs_dist}" if bfs_dist is not None else ""
                self._canvas.create_text(
                    cx, cy - 14, text=f"{name} ({method}){dist_str}",
                    fill=COLOR_CREATURE, font=FONT_LABEL,
                )

    def _draw_target_marker(self, cx, cy, name):
        size = 14
        self._canvas.create_line(cx - size, cy, cx + size, cy, fill=COLOR_TARGET, width=2)
        self._canvas.create_line(cx, cy - size, cx, cy + size, fill=COLOR_TARGET, width=2)
        self._canvas.create_oval(
            cx - 10, cy - 10, cx + 10, cy + 10,
            outline=COLOR_TARGET, width=2,
        )
        self._canvas.create_text(
            cx, cy - 20, text=f"TARGET: {name}",
            fill=COLOR_TARGET, font=FONT_LABEL_BOLD,
        )

    # -- player --

    def _draw_player(self, gw_x, gw_y, slot_w):
        cx = gw_x + 7 * slot_w + slot_w // 2
        cy = gw_y + 5 * slot_w + slot_w // 2
        self._canvas.create_rectangle(
            cx - 8, cy - 8, cx + 8, cy + 8,
            outline=COLOR_PLAYER, width=2,
        )
        self._canvas.create_text(
            cx, cy - 14, text='YOU', fill=COLOR_PLAYER, font=FONT_LABEL_BOLD,
        )

    # -- info panel --

    def _draw_info(self, gw_x, gw_y, gw_w, data):
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
        panel_y = gw_y - panel_h - 4

        self._canvas.create_rectangle(
            gw_x, panel_y, gw_x + gw_w, panel_y + panel_h,
            fill=COLOR_INFO_BG, outline=COLOR_GRID,
        )
        for i, line in enumerate(lines):
            self._canvas.create_text(
                gw_x + 6, panel_y + 4 + i * line_h,
                text=line, fill=COLOR_INFO_TEXT,
                font=FONT_INFO, anchor='nw',
            )

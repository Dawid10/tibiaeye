"""
Status Strip - Top bar with HP/MP bars, bot status, position, and controls.
"""
import customtkinter as ctk

from ..theme import (
    BG_APP, BG_ELEVATED, BG_INPUT, BORDER,
    TEXT_PRIMARY, TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    COLOR_HP_HIGH, COLOR_HP_MED, COLOR_HP_LOW, COLOR_MP,
    STATUS_STRIP_HEIGHT,
)


HP_BAR_WIDTH = 80
MP_BAR_WIDTH = 80
BAR_HEIGHT = 14


def _hp_color(percentage):
    if percentage > 60:
        return COLOR_HP_HIGH
    if percentage > 30:
        return COLOR_HP_MED
    return COLOR_HP_LOW


class StatusStrip(ctk.CTkFrame):
    """Top status bar with HP/MP, status indicator, position, and bot controls."""

    def __init__(self, master, on_start=None, on_pause=None, on_stop=None, **kwargs):
        super().__init__(master, fg_color=BG_APP, height=STATUS_STRIP_HEIGHT, **kwargs)
        self.pack_propagate(False)

        self.on_start = on_start
        self.on_pause = on_pause
        self.on_stop = on_stop

        self._setup_ui()

    def _setup_ui(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=12, pady=6)

        # --- Left section: HP/MP bars ---
        bars_frame = ctk.CTkFrame(inner, fg_color="transparent")
        bars_frame.pack(side="left")

        self._hp_bar, self._hp_label = self._create_bar(bars_frame, "HP", COLOR_HP_HIGH, 0)
        self._mp_bar, self._mp_label = self._create_bar(bars_frame, "MP", COLOR_MP, 12)

        # --- Separator ---
        ctk.CTkFrame(inner, width=1, fg_color=BORDER).pack(side="left", fill="y", padx=12, pady=2)

        # --- Center: Status + Position + Uptime ---
        center = ctk.CTkFrame(inner, fg_color="transparent")
        center.pack(side="left", fill="x", expand=True)

        status_frame = ctk.CTkFrame(center, fg_color="transparent")
        status_frame.pack(side="left", padx=(0, 16))

        self._status_dot = ctk.CTkLabel(
            status_frame, text="\u25CF", width=12,
            font=ctk.CTkFont(size=10), text_color=TEXT_MUTED,
        )
        self._status_dot.pack(side="left")

        self._status_label = ctk.CTkLabel(
            status_frame, text="Stopped",
            font=ctk.CTkFont(family="Courier", size=11), text_color=TEXT_MUTED,
        )
        self._status_label.pack(side="left", padx=(4, 0))

        self._position_label = ctk.CTkLabel(
            center, text="",
            font=ctk.CTkFont(family="Courier", size=11), text_color=TEXT_MUTED,
        )
        self._position_label.pack(side="left", padx=(0, 16))

        self._uptime_label = ctk.CTkLabel(
            center, text="",
            font=ctk.CTkFont(family="Courier", size=11), text_color=TEXT_MUTED,
        )
        self._uptime_label.pack(side="left")

        # --- Right: Controls ---
        controls = ctk.CTkFrame(inner, fg_color="transparent")
        controls.pack(side="right")

        self._start_btn = ctk.CTkButton(
            controls, text="\u25B6", width=32, height=28,
            font=ctk.CTkFont(size=12),
            fg_color="#238636", hover_color="#2ea043",
            text_color="#ffffff", corner_radius=4,
            command=lambda: self.on_start and self.on_start(),
        )
        self._start_btn.pack(side="left", padx=(0, 4))

        self._pause_btn = ctk.CTkButton(
            controls, text="\u23F8", width=32, height=28,
            font=ctk.CTkFont(size=12),
            fg_color=BG_ELEVATED, hover_color=BG_INPUT,
            text_color=COLOR_WARNING,
            border_width=1, border_color=BORDER, corner_radius=4,
            command=lambda: self.on_pause and self.on_pause(),
        )
        self._pause_btn.pack(side="left", padx=(0, 4))

        self._stop_btn = ctk.CTkButton(
            controls, text="\u25A0", width=32, height=28,
            font=ctk.CTkFont(size=12),
            fg_color=BG_ELEVATED, hover_color=BG_INPUT,
            text_color=COLOR_ERROR,
            border_width=1, border_color=BORDER, corner_radius=4,
            command=lambda: self.on_stop and self.on_stop(),
        )
        self._stop_btn.pack(side="left")

        # Bottom border
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(side="bottom", fill="x")

    def _create_bar(self, parent, label_text, color, left_pad):
        container = ctk.CTkFrame(parent, fg_color="transparent")
        container.pack(side="left", padx=(left_pad, 0))

        ctk.CTkLabel(
            container, text=label_text, width=22,
            font=ctk.CTkFont(family="Courier", size=10, weight="bold"),
            text_color=color,
        ).pack(side="left")

        bar_bg = ctk.CTkFrame(container, fg_color=BG_INPUT, width=HP_BAR_WIDTH, height=BAR_HEIGHT, corner_radius=3)
        bar_bg.pack(side="left", padx=(4, 0))
        bar_bg.pack_propagate(False)

        bar = ctk.CTkFrame(bar_bg, fg_color=color, height=BAR_HEIGHT, width=HP_BAR_WIDTH, corner_radius=3)
        bar.place(x=0, y=0, relheight=1.0)

        label = ctk.CTkLabel(
            container, text="100%", width=36,
            font=ctk.CTkFont(family="Courier", size=10), text_color=TEXT_MUTED,
        )
        label.pack(side="left", padx=(4, 0))

        return bar, label

    def set_hp(self, percentage):
        percentage = max(0, min(100, percentage))
        width = max(1, int(HP_BAR_WIDTH * percentage / 100))
        self._hp_bar.configure(width=width, fg_color=_hp_color(percentage))
        self._hp_bar.place(x=0, y=0, relheight=1.0)
        self._hp_label.configure(text=f"{percentage}%")

    def set_mp(self, percentage):
        percentage = max(0, min(100, percentage))
        width = max(1, int(MP_BAR_WIDTH * percentage / 100))
        self._mp_bar.configure(width=width)
        self._mp_bar.place(x=0, y=0, relheight=1.0)
        self._mp_label.configure(text=f"{percentage}%")

    def set_status(self, status):
        """Set bot status: 'running', 'paused', 'stopped', 'reconnecting'."""
        config = {
            "running":      ("Running",       COLOR_SUCCESS),
            "paused":       ("Paused",        COLOR_WARNING),
            "stopped":      ("Stopped",       TEXT_MUTED),
            "reconnecting": ("Reconnecting",  COLOR_ERROR),
        }
        label, color = config.get(status, config["stopped"])
        self._status_dot.configure(text_color=color)
        self._status_label.configure(text=label, text_color=color)

    def set_position(self, x, y, z):
        self._position_label.configure(text=f"({x}, {y}, {z})")

    def set_uptime(self, elapsed_seconds):
        h = int(elapsed_seconds // 3600)
        m = int((elapsed_seconds % 3600) // 60)
        s = int(elapsed_seconds % 60)
        self._uptime_label.configure(text=f"{h:02d}:{m:02d}:{s:02d}")

    def clear_uptime(self):
        self._uptime_label.configure(text="")

    def clear_position(self):
        self._position_label.configure(text="")

    def set_button_states(self, running, paused):
        if running and not paused:
            self._start_btn.configure(state="disabled", fg_color=BG_ELEVATED)
            self._pause_btn.configure(state="normal")
            self._stop_btn.configure(state="normal")
            return
        if running and paused:
            self._start_btn.configure(state="normal", fg_color="#238636")
            self._pause_btn.configure(state="normal")
            self._stop_btn.configure(state="normal")
            return
        self._start_btn.configure(state="normal", fg_color="#238636")
        self._pause_btn.configure(state="disabled")
        self._stop_btn.configure(state="disabled")

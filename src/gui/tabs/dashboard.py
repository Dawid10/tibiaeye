"""
Dashboard Page - Overview with stat cards, battle list, and recent events.
"""
import customtkinter as ctk
from datetime import datetime

from ..theme import (
    BG_APP, BG_SURFACE, BORDER,
    TEXT_PRIMARY, TEXT_MUTED, TEXT_FAINT,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    ACCENT, resolve,
)


MAX_EVENTS = 20
MAX_BATTLE_LIST_ROWS = 12


def _hp_color(percentage):
    if percentage > 60:
        return COLOR_SUCCESS
    if percentage > 30:
        return COLOR_WARNING
    return COLOR_ERROR


def _hp_level(percentage):
    if percentage > 60:
        return "high"
    if percentage > 30:
        return "med"
    return "low"


class DashboardPage(ctk.CTkScrollableFrame):
    """Dashboard overview showing key bot metrics at a glance."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_APP, **kwargs)

        self._stat_values = {}
        self._last_creature_names = []

        self._setup_ui()

    def _setup_ui(self):
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=16, pady=(16, 12))

        ctk.CTkLabel(
            header, text="Dashboard",
            font=ctk.CTkFont(family="Courier", size=18, weight="bold"),
            text_color=TEXT_PRIMARY, anchor="w",
        ).pack(side="left")

        # --- Stat Cards Row ---
        cards_frame = ctk.CTkFrame(self, fg_color="transparent")
        cards_frame.pack(fill="x", padx=16, pady=(0, 12))
        cards_frame.columnconfigure((0, 1, 2, 3), weight=1, uniform="card")

        self._create_stat_card(cards_frame, "uptime",    "UPTIME",    "--:--:--", 0)
        self._create_stat_card(cards_frame, "ticks",     "TICKS",     "0",        1)
        self._create_stat_card(cards_frame, "creatures", "CREATURES", "0",        2)
        self._create_stat_card(cards_frame, "hp",        "HP",        "-%",       3)

        # --- Middle Row: Bot Health + Current Task ---
        mid_frame = ctk.CTkFrame(self, fg_color="transparent")
        mid_frame.pack(fill="x", padx=16, pady=(0, 12))
        mid_frame.columnconfigure((0, 1), weight=1, uniform="mid")

        self._create_health_card(mid_frame, 0)
        self._create_task_card(mid_frame, 1)

        # --- Bottom Row: Battle List + Events ---
        bottom_frame = ctk.CTkFrame(self, fg_color="transparent")
        bottom_frame.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        bottom_frame.columnconfigure((0, 1), weight=1, uniform="bottom")
        bottom_frame.rowconfigure(0, weight=1)

        self._create_battle_list_card(bottom_frame, 0)
        self._create_events_card(bottom_frame, 1)

    def _create_stat_card(self, parent, key, title, initial_value, column):
        card = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        card.grid(row=0, column=column, padx=(0 if column == 0 else 4, 0), pady=0, sticky="nsew")

        ctk.CTkLabel(
            card, text=title,
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 0))

        value_label = ctk.CTkLabel(
            card, text=initial_value,
            font=ctk.CTkFont(family="Courier", size=20, weight="bold"),
            text_color=TEXT_PRIMARY, anchor="w",
        )
        value_label.pack(fill="x", padx=12, pady=(2, 10))

        self._stat_values[key] = value_label

    def _create_health_card(self, parent, column):
        card = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        card.grid(row=0, column=column, padx=(0, 0), sticky="nsew")

        ctk.CTkLabel(
            card, text="BOT HEALTH",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        self._health_dots = {}
        middlewares = ["screenshot", "statusbar", "battlelist", "gamewindow", "radar"]

        for mw in middlewares:
            row = ctk.CTkFrame(card, fg_color="transparent", height=22)
            row.pack(fill="x", padx=12, pady=1)
            row.pack_propagate(False)

            dot = ctk.CTkLabel(
                row, text="\u25CF", width=14,
                font=ctk.CTkFont(size=10), text_color=TEXT_MUTED,
            )
            dot.pack(side="left")

            ctk.CTkLabel(
                row, text=mw,
                font=ctk.CTkFont(family="Courier", size=11),
                text_color=TEXT_MUTED, anchor="w",
            ).pack(side="left", padx=(6, 0))

            self._health_dots[mw] = dot

        ctk.CTkFrame(card, fg_color="transparent", height=8).pack()

    def _create_task_card(self, parent, column):
        card = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        card.grid(row=0, column=column, padx=(4, 0), sticky="nsew")

        ctk.CTkLabel(
            card, text="CURRENT TASK",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        self._task_name = ctk.CTkLabel(
            card, text="Idle",
            font=ctk.CTkFont(family="Courier", size=14, weight="bold"),
            text_color=TEXT_PRIMARY, anchor="w",
        )
        self._task_name.pack(fill="x", padx=12, pady=(0, 4))

        self._task_state = ctk.CTkLabel(
            card, text="",
            font=ctk.CTkFont(family="Courier", size=11),
            text_color=TEXT_MUTED, anchor="w",
        )
        self._task_state.pack(fill="x", padx=12, pady=(0, 10))

    def _create_battle_list_card(self, parent, column):
        card = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        card.grid(row=0, column=column, padx=(0, 0), sticky="nsew")

        ctk.CTkLabel(
            card, text="BATTLE LIST",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        self._battle_textbox = ctk.CTkTextbox(
            card,
            font=ctk.CTkFont(family="Courier", size=10),
            fg_color=BG_SURFACE, wrap="none", state="disabled", border_width=0,
        )
        self._battle_textbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._apply_battle_tags()

    def _apply_battle_tags(self):
        tb = self._battle_textbox._textbox
        tb.tag_configure("name", foreground=resolve(TEXT_PRIMARY))
        tb.tag_configure("hp_high", foreground=COLOR_SUCCESS)
        tb.tag_configure("hp_med", foreground=COLOR_WARNING)
        tb.tag_configure("hp_low", foreground=COLOR_ERROR)
        tb.tag_configure("attack", foreground=COLOR_ERROR)
        tb.tag_configure("muted", foreground=resolve(TEXT_MUTED))

    def _create_events_card(self, parent, column):
        card = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)
        card.grid(row=0, column=column, padx=(4, 0), sticky="nsew")

        ctk.CTkLabel(
            card, text="RECENT EVENTS",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT_MUTED, anchor="w",
        ).pack(fill="x", padx=12, pady=(10, 6))

        self._events_textbox = ctk.CTkTextbox(
            card,
            font=ctk.CTkFont(family="Courier", size=10),
            fg_color=BG_SURFACE, wrap="word", state="disabled", border_width=0,
        )
        self._events_textbox.pack(fill="both", expand=True, padx=8, pady=(0, 8))

        self._apply_event_tags()

    def _apply_event_tags(self):
        tb = self._events_textbox._textbox
        tb.tag_configure("info", foreground=resolve(TEXT_MUTED))
        tb.tag_configure("warning", foreground=COLOR_WARNING)
        tb.tag_configure("error", foreground=COLOR_ERROR)
        tb.tag_configure("success", foreground=COLOR_SUCCESS)
        tb.tag_configure("time", foreground=resolve(TEXT_FAINT))

    # --- Public update methods ---

    def update_stats(self, hp=None, ticks=None, creatures_count=None, elapsed=None):
        if hp is not None:
            self._stat_values["hp"].configure(text=f"{hp}%", text_color=_hp_color(hp))

        if ticks is not None:
            self._stat_values["ticks"].configure(text=str(ticks))

        if creatures_count is not None:
            self._stat_values["creatures"].configure(text=str(creatures_count))

        if elapsed is None:
            return
        h = int(elapsed // 3600)
        m = int((elapsed % 3600) // 60)
        s = int(elapsed % 60)
        self._stat_values["uptime"].configure(text=f"{h:02d}:{m:02d}:{s:02d}")

    def update_health_dots(self, health_status):
        if not health_status:
            return
        for mw, dot in self._health_dots.items():
            status = health_status.get(mw, {})
            if status.get('healthy', True):
                dot.configure(text_color=COLOR_SUCCESS)
                continue
            if status.get('degraded', False):
                dot.configure(text_color=COLOR_WARNING)
                continue
            dot.configure(text_color=COLOR_ERROR)

    def update_task(self, task_name, state=""):
        self._task_name.configure(text=task_name or "Idle")
        self._task_state.configure(text=state)

    def update_battle_list(self, creatures):
        if not creatures:
            current_names = []
        else:
            current_names = [
                (c.name if hasattr(c, 'name') else c.get('name', '?'))
                for c in creatures[:MAX_BATTLE_LIST_ROWS]
            ]

        if current_names == self._last_creature_names:
            return
        self._last_creature_names = current_names

        self._battle_textbox.configure(state="normal")
        self._battle_textbox._textbox.delete("1.0", "end")

        if not creatures:
            self._battle_textbox._textbox.insert("end", "No creatures", "muted")
            self._battle_textbox.configure(state="disabled")
            return

        for creature in creatures[:MAX_BATTLE_LIST_ROWS]:
            name = creature.name if hasattr(creature, 'name') else creature.get('name', '?')
            hp = creature.hpPercentage if hasattr(creature, 'hpPercentage') else creature.get('hp', 100)
            is_attacked = creature.isBeingAttacked if hasattr(creature, 'isBeingAttacked') else creature.get('isBeingAttacked', False)

            prefix = "\u25B8 " if is_attacked else "  "
            tag = "attack" if is_attacked else "name"
            self._battle_textbox._textbox.insert("end", prefix, tag)
            self._battle_textbox._textbox.insert("end", f"{name:<20}", tag)

            if hp is not None:
                hp_tag = f"hp_{_hp_level(hp)}"
                bar_filled = int(hp / 10)
                bar_empty = 10 - bar_filled
                self._battle_textbox._textbox.insert("end", "\u2588" * bar_filled, hp_tag)
                self._battle_textbox._textbox.insert("end", "\u2591" * bar_empty, "muted")
                self._battle_textbox._textbox.insert("end", f" {hp}%", hp_tag)

            self._battle_textbox._textbox.insert("end", "\n", "name")

        self._battle_textbox.configure(state="disabled")

    def add_event(self, message, level="info"):
        timestamp = datetime.now().strftime("%H:%M:%S")

        self._events_textbox.configure(state="normal")
        self._events_textbox._textbox.insert("end", f"{timestamp} ", "time")
        self._events_textbox._textbox.insert("end", f"{message}\n", level)

        line_count = int(self._events_textbox._textbox.index("end-1c").split(".")[0])
        if line_count > MAX_EVENTS:
            self._events_textbox._textbox.delete("1.0", f"{line_count - MAX_EVENTS}.0")

        self._events_textbox.configure(state="disabled")
        self._events_textbox._textbox.see("end")

    def reset(self):
        self._stat_values["uptime"].configure(text="--:--:--")
        self._stat_values["ticks"].configure(text="0")
        self._stat_values["creatures"].configure(text="0")
        self._stat_values["hp"].configure(text="-%", text_color=TEXT_PRIMARY)

        self._task_name.configure(text="Idle")
        self._task_state.configure(text="")

        for dot in self._health_dots.values():
            dot.configure(text_color=TEXT_MUTED)

        self._last_creature_names = []
        self.update_battle_list(None)

    def apply_theme(self):
        """Re-apply textbox tags after theme change."""
        self._apply_battle_tags()
        self._apply_event_tags()

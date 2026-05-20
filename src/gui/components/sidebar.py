"""
Sidebar Navigation - Vertical nav with icon indicators and active state.
"""
import customtkinter as ctk
from typing import Callable, Dict, Optional

from ..theme import (
    BG_APP, BG_ELEVATED, BG_SURFACE, BORDER, ACCENT,
    TEXT_PRIMARY, TEXT_MUTED, SIDEBAR_WIDTH,
)


NAV_ITEMS = (
    ("dashboard",    "\u25A0", "Dashboard"),
    ("cavebot",      "\u2316", "Cavebot"),
    ("healing",      "\u2661", "Healing"),
    ("targeting",    "\u25CE", "Targeting"),
    ("spell_attack", "\u2604", "Spell Atk"),
    ("hardware",     "\u2699", "Hardware"),
    ("control",      "\u2630", "Settings"),
    ("recorder",     "\u25CF", "Recorder"),
    ("status",       "\u2261", "Status"),
    ("diagnostics",  "\u2295", "Diagnostics"),
)


class Sidebar(ctk.CTkFrame):
    """Vertical sidebar navigation with icon + label buttons."""

    def __init__(
        self,
        master,
        on_navigate: Callable[[str], None],
        on_theme_toggle: Optional[Callable[[], None]] = None,
        **kwargs
    ):
        super().__init__(master, fg_color=BG_APP, width=SIDEBAR_WIDTH, **kwargs)
        self.pack_propagate(False)

        self.on_navigate = on_navigate
        self.on_theme_toggle = on_theme_toggle
        self.active_key = "dashboard"
        self._buttons: Dict[str, ctk.CTkFrame] = {}
        self._labels: Dict[str, ctk.CTkLabel] = {}
        self._icons: Dict[str, ctk.CTkLabel] = {}
        self._indicators: Dict[str, ctk.CTkFrame] = {}

        self._setup_ui()

    def _setup_ui(self):
        # Logo / title
        title_frame = ctk.CTkFrame(self, fg_color="transparent")
        title_frame.pack(fill="x", padx=12, pady=(16, 20))

        ctk.CTkLabel(
            title_frame,
            text="TIBIAEYE",
            font=ctk.CTkFont(family="Courier", size=16, weight="bold"),
            text_color=ACCENT,
            anchor="w",
        ).pack(side="left")

        ctk.CTkLabel(
            title_frame,
            text="v2",
            font=ctk.CTkFont(family="Courier", size=10),
            text_color=TEXT_MUTED,
            anchor="w",
        ).pack(side="left", padx=(4, 0), pady=(3, 0))

        # Separator
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=(0, 8))

        # Nav items
        for key, icon, label in NAV_ITEMS:
            self._create_nav_item(key, icon, label)

        # Bottom spacer
        ctk.CTkFrame(self, fg_color="transparent").pack(fill="both", expand=True)

        # Theme toggle at bottom
        ctk.CTkFrame(self, height=1, fg_color=BORDER).pack(fill="x", padx=12, pady=(0, 6))

        theme_row = ctk.CTkFrame(self, fg_color="transparent", height=32)
        theme_row.pack(fill="x", padx=12, pady=(0, 12))

        self._theme_icon = ctk.CTkLabel(
            theme_row, text="\u263E",
            font=ctk.CTkFont(size=14), text_color=TEXT_MUTED, width=20,
        )
        self._theme_icon.pack(side="left")

        self._theme_label = ctk.CTkLabel(
            theme_row, text="Dark",
            font=ctk.CTkFont(family="Courier", size=11), text_color=TEXT_MUTED,
        )
        self._theme_label.pack(side="left", padx=(6, 0))

        self._theme_switch = ctk.CTkSwitch(
            theme_row, text="", width=36, height=18,
            switch_width=36, switch_height=18,
            button_length=0,
            progress_color=ACCENT,
            command=self._on_theme_toggle,
        )
        self._theme_switch.pack(side="right")
        # Start with dark mode on
        self._theme_switch.select()

    def _create_nav_item(self, key, icon, label):
        row = ctk.CTkFrame(self, fg_color="transparent", height=36, cursor="hand2")
        row.pack(fill="x", padx=6, pady=1)
        row.pack_propagate(False)

        indicator = ctk.CTkFrame(row, width=3, fg_color="transparent", corner_radius=2)
        indicator.pack(side="left", fill="y", padx=(0, 0), pady=4)

        icon_label = ctk.CTkLabel(
            row, text=icon,
            font=ctk.CTkFont(size=14),
            text_color=TEXT_MUTED, width=28,
        )
        icon_label.pack(side="left", padx=(8, 0))

        text_label = ctk.CTkLabel(
            row, text=label,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED, anchor="w",
        )
        text_label.pack(side="left", padx=(4, 0), fill="x", expand=True)

        self._buttons[key] = row
        self._labels[key] = text_label
        self._icons[key] = icon_label
        self._indicators[key] = indicator

        for widget in (row, icon_label, text_label):
            widget.bind("<Button-1>", lambda e, k=key: self._on_click(k))
            widget.bind("<Enter>", lambda e, k=key: self._on_enter(k))
            widget.bind("<Leave>", lambda e, k=key: self._on_leave(k))

        if key == self.active_key:
            self._set_active_style(key)

    def _on_click(self, key):
        if key == self.active_key:
            return
        old = self.active_key
        self.active_key = key
        self._set_inactive_style(old)
        self._set_active_style(key)
        self.on_navigate(key)

    def _on_enter(self, key):
        if key == self.active_key:
            return
        self._buttons[key].configure(fg_color=BG_ELEVATED)

    def _on_leave(self, key):
        if key == self.active_key:
            return
        self._buttons[key].configure(fg_color="transparent")

    def _set_active_style(self, key):
        self._buttons[key].configure(fg_color=BG_SURFACE)
        self._labels[key].configure(text_color=TEXT_PRIMARY)
        self._icons[key].configure(text_color=ACCENT)
        self._indicators[key].configure(fg_color=ACCENT)

    def _set_inactive_style(self, key):
        self._buttons[key].configure(fg_color="transparent")
        self._labels[key].configure(text_color=TEXT_MUTED)
        self._icons[key].configure(text_color=TEXT_MUTED)
        self._indicators[key].configure(fg_color="transparent")

    def _on_theme_toggle(self):
        is_dark = self._theme_switch.get()
        if is_dark:
            self._theme_icon.configure(text="\u263E")
            self._theme_label.configure(text="Dark")
        else:
            self._theme_icon.configure(text="\u2600")
            self._theme_label.configure(text="Light")

        if self.on_theme_toggle:
            self.on_theme_toggle()

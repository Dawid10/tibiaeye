"""
Spell Attack Tab - Configure priority-based offensive spell casting.

Groups are evaluated top-to-bottom. First matching group wins.
Within a group, spells are tried in priority order (top = highest).
"""
import customtkinter as ctk
from typing import Dict, Any, List

from ..components.tooltip import Tooltip
from ..theme import (
    BG_SURFACE, BG_ELEVATED, BG_INPUT, BORDER,
    TEXT_PRIMARY, TEXT_MUTED, ACCENT,
    COLOR_ERROR,
)
from ..styles import (
    create_section, create_entry, create_checkbox,
    create_button, create_slider, create_option_menu,
    create_description,
)


COMPARE_OPTIONS = ['greaterThanOrEqual', 'greaterThan', 'lessThanOrEqual', 'lessThan']
COMPARE_LABELS = {
    'greaterThanOrEqual': '>= (at least)',
    'greaterThan': '> (more than)',
    'lessThanOrEqual': '<= (at most)',
    'lessThan': '< (fewer than)',
}
COUNT_MODE_OPTIONS = ['nearest', 'total']
SPELL_GROUP_OPTIONS = ['attack', 'support']


class SpellAttackTab(ctk.CTkScrollableFrame):
    """Spell attack configuration tab."""

    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.config_manager = config_manager
        self._group_frames = []
        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Setup the spell attack tab UI."""
        # Global settings section
        global_section = create_section(self, "Spell Attack Settings")
        global_section.pack(fill="x", padx=5, pady=5)

        global_content = ctk.CTkFrame(global_section, fg_color="transparent")
        global_content.pack(fill="x", padx=10, pady=10)

        # Enable checkbox
        self.enabled_var = ctk.BooleanVar(value=False)
        create_checkbox(
            global_content,
            text="Enable Spell Attack",
            variable=self.enabled_var,
            command=self._save_config,
        ).pack(anchor="w")

        # Mana reserve slider
        reserve_frame = ctk.CTkFrame(global_content, fg_color="transparent")
        reserve_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(
            reserve_frame, text="Mana Reserve:",
            font=ctk.CTkFont(size=12), text_color=TEXT_PRIMARY,
        ).pack(side="left")
        self.reserve_label = ctk.CTkLabel(
            reserve_frame, text="30%", width=40,
            font=ctk.CTkFont(size=12), text_color=TEXT_PRIMARY,
        )
        self.reserve_label.pack(side="right")

        self.reserve_var = ctk.IntVar(value=30)
        self.reserve_slider = create_slider(
            reserve_frame,
            variable=self.reserve_var,
            from_=0, to=100,
            command=self._on_reserve_change,
            width=200,
        )
        self.reserve_slider.pack(side="left", padx=10, fill="x", expand=True)
        Tooltip(self.reserve_slider, "Porcentagem minima de mana que o bot reserva antes de usar spell de ataque. Garante mana para healing.")

        # Groups container
        self._groups_container = ctk.CTkFrame(self, fg_color="transparent")
        self._groups_container.pack(fill="x", padx=5, pady=5)

        # Add group button
        create_button(
            self,
            text="+ Add Spell Group",
            command=self._add_group,
            style="accent",
        ).pack(pady=10)

    def _on_reserve_change(self, value):
        """Update reserve label and save."""
        val = int(float(value))
        self.reserve_var.set(val)
        self.reserve_label.configure(text=f"{val}%")
        self._save_config()

    # ---- Group Management ----

    def _add_group(self, data=None):
        """Add a new spell group frame."""
        idx = len(self._group_frames)
        group_data = data or {
            'name': f'Group {idx + 1}',
            'enabled': True,
            'compare': 'greaterThanOrEqual',
            'value': 1,
            'countMode': 'nearest',
            'spells': [],
        }

        frame = _GroupFrame(
            self._groups_container,
            group_data,
            on_remove=lambda f=None: self._remove_group(f),
            on_move_up=lambda f=None: self._move_group_up(f),
            on_move_down=lambda f=None: self._move_group_down(f),
            on_change=self._save_config,
        )
        frame.pack(fill="x", pady=5)
        self._group_frames.append(frame)
        self._save_config()
        return frame

    def _remove_group(self, frame):
        """Remove a spell group."""
        if frame in self._group_frames:
            self._group_frames.remove(frame)
            frame.destroy()
            self._save_config()

    def _move_group_up(self, frame):
        """Move a group up in the list."""
        idx = self._group_frames.index(frame)
        if idx <= 0:
            return
        self._group_frames[idx], self._group_frames[idx - 1] = (
            self._group_frames[idx - 1], self._group_frames[idx]
        )
        self._repack_groups()
        self._save_config()

    def _move_group_down(self, frame):
        """Move a group down in the list."""
        idx = self._group_frames.index(frame)
        if idx >= len(self._group_frames) - 1:
            return
        self._group_frames[idx], self._group_frames[idx + 1] = (
            self._group_frames[idx + 1], self._group_frames[idx]
        )
        self._repack_groups()
        self._save_config()

    def _repack_groups(self):
        """Re-pack all group frames in current list order."""
        for frame in self._group_frames:
            frame.pack_forget()
        for frame in self._group_frames:
            frame.pack(fill="x", pady=5)

    # ---- Config Persistence ----

    def _load_config(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            return

        config = self.config_manager.get('spellAttack', {})
        self.enabled_var.set(config.get('enabled', False))
        reserve = config.get('manaReservePercent', 30)
        self.reserve_var.set(reserve)
        self.reserve_label.configure(text=f"{reserve}%")

        for group_data in config.get('groups', []):
            self._add_group(group_data)

    def _save_config(self):
        """Save current configuration."""
        if not self.config_manager:
            return

        self.config_manager.set('spellAttack', self.get_settings())
        self.config_manager.save()

    def get_settings(self) -> Dict[str, Any]:
        """Get current spell attack settings for context injection."""
        return {
            'enabled': self.enabled_var.get(),
            'manaReservePercent': self.reserve_var.get(),
            'groups': [f.get_data() for f in self._group_frames],
        }


class _GroupFrame(ctk.CTkFrame):
    """A single spell group configuration frame."""

    def __init__(self, master, data, on_remove, on_move_up, on_move_down, on_change, **kwargs):
        super().__init__(master, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER, **kwargs)
        self._on_remove = on_remove
        self._on_move_up = on_move_up
        self._on_move_down = on_move_down
        self._on_change = on_change
        self._spell_rows = []
        self._build(data)

    def _build(self, data):
        """Build the group UI."""
        # Header row: name + enabled + reorder + remove
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 0))

        ctk.CTkLabel(
            header, text="Name:",
            font=ctk.CTkFont(size=12), text_color=TEXT_PRIMARY,
        ).pack(side="left")
        self.name_var = ctk.StringVar(value=data.get('name', ''))
        name_entry = create_entry(header, textvariable=self.name_var, width=180)
        name_entry.pack(side="left", padx=5)
        self.name_var.trace_add("write", lambda *a: self._on_change())

        self.enabled_var = ctk.BooleanVar(value=data.get('enabled', True))
        create_checkbox(
            header, text="Enabled", variable=self.enabled_var,
            command=self._on_change,
        ).pack(side="left", padx=10)

        create_button(
            header, text="Remove", command=lambda: self._on_remove(self),
            style="danger", width=70,
        ).pack(side="right")

        create_button(
            header, text="\u25bc", command=lambda: self._on_move_down(self),
            style="default", width=28,
        ).pack(side="right", padx=2)

        create_button(
            header, text="\u25b2", command=lambda: self._on_move_up(self),
            style="default", width=28,
        ).pack(side="right", padx=2)

        # Condition row: compare + value + countMode
        cond_frame = ctk.CTkFrame(self, fg_color="transparent")
        cond_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(
            cond_frame, text="Creatures",
            font=ctk.CTkFont(size=12), text_color=TEXT_PRIMARY,
        ).pack(side="left")

        self.compare_var = ctk.StringVar(value=data.get('compare', 'greaterThanOrEqual'))
        compare_menu = create_option_menu(
            cond_frame,
            variable=self.compare_var,
            values=[COMPARE_LABELS[k] for k in COMPARE_OPTIONS],
            width=150,
            command=lambda _: self._on_compare_change(),
        )
        compare_menu.set(COMPARE_LABELS.get(data.get('compare', 'greaterThanOrEqual'), ''))
        compare_menu.pack(side="left", padx=5)

        self.value_var = ctk.StringVar(value=str(data.get('value', 1)))
        create_entry(
            cond_frame, textvariable=self.value_var, width=50,
        ).pack(side="left", padx=5)
        self.value_var.trace_add("write", lambda *a: self._on_change())

        mode_label = ctk.CTkLabel(
            cond_frame, text="Mode:",
            font=ctk.CTkFont(size=12), text_color=TEXT_PRIMARY,
        )
        mode_label.pack(side="left", padx=(10, 0))
        self.count_mode_var = ctk.StringVar(value=data.get('countMode', 'nearest'))
        create_option_menu(
            cond_frame,
            variable=self.count_mode_var,
            values=COUNT_MODE_OPTIONS,
            width=100,
            command=lambda _: self._on_change(),
        ).pack(side="left", padx=5)
        Tooltip(mode_label, "nearest: conta apenas criaturas acessiveis (pathfinding). total: conta todas na tela.")

        # Spells header
        spells_header = ctk.CTkFrame(self, fg_color="transparent")
        spells_header.pack(fill="x", padx=10, pady=(5, 0))
        create_description(
            spells_header, text="Spells (priority order - top = highest):",
        ).pack(side="left")

        # Spells container
        self._spells_container = ctk.CTkFrame(self, fg_color="transparent")
        self._spells_container.pack(fill="x", padx=10)

        for spell_data in data.get('spells', []):
            self._add_spell(spell_data)

        # Add spell button
        create_button(
            self, text="+ Add Spell", command=self._add_spell,
            style="default", width=100,
        ).pack(pady=(5, 10))

    def _on_compare_change(self):
        """Reverse-map the label back to the key."""
        label = self.compare_var.get()
        for key, lbl in COMPARE_LABELS.items():
            if lbl == label:
                self.compare_var.set(key)
                break
        self._on_change()

    def _add_spell(self, data=None):
        """Add a spell row."""
        spell_data = data or {
            'name': '', 'hotkey': '', 'manaCost': 0,
            'cooldown': 2.0, 'spellGroup': 'attack', 'enabled': True,
        }
        row = _SpellRow(
            self._spells_container, spell_data,
            on_remove=lambda r=None: self._remove_spell(r),
            on_move_up=lambda r=None: self._move_spell_up(r),
            on_move_down=lambda r=None: self._move_spell_down(r),
            on_change=self._on_change,
        )
        row.pack(fill="x", pady=2)
        self._spell_rows.append(row)
        self._on_change()

    def _remove_spell(self, row):
        """Remove a spell row."""
        if row in self._spell_rows:
            self._spell_rows.remove(row)
            row.destroy()
            self._on_change()

    def _move_spell_up(self, row):
        """Move a spell up in priority."""
        idx = self._spell_rows.index(row)
        if idx <= 0:
            return
        self._spell_rows[idx], self._spell_rows[idx - 1] = (
            self._spell_rows[idx - 1], self._spell_rows[idx]
        )
        self._repack_spells()
        self._on_change()

    def _move_spell_down(self, row):
        """Move a spell down in priority."""
        idx = self._spell_rows.index(row)
        if idx >= len(self._spell_rows) - 1:
            return
        self._spell_rows[idx], self._spell_rows[idx + 1] = (
            self._spell_rows[idx + 1], self._spell_rows[idx]
        )
        self._repack_spells()
        self._on_change()

    def _repack_spells(self):
        """Re-pack all spell rows in current list order."""
        for row in self._spell_rows:
            row.pack_forget()
        for row in self._spell_rows:
            row.pack(fill="x", pady=2)

    def get_data(self):
        """Get group data as dict."""
        compare = self.compare_var.get()
        # Handle case where compare_var still has the label text
        for key, lbl in COMPARE_LABELS.items():
            if compare == lbl:
                compare = key
                break

        try:
            value = int(self.value_var.get())
        except (ValueError, TypeError):
            value = 1

        return {
            'name': self.name_var.get(),
            'enabled': self.enabled_var.get(),
            'compare': compare,
            'value': value,
            'countMode': self.count_mode_var.get(),
            'spells': [r.get_data() for r in self._spell_rows],
        }


class _SpellRow(ctk.CTkFrame):
    """A single spell configuration row within a group."""

    def __init__(self, master, data, on_remove, on_move_up, on_move_down, on_change, **kwargs):
        super().__init__(master, fg_color=BG_ELEVATED, corner_radius=4, **kwargs)
        self._on_remove = on_remove
        self._on_move_up = on_move_up
        self._on_move_down = on_move_down
        self._on_change = on_change
        self._build(data)

    def _build(self, data):
        row = ctk.CTkFrame(self, fg_color="transparent")
        row.pack(fill="x", padx=5, pady=3)

        # Reorder buttons
        create_button(
            row, text="\u25b2", command=lambda: self._on_move_up(self),
            style="ghost", width=22,
        ).pack(side="left", padx=(0, 1))

        create_button(
            row, text="\u25bc", command=lambda: self._on_move_down(self),
            style="ghost", width=22,
        ).pack(side="left", padx=(0, 4))

        self.enabled_var = ctk.BooleanVar(value=data.get('enabled', True))
        create_checkbox(
            row, text="", variable=self.enabled_var,
            command=self._on_change,
        ).pack(side="left")

        ctk.CTkLabel(row, text="Name:", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=(2, 0))
        self.name_var = ctk.StringVar(value=data.get('name', ''))
        create_entry(row, textvariable=self.name_var, width=100).pack(side="left", padx=2)
        self.name_var.trace_add("write", lambda *a: self._on_change())

        ctk.CTkLabel(row, text="Key:", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=(4, 0))
        self.hotkey_var = ctk.StringVar(value=data.get('hotkey', ''))
        create_entry(row, textvariable=self.hotkey_var, width=40).pack(side="left", padx=2)
        self.hotkey_var.trace_add("write", lambda *a: self._on_change())

        ctk.CTkLabel(row, text="CD:", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=(4, 0))
        self.cooldown_var = ctk.StringVar(value=str(data.get('cooldown', 2.0)))
        create_entry(row, textvariable=self.cooldown_var, width=40).pack(side="left", padx=2)
        self.cooldown_var.trace_add("write", lambda *a: self._on_change())

        ctk.CTkLabel(row, text="Mana:", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=(4, 0))
        self.mana_var = ctk.StringVar(value=str(data.get('manaCost', 0)))
        create_entry(row, textvariable=self.mana_var, width=45).pack(side="left", padx=2)
        self.mana_var.trace_add("write", lambda *a: self._on_change())

        ctk.CTkLabel(row, text="Group:", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED).pack(side="left", padx=(4, 0))
        self.group_var = ctk.StringVar(value=data.get('spellGroup', 'attack'))
        create_option_menu(
            row, variable=self.group_var, values=SPELL_GROUP_OPTIONS,
            width=80,
            command=lambda _: self._on_change(),
        ).pack(side="left", padx=2)

        create_button(
            row, text="X", command=lambda: self._on_remove(self),
            style="danger", width=28,
        ).pack(side="right")

    def get_data(self):
        """Get spell data as dict."""
        try:
            cooldown = float(self.cooldown_var.get())
        except (ValueError, TypeError):
            cooldown = 2.0

        try:
            mana_cost = int(self.mana_var.get())
        except (ValueError, TypeError):
            mana_cost = 0

        return {
            'name': self.name_var.get(),
            'hotkey': self.hotkey_var.get(),
            'manaCost': mana_cost,
            'cooldown': cooldown,
            'spellGroup': self.group_var.get(),
            'enabled': self.enabled_var.get(),
        }

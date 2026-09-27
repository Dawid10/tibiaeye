"""
Healing Tab - Configure healing potions, spells, and food.
"""
import customtkinter as ctk
from typing import Dict, Any, List, Optional

from ..components.tooltip import Tooltip
from ..theme import BG_SURFACE, BG_ELEVATED, TEXT_MUTED, COLOR_ERROR
from ..styles import (
    create_section, create_entry, create_checkbox,
    create_button, create_slider, create_description,
)


def _safe_float(value, default: float) -> float:
    try:
        return float(value or default)
    except (ValueError, TypeError):
        return default


def _safe_int(value, default: int) -> int:
    try:
        return int(value or default)
    except (ValueError, TypeError):
        return default


class HealingTab(ctk.CTkScrollableFrame):
    """Healing configuration tab with potions, spells, and food settings."""

    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.spell_frames: List[ctk.CTkFrame] = []

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Setup the healing tab UI."""
        self._setup_health_potion_section()
        self._setup_mana_potion_section()
        self._setup_spells_section()
        self._setup_food_section()

    def _setup_health_potion_section(self):
        """Setup health potion section."""
        hp_section = create_section(self, "Health Potions")
        hp_section.pack(fill="x", padx=10, pady=(10, 5))

        hp_content = ctk.CTkFrame(hp_section, fg_color="transparent")
        hp_content.pack(fill="x", padx=10, pady=10)

        self.hp_enabled_var = ctk.BooleanVar(value=True)
        create_checkbox(
            hp_content,
            text="Enable Health Potion",
            variable=self.hp_enabled_var,
            command=self._save_config
        ).pack(anchor="w")

        # HP Threshold slider
        threshold_frame = ctk.CTkFrame(hp_content, fg_color="transparent")
        threshold_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(threshold_frame, text="HP Threshold:").pack(side="left")

        self.hp_threshold_var = ctk.IntVar(value=30)
        self.hp_threshold_slider = create_slider(
            threshold_frame,
            variable=self.hp_threshold_var,
            from_=5,
            to=95,
            command=self._on_hp_threshold_change
        )
        self.hp_threshold_slider.pack(side="left", fill="x", expand=True, padx=10)

        self.hp_threshold_label = ctk.CTkLabel(threshold_frame, text="30%", width=40)
        self.hp_threshold_label.pack(side="left")
        Tooltip(self.hp_threshold_slider, "Porcentagem de HP abaixo da qual o bot usa Health Potion.")

        # HP Hotkey
        hotkey_frame = ctk.CTkFrame(hp_content, fg_color="transparent")
        hotkey_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(hotkey_frame, text="Hotkey:").pack(side="left")
        self.hp_hotkey_var = ctk.StringVar(value="1")
        self.hp_hotkey_var.trace_add("write", self._on_entry_change)
        create_entry(hotkey_frame, textvariable=self.hp_hotkey_var, width=60).pack(side="left", padx=10)

        ctk.CTkLabel(hotkey_frame, text="Cooldown:").pack(side="left", padx=(20, 0))
        self.hp_cooldown_var = ctk.StringVar(value="1.0")
        self.hp_cooldown_var.trace_add("write", self._on_entry_change)
        create_entry(hotkey_frame, textvariable=self.hp_cooldown_var, width=60).pack(side="left", padx=10)
        ctk.CTkLabel(hotkey_frame, text="s", text_color=TEXT_MUTED).pack(side="left")

    def _setup_mana_potion_section(self):
        """Setup mana potion section."""
        mp_section = create_section(self, "Mana Potions")
        mp_section.pack(fill="x", padx=10, pady=5)

        mp_content = ctk.CTkFrame(mp_section, fg_color="transparent")
        mp_content.pack(fill="x", padx=10, pady=10)

        self.mp_enabled_var = ctk.BooleanVar(value=True)
        create_checkbox(
            mp_content,
            text="Enable Mana Potion",
            variable=self.mp_enabled_var,
            command=self._save_config
        ).pack(anchor="w")

        # MP Threshold slider
        mp_threshold_frame = ctk.CTkFrame(mp_content, fg_color="transparent")
        mp_threshold_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(mp_threshold_frame, text="MP Threshold:").pack(side="left")

        self.mp_threshold_var = ctk.IntVar(value=50)
        self.mp_threshold_slider = create_slider(
            mp_threshold_frame,
            variable=self.mp_threshold_var,
            from_=5,
            to=95,
            command=self._on_mp_threshold_change
        )
        self.mp_threshold_slider.pack(side="left", fill="x", expand=True, padx=10)

        self.mp_threshold_label = ctk.CTkLabel(mp_threshold_frame, text="50%", width=40)
        self.mp_threshold_label.pack(side="left")
        Tooltip(self.mp_threshold_slider, "Porcentagem de mana abaixo da qual o bot usa Mana Potion.")

        # MP Hotkey
        mp_hotkey_frame = ctk.CTkFrame(mp_content, fg_color="transparent")
        mp_hotkey_frame.pack(fill="x", pady=(10, 0))

        ctk.CTkLabel(mp_hotkey_frame, text="Hotkey:").pack(side="left")
        self.mp_hotkey_var = ctk.StringVar(value="2")
        self.mp_hotkey_var.trace_add("write", self._on_entry_change)
        create_entry(mp_hotkey_frame, textvariable=self.mp_hotkey_var, width=60).pack(side="left", padx=10)

        ctk.CTkLabel(mp_hotkey_frame, text="Cooldown:").pack(side="left", padx=(20, 0))
        self.mp_cooldown_var = ctk.StringVar(value="1.0")
        self.mp_cooldown_var.trace_add("write", self._on_entry_change)
        create_entry(mp_hotkey_frame, textvariable=self.mp_cooldown_var, width=60).pack(side="left", padx=10)
        ctk.CTkLabel(mp_hotkey_frame, text="s", text_color=TEXT_MUTED).pack(side="left")

    def _setup_spells_section(self):
        """Setup healing spells section."""
        spells_section = create_section(self, "Healing Spells")
        spells_section.pack(fill="x", padx=10, pady=5)

        self.spells_container = ctk.CTkFrame(spells_section, fg_color="transparent")
        self.spells_container.pack(fill="x", padx=10, pady=10)

        create_button(
            spells_section,
            text="+ Add Spell",
            command=self._add_spell,
            style="accent",
            width=100,
        ).pack(anchor="w", padx=10, pady=(0, 10))

    def _setup_food_section(self):
        """Setup food section."""
        food_section = create_section(self, "Food")
        food_section.pack(fill="x", padx=10, pady=(5, 10))

        food_content = ctk.CTkFrame(food_section, fg_color="transparent")
        food_content.pack(fill="x", padx=10, pady=10)

        self.food_enabled_var = ctk.BooleanVar(value=True)
        create_checkbox(
            food_content,
            text="Enable Auto-Eat",
            variable=self.food_enabled_var,
            command=self._save_config
        ).pack(anchor="w")

        food_settings = ctk.CTkFrame(food_content, fg_color="transparent")
        food_settings.pack(fill="x", pady=(10, 0))

        food_label = ctk.CTkLabel(food_settings, text="Eat when food <=")
        food_label.pack(side="left")
        Tooltip(food_label, "Quando o tempo de food restante for menor ou igual a este valor (em minutos), o bot pressiona a hotkey de food.")
        self.food_threshold_var = ctk.StringVar(value="5")
        self.food_threshold_var.trace_add("write", self._on_entry_change)
        create_entry(food_settings, textvariable=self.food_threshold_var, width=50).pack(side="left", padx=5)
        ctk.CTkLabel(food_settings, text="minutes").pack(side="left")

        ctk.CTkLabel(food_settings, text="Hotkey:").pack(side="left", padx=(20, 0))
        self.food_hotkey_var = ctk.StringVar(value="f")
        self.food_hotkey_var.trace_add("write", self._on_entry_change)
        create_entry(food_settings, textvariable=self.food_hotkey_var, width=60).pack(side="left", padx=5)

        ctk.CTkLabel(food_settings, text="Cooldown:").pack(side="left", padx=(20, 0))
        self.food_cooldown_var = ctk.StringVar(value="2.0")
        self.food_cooldown_var.trace_add("write", self._on_entry_change)
        create_entry(food_settings, textvariable=self.food_cooldown_var, width=60).pack(side="left", padx=5)
        ctk.CTkLabel(food_settings, text="s", text_color=TEXT_MUTED).pack(side="left")

    def _on_hp_threshold_change(self, value):
        """Update HP threshold label."""
        self.hp_threshold_label.configure(text=f"{int(value)}%")
        self._save_config()

    def _on_mp_threshold_change(self, value):
        """Update MP threshold label."""
        self.mp_threshold_label.configure(text=f"{int(value)}%")
        self._save_config()

    def _on_spell_change(self, *args):
        """Called when a spell field changes. Debounces saves."""
        if hasattr(self, '_save_pending'):
            self.after_cancel(self._save_pending)
        self._save_pending = self.after(500, self._save_config)

    def _on_entry_change(self, *args):
        """Called when an entry field changes. Debounces saves."""
        if hasattr(self, '_save_pending'):
            self.after_cancel(self._save_pending)
        self._save_pending = self.after(500, self._save_config)

    def _add_spell(self, spell_data: Optional[Dict] = None):
        """Add a new spell configuration row."""
        spell_frame = ctk.CTkFrame(self.spells_container, fg_color=BG_ELEVATED, corner_radius=6)
        spell_frame.pack(fill="x", pady=5)

        spell_num = len(self.spell_frames) + 1

        header = ctk.CTkFrame(spell_frame, fg_color="transparent")
        header.pack(fill="x", padx=10, pady=(8, 0))

        # Enabled checkbox and name
        enabled_var = ctk.BooleanVar(value=spell_data.get('enabled', True) if spell_data else True)
        create_checkbox(
            header,
            text=f"Spell {spell_num}:",
            variable=enabled_var,
            command=self._save_config
        ).pack(side="left")

        name_var = ctk.StringVar(value=spell_data.get('name', f'Heal {spell_num}') if spell_data else f'Heal {spell_num}')
        name_var.trace_add("write", self._on_spell_change)
        create_entry(header, textvariable=name_var, width=120).pack(side="left", padx=10)

        # Remove button
        create_button(
            header,
            text="X",
            command=lambda: self._remove_spell(spell_frame),
            style="danger",
            width=24,
            height=24,
        ).pack(side="right")

        # Settings row 1
        row1 = ctk.CTkFrame(spell_frame, fg_color="transparent")
        row1.pack(fill="x", padx=10, pady=(5, 0))

        ctk.CTkLabel(row1, text="HP <").pack(side="left")
        threshold_var = ctk.StringVar(value=str(spell_data.get('threshold', 70)) if spell_data else "70")
        threshold_var.trace_add("write", self._on_spell_change)
        create_entry(row1, textvariable=threshold_var, width=50).pack(side="left", padx=5)
        ctk.CTkLabel(row1, text="%").pack(side="left")

        ctk.CTkLabel(row1, text="Spell:").pack(side="left", padx=(20, 0))
        spell_var = ctk.StringVar(value=spell_data.get('spell', 'exura') if spell_data else 'exura')
        spell_var.trace_add("write", self._on_spell_change)
        create_entry(row1, textvariable=spell_var, width=120).pack(side="left", padx=5)

        # Settings row 2
        row2 = ctk.CTkFrame(spell_frame, fg_color="transparent")
        row2.pack(fill="x", padx=10, pady=(5, 10))

        ctk.CTkLabel(row2, text="Min Mana:").pack(side="left")
        min_mana_var = ctk.StringVar(value=str(spell_data.get('minMana', 10)) if spell_data else "10")
        min_mana_var.trace_add("write", self._on_spell_change)
        create_entry(row2, textvariable=min_mana_var, width=50).pack(side="left", padx=5)
        ctk.CTkLabel(row2, text="%").pack(side="left")

        ctk.CTkLabel(row2, text="Hotkey:").pack(side="left", padx=(20, 0))
        hotkey_var = ctk.StringVar(value=spell_data.get('hotkey', f'F{spell_num}') if spell_data else f'F{spell_num}')
        hotkey_var.trace_add("write", self._on_spell_change)
        create_entry(row2, textvariable=hotkey_var, width=60).pack(side="left", padx=5)

        # Store references
        spell_frame.vars = {
            'enabled': enabled_var,
            'name': name_var,
            'threshold': threshold_var,
            'spell': spell_var,
            'minMana': min_mana_var,
            'hotkey': hotkey_var
        }

        self.spell_frames.append(spell_frame)

    def _remove_spell(self, spell_frame: ctk.CTkFrame):
        """Remove a spell configuration."""
        if spell_frame in self.spell_frames:
            self.spell_frames.remove(spell_frame)
            spell_frame.destroy()
            self._save_config()

    def reload(self, config_manager):
        """Show another profile's settings in the existing widgets."""
        self.config_manager = config_manager
        for spell_frame in self.spell_frames:
            spell_frame.destroy()
        self.spell_frames.clear()
        self._load_config()

    def _load_config(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            self._add_spell({'name': 'Emergency Heal', 'enabled': True, 'threshold': 20, 'spell': 'exura vita', 'hotkey': 'F1', 'minMana': 10})
            self._add_spell({'name': 'Strong Heal', 'enabled': True, 'threshold': 40, 'spell': 'exura gran', 'hotkey': 'F2', 'minMana': 10})
            self._add_spell({'name': 'Light Heal', 'enabled': True, 'threshold': 70, 'spell': 'exura', 'hotkey': 'F3', 'minMana': 10})
            return

        # Health potion
        hp_config = self.config_manager.get('healing.healthPotion', {})
        self.hp_enabled_var.set(hp_config.get('enabled', True))
        self.hp_threshold_var.set(hp_config.get('threshold', 30))
        self.hp_threshold_label.configure(text=f"{hp_config.get('threshold', 30)}%")
        self.hp_hotkey_var.set(hp_config.get('hotkey', '1'))
        self.hp_cooldown_var.set(str(hp_config.get('cooldown', 1.0)))

        # Mana potion
        mp_config = self.config_manager.get('healing.manaPotion', {})
        self.mp_enabled_var.set(mp_config.get('enabled', True))
        self.mp_threshold_var.set(mp_config.get('threshold', 50))
        self.mp_threshold_label.configure(text=f"{mp_config.get('threshold', 50)}%")
        self.mp_hotkey_var.set(mp_config.get('hotkey', '2'))
        self.mp_cooldown_var.set(str(mp_config.get('cooldown', 1.0)))

        # Spells
        spells = self.config_manager.get('healing.spells', [])
        for spell_data in spells:
            self._add_spell(spell_data)

        # Food
        food_config = self.config_manager.get('healing.food', {})
        self.food_enabled_var.set(food_config.get('enabled', True))
        self.food_threshold_var.set(str(food_config.get('threshold', 5)))
        self.food_hotkey_var.set(food_config.get('hotkey', 'f'))
        self.food_cooldown_var.set(str(food_config.get('cooldown', 2.0)))

    def _save_config(self):
        """Save current configuration."""
        if not self.config_manager:
            return

        # Health potion
        self.config_manager.set('healing.healthPotion', {
            'enabled': self.hp_enabled_var.get(),
            'threshold': self.hp_threshold_var.get(),
            'hotkey': self.hp_hotkey_var.get(),
            'cooldown': _safe_float(self.hp_cooldown_var.get(), 1.0)
        })

        # Mana potion
        self.config_manager.set('healing.manaPotion', {
            'enabled': self.mp_enabled_var.get(),
            'threshold': self.mp_threshold_var.get(),
            'hotkey': self.mp_hotkey_var.get(),
            'cooldown': _safe_float(self.mp_cooldown_var.get(), 1.0)
        })

        # Spells
        spells = []
        for spell_frame in self.spell_frames:
            try:
                spells.append({
                    'enabled': spell_frame.vars['enabled'].get(),
                    'name': spell_frame.vars['name'].get(),
                    'threshold': int(spell_frame.vars['threshold'].get() or 70),
                    'spell': spell_frame.vars['spell'].get(),
                    'minMana': int(spell_frame.vars['minMana'].get() or 10),
                    'hotkey': spell_frame.vars['hotkey'].get()
                })
            except (ValueError, KeyError):
                pass
        self.config_manager.set('healing.spells', spells)

        # Food
        self.config_manager.set('healing.food', {
            'enabled': self.food_enabled_var.get(),
            'threshold': _safe_int(self.food_threshold_var.get(), 5),
            'hotkey': self.food_hotkey_var.get(),
            'cooldown': _safe_float(self.food_cooldown_var.get(), 2.0)
        })

        self.config_manager.save()

    def get_settings(self) -> Dict[str, Any]:
        """Get current healing settings."""
        spells = []
        for spell_frame in self.spell_frames:
            try:
                spells.append({
                    'enabled': spell_frame.vars['enabled'].get(),
                    'name': spell_frame.vars['name'].get(),
                    'threshold': int(spell_frame.vars['threshold'].get() or 70),
                    'spell': spell_frame.vars['spell'].get(),
                    'minMana': int(spell_frame.vars['minMana'].get() or 10),
                    'hotkey': spell_frame.vars['hotkey'].get()
                })
            except (ValueError, KeyError):
                pass

        return {
            'healthPotion': {
                'enabled': self.hp_enabled_var.get(),
                'threshold': self.hp_threshold_var.get(),
                'hotkey': self.hp_hotkey_var.get(),
                'cooldown': _safe_float(self.hp_cooldown_var.get(), 1.0)
            },
            'manaPotion': {
                'enabled': self.mp_enabled_var.get(),
                'threshold': self.mp_threshold_var.get(),
                'hotkey': self.mp_hotkey_var.get(),
                'cooldown': _safe_float(self.mp_cooldown_var.get(), 1.0)
            },
            'spells': spells,
            'food': {
                'enabled': self.food_enabled_var.get(),
                'threshold': _safe_int(self.food_threshold_var.get(), 5),
                'hotkey': self.food_hotkey_var.get(),
                'cooldown': _safe_float(self.food_cooldown_var.get(), 2.0)
            }
        }

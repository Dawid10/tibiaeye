"""
Cavebot Tab - Configure waypoints, routes, and refill settings.
"""
import customtkinter as ctk
from tkinter import filedialog
from typing import Dict, Any, List, Optional
import json
import os

from ..components.waypoint_list import WaypointList
from ..theme import (
    BG_SURFACE, BG_ELEVATED, BG_INPUT, BORDER,
    TEXT_PRIMARY, TEXT_MUTED, ACCENT,
)
from ..styles import (
    create_section, create_entry, create_checkbox,
    create_button, create_option_menu, create_description,
)

_SLOTS_DIR = os.path.join(
    os.path.dirname(__file__), os.pardir, os.pardir,
    "repositories", "inventory", "images", "slots"
)
_EXCLUDED_SLOT_KEYWORDS = {"depot", "stash", "empty", "flask"}


def _discover_backpacks() -> List[str]:
    """Build backpack list from slot template files."""
    if not os.path.isdir(_SLOTS_DIR):
        return ["Beach Backpack", "Brocade Backpack", "Camouflage Backpack"]
    names = []
    for filename in sorted(os.listdir(_SLOTS_DIR)):
        if not filename.lower().endswith(".png"):
            continue
        name = filename[:-4]
        if not name.lower().endswith("backpack"):
            continue
        if any(kw in name.lower() for kw in _EXCLUDED_SLOT_KEYWORDS):
            continue
        names.append(name)
    return names or ["Beach Backpack"]


class CavebotTab(ctk.CTkFrame):
    """Cavebot configuration tab with waypoints and refill settings."""

    CITIES = ["Darashia", "Thais", "Carlin", "Ankrahmun", "Edron", "Venore", "Liberty Bay", "Port Hope", "Yalahar"]
    BACKPACKS = _discover_backpacks()
    DEPOT_CHESTS = ["1", "2", "3", "4"]
    HP_POTIONS = ["Health Potion", "Strong Health Potion", "Great Health Potion", "Ultimate Health Potion", "Supreme Health Potion"]
    MP_POTIONS = ["Mana Potion", "Strong Mana Potion", "Great Mana Potion", "Ultimate Mana Potion"]

    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.waypoints: List[Dict] = []
        self.route_file: str = ""

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Setup the cavebot tab UI."""
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)

        right_panel = ctk.CTkFrame(self, fg_color="transparent", width=320)
        right_panel.pack(side="right", fill="both", padx=(5, 10), pady=10)
        right_panel.pack_propagate(False)

        # === LEFT PANEL: Waypoints ===
        waypoints_section = create_section(left_panel, "Waypoints")
        waypoints_section.pack(fill="both", expand=True)

        # Route file selection
        file_frame = ctk.CTkFrame(waypoints_section, fg_color="transparent")
        file_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            file_frame, text="Route File:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.route_file_var = ctk.StringVar(value="")
        self.route_file_var.trace_add("write", self._on_entry_change)
        self.route_file_entry = create_entry(
            file_frame, textvariable=self.route_file_var, width=200,
        )
        self.route_file_entry.pack(side="left", fill="x", expand=True, padx=10)

        create_button(
            file_frame, text="Browse", command=self._browse_route, width=70,
        ).pack(side="left")

        # Route info and controls
        controls_frame = ctk.CTkFrame(waypoints_section, fg_color="transparent")
        controls_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            controls_frame, text="Start from waypoint:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.start_waypoint_var = ctk.StringVar(value="0")
        self.start_waypoint_var.trace_add("write", self._on_entry_change)
        create_entry(
            controls_frame, textvariable=self.start_waypoint_var, width=60,
        ).pack(side="left", padx=10)

        self.loop_var = ctk.BooleanVar(value=True)
        create_checkbox(
            controls_frame, text="Loop route",
            variable=self.loop_var, command=self._save_config,
        ).pack(side="left", padx=20)

        create_button(
            controls_frame, text="Load Route",
            command=self._load_route, width=90,
        ).pack(side="right", padx=(10, 0))

        create_button(
            controls_frame, text="Reload",
            command=self._reload_route, width=70,
        ).pack(side="right")

        create_button(
            controls_frame, text="Clear",
            command=self._clear_route, style="danger", width=60,
        ).pack(side="right", padx=(0, 10))

        # Waypoint list
        self.waypoint_list = WaypointList(
            waypoints_section,
            on_waypoint_click=self._on_waypoint_click,
            fg_color=BG_SURFACE,
        )
        self.waypoint_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # === RIGHT PANEL: Tabview for Refill & Loot ===
        self.right_tabview = ctk.CTkTabview(
            right_panel, fg_color=BG_SURFACE,
            segmented_button_fg_color=BG_ELEVATED,
            segmented_button_selected_color=ACCENT,
            segmented_button_unselected_color=BG_INPUT,
            segmented_button_selected_hover_color=ACCENT,
            segmented_button_unselected_hover_color=BG_ELEVATED,
            border_width=1, border_color=BORDER,
        )
        self.right_tabview.pack(fill="both", expand=True)

        self.right_tabview.add("Refill")
        self.right_tabview.add("Loot")

        # ==================== REFILL TAB ====================
        refill_tab = self.right_tabview.tab("Refill")

        refill_content = ctk.CTkScrollableFrame(refill_tab, fg_color="transparent")
        refill_content.pack(fill="both", expand=True, padx=5, pady=5)

        self._build_refill_tab(refill_content)

        # ==================== LOOT TAB ====================
        loot_tab = self.right_tabview.tab("Loot")

        loot_content = ctk.CTkScrollableFrame(loot_tab, fg_color="transparent")
        loot_content.pack(fill="both", expand=True, padx=5, pady=5)

        self._build_loot_tab(loot_content)

    def _build_refill_tab(self, parent):
        """Build the refill tab content."""
        # City selection
        city_frame = ctk.CTkFrame(parent, fg_color="transparent")
        city_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            city_frame, text="City:", width=80, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.city_var = ctk.StringVar(value="Darashia")
        self.city_menu = create_option_menu(
            city_frame, variable=self.city_var,
            values=self.CITIES, command=self._save_config,
        )
        self.city_menu.pack(side="left", fill="x", expand=True)

        # Refill when thresholds
        create_description(parent, "REFILL WHEN").pack(anchor="w", pady=(5, 5))

        self._build_threshold_row(
            parent, "HP Potions <", "hp_min_var", "50", "units",
        )
        self._build_threshold_row(
            parent, "MP Potions <", "mp_min_var", "100", "units",
        )

        # Capacity with checkbox
        cap_min_frame = ctk.CTkFrame(parent, fg_color="transparent")
        cap_min_frame.pack(fill="x", pady=2)

        self.check_capacity_var = ctk.BooleanVar(value=True)
        create_checkbox(
            cap_min_frame, text="", variable=self.check_capacity_var,
            command=self._save_config,
        ).pack(side="left")

        ctk.CTkLabel(
            cap_min_frame, text="Capacity <", width=80, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.cap_min_var = ctk.StringVar(value="200")
        self.cap_min_var.trace_add("write", self._on_entry_change)
        create_entry(
            cap_min_frame, textvariable=self.cap_min_var, width=60,
        ).pack(side="left")

        ctk.CTkLabel(
            cap_min_frame, text="oz",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left", padx=5)

        # Refill to targets
        create_description(parent, "REFILL TO").pack(anchor="w", pady=(10, 5))

        self._build_threshold_row(
            parent, "HP Potions:", "hp_target_var", "200", "units",
        )

        hp_type_frame = ctk.CTkFrame(parent, fg_color="transparent")
        hp_type_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            hp_type_frame, text="HP Type:", width=100, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.hp_potion_type_var = ctk.StringVar(value="Health Potion")
        create_option_menu(
            hp_type_frame, variable=self.hp_potion_type_var,
            values=self.HP_POTIONS, width=150, command=self._save_config,
        ).pack(side="left")

        self._build_threshold_row(
            parent, "MP Potions:", "mp_target_var", "400", "units",
        )

        mp_type_frame = ctk.CTkFrame(parent, fg_color="transparent")
        mp_type_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            mp_type_frame, text="MP Type:", width=100, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.mp_potion_type_var = ctk.StringVar(value="Mana Potion")
        create_option_menu(
            mp_type_frame, variable=self.mp_potion_type_var,
            values=self.MP_POTIONS, width=150, command=self._save_config,
        ).pack(side="left")

        # Deposit gold option
        self.deposit_gold_var = ctk.BooleanVar(value=True)
        create_checkbox(
            parent, text="Deposit gold before refill",
            variable=self.deposit_gold_var, command=self._save_config,
        ).pack(anchor="w", pady=(10, 2))

        # Return label
        create_description(parent, "RETURN TO LABEL").pack(anchor="w", pady=(10, 5))

        self.return_label_var = ctk.StringVar(value="caveStart")
        self.return_label_var.trace_add("write", self._on_entry_change)
        create_entry(
            parent, textvariable=self.return_label_var,
            width=200, placeholder="e.g. huntStart",
        ).pack(anchor="w")

    def _build_threshold_row(self, parent, label, var_attr, default, unit):
        """Build a labeled threshold entry row."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            frame, text=label, width=100, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        var = ctk.StringVar(value=default)
        var.trace_add("write", self._on_entry_change)
        setattr(self, var_attr, var)

        create_entry(frame, textvariable=var, width=60).pack(side="left")

        ctk.CTkLabel(
            frame, text=unit,
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left", padx=5)

    def _build_loot_tab(self, parent):
        """Build the loot tab content."""
        # Loot options
        create_description(parent, "LOOT OPTIONS").pack(anchor="w", pady=(0, 10))

        self.deposit_loot_var = ctk.BooleanVar(value=True)
        create_checkbox(
            parent, text="Deposit loot at depot",
            variable=self.deposit_loot_var, command=self._save_config,
        ).pack(anchor="w", pady=2)

        self.drop_flasks_var = ctk.BooleanVar(value=True)
        create_checkbox(
            parent, text="Drop empty flasks",
            variable=self.drop_flasks_var, command=self._save_config,
        ).pack(anchor="w", pady=2)

        # Backpack selection
        create_description(parent, "BACKPACKS").pack(anchor="w", pady=(15, 10))

        self._build_backpack_row(parent, "Loot BP:", "loot_backpack_var", "Beach Backpack")
        self._build_backpack_row(parent, "Main BP:", "main_backpack_var", "Golden Backpack")
        self._build_backpack_row(parent, "Stash BP:", "stash_backpack_var", "Beach Backpack")

        # Depot chest selection
        create_description(parent, "DEPOT").pack(anchor="w", pady=(15, 10))

        depot_chest_frame = ctk.CTkFrame(parent, fg_color="transparent")
        depot_chest_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            depot_chest_frame, text="Chest:", width=80, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.depot_chest_var = ctk.StringVar(value="1")
        create_option_menu(
            depot_chest_frame, variable=self.depot_chest_var,
            values=self.DEPOT_CHESTS, width=150, command=self._save_config,
        ).pack(side="left")

    def _build_backpack_row(self, parent, label, var_attr, default):
        """Build a backpack selection row."""
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            frame, text=label, width=80, anchor="w",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        var = ctk.StringVar(value=default)
        setattr(self, var_attr, var)

        create_option_menu(
            frame, variable=var, values=self.BACKPACKS,
            width=150, command=self._save_config,
        ).pack(side="left")

    def _browse_route(self):
        """Open file dialog to browse for route file."""
        initial_dir = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(__file__)))), "routes")
        if not os.path.exists(initial_dir):
            initial_dir = os.path.expanduser("~")

        filename = filedialog.askopenfilename(
            title="Select Route File",
            initialdir=initial_dir,
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
        )

        if filename:
            self.route_file_var.set(filename)
            self._load_route()

    def _clear_route(self):
        """Unload the route: no waypoints, so the cavebot only fights what comes (targeting only)."""
        self.waypoints = []
        self.route_file = ""
        self.waypoint_list.set_waypoints([])
        self.start_waypoint_var.set("0")
        self.route_file_var.set("")
        self._save_config()

    def _load_route(self):
        """Load waypoints from the selected route file."""
        route_file = self.route_file_var.get()
        if not route_file or not os.path.exists(route_file):
            return

        try:
            with open(route_file, 'r') as f:
                data = json.load(f)

            # Handle both list format and dict format
            if isinstance(data, list):
                self.waypoints = data
            elif isinstance(data, dict) and 'waypoints' in data:
                self.waypoints = data['waypoints']
            else:
                self.waypoints = []

            self.route_file = route_file
            self.waypoint_list.set_waypoints(self.waypoints)

            # Update start waypoint
            try:
                start_idx = int(self.start_waypoint_var.get())
                if 0 <= start_idx < len(self.waypoints):
                    self.waypoint_list.set_current_index(start_idx)
            except ValueError:
                pass

            self._save_config()

        except (json.JSONDecodeError, IOError) as e:
            print(f"Error loading route: {e}")

    def _reload_route(self):
        """Reload the current route file."""
        self._load_route()

    def _on_waypoint_click(self, index: int):
        """Handle waypoint click in the list."""
        self.start_waypoint_var.set(str(index))
        self.waypoint_list.set_current_index(index)

    def reload(self, config_manager):
        """Show another profile's settings in the existing widgets."""
        self.config_manager = config_manager
        self._load_config()

    def _load_config(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            return

        # Refill settings - MUST load before _load_route() which triggers _save_config()
        refill = self.config_manager.get('refill', {})
        self.city_var.set(refill.get('city', 'Darashia'))
        self.hp_min_var.set(str(refill.get('hpPotionMin', 50)))
        self.mp_min_var.set(str(refill.get('mpPotionMin', 100)))
        self.cap_min_var.set(str(refill.get('capMin', 200)))
        self.check_capacity_var.set(refill.get('checkCapacity', True))
        self.hp_target_var.set(str(refill.get('hpPotionTarget', 200)))
        self.mp_target_var.set(str(refill.get('mpPotionTarget', 400)))
        self.hp_potion_type_var.set(refill.get('hpPotionItem', 'Health Potion'))
        self.mp_potion_type_var.set(refill.get('mpPotionItem', 'Mana Potion'))
        self.deposit_gold_var.set(refill.get('depositGold', True))
        self.deposit_loot_var.set(refill.get('depositLoot', True))
        self.drop_flasks_var.set(refill.get('dropFlasks', True))
        self.loot_backpack_var.set(refill.get('lootBackpack', 'Beach Backpack'))
        self.main_backpack_var.set(refill.get('mainBackpack', 'Golden Backpack'))
        self.stash_backpack_var.set(refill.get('stashBackpack', refill.get('lootBackpack', 'Beach Backpack')))
        self.depot_chest_var.set(str(refill.get('depotChest', 1)))
        self.return_label_var.set(refill.get('returnLabel', 'caveStart'))

        # Cavebot settings
        cavebot = self.config_manager.get('cavebot', {})
        self.route_file_var.set(cavebot.get('routeFile', ''))
        self.start_waypoint_var.set(str(cavebot.get('startWaypoint', 0)))
        self.loop_var.set(cavebot.get('loop', True))

        # Load route if exists (this calls _save_config, so refill must be loaded first)
        if self.route_file_var.get():
            self._load_route()
        else:
            self._clear_route()

    def _on_entry_change(self, *args):
        """Called when an entry field changes. Debounces saves."""
        if hasattr(self, '_save_pending'):
            self.after_cancel(self._save_pending)
        self._save_pending = self.after(500, self._save_config)

    def _save_config(self, *args):
        """Save current configuration."""
        if not self.config_manager:
            return

        try:
            start_wp = int(self.start_waypoint_var.get())
        except ValueError:
            start_wp = 0

        self.config_manager.set('cavebot', {
            'routeFile': self.route_file_var.get(),
            'startWaypoint': start_wp,
            'loop': self.loop_var.get()
        })

        try:
            hp_min = int(self.hp_min_var.get())
            mp_min = int(self.mp_min_var.get())
            cap_min = int(self.cap_min_var.get())
            hp_target = int(self.hp_target_var.get())
            mp_target = int(self.mp_target_var.get())
        except ValueError:
            hp_min, mp_min, cap_min, hp_target, mp_target = 50, 100, 200, 200, 400

        try:
            depot_chest = int(self.depot_chest_var.get())
        except ValueError:
            depot_chest = 1

        self.config_manager.set('refill', {
            'city': self.city_var.get(),
            'hpPotionMin': hp_min,
            'mpPotionMin': mp_min,
            'capMin': cap_min,
            'checkCapacity': self.check_capacity_var.get(),
            'hpPotionTarget': hp_target,
            'mpPotionTarget': mp_target,
            'hpPotionItem': self.hp_potion_type_var.get(),
            'mpPotionItem': self.mp_potion_type_var.get(),
            'depositGold': self.deposit_gold_var.get(),
            'depositLoot': self.deposit_loot_var.get(),
            'dropFlasks': self.drop_flasks_var.get(),
            'lootBackpack': self.loot_backpack_var.get(),
            'mainBackpack': self.main_backpack_var.get(),
            'stashBackpack': self.stash_backpack_var.get(),
            'depotChest': depot_chest,
            'returnLabel': self.return_label_var.get()
        })

        self.config_manager.save()

    def get_waypoints(self) -> List[Dict]:
        """Get the current waypoints."""
        return self.waypoints

    def get_settings(self) -> Dict[str, Any]:
        """Get current cavebot settings."""
        try:
            start_wp = int(self.start_waypoint_var.get())
        except ValueError:
            start_wp = 0

        try:
            hp_min = int(self.hp_min_var.get())
            mp_min = int(self.mp_min_var.get())
            cap_min = int(self.cap_min_var.get())
            hp_target = int(self.hp_target_var.get())
            mp_target = int(self.mp_target_var.get())
        except ValueError:
            hp_min, mp_min, cap_min, hp_target, mp_target = 50, 100, 200, 200, 400

        try:
            depot_chest = int(self.depot_chest_var.get())
        except ValueError:
            depot_chest = 1

        return {
            'cavebot': {
                'routeFile': self.route_file_var.get(),
                'startWaypoint': start_wp,
                'loop': self.loop_var.get()
            },
            'refill': {
                'city': self.city_var.get(),
                'hpPotionMin': hp_min,
                'mpPotionMin': mp_min,
                'capMin': cap_min,
                'checkCapacity': self.check_capacity_var.get(),
                'hpPotionTarget': hp_target,
                'mpPotionTarget': mp_target,
                'hpPotionItem': self.hp_potion_type_var.get(),
                'mpPotionItem': self.mp_potion_type_var.get(),
                'depositGold': self.deposit_gold_var.get(),
                'depositLoot': self.deposit_loot_var.get(),
                'dropFlasks': self.drop_flasks_var.get(),
                'lootBackpack': self.loot_backpack_var.get(),
                'mainBackpack': self.main_backpack_var.get(),
                'stashBackpack': self.stash_backpack_var.get(),
                'depotChest': depot_chest,
                'returnLabel': self.return_label_var.get()
            },
            'waypoints': self.waypoints
        }

    def set_current_waypoint(self, index: int):
        """Update the current waypoint display (called from game loop)."""
        if self.waypoints and 0 <= index < len(self.waypoints):
            self.waypoint_list.set_current_index(index)

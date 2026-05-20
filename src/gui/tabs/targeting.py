"""
Targeting Tab - Configure monster whitelist and blacklist for combat.
"""
import customtkinter as ctk
from typing import Dict, Any, List, Set, Optional
import os

from ..theme import (
    BG_SURFACE, BG_INPUT, BORDER,
    TEXT_PRIMARY, TEXT_MUTED, ACCENT,
    COLOR_WARNING, COLOR_ERROR,
    resolve,
)
from ..styles import (
    create_section, create_entry, create_checkbox,
    create_button, create_radio, create_description,
)


class TargetingTab(ctk.CTkScrollableFrame):
    """Targeting configuration tab with whitelist and blacklist management."""

    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.whitelist: Set[str] = set()
        self.blacklist: Set[str] = set()
        self.available_monsters: List[str] = []
        self._whitelist_selected: Optional[str] = None
        self._blacklist_selected: Optional[str] = None

        self._load_available_monsters()
        self._setup_ui()
        self._load_config()

    def _load_available_monsters(self):
        """Load available monster names from the battlelist/images/monsters folder."""
        monsters_dir = os.path.join(
            os.path.dirname(os.path.dirname(os.path.dirname(__file__))),
            "repositories",
            "battlelist",
            "images",
            "monsters"
        )

        if os.path.exists(monsters_dir):
            for filename in os.listdir(monsters_dir):
                if filename.endswith('.png'):
                    monster_name = filename[:-4]
                    self.available_monsters.append(monster_name)

        self.available_monsters.sort()
        print(f"[TargetingTab] Loaded {len(self.available_monsters)} monsters from {monsters_dir}")

    def _setup_ui(self):
        """Setup the targeting tab UI."""
        main_container = ctk.CTkFrame(self, fg_color="transparent")
        main_container.pack(fill="x", padx=10, pady=10)

        main_container.grid_columnconfigure(0, weight=1)
        main_container.grid_columnconfigure(1, weight=1)
        main_container.grid_rowconfigure(1, minsize=300)

        # === TARGETING MODE ===
        mode_section = create_section(main_container, "Targeting Mode")
        mode_section.grid(row=0, column=0, columnspan=2, sticky="ew", pady=(0, 10))

        mode_content = ctk.CTkFrame(mode_section, fg_color="transparent")
        mode_content.pack(fill="x", padx=12, pady=10)

        self.mode_var = ctk.StringVar(value="all")

        radio_all = create_radio(mode_content, "Attack all monsters (default)", self.mode_var, "all")
        radio_all.configure(command=self._on_mode_change)
        radio_all.pack(anchor="w", pady=2)

        radio_whitelist = create_radio(mode_content, "Whitelist only - Attack ONLY monsters in whitelist", self.mode_var, "whitelist")
        radio_whitelist.configure(command=self._on_mode_change)
        radio_whitelist.pack(anchor="w", pady=2)

        radio_blacklist = create_radio(mode_content, "Blacklist only - Attack all EXCEPT monsters in blacklist", self.mode_var, "blacklist")
        radio_blacklist.configure(command=self._on_mode_change)
        radio_blacklist.pack(anchor="w", pady=2)

        self.targeting_enabled_var = ctk.BooleanVar(value=True)
        checkbox = create_checkbox(
            mode_content,
            "Enable targeting (uncheck to disable all attacks)",
            self.targeting_enabled_var,
            command=self._save_config
        )
        checkbox.pack(anchor="w", pady=(10, 0))

        # === WHITELIST ===
        whitelist_section = create_section(main_container, "Whitelist (Attack Only These)")
        whitelist_section.grid(row=1, column=0, sticky="nsew", padx=(0, 5))

        self._setup_list_section(whitelist_section, "whitelist")

        # === BLACKLIST ===
        blacklist_section = create_section(main_container, "Blacklist (Never Attack)")
        blacklist_section.grid(row=1, column=1, sticky="nsew", padx=(5, 0))

        self._setup_list_section(blacklist_section, "blacklist")

        # === QUICK ADD FROM TEMPLATES ===
        templates_section = create_section(main_container, "Quick Add from Monster Templates")
        templates_section.grid(row=2, column=0, columnspan=2, sticky="ew", pady=(10, 0))

        templates_content = ctk.CTkFrame(templates_section, fg_color="transparent")
        templates_content.pack(fill="x", padx=12, pady=10)

        # Search/filter
        search_frame = ctk.CTkFrame(templates_content, fg_color="transparent")
        search_frame.pack(fill="x", pady=(0, 10))

        ctk.CTkLabel(
            search_frame, text="Search:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.search_var = ctk.StringVar()
        self.search_var.trace_add("write", self._filter_monsters)
        self.search_entry = create_entry(
            search_frame,
            textvariable=self.search_var,
            width=200,
            placeholder="Type to filter..."
        )
        self.search_entry.pack(side="left", padx=10)

        # Monster list with buttons
        monster_frame = ctk.CTkFrame(templates_content, fg_color="transparent")
        monster_frame.pack(fill="x")

        self.monster_listbox = ctk.CTkTextbox(
            monster_frame,
            height=120,
            font=ctk.CTkFont(size=11),
            wrap="none",
            state="disabled",
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
        )
        self.monster_listbox.pack(side="left", fill="x", expand=True)

        self.monster_listbox._textbox.bind("<Button-1>", self._on_monster_click)
        self.monster_listbox._textbox.tag_configure("monster", foreground=resolve(TEXT_PRIMARY))
        self.monster_listbox._textbox.tag_configure("selected", foreground=resolve(ACCENT), background=resolve(BG_SURFACE))

        # Add buttons
        btn_frame = ctk.CTkFrame(monster_frame, fg_color="transparent")
        btn_frame.pack(side="right", padx=(10, 0))

        create_button(
            btn_frame, "Add to Whitelist",
            command=lambda: self._add_selected_to_list("whitelist"),
            style="accent", width=120,
        ).pack(pady=2)

        create_button(
            btn_frame, "Add to Blacklist",
            command=lambda: self._add_selected_to_list("blacklist"),
            style="danger", width=120,
        ).pack(pady=2)

        self._populate_monster_list()

    def _setup_list_section(self, parent, list_type: str):
        """Setup whitelist or blacklist section."""
        content = ctk.CTkFrame(parent, fg_color="transparent")
        content.pack(fill="both", expand=True, padx=12, pady=10)

        # List display
        textbox = ctk.CTkTextbox(
            content,
            font=ctk.CTkFont(size=11),
            wrap="none",
            state="disabled",
            fg_color=BG_INPUT,
            border_color=BORDER,
            border_width=1,
        )
        textbox.pack(fill="both", expand=True, pady=(0, 10))

        if list_type == "whitelist":
            self.whitelist_textbox = textbox
            self._whitelist_selected = None
        else:
            self.blacklist_textbox = textbox
            self._blacklist_selected = None

        textbox._textbox.bind("<Button-1>", lambda e: self._on_list_click(list_type, e))
        textbox._textbox.tag_configure("selected", foreground=resolve(ACCENT), background=resolve(BG_SURFACE))

        # Input frame
        input_frame = ctk.CTkFrame(content, fg_color="transparent")
        input_frame.pack(fill="x")

        entry_var = ctk.StringVar()
        entry = create_entry(
            input_frame,
            textvariable=entry_var,
            placeholder="Monster name..."
        )
        entry.pack(side="left", fill="x", expand=True)

        entry.bind("<Return>", lambda e: self._add_to_list(list_type, entry_var.get(), entry_var))

        create_button(
            input_frame, "Add",
            command=lambda: self._add_to_list(list_type, entry_var.get(), entry_var),
            width=60,
        ).pack(side="left", padx=(5, 0))

        create_button(
            input_frame, "Remove",
            command=lambda: self._remove_selected_from_list(list_type),
            width=70,
            style="default",
            fg_color=COLOR_WARNING, hover_color="#b8860b",
        ).pack(side="left", padx=(5, 0))

        create_button(
            input_frame, "Clear All",
            command=lambda: self._clear_list(list_type),
            width=70,
            style="danger",
        ).pack(side="left", padx=(5, 0))

    def _add_to_list(self, list_type: str, monster_name: str, entry_var: Optional[ctk.StringVar] = None):
        """Add a monster to whitelist or blacklist."""
        monster_name = monster_name.strip().lower()
        if not monster_name:
            return

        if list_type == "whitelist":
            self.whitelist.add(monster_name)
            self.blacklist.discard(monster_name)
        else:
            self.blacklist.add(monster_name)
            self.whitelist.discard(monster_name)

        if entry_var:
            entry_var.set("")

        self._update_list_displays()
        self._save_config()

    def _remove_from_list(self, list_type: str, monster_name: str):
        """Remove a monster from whitelist or blacklist."""
        if list_type == "whitelist":
            self.whitelist.discard(monster_name)
            self._whitelist_selected = None
        else:
            self.blacklist.discard(monster_name)
            self._blacklist_selected = None

        self._update_list_displays()
        self._save_config()

    def _on_list_click(self, list_type: str, event):
        """Handle click on whitelist/blacklist to select item."""
        textbox = self.whitelist_textbox if list_type == "whitelist" else self.blacklist_textbox

        try:
            index = textbox._textbox.index(f"@{event.x},{event.y}")
            line_num = int(index.split(".")[0])
            line_text = textbox._textbox.get(f"{line_num}.0", f"{line_num}.end").strip()

            if not line_text or line_text.startswith("("):
                return

            textbox._textbox.tag_remove("selected", "1.0", "end")
            textbox._textbox.tag_add("selected", f"{line_num}.0", f"{line_num}.end")

            if list_type == "whitelist":
                self._whitelist_selected = line_text
            else:
                self._blacklist_selected = line_text
        except Exception:
            pass

    def _remove_selected_from_list(self, list_type: str):
        """Remove the currently selected monster from the list."""
        if list_type == "whitelist":
            selected = self._whitelist_selected
        else:
            selected = self._blacklist_selected

        if selected:
            self._remove_from_list(list_type, selected)

    def _clear_list(self, list_type: str):
        """Clear all entries from a list."""
        if list_type == "whitelist":
            self.whitelist.clear()
        else:
            self.blacklist.clear()

        self._update_list_displays()
        self._save_config()

    def _update_list_displays(self):
        """Update the textbox displays for both lists."""
        self.whitelist_textbox.configure(state="normal")
        self.whitelist_textbox.delete("1.0", "end")

        if self.whitelist:
            for monster in sorted(self.whitelist):
                self.whitelist_textbox.insert("end", f"  {monster}\n")
        else:
            self.whitelist_textbox.insert("end", "  (empty - add monsters to attack only these)\n")

        self.whitelist_textbox.configure(state="disabled")

        self.blacklist_textbox.configure(state="normal")
        self.blacklist_textbox.delete("1.0", "end")

        if self.blacklist:
            for monster in sorted(self.blacklist):
                self.blacklist_textbox.insert("end", f"  {monster}\n")
        else:
            self.blacklist_textbox.insert("end", "  (empty - add monsters to never attack)\n")

        self.blacklist_textbox.configure(state="disabled")

        # Bind double-click to remove
        self.whitelist_textbox._textbox.bind("<Double-Button-1>",
            lambda e: self._on_list_double_click("whitelist", e))
        self.blacklist_textbox._textbox.bind("<Double-Button-1>",
            lambda e: self._on_list_double_click("blacklist", e))

    def _on_list_double_click(self, list_type: str, event):
        """Handle double-click to remove monster from list."""
        textbox = self.whitelist_textbox if list_type == "whitelist" else self.blacklist_textbox

        try:
            index = textbox._textbox.index(f"@{event.x},{event.y}")
            line_num = int(index.split(".")[0])
            line_text = textbox._textbox.get(f"{line_num}.0", f"{line_num}.end").strip()

            if line_text and not line_text.startswith("("):
                self._remove_from_list(list_type, line_text)
        except Exception:
            pass

    def _populate_monster_list(self):
        """Populate the monster list from templates."""
        self.monster_listbox.configure(state="normal")
        self.monster_listbox.delete("1.0", "end")

        for monster in self.available_monsters:
            self.monster_listbox.insert("end", f"  {monster}\n", "monster")

        self.monster_listbox.configure(state="disabled")

    def _filter_monsters(self, *args):
        """Filter monster list based on search."""
        search_text = self.search_var.get().lower()

        self.monster_listbox.configure(state="normal")
        self.monster_listbox.delete("1.0", "end")

        for monster in self.available_monsters:
            if search_text in monster.lower():
                self.monster_listbox.insert("end", f"  {monster}\n", "monster")

        self.monster_listbox.configure(state="disabled")

    def _on_monster_click(self, event):
        """Handle click on monster list to select."""
        try:
            index = self.monster_listbox._textbox.index(f"@{event.x},{event.y}")
            line_num = int(index.split(".")[0])

            self.monster_listbox._textbox.tag_remove("selected", "1.0", "end")
            self.monster_listbox._textbox.tag_add("selected", f"{line_num}.0", f"{line_num}.end")

            line_text = self.monster_listbox._textbox.get(f"{line_num}.0", f"{line_num}.end").strip()
            self._selected_monster = line_text
        except Exception:
            pass

    def _add_selected_to_list(self, list_type: str):
        """Add the selected monster from templates to a list."""
        if hasattr(self, '_selected_monster') and self._selected_monster:
            self._add_to_list(list_type, self._selected_monster)

    def _on_mode_change(self):
        """Handle targeting mode change."""
        self._save_config()

    def _load_config(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            self._update_list_displays()
            return

        targeting = self.config_manager.get('targeting', {})

        self.mode_var.set(targeting.get('mode', 'all'))
        self.targeting_enabled_var.set(targeting.get('enabled', True))
        self.whitelist = set(targeting.get('whitelist', []))
        self.blacklist = set(targeting.get('blacklist', []))

        self._update_list_displays()

    def _save_config(self):
        """Save current configuration."""
        if not self.config_manager:
            return

        self.config_manager.set('targeting', {
            'enabled': self.targeting_enabled_var.get(),
            'mode': self.mode_var.get(),
            'whitelist': list(self.whitelist),
            'blacklist': list(self.blacklist)
        })

        self.config_manager.save()

    def get_settings(self) -> Dict[str, Any]:
        """Get current targeting settings."""
        return {
            'enabled': self.targeting_enabled_var.get(),
            'mode': self.mode_var.get(),
            'whitelist': list(self.whitelist),
            'blacklist': list(self.blacklist)
        }

    def should_attack(self, creature_name: str) -> bool:
        """Check if a creature should be attacked based on current settings."""
        if not self.targeting_enabled_var.get():
            return False

        creature_lower = creature_name.lower()
        mode = self.mode_var.get()

        if mode == "whitelist":
            return creature_lower in self.whitelist

        if mode == "blacklist":
            return creature_lower not in self.blacklist

        return True

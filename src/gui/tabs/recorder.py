"""
Recorder Tab - Record waypoints while playing.

Same functionality as scripts/waypoint_recorder.py but integrated into the GUI.
"""
import customtkinter as ctk
from tkinter import filedialog, simpledialog
from typing import Dict, Any, List, Optional, Callable
import json
import os
import time
import threading
import cv2

from ..components.waypoint_list import WaypointList
from ..theme import (
    BG_SURFACE, BG_ELEVATED, BG_INPUT, BORDER,
    TEXT_PRIMARY, TEXT_MUTED, ACCENT, ACCENT_HOVER,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_INFO,
)
from ..styles import (
    create_section, create_entry, create_checkbox,
    create_button, create_option_menu, create_description,
)


def _waypoint_button(parent, text, command, fg_color, hover_color, state="disabled"):
    """Create a styled waypoint action button."""
    return ctk.CTkButton(
        parent,
        text=text,
        width=100,
        height=32,
        font=ctk.CTkFont(size=12),
        fg_color=fg_color,
        hover_color=hover_color,
        command=command,
        state=state,
        corner_radius=4,
    )


def _hotkey_hint(parent, text):
    """Create a muted hotkey hint label."""
    return ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=11),
        text_color=TEXT_MUTED,
    )


def _separator(parent):
    """Create a themed horizontal separator."""
    sep = ctk.CTkFrame(parent, height=1, fg_color=BORDER)
    sep.pack(fill="x", pady=10)
    return sep


def _section_header(parent, text):
    """Create a bold section header label."""
    ctk.CTkLabel(
        parent,
        text=text,
        font=ctk.CTkFont(size=13, weight="bold"),
        text_color=TEXT_PRIMARY,
    ).pack(anchor="w", pady=(10, 5))


class RecorderTab(ctk.CTkFrame):
    """Waypoint recorder tab for recording hunt routes."""

    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.config_manager = config_manager
        self.waypoints: List[Dict] = []
        self.output_file: str = ""
        self.recording = False
        self._previous_coord = None
        self._label_counter = 0
        self._owned_file = None  # the route file this session loaded or saved; others need confirmation to overwrite
        self._coord_update_thread: Optional[threading.Thread] = None
        self._stop_coord_update = False
        self._selected_index: int = -1  # -1 means append at end

        # Screen capture (lazy init)
        self._screen = None

        self._setup_ui()
        self._load_config()

    def _get_screen(self):
        """Lazy init screen capture."""
        if self._screen is None:
            from src.core import get_screen_capture
            self._screen = get_screen_capture()
        return self._screen

    def _setup_ui(self):
        """Setup the recorder tab UI."""
        # Split into left and right panels
        left_panel = ctk.CTkFrame(self, fg_color="transparent")
        left_panel.pack(side="left", fill="both", expand=True, padx=(10, 5), pady=10)

        right_panel = ctk.CTkFrame(self, fg_color="transparent", width=280)
        right_panel.pack(side="right", fill="both", padx=(5, 10), pady=10)
        right_panel.pack_propagate(False)

        # === LEFT PANEL: Recorded Waypoints ===
        waypoints_section = create_section(left_panel, "Recorded Waypoints")
        waypoints_section.pack(fill="both", expand=True)

        # File controls
        file_frame = ctk.CTkFrame(waypoints_section, fg_color="transparent")
        file_frame.pack(fill="x", padx=10, pady=10)

        ctk.CTkLabel(
            file_frame, text="Output File:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.output_file_var = ctk.StringVar(value="")
        self.output_file_var.trace_add("write", self._on_settings_change)
        self.output_file_entry = create_entry(
            file_frame,
            textvariable=self.output_file_var,
            placeholder="routes/my_route.json",
        )
        self.output_file_entry.pack(side="left", fill="x", expand=True, padx=10)

        create_button(
            file_frame, text="Browse", command=self._browse_output,
            width=70,
        ).pack(side="left", padx=(0, 5))

        create_button(
            file_frame, text="Load", command=self._load_waypoints,
            width=60,
        ).pack(side="left", padx=(0, 5))

        create_button(
            file_frame, text="Save", command=self._save_waypoints,
            style="accent", width=60,
        ).pack(side="left")

        # Status bar
        status_frame = ctk.CTkFrame(waypoints_section, fg_color="transparent")
        status_frame.pack(fill="x", padx=10, pady=(0, 10))

        self.status_label = ctk.CTkLabel(
            status_frame,
            text="Status: Not recording",
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
        )
        self.status_label.pack(side="left")

        self.coord_label = ctk.CTkLabel(
            status_frame,
            text="Position: ---",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=ACCENT,
        )
        self.coord_label.pack(side="right")

        # Waypoint list
        self.waypoint_list = WaypointList(
            waypoints_section,
            on_waypoint_click=self._on_waypoint_click,
            fg_color=BG_SURFACE,
        )
        self.waypoint_list.pack(fill="both", expand=True, padx=10, pady=(0, 10))

        # === RIGHT PANEL: Recording Controls ===
        controls_section = create_section(right_panel, "Recording Controls")
        controls_section.pack(fill="both", expand=True)

        controls_content = ctk.CTkScrollableFrame(controls_section, fg_color="transparent")
        controls_content.pack(fill="both", expand=True, padx=5, pady=5)

        # Start/Stop Recording
        record_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        record_frame.pack(fill="x", pady=(5, 15))

        self.record_btn = ctk.CTkButton(
            record_frame,
            text="Start Recording",
            font=ctk.CTkFont(size=14, weight="bold"),
            height=40,
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
            command=self._toggle_recording,
            corner_radius=4,
        )
        self.record_btn.pack(fill="x")

        # Waypoint buttons header
        _section_header(controls_content, "Add Waypoint:")

        # Walk button
        walk_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        walk_frame.pack(fill="x", pady=2)

        self.walk_btn = _waypoint_button(
            walk_frame, "WALK", self._add_walk,
            fg_color=COLOR_INFO, hover_color="#4590d4",
        )
        self.walk_btn.pack(side="left")
        _hotkey_hint(walk_frame, "(F6)").pack(side="left", padx=5)

        # Rope button
        rope_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        rope_frame.pack(fill="x", pady=2)

        self.rope_btn = _waypoint_button(
            rope_frame, "ROPE", self._add_rope,
            fg_color="#9b59b6", hover_color="#8e44ad",
        )
        self.rope_btn.pack(side="left")
        _hotkey_hint(rope_frame, "(F7)").pack(side="left", padx=5)

        # Shovel button
        shovel_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        shovel_frame.pack(fill="x", pady=2)

        self.shovel_btn = _waypoint_button(
            shovel_frame, "SHOVEL", self._add_shovel,
            fg_color=COLOR_WARNING, hover_color="#b8860b",
        )
        self.shovel_btn.pack(side="left")
        _hotkey_hint(shovel_frame, "(F8)").pack(side="left", padx=5)

        # Ladder button (useHole - right-click on ladder)
        ladder_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        ladder_frame.pack(fill="x", pady=2)

        self.ladder_btn = _waypoint_button(
            ladder_frame, "LADDER", self._add_ladder,
            fg_color="#795548", hover_color="#5d4037",
        )
        self.ladder_btn.pack(side="left")
        _hotkey_hint(ladder_frame, "(F4)").pack(side="left", padx=5)

        # Label button
        label_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        label_frame.pack(fill="x", pady=2)

        self.label_btn = _waypoint_button(
            label_frame, "LABEL", self._add_label,
            fg_color=ACCENT, hover_color=ACCENT_HOVER,
        )
        self.label_btn.pack(side="left")
        _hotkey_hint(label_frame, "(F9)").pack(side="left", padx=5)

        # Refill Checker button
        refill_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        refill_frame.pack(fill="x", pady=2)

        self.refill_btn = _waypoint_button(
            refill_frame, "REFILL CHECK", self._add_refill_checker,
            fg_color=COLOR_ERROR, hover_color="#da3633",
        )
        self.refill_btn.pack(side="left")
        _hotkey_hint(refill_frame, "(F10)").pack(side="left", padx=5)

        # Separator
        _separator(controls_content)

        # Stairs section
        _section_header(controls_content, "Stairs:")

        stairs_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        stairs_frame.pack(fill="x", pady=2)

        self.move_down_btn = _waypoint_button(
            stairs_frame, "MOVE DOWN", self._add_move_down,
            fg_color=BG_ELEVATED, hover_color=BG_INPUT,
        )
        self.move_down_btn.pack(side="left", padx=(0, 5))

        self.move_up_btn = _waypoint_button(
            stairs_frame, "MOVE UP", self._add_move_up,
            fg_color=BG_ELEVATED, hover_color=BG_INPUT,
        )
        self.move_up_btn.pack(side="left")

        # Direction selection for stairs
        dir_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        dir_frame.pack(fill="x", pady=5)

        ctk.CTkLabel(
            dir_frame, text="Direction:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
        ).pack(side="left")

        self.direction_var = ctk.StringVar(value="south")
        self.direction_var.trace_add("write", self._on_settings_change)
        self.direction_menu = create_option_menu(
            dir_frame,
            variable=self.direction_var,
            values=["north", "south", "east", "west"],
            width=100,
            command=lambda _: self._save_config(),
        )
        self.direction_menu.pack(side="left", padx=10)

        # Separator
        _separator(controls_content)

        # Actions section
        _section_header(controls_content, "Actions:")

        # Undo button
        undo_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        undo_frame.pack(fill="x", pady=2)

        self.undo_btn = _waypoint_button(
            undo_frame, "UNDO", self._undo,
            fg_color=COLOR_ERROR, hover_color="#da3633",
        )
        self.undo_btn.pack(side="left")
        _hotkey_hint(undo_frame, "(F5)").pack(side="left", padx=5)

        # Save button (always enabled)
        save_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        save_frame.pack(fill="x", pady=2)

        self.save_btn = _waypoint_button(
            save_frame, "SAVE", self._save_waypoints,
            fg_color=COLOR_SUCCESS, hover_color=ACCENT_HOVER,
            state="normal",
        )
        self.save_btn.pack(side="left")
        _hotkey_hint(save_frame, "(Cmd+S / F11)").pack(side="left", padx=5)

        # Clear all button
        clear_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        clear_frame.pack(fill="x", pady=(10, 2))

        self.clear_btn = _waypoint_button(
            clear_frame, "CLEAR ALL", self._clear_all,
            fg_color=BG_ELEVATED, hover_color=BG_INPUT,
            state="normal",
        )
        self.clear_btn.pack(side="left")

        # Insert mode section
        _separator(controls_content)
        _section_header(controls_content, "Edit Mode:")

        self.insert_mode_var = ctk.BooleanVar(value=False)
        insert_mode_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        insert_mode_frame.pack(fill="x", pady=2)

        create_checkbox(
            insert_mode_frame,
            text="Insert at selection",
            variable=self.insert_mode_var,
            command=self._on_insert_mode_change,
        ).pack(side="left")

        # Selected index indicator
        self.selection_label = ctk.CTkLabel(
            insert_mode_frame,
            text="(End)",
            font=ctk.CTkFont(size=11),
            text_color=ACCENT,
        )
        self.selection_label.pack(side="left", padx=10)

        # Move and Delete buttons frame
        edit_buttons_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        edit_buttons_frame.pack(fill="x", pady=(5, 2))

        self.move_up_wp_btn = create_button(
            edit_buttons_frame, text="▲ UP", command=self._move_waypoint_up,
            width=65,
        )
        self.move_up_wp_btn.pack(side="left", padx=(0, 5))

        self.move_down_wp_btn = create_button(
            edit_buttons_frame, text="▼ DOWN", command=self._move_waypoint_down,
            width=65,
        )
        self.move_down_wp_btn.pack(side="left", padx=(0, 5))

        self.delete_btn = create_button(
            edit_buttons_frame, text="DELETE", command=self._delete_selected,
            style="danger", width=65,
        )
        self.delete_btn.pack(side="left")

        # Hotkey settings section
        _separator(controls_content)
        _section_header(controls_content, "Hotkey Settings:")

        # Rope hotkey
        rope_hk_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        rope_hk_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            rope_hk_frame, text="Rope hotkey:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
            width=100, anchor="w",
        ).pack(side="left")
        self.rope_hotkey_var = ctk.StringVar(value="t")
        self.rope_hotkey_var.trace_add("write", self._on_settings_change)
        create_entry(
            rope_hk_frame,
            textvariable=self.rope_hotkey_var,
            width=40,
        ).pack(side="left")

        # Shovel hotkey
        shovel_hk_frame = ctk.CTkFrame(controls_content, fg_color="transparent")
        shovel_hk_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            shovel_hk_frame, text="Shovel hotkey:",
            font=ctk.CTkFont(size=12), text_color=TEXT_MUTED,
            width=100, anchor="w",
        ).pack(side="left")
        self.shovel_hotkey_var = ctk.StringVar(value="r")
        self.shovel_hotkey_var.trace_add("write", self._on_settings_change)
        create_entry(
            shovel_hk_frame,
            textvariable=self.shovel_hotkey_var,
            width=40,
        ).pack(side="left")

    def _browse_output(self):
        """Browse to select an existing route file or specify output location."""
        routes_dir = os.path.abspath(self._get_routes_dir())
        if not os.path.exists(routes_dir):
            os.makedirs(routes_dir, exist_ok=True)

        # Change to routes directory to force macOS dialog to open there
        original_cwd = os.getcwd()
        try:
            os.chdir(routes_dir)
            filename = filedialog.askopenfilename(
                title="Select Route File",
                initialdir=routes_dir,
                filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
            )
        finally:
            os.chdir(original_cwd)

        if filename:
            self.output_file_var.set(filename)
            self._save_config()

    def _load_waypoints(self):
        """Load existing waypoints from file."""
        output_file = self.output_file_var.get()
        if not output_file:
            # Open file dialog if no file selected
            routes_dir = os.path.abspath(self._get_routes_dir())
            if not os.path.exists(routes_dir):
                routes_dir = os.path.expanduser("~")

            # Change to routes directory to force macOS dialog to open there
            original_cwd = os.getcwd()
            try:
                os.chdir(routes_dir)
                filename = filedialog.askopenfilename(
                    title="Load Waypoints",
                    initialdir=routes_dir,
                    filetypes=[("JSON files", "*.json"), ("All files", "*.*")]
                )
            finally:
                os.chdir(original_cwd)

            if filename:
                self.output_file_var.set(filename)
                output_file = filename
            else:
                return

        if not os.path.exists(output_file):
            self._update_status("File not found")
            return

        try:
            with open(output_file, 'r') as f:
                data = json.load(f)

            if isinstance(data, list):
                self.waypoints = data
            elif isinstance(data, dict) and 'waypoints' in data:
                self.waypoints = data['waypoints']
            else:
                self.waypoints = []

            # Ensure all waypoints have IDs
            for i, wp in enumerate(self.waypoints):
                wp['id'] = i

            self._update_label_counter()
            self._refresh_waypoint_list()
            self._owned_file = os.path.abspath(output_file)
            self._update_status(f"Loaded {len(self.waypoints)} waypoints")
            self._save_config()

        except (json.JSONDecodeError, IOError) as e:
            self._update_status(f"Error loading: {e}")

    def _toggle_recording(self):
        """Toggle recording state."""
        if self.recording:
            self._stop_recording()
        else:
            self._start_recording()

    def _start_recording(self):
        """Start recording waypoints."""
        self.recording = True
        self.record_btn.configure(
            text="Stop Recording",
            fg_color=COLOR_ERROR,
            hover_color="#da3633",
        )
        self._set_buttons_state("normal")
        self._update_status("Recording...")

        # Start coordinate update thread
        self._stop_coord_update = False
        self._coord_update_thread = threading.Thread(target=self._update_coord_loop, daemon=True)
        self._coord_update_thread.start()

        # Bind keyboard shortcuts
        self._bind_shortcuts()

    def _stop_recording(self):
        """Stop recording waypoints."""
        self.recording = False
        self._stop_coord_update = True
        self.record_btn.configure(
            text="Start Recording",
            fg_color=ACCENT,
            hover_color=ACCENT_HOVER,
        )
        self._set_buttons_state("disabled")
        self._update_status(f"Stopped. {len(self.waypoints)} waypoints recorded")

        # Unbind keyboard shortcuts
        self._unbind_shortcuts()

    def _set_buttons_state(self, state: str):
        """Set state for all waypoint buttons (except SAVE which is always enabled)."""
        self.walk_btn.configure(state=state)
        self.rope_btn.configure(state=state)
        self.shovel_btn.configure(state=state)
        self.ladder_btn.configure(state=state)
        self.label_btn.configure(state=state)
        self.refill_btn.configure(state=state)
        self.move_down_btn.configure(state=state)
        self.move_up_btn.configure(state=state)
        self.undo_btn.configure(state=state)
        # save_btn is always enabled

    def _bind_shortcuts(self):
        """Bind keyboard shortcuts."""
        root = self.winfo_toplevel()
        root.bind('<F4>', lambda e: self._add_ladder())
        root.bind('<F5>', lambda e: self._undo())
        root.bind('<F6>', lambda e: self._add_walk())
        root.bind('<F7>', lambda e: self._add_rope())
        root.bind('<F8>', lambda e: self._add_shovel())
        root.bind('<F9>', lambda e: self._add_label())
        root.bind('<F10>', lambda e: self._add_refill_checker())
        root.bind('<F11>', lambda e: self._save_waypoints())
        root.bind('<Command-s>', lambda e: self._save_waypoints())  # macOS takes F11 for "Show Desktop"
        root.bind('<Control-s>', lambda e: self._save_waypoints())
        root.bind('<Shift-F6>', lambda e: self._add_move_down())
        root.bind('<Shift-F7>', lambda e: self._add_move_up())

    def _unbind_shortcuts(self):
        """Unbind keyboard shortcuts."""
        root = self.winfo_toplevel()
        for key in ['<F4>', '<F5>', '<F6>', '<F7>', '<F8>', '<F9>', '<F10>', '<F11>', '<Command-s>', '<Control-s>',
                    '<Shift-F6>', '<Shift-F7>']:
            try:
                root.unbind(key)
            except Exception:
                pass

    def _update_coord_loop(self):
        """Background thread to update coordinate display."""
        from src.repositories.radar import get_coordinate

        while not self._stop_coord_update:
            try:
                screen = self._get_screen()
                img = screen.capture()
                gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
                coord = get_coordinate(gray, self._previous_coord)

                if coord:
                    self._previous_coord = coord
                    # Update label in main thread
                    self.after(0, lambda c=coord: self.coord_label.configure(
                        text=f"Position: ({c[0]}, {c[1]}, {c[2]})"
                    ))
                else:
                    self.after(0, lambda: self.coord_label.configure(text="Position: Not detected"))

            except Exception:
                pass

            time.sleep(0.3)  # Update every 300ms

    def _get_current_coordinate(self):
        """Get current coordinate from radar."""
        from src.repositories.radar import get_coordinate

        try:
            screen = self._get_screen()
            img = screen.capture()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            coord = get_coordinate(gray, self._previous_coord)
            if coord:
                self._previous_coord = coord
            return coord
        except Exception:
            return None

    def _add_waypoint(self, wp_type: str, options: dict = None, label: str = ""):
        """Add a waypoint at current position or selected index."""
        if not self.recording:
            return False

        coord = self._get_current_coordinate()
        if coord is None:
            self._update_status("ERROR: Could not detect position!")
            return False

        waypoint = {
            "id": 0,  # Will be reassigned
            "type": wp_type,
            "coordinate": list(coord),
            "label": label,
            "options": options or {}
        }

        # Insert at selected position or append at end
        if self.insert_mode_var.get() and 0 <= self._selected_index < len(self.waypoints):
            insert_pos = self._selected_index + 1  # Insert AFTER selected
            self.waypoints.insert(insert_pos, waypoint)
            self._selected_index = insert_pos  # Move selection to new waypoint
            self._reindex_waypoints()
            self._refresh_waypoint_list(keep_selection=True)
            label_text = f" ({label})" if label else ""
            self._update_status(f"Inserted {wp_type} at position {insert_pos}")
        else:
            self.waypoints.append(waypoint)
            self._reindex_waypoints()
            self._refresh_waypoint_list()
            label_text = f" ({label})" if label else ""
            self._update_status(f"[{len(self.waypoints)-1}] Added {wp_type} at {coord}{label_text}")

        return True

    def _reindex_waypoints(self):
        """Reassign IDs to all waypoints after insert/delete."""
        for i, wp in enumerate(self.waypoints):
            wp['id'] = i

    def _add_walk(self):
        """Add walk waypoint."""
        self._add_waypoint("walk")

    def _add_rope(self):
        """Add rope waypoint."""
        hotkey = self.rope_hotkey_var.get() or "t"
        self._add_waypoint("useRope", {"hotkey": hotkey})

    def _add_shovel(self):
        """Add shovel waypoint."""
        hotkey = self.shovel_hotkey_var.get() or "r"
        self._add_waypoint("useShovel", {"hotkey": hotkey})

    def _add_ladder(self):
        """Add ladder waypoint (right-click on ladder to climb)."""
        self._add_waypoint("useLadder")

    def _add_label(self):
        """Add label waypoint with user input."""
        # Ask for label name
        name = simpledialog.askstring(
            "Add Label",
            "Enter label name:",
            initialvalue=f"label_{self._label_counter + 1}"
        )

        if name:
            self._label_counter += 1
            self._add_waypoint("label", label=name)

    def _add_refill_checker(self):
        """Add refill checker waypoint."""
        options = {
            "minimumAmountOfHealthPotions": 50,
            "minimumAmountOfManaPotions": 100,
            "minimumAmountOfCap": 300,
            "waypointLabelToRedirect": "huntStart"
        }
        self._add_waypoint("refillChecker", options, label="checkSupplies")

    def _add_move_down(self):
        """Add moveDown waypoint."""
        direction = self.direction_var.get()
        self._add_waypoint("moveDown", {"direction": direction})

    def _add_move_up(self):
        """Add moveUp waypoint."""
        direction = self.direction_var.get()
        self._add_waypoint("moveUp", {"direction": direction})

    def _undo(self):
        """Remove last waypoint."""
        if not self.waypoints:
            self._update_status("No waypoints to remove")
            return

        removed = self.waypoints.pop()
        self._reindex_waypoints()
        self._refresh_waypoint_list()
        self._update_status(f"Removed: {removed['type']} at {removed['coordinate']}")

    def _get_routes_dir(self) -> str:
        """Get the routes directory path."""
        # src/gui/tabs/recorder.py -> go up 4 levels to project root
        current_file = os.path.abspath(__file__)
        project_root = os.path.dirname(os.path.dirname(os.path.dirname(os.path.dirname(current_file))))
        return os.path.join(project_root, "routes")

    def _normalize_output_path(self, filename: str) -> str:
        """Normalize output path: add routes/ prefix and .json extension if needed."""
        if not filename:
            return ""

        # Add .json extension if not present
        if not filename.lower().endswith('.json'):
            filename = filename + '.json'

        # If it's just a filename (no directory), put it in routes/
        if os.path.dirname(filename) == '':
            filename = os.path.join(self._get_routes_dir(), filename)

        return filename

    def _confirm_overwrite(self, output_file):
        """A different route already on disk (e.g. Output File left from an old route) is only replaced if confirmed."""
        if not os.path.exists(output_file) or os.path.abspath(output_file) == self._owned_file:
            return True
        from tkinter import messagebox
        return messagebox.askyesno(
            "Overwrite route?",
            f"{os.path.basename(output_file)} already exists and is a different route.\n\n"
            f"Replace it with these {len(self.waypoints)} waypoints?",
        )

    def _save_waypoints(self):
        """Save waypoints to file."""
        output_file = self.output_file_var.get().strip()

        if not output_file:
            self._browse_output()
            output_file = self.output_file_var.get().strip()
            if not output_file:
                return

        # Normalize path (add routes/ and .json if needed)
        output_file = self._normalize_output_path(output_file)

        # Update the var with normalized path
        self.output_file_var.set(output_file)

        if not self._confirm_overwrite(output_file):
            self._update_status("Not saved - change Output File to a new name")
            return

        # Ensure directory exists
        os.makedirs(os.path.dirname(output_file) or '.', exist_ok=True)

        data = {
            "name": os.path.splitext(os.path.basename(output_file))[0],
            "waypoints": self.waypoints,
            "metadata": {
                "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        try:
            with open(output_file, 'w') as f:
                json.dump(data, f, indent=2)

            self._owned_file = os.path.abspath(output_file)
            self._update_status(f"Saved {len(self.waypoints)} waypoints to {os.path.basename(output_file)}")
            self._save_config()
        except IOError as e:
            self._update_status(f"Error saving: {e}")

    def _clear_all(self):
        """Clear all waypoints."""
        if self.waypoints:
            # Simple confirmation
            from tkinter import messagebox
            if messagebox.askyesno("Clear All", "Are you sure you want to clear all waypoints?"):
                self.waypoints = []
                self._label_counter = 0
                self._refresh_waypoint_list()
                self._update_status("Cleared all waypoints")

    def _on_waypoint_click(self, index: int):
        """Handle waypoint click in the list."""
        self._selected_index = index
        self.waypoint_list.set_current_index(index)
        self._update_selection_label()

    def _refresh_waypoint_list(self, keep_selection: bool = False):
        """Refresh the waypoint list display."""
        self.waypoint_list.set_waypoints(self.waypoints)
        if self.waypoints:
            if keep_selection and 0 <= self._selected_index < len(self.waypoints):
                self.waypoint_list.set_current_index(self._selected_index)
            else:
                self._selected_index = len(self.waypoints) - 1
                self.waypoint_list.set_current_index(self._selected_index)
        else:
            self._selected_index = -1
        self._update_selection_label()

    def _update_selection_label(self):
        """Update the selection indicator label."""
        if self._selected_index >= 0 and self._selected_index < len(self.waypoints):
            wp = self.waypoints[self._selected_index]
            wp_type = wp.get('type', 'walk')
            self.selection_label.configure(text=f"(#{self._selected_index} {wp_type})")
        else:
            self.selection_label.configure(text="(End)")

    def _on_insert_mode_change(self):
        """Handle insert mode checkbox change."""
        if self.insert_mode_var.get():
            self._update_status("Insert mode: ON - new waypoints insert after selection")
        else:
            self._update_status("Insert mode: OFF - new waypoints append at end")

    def _delete_selected(self):
        """Delete the selected waypoint."""
        if not self.waypoints:
            self._update_status("No waypoints to delete")
            return

        if self._selected_index < 0 or self._selected_index >= len(self.waypoints):
            self._update_status("No waypoint selected")
            return

        removed = self.waypoints.pop(self._selected_index)
        self._reindex_waypoints()

        # Adjust selection
        if self._selected_index >= len(self.waypoints):
            self._selected_index = len(self.waypoints) - 1

        self._refresh_waypoint_list(keep_selection=True)
        self._update_status(f"Deleted: {removed['type']} at {removed['coordinate']}")

    def _move_waypoint_up(self):
        """Move the selected waypoint up in the list."""
        if not self.waypoints:
            self._update_status("No waypoints to move")
            return

        if self._selected_index <= 0:
            self._update_status("Already at the top")
            return

        # Swap with previous waypoint
        idx = self._selected_index
        self.waypoints[idx], self.waypoints[idx - 1] = self.waypoints[idx - 1], self.waypoints[idx]
        self._selected_index = idx - 1
        self._reindex_waypoints()
        self._refresh_waypoint_list(keep_selection=True)
        self._update_status(f"Moved waypoint to position {self._selected_index}")

    def _move_waypoint_down(self):
        """Move the selected waypoint down in the list."""
        if not self.waypoints:
            self._update_status("No waypoints to move")
            return

        if self._selected_index < 0 or self._selected_index >= len(self.waypoints) - 1:
            self._update_status("Already at the bottom")
            return

        # Swap with next waypoint
        idx = self._selected_index
        self.waypoints[idx], self.waypoints[idx + 1] = self.waypoints[idx + 1], self.waypoints[idx]
        self._selected_index = idx + 1
        self._reindex_waypoints()
        self._refresh_waypoint_list(keep_selection=True)
        self._update_status(f"Moved waypoint to position {self._selected_index}")

    def _update_status(self, message: str):
        """Update status label."""
        prefix = "Recording" if self.recording else "Status"
        self.status_label.configure(text=f"{prefix}: {message}")

    def _update_label_counter(self):
        """Update label counter based on existing waypoints."""
        max_label = 0
        for wp in self.waypoints:
            label = wp.get('label', '')
            if label.startswith('label_'):
                try:
                    num = int(label.split('_')[1])
                    max_label = max(max_label, num)
                except (ValueError, IndexError):
                    pass
        self._label_counter = max_label

    def reload(self, config_manager):
        """Show another profile's settings in the existing widgets."""
        self.config_manager = config_manager
        self._load_config()

    def _load_config(self):
        """Load configuration from config manager."""
        if not self.config_manager:
            return

        # Load from config (defaults come from src.core.defaults.DEFAULT_CONFIG)
        self.output_file_var.set(self.config_manager.get('recorder.outputFile', ''))
        self.rope_hotkey_var.set(self.config_manager.get('recorder.ropeHotkey', 't'))
        self.shovel_hotkey_var.set(self.config_manager.get('recorder.shovelHotkey', 'r'))
        self.direction_var.set(self.config_manager.get('recorder.direction', 'south'))

    def _on_settings_change(self, *args):
        """Called when a setting changes. Debounces saves."""
        # Use after to debounce rapid changes (e.g., typing)
        if hasattr(self, '_save_pending'):
            self.after_cancel(self._save_pending)
        self._save_pending = self.after(500, self._save_config)

    def _save_config(self):
        """Save current configuration."""
        if not self.config_manager:
            return

        self.config_manager.set('recorder', {
            'outputFile': self.output_file_var.get(),
            'ropeHotkey': self.rope_hotkey_var.get(),
            'shovelHotkey': self.shovel_hotkey_var.get(),
            'direction': self.direction_var.get()
        })
        self.config_manager.save()

    def get_waypoints(self) -> List[Dict]:
        """Get the current waypoints."""
        return self.waypoints

    def destroy(self):
        """Clean up when tab is destroyed."""
        self._stop_coord_update = True
        self._unbind_shortcuts()
        super().destroy()

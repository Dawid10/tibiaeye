"""
Waypoint List Component - Display and navigate waypoints.

Uses CTkTextbox for efficient rendering of large waypoint lists.
"""
import customtkinter as ctk
from typing import List, Dict, Optional, Callable

from ..theme import (
    BG_APP, BG_ELEVATED, ACCENT, TEXT_PRIMARY, BORDER, COLOR_WARNING,
    resolve,
)


class WaypointList(ctk.CTkFrame):
    """Widget for displaying waypoints with current waypoint highlighting."""

    def __init__(
        self,
        master,
        on_waypoint_click: Optional[Callable[[int], None]] = None,
        **kwargs
    ):
        super().__init__(master, **kwargs)

        self.waypoints: List[Dict] = []
        self.current_index = 0
        self.on_waypoint_click = on_waypoint_click

        self._setup_ui()

    def _setup_ui(self):
        """Setup the waypoint list UI."""
        # Header
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=(5, 0))

        # Column headers
        ctk.CTkLabel(
            header, text="#",
            width=35,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w"
        ).pack(side="left")

        ctk.CTkLabel(
            header, text="Type",
            width=90,
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w"
        ).pack(side="left", padx=(5, 0))

        ctk.CTkLabel(
            header, text="Coordinates",
            font=ctk.CTkFont(size=11, weight="bold"),
            anchor="w"
        ).pack(side="left", fill="x", expand=True, padx=(5, 0))

        # Separator
        sep = ctk.CTkFrame(self, height=1, fg_color=BORDER)
        sep.pack(fill="x", padx=5, pady=5)

        # Text widget for waypoints (much more efficient than individual frames)
        self.textbox = ctk.CTkTextbox(
            self,
            font=ctk.CTkFont(family="Courier", size=11),
            wrap="none",
            state="disabled",
            fg_color=BG_APP
        )
        self.textbox.pack(fill="both", expand=True, padx=5, pady=(0, 5))

        # Configure tags for highlighting
        self._apply_tags()

        # Bind click event
        self.textbox._textbox.bind("<Button-1>", self._on_text_click)

        # Footer with current waypoint info
        self.footer = ctk.CTkLabel(
            self,
            text="No waypoints loaded",
            font=ctk.CTkFont(size=11),
            anchor="w"
        )
        self.footer.pack(fill="x", padx=5, pady=(0, 5))

    def _apply_tags(self):
        """Apply tag colors from theme."""
        self.textbox._textbox.tag_configure(
            "current",
            background=resolve(BG_ELEVATED),
            foreground=ACCENT,
        )
        self.textbox._textbox.tag_configure("normal", foreground=resolve(TEXT_PRIMARY))
        self.textbox._textbox.tag_configure("type_special", foreground=COLOR_WARNING)

    def apply_theme(self):
        """Re-apply tag colors after theme change."""
        self._apply_tags()

    def set_waypoints(self, waypoints: List[Dict]):
        """Set the list of waypoints to display."""
        self.waypoints = waypoints
        self._rebuild_list()

    def set_current_index(self, index: int):
        """Set the currently active waypoint index."""
        # Only update if index actually changed and is valid
        if index == self.current_index:
            return
        if not (0 <= index < len(self.waypoints)):
            return

        old_index = self.current_index
        self.current_index = index

        # Update only the changed lines instead of rebuilding everything
        self._update_line_highlighting(old_index, index)
        self._scroll_to_current()
        self._update_footer()

    def _update_line_highlighting(self, old_index: int, new_index: int):
        """Update highlighting for specific lines without rebuilding."""
        if not self.waypoints:
            return

        try:
            self.textbox.configure(state="normal")

            # Remove highlight from old line
            if 0 <= old_index < len(self.waypoints):
                old_line_start = f"{old_index + 1}.0"
                old_line_end = f"{old_index + 1}.end"
                self.textbox._textbox.tag_remove("current", old_line_start, old_line_end)
                self.textbox._textbox.tag_add("normal", old_line_start, old_line_end)

                # Update indicator character
                self.textbox._textbox.delete(f"{old_index + 1}.0", f"{old_index + 1}.1")
                self.textbox._textbox.insert(f"{old_index + 1}.0", " ", "normal")

            # Add highlight to new line
            if 0 <= new_index < len(self.waypoints):
                new_line_start = f"{new_index + 1}.0"
                new_line_end = f"{new_index + 1}.end"
                self.textbox._textbox.tag_remove("normal", new_line_start, new_line_end)
                self.textbox._textbox.tag_add("current", new_line_start, new_line_end)

                # Update indicator character
                self.textbox._textbox.delete(f"{new_index + 1}.0", f"{new_index + 1}.1")
                self.textbox._textbox.insert(f"{new_index + 1}.0", ">", "current")

            self.textbox.configure(state="disabled")
        except Exception:
            # Fallback to full rebuild if something goes wrong
            self._rebuild_list()

    def _rebuild_list(self):
        """Rebuild the waypoint list display."""
        self.textbox.configure(state="normal")
        self.textbox._textbox.delete("1.0", "end")

        if not self.waypoints:
            self.textbox._textbox.insert("end", "  No waypoints loaded\n", "normal")
            self.textbox.configure(state="disabled")
            self._update_footer()
            return

        # Type icons for special waypoints
        type_icons = {
            'walk': '   ',
            'stand': '   ',
            'refillChecker': '[C]',
            'refill': '[R]',
            'useHole': '[H]',
            'useLadder': '[Ld]',
            'useShovel': '[S]',
            'useRope': '[U]',
            'depositGold': '[$]',
            'depositItems': '[D]',
            'moveUp': '[^]',
            'moveDown': '[v]',
            'label': '[L]'
        }

        for i, wp in enumerate(self.waypoints):
            is_current = i == self.current_index
            indicator = ">" if is_current else " "

            wp_type = wp.get('type', 'walk')
            icon = type_icons.get(wp_type, '   ')

            # Format coordinates
            coord = wp.get('coordinate')
            if coord:
                coord_text = f"({coord[0]}, {coord[1]}, {coord[2]})"
            else:
                coord_text = "-"

            # Format options
            options = wp.get('options', {})
            option_text = self._format_options(options)

            # Build line
            line = f"{indicator} {i:3d}  {icon} {wp_type:<14} {coord_text:<20}"
            if option_text:
                line += f" {option_text}"
            line += "\n"

            # Insert with appropriate tag
            tag = "current" if is_current else "normal"
            self.textbox._textbox.insert("end", line, tag)

        self.textbox.configure(state="disabled")
        self._update_footer()

    def _format_options(self, options: Dict) -> str:
        """Format waypoint options for display."""
        if not options:
            return ""

        parts = []
        if 'label' in options:
            parts.append(options['label'])
        if 'direction' in options:
            parts.append(options['direction'])
        if 'minHpPotions' in options:
            parts.append(f"hp<{options['minHpPotions']}")
        if 'minManaPotions' in options:
            parts.append(f"mp<{options['minManaPotions']}")

        if not parts:
            return ""
        return ", ".join(parts)

    def _scroll_to_current(self):
        """Scroll to make the current waypoint visible."""
        if not self.waypoints:
            return

        try:
            # Calculate line number (1-indexed for tkinter)
            line_num = self.current_index + 1
            self.textbox._textbox.see(f"{line_num}.0")
        except Exception:
            pass

    def _update_footer(self):
        """Update the footer with current waypoint info."""
        total = len(self.waypoints)
        if total > 0:
            self.footer.configure(text=f"Current: Waypoint {self.current_index} of {total}")
            return
        self.footer.configure(text="No waypoints loaded")

    def _on_text_click(self, event):
        """Handle click on the text widget to select waypoint."""
        if not self.waypoints or not self.on_waypoint_click:
            return

        try:
            # Get the line number that was clicked
            index = self.textbox._textbox.index(f"@{event.x},{event.y}")
            line_num = int(index.split(".")[0]) - 1  # Convert to 0-indexed

            if 0 <= line_num < len(self.waypoints):
                self.on_waypoint_click(line_num)
        except Exception:
            pass

"""
Stat Bar Component - HP/MP progress bar widget.
"""
import customtkinter as ctk
from typing import Optional, Tuple

from ..theme import (
    BG_INPUT,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, COLOR_INFO,
)


# Purple for generic bars (no theme constant needed)
_COLOR_GENERIC = "#9b59b6"


class StatBar(ctk.CTkFrame):
    """Widget for displaying HP/MP bars with percentage."""

    # Color schemes
    COLORS = {
        "hp": {
            "high": COLOR_SUCCESS,
            "medium": COLOR_WARNING,
            "low": COLOR_ERROR,
        },
        "mp": {
            "high": COLOR_INFO,
            "medium": COLOR_INFO,
            "low": COLOR_INFO,
        },
        "cpu": {
            "high": COLOR_ERROR,
            "medium": COLOR_WARNING,
            "low": COLOR_SUCCESS,
        },
        "memory": {
            "high": COLOR_ERROR,
            "medium": COLOR_WARNING,
            "low": COLOR_SUCCESS,
        },
        "generic": {
            "high": _COLOR_GENERIC,
            "medium": _COLOR_GENERIC,
            "low": _COLOR_GENERIC,
        },
    }

    def __init__(
        self,
        master,
        label: str = "HP",
        bar_type: str = "hp",
        initial_value: int = 100,
        show_percentage: bool = True,
        height: int = 20,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.bar_type = bar_type
        self.show_percentage = show_percentage
        self.value = initial_value

        self._setup_ui(label, height)
        self.set_value(initial_value)

    def _setup_ui(self, label: str, height: int):
        """Setup the stat bar UI."""
        # Label
        self.label = ctk.CTkLabel(
            self,
            text=f"{label}:",
            font=ctk.CTkFont(size=12, weight="bold"),
            width=60,
            anchor="w"
        )
        self.label.pack(side="left", padx=(0, 5))

        # Progress bar container
        bar_frame = ctk.CTkFrame(self, fg_color=BG_INPUT, corner_radius=4)
        bar_frame.pack(side="left", fill="x", expand=True)

        # Progress bar
        self.progress = ctk.CTkProgressBar(
            bar_frame,
            height=height,
            corner_radius=4,
            progress_color=self._get_color(100)
        )
        self.progress.pack(fill="x", padx=2, pady=2)
        self.progress.set(1.0)

        # Percentage label
        if self.show_percentage:
            self.percentage_label = ctk.CTkLabel(
                self,
                text="100%",
                font=ctk.CTkFont(size=12),
                width=45,
                anchor="e"
            )
            self.percentage_label.pack(side="right", padx=(5, 0))

    def _get_color(self, percentage: int) -> str:
        """Get the appropriate color based on percentage."""
        colors = self.COLORS.get(self.bar_type, self.COLORS["generic"])

        if self.bar_type in ("cpu", "memory"):
            if percentage > 60:
                return colors["high"]
            if percentage > 30:
                return colors["medium"]
            return colors["low"]

        if percentage > 60:
            return colors["high"]
        if percentage > 30:
            return colors["medium"]
        return colors["low"]

    def set_value(self, percentage: int):
        """Set the bar value (0-100)."""
        self.value = max(0, min(100, percentage))

        # Update progress bar
        self.progress.set(self.value / 100)
        self.progress.configure(progress_color=self._get_color(self.value))

        # Update percentage label
        if self.show_percentage:
            self.percentage_label.configure(text=f"{self.value}%")

    def get_value(self) -> int:
        """Get the current bar value."""
        return self.value


class CompactStatBar(ctk.CTkFrame):
    """Compact stat bar without label, for inline use."""

    def __init__(
        self,
        master,
        bar_type: str = "hp",
        initial_value: int = 100,
        width: int = 100,
        height: int = 12,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.bar_type = bar_type
        self.value = initial_value

        # Progress bar
        self.progress = ctk.CTkProgressBar(
            self,
            width=width,
            height=height,
            corner_radius=3,
            progress_color=StatBar.COLORS.get(bar_type, StatBar.COLORS["generic"])["high"]
        )
        self.progress.pack()
        self.progress.set(initial_value / 100)

    def set_value(self, percentage: int):
        """Set the bar value (0-100)."""
        self.value = max(0, min(100, percentage))
        self.progress.set(self.value / 100)

        # Update color
        colors = StatBar.COLORS.get(self.bar_type, StatBar.COLORS["generic"])
        if self.value > 60:
            color = colors["high"]
        elif self.value > 30:
            color = colors["medium"]
        else:
            color = colors["low"]
        self.progress.configure(progress_color=color)

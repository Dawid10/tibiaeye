"""
GUI Theme - Shared color constants and theme values.

All colors are (light_mode, dark_mode) tuples.
CustomTkinter auto-selects the right value based on appearance mode.
For raw tkinter widgets (tag_configure), use resolve() to get the current value.
"""
import customtkinter as ctk


# --- Color tuples: (light, dark) ---

# Backgrounds
BG_APP = ("#f6f8fa", "#0d1117")
BG_SURFACE = ("#ffffff", "#161b22")
BG_ELEVATED = ("#eaeef2", "#1c2333")
BG_BOTTOM_BAR = ("#e1e4e8", "#010409")
BG_INPUT = ("#f0f3f6", "#21262d")

# Borders
BORDER = ("#d0d7de", "#21262d")
BORDER_MUTED = ("#d8dee4", "#30363d")

# Text
TEXT_PRIMARY = ("#1f2328", "#e6edf3")
TEXT_MUTED = ("#656d76", "#6e7681")
TEXT_FAINT = ("#8c959f", "#484f58")

# Accent (same in both modes for brand consistency)
ACCENT = "#4ecca3"
ACCENT_HOVER = "#3db892"

# Semantic
COLOR_SUCCESS = "#4ecca3"
COLOR_WARNING = "#d29922"
COLOR_ERROR = "#f85149"
COLOR_INFO = "#58a6ff"

# HP/MP
COLOR_HP_HIGH = "#4ecca3"
COLOR_HP_MED = "#d29922"
COLOR_HP_LOW = "#f85149"
COLOR_MP = "#58a6ff"

# System meters
CPU_THRESHOLD_HIGH = 70
CPU_THRESHOLD_MED = 30
MEM_THRESHOLD_HIGH_MB = 500
MEM_THRESHOLD_MED_MB = 200
MEM_MAX_SCALE_MB = 1024
METER_BAR_WIDTH = 48

# Layout
STATUS_BAR_HEIGHT = 28
STATUS_STRIP_HEIGHT = 48
SIDEBAR_WIDTH = 170

# Polling intervals (ms)
SYSTEM_INFO_POLL_MS = 3000


def resolve(color):
    """Resolve a color tuple to a single value based on current appearance mode.

    Use this for raw tkinter calls (tag_configure, etc.) that don't support CTk tuples.
    """
    if not isinstance(color, tuple):
        return color
    mode = ctk.get_appearance_mode()
    if mode == "Light":
        return color[0]
    return color[1]


def is_dark():
    return ctk.get_appearance_mode() == "Dark"

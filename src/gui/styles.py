"""
Shared UI builders for themed sections and form fields.

All tabs should use these helpers instead of hardcoding colors.
"""
import customtkinter as ctk

from .theme import (
    BG_SURFACE, BG_ELEVATED, BG_INPUT, BORDER,
    ACCENT, TEXT_PRIMARY, TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    resolve,
)


def create_section(parent, title):
    """Create a themed section frame with title header."""
    section = ctk.CTkFrame(parent, fg_color=BG_SURFACE, corner_radius=8, border_width=1, border_color=BORDER)

    ctk.CTkLabel(
        section, text=title.upper(),
        font=ctk.CTkFont(family="Courier", size=10),
        text_color=TEXT_MUTED, anchor="w",
    ).pack(fill="x", padx=12, pady=(10, 4))

    return section


def create_field_row(parent, label_text, widget_factory, label_width=120):
    """Create a labeled form row. widget_factory receives the row frame."""
    row = ctk.CTkFrame(parent, fg_color="transparent")
    row.pack(fill="x", pady=3)

    ctk.CTkLabel(
        row, text=label_text,
        font=ctk.CTkFont(size=12),
        text_color=TEXT_MUTED, width=label_width, anchor="w",
    ).pack(side="left")

    return widget_factory(row)


def create_entry(parent, textvariable, width=80, placeholder="", show=""):
    """Create a themed entry field."""
    kwargs = {
        "textvariable": textvariable,
        "width": width,
        "height": 28,
        "font": ctk.CTkFont(size=12),
        "fg_color": BG_INPUT,
        "border_color": BORDER,
        "border_width": 1,
    }
    if placeholder:
        kwargs["placeholder_text"] = placeholder
    if show:
        kwargs["show"] = show
    entry = ctk.CTkEntry(parent, **kwargs)
    return entry


def create_checkbox(parent, text, variable, command=None):
    """Create a themed checkbox."""
    return ctk.CTkCheckBox(
        parent, text=text, variable=variable,
        command=command,
        font=ctk.CTkFont(size=12),
        text_color=TEXT_PRIMARY,
        checkbox_width=18, checkbox_height=18,
        fg_color=ACCENT, hover_color=ACCENT,
        border_color=BORDER,
    )


def create_radio(parent, text, variable, value):
    """Create a themed radio button."""
    return ctk.CTkRadioButton(
        parent, text=text, variable=variable, value=value,
        font=ctk.CTkFont(size=12),
        text_color=TEXT_PRIMARY,
        radiobutton_width=16, radiobutton_height=16,
        fg_color=ACCENT, hover_color=ACCENT,
        border_color=BORDER,
    )


def create_button(parent, text, command, style="default", **kwargs):
    """Create a themed button. style: 'default', 'accent', 'danger', 'ghost'."""
    styles = {
        "default": {"fg_color": BG_ELEVATED, "hover_color": BG_INPUT, "text_color": TEXT_PRIMARY, "border_width": 1, "border_color": BORDER},
        "accent":  {"fg_color": ACCENT, "hover_color": "#3db892", "text_color": ("#0d1117", "#0d1117")},
        "danger":  {"fg_color": COLOR_ERROR, "hover_color": "#da3633", "text_color": "#ffffff"},
        "ghost":   {"fg_color": "transparent", "hover_color": BG_ELEVATED, "text_color": TEXT_MUTED, "border_width": 0},
    }
    base = styles.get(style, styles["default"])
    base.update(kwargs)
    # Defaults that can be overridden via kwargs
    base.setdefault("font", ctk.CTkFont(size=12))
    base.setdefault("height", 28)
    base.setdefault("corner_radius", 4)
    return ctk.CTkButton(
        parent, text=text, command=command,
        **base,
    )


def create_slider(parent, variable, from_=0, to=100, command=None, width=200):
    """Create a themed slider."""
    return ctk.CTkSlider(
        parent, variable=variable,
        from_=from_, to=to, width=width,
        button_color=ACCENT, button_hover_color="#3db892",
        progress_color=ACCENT,
        fg_color=BG_INPUT,
        command=command,
    )


def create_option_menu(parent, variable=None, values=None, command=None, width=160):
    """Create a themed dropdown."""
    return ctk.CTkOptionMenu(
        parent, variable=variable, values=values or [],
        command=command, width=width, height=28,
        font=ctk.CTkFont(size=12),
        fg_color=BG_INPUT, button_color=BG_ELEVATED,
        button_hover_color=ACCENT,
        dropdown_fg_color=BG_SURFACE,
    )


def create_stat_label(parent, text, bold=False):
    """Create a stat value label."""
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(family="Courier", size=12, weight="bold" if bold else "normal"),
        text_color=TEXT_PRIMARY, anchor="w",
    )


def create_description(parent, text):
    """Create a muted description label."""
    return ctk.CTkLabel(
        parent, text=text,
        font=ctk.CTkFont(size=11),
        text_color=TEXT_MUTED, anchor="w",
    )

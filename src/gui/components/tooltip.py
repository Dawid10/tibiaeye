"""
Tooltip Component - Hover tooltip for CustomTkinter widgets.
"""
import customtkinter as ctk


class Tooltip:
    """Shows a tooltip on hover over a widget."""

    def __init__(self, widget, text, delay=400):
        self.widget = widget
        self.text = text
        self.delay = delay
        self._toplevel = None
        self._after_id = None

        widget.bind("<Enter>", self._on_enter)
        widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        self._after_id = self.widget.after(self.delay, self._show)

    def _on_leave(self, event=None):
        if self._after_id:
            self.widget.after_cancel(self._after_id)
            self._after_id = None
        self._hide()

    def _show(self):
        if self._toplevel:
            return

        x = self.widget.winfo_rootx() + self.widget.winfo_width() // 2
        y = self.widget.winfo_rooty() + self.widget.winfo_height() + 4

        self._toplevel = ctk.CTkToplevel(self.widget)
        self._toplevel.wm_overrideredirect(True)
        self._toplevel.wm_geometry(f"+{x}+{y}")
        self._toplevel.attributes("-topmost", True)

        label = ctk.CTkLabel(
            self._toplevel,
            text=self.text,
            font=ctk.CTkFont(size=11),
            fg_color="#2b2b3d",
            corner_radius=6,
            padx=8,
            pady=4,
            wraplength=300,
        )
        label.pack()

    def _hide(self):
        if self._toplevel:
            self._toplevel.destroy()
            self._toplevel = None

    def update_text(self, text):
        self.text = text

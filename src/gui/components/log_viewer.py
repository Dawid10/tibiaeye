"""
Log Viewer Component - Real-time log display widget.
"""
import customtkinter as ctk
from datetime import datetime
from typing import Optional
import queue
import threading

from ..theme import (
    TEXT_PRIMARY, TEXT_MUTED, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    resolve,
)


class LogViewer(ctk.CTkFrame):
    """Widget for displaying real-time logs with auto-scroll."""

    def __init__(self, master, max_lines: int = 500, **kwargs):
        super().__init__(master, **kwargs)

        self.max_lines = max_lines
        self.auto_scroll = True
        self.log_queue = queue.Queue()

        self._setup_ui()
        self._start_queue_processor()

    def _setup_ui(self):
        """Setup the log viewer UI."""
        # Header with controls
        header = ctk.CTkFrame(self, fg_color="transparent")
        header.pack(fill="x", padx=5, pady=(5, 0))

        ctk.CTkLabel(
            header,
            text="Logs",
            font=ctk.CTkFont(size=14, weight="bold")
        ).pack(side="left")

        # Auto-scroll toggle
        self.auto_scroll_var = ctk.BooleanVar(value=True)
        ctk.CTkCheckBox(
            header,
            text="Auto-scroll",
            variable=self.auto_scroll_var,
            command=self._toggle_auto_scroll,
            height=20,
            checkbox_width=18,
            checkbox_height=18
        ).pack(side="right")

        # Clear button
        ctk.CTkButton(
            header,
            text="Clear",
            width=60,
            height=24,
            command=self.clear
        ).pack(side="right", padx=5)

        # Text area with scrollbar
        text_frame = ctk.CTkFrame(self, fg_color="transparent")
        text_frame.pack(fill="both", expand=True, padx=5, pady=5)

        self.textbox = ctk.CTkTextbox(
            text_frame,
            font=ctk.CTkFont(family="Courier", size=11),
            wrap="word",
            state="disabled"
        )
        self.textbox.pack(fill="both", expand=True)

        # Configure tags for log levels
        self._apply_tags()

    def _apply_tags(self):
        """Apply tag colors from theme."""
        self.textbox._textbox.tag_configure("info", foreground=resolve(TEXT_PRIMARY))
        self.textbox._textbox.tag_configure("warning", foreground=COLOR_WARNING)
        self.textbox._textbox.tag_configure("error", foreground=COLOR_ERROR)
        self.textbox._textbox.tag_configure("success", foreground=COLOR_SUCCESS)
        self.textbox._textbox.tag_configure("time", foreground=resolve(TEXT_MUTED))

    def apply_theme(self):
        """Re-apply tag colors after theme change."""
        self._apply_tags()

    def _toggle_auto_scroll(self):
        """Toggle auto-scroll behavior."""
        self.auto_scroll = self.auto_scroll_var.get()

    def _start_queue_processor(self):
        """Start processing log queue."""
        self._process_queue()

    def _process_queue(self):
        """Process pending log messages from queue."""
        try:
            while True:
                message, level = self.log_queue.get_nowait()
                self._append_log(message, level)
        except queue.Empty:
            pass
        # Schedule next check
        self.after(100, self._process_queue)

    def _append_log(self, message: str, level: str = "info"):
        """Append a log message to the textbox."""
        timestamp = datetime.now().strftime("[%H:%M:%S]")

        self.textbox.configure(state="normal")

        # Add timestamp
        self.textbox._textbox.insert("end", f"{timestamp} ", "time")

        # Add message with appropriate tag
        self.textbox._textbox.insert("end", f"{message}\n", level)

        # Trim if too many lines
        line_count = int(self.textbox._textbox.index("end-1c").split(".")[0])
        if line_count > self.max_lines:
            self.textbox._textbox.delete("1.0", f"{line_count - self.max_lines}.0")

        self.textbox.configure(state="disabled")

        # Auto-scroll to bottom
        if self.auto_scroll:
            self.textbox._textbox.see("end")

    def log(self, message: str, level: str = "info"):
        """
        Add a log message (thread-safe).

        Args:
            message: The log message
            level: Log level - 'info', 'warning', 'error', 'success'
        """
        self.log_queue.put((message, level))

    def info(self, message: str):
        """Log an info message."""
        self.log(message, "info")

    def warning(self, message: str):
        """Log a warning message."""
        self.log(message, "warning")

    def error(self, message: str):
        """Log an error message."""
        self.log(message, "error")

    def success(self, message: str):
        """Log a success message."""
        self.log(message, "success")

    def clear(self):
        """Clear all logs."""
        self.textbox.configure(state="normal")
        self.textbox._textbox.delete("1.0", "end")
        self.textbox.configure(state="disabled")

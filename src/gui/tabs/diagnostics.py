"""
Diagnostics Tab - Health dashboard for bot subsystems.
"""
import customtkinter as ctk
import time

from ..theme import (
    BG_APP, TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    resolve,
)
from ..styles import create_section


class DiagnosticsTab(ctk.CTkScrollableFrame):
    """Shows subsystem health, connections, recovery, and recent errors."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self._rows = {}
        self._conn_rows = {}
        self._recovery_rows = {}
        self._setup_ui()

    def _setup_ui(self):
        # Subsystem Health
        health_section = create_section(self, "Subsystem Health")
        health_section.pack(fill="x", padx=5, pady=(5, 3))

        self._health_frame = ctk.CTkFrame(health_section, fg_color="transparent")
        self._health_frame.pack(fill="x", padx=10, pady=(0, 8))

        for name in ("screenshot", "statusbar", "battlelist", "gamewindow", "radar", "skills", "chat"):
            self._add_health_row(name)

        # Connections
        conn_section = create_section(self, "Connections")
        conn_section.pack(fill="x", padx=5, pady=3)

        self._conn_frame = ctk.CTkFrame(conn_section, fg_color="transparent")
        self._conn_frame.pack(fill="x", padx=10, pady=(0, 8))

        for name in ("Arduino", "Telemetry"):
            self._add_conn_row(name)

        # Recovery Status
        recovery_section = create_section(self, "Recovery Status")
        recovery_section.pack(fill="x", padx=5, pady=3)

        self._recovery_frame = ctk.CTkFrame(recovery_section, fg_color="transparent")
        self._recovery_frame.pack(fill="x", padx=10, pady=(0, 8))

        for name in ("Stuck", "Reconnect", "Safe Mode"):
            self._add_recovery_row(name)

        # Recent Errors
        errors_section = create_section(self, "Recent Errors")
        errors_section.pack(fill="x", padx=5, pady=(3, 5))

        self._errors_textbox = ctk.CTkTextbox(
            errors_section,
            font=ctk.CTkFont(family="Courier", size=11),
            height=150,
            state="disabled",
            fg_color=BG_APP,
        )
        self._errors_textbox.pack(fill="x", padx=10, pady=(0, 8))

        self._errors_textbox._textbox.tag_configure("time", foreground=resolve(TEXT_MUTED))
        self._errors_textbox._textbox.tag_configure("error", foreground=resolve(COLOR_ERROR))
        self._errors_textbox._textbox.tag_configure("subsystem", foreground=resolve(COLOR_WARNING))

    def _add_health_row(self, name):
        row = ctk.CTkFrame(self._health_frame, fg_color="transparent")
        row.pack(fill="x", pady=1)

        dot = ctk.CTkLabel(row, text="\u25CF", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED, width=14)
        dot.pack(side="left")

        label = ctk.CTkLabel(row, text=name.capitalize(), font=ctk.CTkFont(size=12), width=120, anchor="w")
        label.pack(side="left", padx=(4, 0))

        status = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, anchor="w")
        status.pack(side="left", fill="x", expand=True)

        self._rows[name] = (dot, status)

    def _add_conn_row(self, name):
        row = ctk.CTkFrame(self._conn_frame, fg_color="transparent")
        row.pack(fill="x", pady=1)

        dot = ctk.CTkLabel(row, text="\u25CF", font=ctk.CTkFont(size=12), text_color=TEXT_MUTED, width=14)
        dot.pack(side="left")

        label = ctk.CTkLabel(row, text=name, font=ctk.CTkFont(size=12), width=120, anchor="w")
        label.pack(side="left", padx=(4, 0))

        status = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, anchor="w")
        status.pack(side="left", fill="x", expand=True)

        self._conn_rows[name] = (dot, status)

    def _add_recovery_row(self, name):
        row = ctk.CTkFrame(self._recovery_frame, fg_color="transparent")
        row.pack(fill="x", pady=1)

        label = ctk.CTkLabel(row, text=f"{name}:", font=ctk.CTkFont(size=12), width=120, anchor="w")
        label.pack(side="left")

        status = ctk.CTkLabel(row, text="--", font=ctk.CTkFont(size=11), text_color=TEXT_MUTED, anchor="w")
        status.pack(side="left", fill="x", expand=True)

        self._recovery_rows[name] = status

    def update_health(self, health_status):
        """Update subsystem health from BotHealth.get_status()."""
        for name, (dot, status_label) in self._rows.items():
            info = health_status.get(name, {})
            failures = info.get('failures', 0)
            healthy = info.get('healthy', True)

            if healthy:
                dot.configure(text_color=COLOR_SUCCESS)
                status_label.configure(text="OK", text_color=COLOR_SUCCESS)
                continue
            dot.configure(text_color=COLOR_ERROR)
            status_label.configure(
                text=f"{failures} failures",
                text_color=COLOR_ERROR,
            )

    def update_connections(self, arduino_connected, arduino_port, telemetry_connected):
        """Update connection indicators."""
        # Arduino
        dot, label = self._conn_rows["Arduino"]
        if arduino_connected:
            dot.configure(text_color=COLOR_SUCCESS)
            label.configure(text=f"Connected ({arduino_port})", text_color=COLOR_SUCCESS)
        elif arduino_port:
            dot.configure(text_color=COLOR_ERROR)
            label.configure(text="Disconnected", text_color=COLOR_ERROR)
        else:
            dot.configure(text_color=TEXT_MUTED)
            label.configure(text="Not configured", text_color=TEXT_MUTED)

        # Telemetry
        dot, label = self._conn_rows["Telemetry"]
        if telemetry_connected:
            dot.configure(text_color=COLOR_SUCCESS)
            label.configure(text="Connected (WS)", text_color=COLOR_SUCCESS)
        else:
            dot.configure(text_color=TEXT_MUTED)
            label.configure(text="Disconnected", text_color=TEXT_MUTED)

    def update_recovery(self, is_stuck, is_reconnecting, safe_mode):
        """Update recovery status indicators."""
        stuck_label = self._recovery_rows["Stuck"]
        if is_stuck:
            stuck_label.configure(text="Stuck detected!", text_color=COLOR_ERROR)
        else:
            stuck_label.configure(text="Not stuck", text_color=COLOR_SUCCESS)

        reconnect_label = self._recovery_rows["Reconnect"]
        if is_reconnecting:
            reconnect_label.configure(text="Reconnecting...", text_color=COLOR_WARNING)
        else:
            reconnect_label.configure(text="Connected", text_color=COLOR_SUCCESS)

        safe_label = self._recovery_rows["Safe Mode"]
        if safe_mode:
            safe_label.configure(text="Active", text_color=COLOR_ERROR)
        else:
            safe_label.configure(text="Inactive", text_color=COLOR_SUCCESS)

    def update_recent_errors(self, errors):
        """Update recent errors list from BotHealth.get_recent_errors()."""
        self._errors_textbox.configure(state="normal")
        self._errors_textbox._textbox.delete("1.0", "end")

        if not errors:
            self._errors_textbox._textbox.insert("end", "No recent errors", "time")
        else:
            for err in errors:
                ts = time.strftime("%H:%M:%S", time.localtime(err['time']))
                self._errors_textbox._textbox.insert("end", f"{ts}  ", "time")
                self._errors_textbox._textbox.insert("end", f"[{err['subsystem']}] ", "subsystem")
                self._errors_textbox._textbox.insert("end", f"{err['friendly']}\n", "error")

        self._errors_textbox.configure(state="disabled")

    def get_settings(self):
        return {}

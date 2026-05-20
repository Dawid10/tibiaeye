"""
Bot Control Tab - Main control panel for the bot.
"""
import customtkinter as ctk
from typing import Callable, Optional, Dict, Any

from ..components.log_viewer import LogViewer
from ..components.tooltip import Tooltip
from ..theme import (
    TEXT_MUTED, ACCENT, COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR, resolve,
)
from ..styles import (
    create_section, create_entry, create_checkbox, create_button,
    create_option_menu, create_description,
)


class BotControlTab(ctk.CTkScrollableFrame):
    """Main bot control tab with start/stop/pause buttons and module toggles."""

    def __init__(
        self,
        master,
        on_start: Optional[Callable] = None,
        on_pause: Optional[Callable] = None,
        on_stop: Optional[Callable] = None,
        on_overlay_toggle: Optional[Callable] = None,
        on_debug_overlay_toggle: Optional[Callable] = None,
        config_manager = None,
        **kwargs
    ):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.on_start = on_start
        self.on_pause = on_pause
        self.on_stop = on_stop
        self.on_overlay_toggle = on_overlay_toggle
        self.on_debug_overlay_toggle = on_debug_overlay_toggle
        self.config_manager = config_manager

        self._setup_ui()

    def _setup_ui(self):
        """Setup the bot control tab UI."""
        self._setup_controls_section()
        self._setup_modules_section()
        self._setup_server_save_section()
        self._setup_reconnect_section()
        self._setup_config_section()
        self._setup_logs_section()

    def _setup_controls_section(self):
        controls_section = create_section(self, "Controls")
        controls_section.pack(fill="x", padx=10, pady=(10, 5))

        buttons_frame = ctk.CTkFrame(controls_section, fg_color="transparent")
        buttons_frame.pack(fill="x", padx=10, pady=10)

        self.start_btn = create_button(
            buttons_frame, "START", self._on_start_click,
            style="accent", width=100, height=40,
            font=ctk.CTkFont(size=14, weight="bold"),
        )
        self.start_btn.pack(side="left", padx=(0, 10))

        self.pause_btn = ctk.CTkButton(
            buttons_frame,
            text="PAUSE",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=100,
            height=40,
            fg_color=COLOR_WARNING,
            hover_color="#b8860b",
            text_color="#1a1a1a",
            command=self._on_pause_click,
            state="disabled"
        )
        self.pause_btn.pack(side="left", padx=(0, 10))

        self.stop_btn = ctk.CTkButton(
            buttons_frame,
            text="STOP",
            font=ctk.CTkFont(size=14, weight="bold"),
            width=100,
            height=40,
            fg_color=COLOR_ERROR,
            hover_color="#da3633",
            command=self._on_stop_click,
            state="disabled"
        )
        self.stop_btn.pack(side="left")

        status_frame = ctk.CTkFrame(buttons_frame, fg_color="transparent")
        status_frame.pack(side="right", padx=(20, 0))

        ctk.CTkLabel(
            status_frame,
            text="Status:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left", padx=(0, 5))

        self.status_indicator = ctk.CTkLabel(
            status_frame,
            text="Stopped",
            font=ctk.CTkFont(size=12, weight="bold"),
            text_color=TEXT_MUTED
        )
        self.status_indicator.pack(side="left")

        self._setup_tick_rate(controls_section)
        self._setup_window_selector(controls_section)

    def _setup_tick_rate(self, parent):
        tick_frame = ctk.CTkFrame(parent, fg_color="transparent")
        tick_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            tick_frame,
            text="Tick Rate:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")

        self.tick_rate_var = ctk.StringVar(
            value=str(self.config_manager.get('general.tickRate', 0.100) if self.config_manager else 0.100)
        )
        self.tick_rate_entry = create_entry(tick_frame, self.tick_rate_var, width=80)
        self.tick_rate_entry.pack(side="left", padx=5)

        self.tick_rate_var.trace_add("write", self.on_tick_rate_change)

        create_description(tick_frame, "seconds").pack(side="left")
        Tooltip(self.tick_rate_entry, "Intervalo entre cada ciclo do bot (em segundos). Menor = mais rapido, mais CPU.")

    def _setup_window_selector(self, parent):
        window_frame = ctk.CTkFrame(parent, fg_color="transparent")
        window_frame.pack(fill="x", padx=10, pady=(0, 10))

        ctk.CTkLabel(
            window_frame,
            text="Window:",
            font=ctk.CTkFont(size=12)
        ).pack(side="left")

        self._window_options = self._build_window_options()
        saved_window = self.config_manager.get('general.window', '') if self.config_manager else ''
        initial_value = saved_window if saved_window in self._window_options else "Full Screen"

        self.window_var = ctk.StringVar(value=initial_value)
        self.window_menu = create_option_menu(
            window_frame,
            variable=self.window_var,
            values=list(self._window_options.keys()),
            width=200,
            command=self._on_window_change,
        )
        self.window_menu.pack(side="left", padx=5)

        create_button(
            window_frame, "Refresh", self._refresh_windows,
            style="default", width=60,
        ).pack(side="left")

    def _setup_modules_section(self):
        modules_section = create_section(self, "Active Modules")
        modules_section.pack(fill="x", padx=10, pady=5)

        modules_frame = ctk.CTkFrame(modules_section, fg_color="transparent")
        modules_frame.pack(fill="x", padx=10, pady=10)

        self.healing_var = ctk.BooleanVar(
            value=self.config_manager.get('general.enableHealing', True) if self.config_manager else True
        )
        create_checkbox(
            modules_frame, "Enable Healing", self.healing_var,
            command=self._on_module_change,
        ).pack(anchor="w", pady=2)

        self.cavebot_var = ctk.BooleanVar(
            value=self.config_manager.get('general.enableCavebot', True) if self.config_manager else True
        )
        create_checkbox(
            modules_frame, "Enable Cavebot", self.cavebot_var,
            command=self._on_module_change,
        ).pack(anchor="w", pady=2)

        self._setup_loot_row(modules_frame)
        self._setup_stuck_row(modules_frame)

        self.logging_var = ctk.BooleanVar(
            value=self.config_manager.get('general.enableLogging', False) if self.config_manager else False
        )
        create_checkbox(
            modules_frame, "Enable Session Logging", self.logging_var,
            command=self._on_module_change,
        ).pack(anchor="w", pady=2)

        self.overlay_var = ctk.BooleanVar(
            value=self.config_manager.get('general.showOverlay', False) if self.config_manager else False
        )
        create_checkbox(
            modules_frame, "Show Screen Overlay", self.overlay_var,
            command=self._on_overlay_change,
        ).pack(anchor="w", pady=2)

        self.debug_overlay_var = ctk.BooleanVar(
            value=self.config_manager.get('general.showDebugOverlay', False) if self.config_manager else False
        )
        create_checkbox(
            modules_frame, "Show Debug Overlay (Grid + Creatures)", self.debug_overlay_var,
            command=self._on_debug_overlay_change,
        ).pack(anchor="w", pady=2)

    def _setup_loot_row(self, parent):
        loot_frame = ctk.CTkFrame(parent, fg_color="transparent")
        loot_frame.pack(anchor="w", pady=2)

        self.loot_var = ctk.BooleanVar(
            value=self.config_manager.get('general.enableLoot', True) if self.config_manager else True
        )
        create_checkbox(
            loot_frame, "Enable Loot (Hotkey:", self.loot_var,
            command=self._on_module_change,
        ).pack(side="left")

        self.loot_hotkey_var = ctk.StringVar(
            value=self.config_manager.get('general.lootHotkey', 'g') if self.config_manager else 'g'
        )
        self.loot_hotkey_var.trace_add("write", self.on_loot_hotkey_change)

        create_entry(loot_frame, self.loot_hotkey_var, width=40).pack(side="left", padx=2)

        ctk.CTkLabel(loot_frame, text=")").pack(side="left")

    def _setup_stuck_row(self, parent):
        stuck_frame = ctk.CTkFrame(parent, fg_color="transparent")
        stuck_frame.pack(anchor="w", pady=2)

        self.stuck_alert_var = ctk.BooleanVar(
            value=self.config_manager.get('general.enableStuckAlert', True) if self.config_manager else True
        )
        create_checkbox(
            stuck_frame, "Enable Stuck Alert (Timeout:", self.stuck_alert_var,
            command=self._on_module_change,
        ).pack(side="left")

        self.stuck_timeout_var = ctk.StringVar(
            value=str(self.config_manager.get('general.stuckAlertTimeout', 120) if self.config_manager else 120)
        )
        self.stuck_timeout_var.trace_add("write", self.on_stuck_timeout_change)

        create_entry(stuck_frame, self.stuck_timeout_var, width=50).pack(side="left", padx=2)

        stuck_seconds_label = ctk.CTkLabel(stuck_frame, text="s)")
        stuck_seconds_label.pack(side="left")
        Tooltip(stuck_seconds_label, "Tempo em segundos parado na mesma posicao antes de ativar alerta sonoro.")

    def _setup_server_save_section(self):
        server_save_section = create_section(self, "Server Save")
        server_save_section.pack(fill="x", padx=10, pady=5)

        ss_frame = ctk.CTkFrame(server_save_section, fg_color="transparent")
        ss_frame.pack(fill="x", padx=10, pady=10)

        self.server_save_var = ctk.BooleanVar(
            value=self.config_manager.get('serverSave.enabled', True) if self.config_manager else True
        )
        create_checkbox(
            ss_frame, "Enable Server Save Handling", self.server_save_var,
            command=self._on_server_save_change,
        ).pack(anchor="w", pady=2)

        ss_time_frame = ctk.CTkFrame(ss_frame, fg_color="transparent")
        ss_time_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            ss_time_frame,
            text="Save Time (CET):",
            font=ctk.CTkFont(size=12),
            width=120,
            anchor="w"
        ).pack(side="left")

        self.server_save_time_var = ctk.StringVar(
            value=self.config_manager.get('serverSave.time', '10:00') if self.config_manager else '10:00'
        )
        self.server_save_time_var.trace_add("write", self._on_server_save_change_trace)
        create_entry(
            ss_time_frame, self.server_save_time_var,
            width=60, placeholder="HH:MM",
        ).pack(side="left", padx=5)

    def _setup_reconnect_section(self):
        reconnect_section = create_section(self, "Auto-Reconnect")
        reconnect_section.pack(fill="x", padx=10, pady=5)

        reconnect_frame = ctk.CTkFrame(reconnect_section, fg_color="transparent")
        reconnect_frame.pack(fill="x", padx=10, pady=10)

        self.reconnect_var = ctk.BooleanVar(
            value=self.config_manager.get('reconnect.enabled', False) if self.config_manager else False
        )
        create_checkbox(
            reconnect_frame, "Enable Auto-Reconnect", self.reconnect_var,
            command=self._on_reconnect_change,
        ).pack(anchor="w", pady=2)

        email_frame = ctk.CTkFrame(reconnect_frame, fg_color="transparent")
        email_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            email_frame,
            text="Email:",
            font=ctk.CTkFont(size=12),
            width=80,
            anchor="w"
        ).pack(side="left")

        self.reconnect_email_var = ctk.StringVar(
            value=self.config_manager.get('reconnect.email', '') if self.config_manager else ''
        )
        self.reconnect_email_var.trace_add("write", self._on_reconnect_change_trace)
        create_entry(email_frame, self.reconnect_email_var, width=200).pack(side="left", padx=5)

        password_frame = ctk.CTkFrame(reconnect_frame, fg_color="transparent")
        password_frame.pack(fill="x", pady=2)

        ctk.CTkLabel(
            password_frame,
            text="Password:",
            font=ctk.CTkFont(size=12),
            width=80,
            anchor="w"
        ).pack(side="left")

        self.reconnect_password_var = ctk.StringVar(
            value=self.config_manager.get('reconnect.password', '') if self.config_manager else ''
        )
        self.reconnect_password_var.trace_add("write", self._on_reconnect_change_trace)
        create_entry(
            password_frame, self.reconnect_password_var,
            width=200, show="*",
        ).pack(side="left", padx=5)

    def _setup_config_section(self):
        config_section = create_section(self, "Configuration")
        config_section.pack(fill="x", padx=10, pady=5)

        config_buttons = ctk.CTkFrame(config_section, fg_color="transparent")
        config_buttons.pack(fill="x", padx=10, pady=10)

        create_button(
            config_buttons, "Export", self._export_config,
            style="default", width=80,
        ).pack(side="left", padx=(0, 5))

        create_button(
            config_buttons, "Import", self._import_config,
            style="default", width=80,
        ).pack(side="left", padx=(0, 5))

        create_button(
            config_buttons, "Reset", self._reset_config,
            style="danger", width=80,
        ).pack(side="left")

    def _setup_logs_section(self):
        logs_section = create_section(self, "Real-time Logs")
        logs_section.pack(fill="x", padx=10, pady=(5, 10))

        self.log_viewer = LogViewer(logs_section, height=250)
        self.log_viewer.pack(fill="x", padx=5, pady=5)

    def _build_window_options(self) -> dict:
        """Build window options dict: display_name -> window_id (0 for Full Screen)."""
        options = {"Full Screen": 0}
        try:
            from ...utils.window import get_tibia_windows
            for win in get_tibia_windows():
                options[win["title"]] = win["id"]
        except Exception:
            pass
        return options

    def _refresh_windows(self):
        """Re-scan Tibia windows and update dropdown."""
        self._window_options = self._build_window_options()
        self.window_menu.configure(values=list(self._window_options.keys()))

    def _on_window_change(self, value: str):
        """Handle window selection change."""
        if not self.config_manager:
            return
        self.config_manager.set('general.window', value)
        self.config_manager.save()

    def get_selected_window_id(self) -> int:
        """Return the window ID for the currently selected window (0 = full screen)."""
        return self._window_options.get(self.window_var.get(), 0)

    def _on_start_click(self):
        """Handle start button click."""
        self.set_status("running")
        if self.on_start:
            self.on_start()

    def _on_pause_click(self):
        """Handle pause button click."""
        current_text = self.pause_btn.cget("text")
        if current_text == "PAUSE":
            self.set_status("paused")
        else:
            self.set_status("running")

        if self.on_pause:
            self.on_pause()

    def _on_stop_click(self):
        """Handle stop button click."""
        self.set_status("stopped")
        if self.on_stop:
            self.on_stop()

    def _on_module_change(self):
        """Handle module toggle changes."""
        if not self.config_manager:
            return
        self.config_manager.set('general.enableHealing', self.healing_var.get())
        self.config_manager.set('general.enableCavebot', self.cavebot_var.get())
        self.config_manager.set('general.enableLoot', self.loot_var.get())
        self.config_manager.set('general.lootHotkey', self.loot_hotkey_var.get())
        self.config_manager.set('general.enableLogging', self.logging_var.get())
        self.config_manager.set('general.enableStuckAlert', self.stuck_alert_var.get())
        try:
            timeout = int(self.stuck_timeout_var.get())
            self.config_manager.set('general.stuckAlertTimeout', timeout)
        except ValueError:
            pass
        try:
            tick_rate = float(self.tick_rate_var.get())
            self.config_manager.set('general.tickRate', tick_rate)
        except ValueError:
            pass
        self.config_manager.save()

    def _on_overlay_change(self):
        """Handle overlay toggle change."""
        enabled = self.overlay_var.get()
        if self.config_manager:
            self.config_manager.set('general.showOverlay', enabled)
            self.config_manager.save()
        if self.on_overlay_toggle:
            self.on_overlay_toggle(enabled)

    def _on_debug_overlay_change(self):
        """Handle debug overlay toggle change."""
        enabled = self.debug_overlay_var.get()
        if self.config_manager:
            self.config_manager.set('general.showDebugOverlay', enabled)
            self.config_manager.save()
        if self.on_debug_overlay_toggle:
            self.on_debug_overlay_toggle(enabled)

    def on_loot_hotkey_change(self, *args):
        """Handle loot hotkey change."""
        if not self.config_manager:
            return
        self.config_manager.set('general.lootHotkey', self.loot_hotkey_var.get())
        self.config_manager.save()

    def on_stuck_timeout_change(self, *args):
        """Handle stuck timeout change."""
        if not self.config_manager:
            return
        try:
            timeout = int(self.stuck_timeout_var.get())
            self.config_manager.set('general.stuckAlertTimeout', timeout)
        except ValueError:
            pass
        self.config_manager.save()

    def on_tick_rate_change(self, *args):
        """Handle tick rate change."""
        if not self.config_manager:
            return
        try:
            tick_rate = float(self.tick_rate_var.get())
            self.config_manager.set('general.tickRate', tick_rate)
        except ValueError:
            pass
        self.config_manager.save()

    def _on_server_save_change(self):
        """Handle server save config change."""
        if not self.config_manager:
            return
        self.config_manager.set('serverSave.enabled', self.server_save_var.get())
        self.config_manager.set('serverSave.time', self.server_save_time_var.get())
        self.config_manager.save()

    def _on_server_save_change_trace(self, *args):
        """Handle server save time field change (trace callback)."""
        self._on_server_save_change()

    def _on_reconnect_change(self):
        """Handle reconnect checkbox change."""
        self._save_reconnect_config()

    def _on_reconnect_change_trace(self, *args):
        """Handle reconnect field changes (trace callback)."""
        self._save_reconnect_config()

    def _save_reconnect_config(self):
        """Save reconnect config to config manager."""
        if not self.config_manager:
            return
        self.config_manager.set('reconnect.enabled', self.reconnect_var.get())
        self.config_manager.set('reconnect.email', self.reconnect_email_var.get())
        self.config_manager.set('reconnect.password', self.reconnect_password_var.get())
        self.config_manager.save()

    def set_status(self, status: str):
        """Set the bot status (running, paused, stopped)."""
        if status == "running":
            self.status_indicator.configure(text="Running", text_color=COLOR_SUCCESS)
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal", text="PAUSE")
            self.stop_btn.configure(state="normal")
            return
        if status == "paused":
            self.status_indicator.configure(text="Paused", text_color=COLOR_WARNING)
            self.start_btn.configure(state="disabled")
            self.pause_btn.configure(state="normal", text="RESUME")
            self.stop_btn.configure(state="normal")
            return
        self.status_indicator.configure(text="Stopped", text_color=TEXT_MUTED)
        self.start_btn.configure(state="normal")
        self.pause_btn.configure(state="disabled", text="PAUSE")
        self.stop_btn.configure(state="disabled")

    def get_settings(self) -> Dict[str, Any]:
        try:
            tick_rate = float(self.tick_rate_var.get())
        except (ValueError, TypeError):
            tick_rate = 0.100
        try:
            stuck_timeout = int(self.stuck_timeout_var.get())
        except (ValueError, TypeError):
            stuck_timeout = 120
        return {
            'tickRate': tick_rate,
            'enableHealing': self.healing_var.get(),
            'enableCavebot': self.cavebot_var.get(),
            'enableLoot': self.loot_var.get(),
            'lootHotkey': self.loot_hotkey_var.get(),
            'enableStuckAlert': self.stuck_alert_var.get(),
            'stuckAlertTimeout': stuck_timeout,
            'enableLogging': self.logging_var.get(),
            'window': self.window_var.get(),
            'windowId': self.get_selected_window_id(),
            'reconnect': {
                'enabled': self.reconnect_var.get(),
                'email': self.reconnect_email_var.get(),
                'password': self.reconnect_password_var.get(),
            },
            'serverSave': {
                'enabled': self.server_save_var.get(),
                'time': self.server_save_time_var.get(),
            },
        }

    def _export_config(self):
        """Export sanitized config to file."""
        if not self.config_manager:
            return
        from tkinter import filedialog
        path = filedialog.asksaveasfilename(
            defaultextension=".json",
            filetypes=[("JSON files", "*.json")],
            title="Export Configuration",
        )
        if not path:
            return
        from ..config_io import export_config
        ok, msg = export_config(self.config_manager.config, path)
        self.log(msg, "success" if ok else "error")

    def _import_config(self):
        """Import config from file."""
        if not self.config_manager:
            return
        from tkinter import filedialog
        path = filedialog.askopenfilename(
            filetypes=[("JSON files", "*.json")],
            title="Import Configuration",
        )
        if not path:
            return
        from ..config_io import import_config
        config, msg = import_config(path)
        if config is None:
            self.log(msg, "error")
            return
        self.config_manager.config = config
        self.config_manager.save()
        self.log(msg, "success")
        self.log("Restart the app to apply imported settings.", "warning")

    def _reset_config(self):
        """Reset config to defaults with confirmation."""
        if not self.config_manager:
            return
        import customtkinter as ctk
        dialog = ctk.CTkToplevel(self)
        dialog.title("Reset Configuration")
        dialog.geometry("350x150")
        dialog.transient(self.winfo_toplevel())
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(
            dialog, text="Reset all settings to defaults?",
            font=ctk.CTkFont(size=14),
        ).pack(pady=(20, 15))

        btn_frame = ctk.CTkFrame(dialog, fg_color="transparent")
        btn_frame.pack()

        def do_reset():
            self.config_manager.reset_to_defaults()
            self.log("Config reset to defaults. Restart app to apply.", "warning")
            dialog.destroy()

        create_button(btn_frame, "Reset", do_reset, style="danger", width=80).pack(side="left", padx=5)
        create_button(btn_frame, "Cancel", dialog.destroy, style="default", width=80).pack(side="left", padx=5)

    def log(self, message: str, level: str = "info"):
        """Add a log message."""
        self.log_viewer.log(message, level)

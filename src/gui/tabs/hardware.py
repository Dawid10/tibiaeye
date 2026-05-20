"""
Hardware Tab - Configure input/capture hardware mode.

Allows switching between software (pyautogui + mss), Arduino HID,
and full hardware (Arduino + capture card) modes.
"""
import customtkinter as ctk
from typing import Dict, Any

from ..theme import COLOR_SUCCESS, COLOR_ERROR, COLOR_WARNING, resolve
from ..styles import (
    create_section, create_entry, create_checkbox,
    create_button, create_radio, create_option_menu, create_description,
)


class HardwareTab(ctk.CTkScrollableFrame):
    """Hardware configuration tab."""

    def __init__(self, master, config_manager=None, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self.config_manager = config_manager

        self._setup_ui()
        self._load_config()

    def _setup_ui(self):
        """Setup the hardware tab UI."""
        # === Mode Selection ===
        mode_section = create_section(self, "Hardware Mode")
        mode_section.pack(fill="x", padx=10, pady=(10, 5))

        self.mode_var = ctk.StringVar(value="software")
        self.mode_var.trace_add("write", self._on_mode_change)

        modes = [
            ("Software (pyautogui + mss)", "software",
             "Default mode. Works on Mac. Detectable on Windows."),
            ("Capture Card (pyautogui + capture card)", "capture_card",
             "Software input + capture card for screenshots. For capture cards like Exbom 1080HD."),
            ("Arduino HID + mss", "arduino",
             "Undetectable input via Arduino Leonardo. Screenshots via mss."),
            ("Full Hardware (Arduino + Capture Card)", "full_hardware",
             "Undetectable input + capture. Required for anti-cheat on Windows."),
        ]

        for label, value, description in modes:
            frame = ctk.CTkFrame(mode_section, fg_color="transparent")
            frame.pack(fill="x", padx=10, pady=2)

            rb = create_radio(frame, label, self.mode_var, value)
            rb.pack(anchor="w")

            desc_label = create_description(frame, description)
            desc_label.pack(anchor="w", padx=24, pady=(0, 4))

        # === Arduino Settings ===
        arduino_section = create_section(self, "Arduino Settings")
        arduino_section.pack(fill="x", padx=10, pady=5)

        # Serial port
        port_frame = ctk.CTkFrame(arduino_section, fg_color="transparent")
        port_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(port_frame, text="Serial Port:").pack(side="left")

        self.port_var = ctk.StringVar(value="")
        self.port_var.trace_add("write", self._on_settings_change)

        self.port_entry = create_entry(
            port_frame,
            textvariable=self.port_var,
            placeholder="Auto-detect (leave empty)",
        )
        self.port_entry.configure(width=None)
        self.port_entry.pack(side="left", fill="x", expand=True, padx=10)

        self.detect_btn = create_button(
            port_frame, text="Detect", command=self._detect_arduino,
            width=70,
        )
        self.detect_btn.pack(side="right")

        # Port dropdown
        self.ports_dropdown = create_option_menu(
            arduino_section, values=["Scanning..."],
            command=self._on_port_selected,
        )
        self.ports_dropdown.pack(fill="x", padx=10, pady=(0, 5))
        self.ports_dropdown.set("Available ports...")

        # === Capture Card Settings ===
        capture_section = create_section(self, "Capture Card Settings")
        capture_section.pack(fill="x", padx=10, pady=5)

        device_frame = ctk.CTkFrame(capture_section, fg_color="transparent")
        device_frame.pack(fill="x", padx=10, pady=5)

        ctk.CTkLabel(device_frame, text="Device Index:").pack(side="left")

        self.device_var = ctk.StringVar(value="0")
        self.device_var.trace_add("write", self._on_settings_change)

        self.device_entry = create_entry(
            device_frame,
            textvariable=self.device_var,
            width=60,
        )
        self.device_entry.pack(side="left", padx=10)

        desc = create_description(device_frame, "(0 = first capture device)")
        desc.pack(side="left")

        # === Debug ===
        debug_frame = ctk.CTkFrame(capture_section, fg_color="transparent")
        debug_frame.pack(fill="x", padx=10, pady=(0, 8))

        self.debug_var = ctk.BooleanVar(value=False)
        self.debug_check = create_checkbox(
            debug_frame, text="Debug: log every Arduino command",
            variable=self.debug_var,
        )
        self.debug_check.pack(anchor="w")

        # === Test Connection ===
        test_section = ctk.CTkFrame(self, fg_color="transparent")
        test_section.pack(fill="x", padx=10, pady=10)

        self.test_btn = create_button(
            test_section, text="Test Connection",
            command=self._test_connection,
            style="accent",
        )
        self.test_btn.pack(side="left")

        self.status_label = ctk.CTkLabel(
            test_section, text="",
            font=ctk.CTkFont(size=12)
        )
        self.status_label.pack(side="left", padx=10)

    def _load_config(self):
        """Load saved hardware config."""
        if not self.config_manager:
            return
        self.mode_var.set(self.config_manager.get('hardware.mode', 'software'))
        self.port_var.set(self.config_manager.get('hardware.arduinoPort', ''))
        self.device_var.set(str(self.config_manager.get('hardware.captureDevice', 0)))

    def _on_settings_change(self, *args):
        """Save settings when changed."""
        if not self.config_manager:
            return
        self.config_manager.set('hardware.arduinoPort', self.port_var.get())
        try:
            self.config_manager.set('hardware.captureDevice', int(self.device_var.get()))
        except ValueError:
            pass
        self.config_manager.save()

    def _on_mode_change(self, *args):
        """Save mode when changed."""
        if self.config_manager:
            self.config_manager.set('hardware.mode', self.mode_var.get())
            self.config_manager.save()

    def _on_port_selected(self, port_str):
        """Set port from dropdown selection."""
        if port_str and port_str != "Available ports..." and port_str != "Scanning..." and port_str != "No ports found":
            # Extract device path (first part before " - ")
            device = port_str.split(" - ")[0].strip()
            self.port_var.set(device)

    def _detect_arduino(self):
        """Scan serial ports and populate dropdown."""
        try:
            import serial.tools.list_ports
            ports = list(serial.tools.list_ports.comports())

            if not ports:
                self.ports_dropdown.configure(values=["No ports found"])
                self.ports_dropdown.set("No ports found")
                return

            port_strings = []
            auto_port = None
            for p in ports:
                desc = f"{p.device} - {p.description}"
                port_strings.append(desc)
                # Auto-select Arduino Leonardo
                if p.vid == 0x2341 or "arduino" in (p.description or "").lower():
                    auto_port = p.device

            self.ports_dropdown.configure(values=port_strings)
            self.ports_dropdown.set(port_strings[0])

            if auto_port:
                self.port_var.set(auto_port)
                self.status_label.configure(
                    text=f"Arduino detected: {auto_port}",
                    text_color=COLOR_SUCCESS
                )

        except ImportError:
            self.status_label.configure(
                text="pyserial not installed (pip install pyserial)",
                text_color=COLOR_ERROR
            )

    def _test_connection(self):
        """Test connection to selected hardware."""
        mode = self.mode_var.get()

        if mode == "software":
            self.status_label.configure(text="Software mode - no hardware needed", text_color=COLOR_SUCCESS)
            return

        port = self.port_var.get()
        if not port and mode in ("arduino", "full_hardware"):
            self.status_label.configure(text="Enter a serial port or click Detect", text_color=COLOR_ERROR)
            return

        self.status_label.configure(text="Testing...", text_color=COLOR_WARNING)
        self.update()

        # Test Arduino
        if mode in ("arduino", "full_hardware"):
            from src.hardware import arduino
            if arduino.connect(port):
                arduino.disconnect()
                self.status_label.configure(text="Arduino OK!", text_color=COLOR_SUCCESS)
            else:
                self.status_label.configure(text="Arduino connection failed", text_color=COLOR_ERROR)
                return

        # Test capture card
        if mode in ("full_hardware", "capture_card"):
            try:
                device_idx = int(self.device_var.get())
            except ValueError:
                device_idx = 0

            from src.hardware import capture
            if capture.connect(device_idx):
                frame = capture.capture_frame()
                capture.disconnect()
                if frame is not None:
                    h, w = frame.shape[:2]
                    prefix = "Arduino + Capture" if mode == "full_hardware" else "Capture Card"
                    self.status_label.configure(
                        text=f"{prefix} OK! ({w}x{h})",
                        text_color=COLOR_SUCCESS
                    )
                else:
                    self.status_label.configure(text="Capture card opened but no frame", text_color=COLOR_ERROR)
            else:
                self.status_label.configure(text="Capture card failed", text_color=COLOR_ERROR)

    def get_settings(self) -> Dict[str, Any]:
        """Return current hardware settings."""
        try:
            device = int(self.device_var.get())
        except ValueError:
            device = 0

        return {
            'mode': self.mode_var.get(),
            'arduinoPort': self.port_var.get(),
            'captureDevice': device,
            'debug': self.debug_var.get(),
        }

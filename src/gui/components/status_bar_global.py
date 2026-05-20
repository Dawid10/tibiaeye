"""
Global Status Bar - Bottom bar with subsystem indicators and CPU/Memory meters.
"""
import os
import customtkinter as ctk

from ..theme import (
    BG_BOTTOM_BAR, BG_INPUT, BORDER, TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    CPU_THRESHOLD_HIGH, CPU_THRESHOLD_MED,
    MEM_THRESHOLD_HIGH_MB, MEM_THRESHOLD_MED_MB, MEM_MAX_SCALE_MB,
    METER_BAR_WIDTH, SYSTEM_INFO_POLL_MS, STATUS_BAR_HEIGHT,
)


COLOR_GRAY = ("#b1bac4", "#484f58")

ENV_COLORS = {
    "prod": {"bg": "#da3633", "text": "#ffffff"},
    "local": {"bg": ("#e1e4e8", "#1c2333"), "text": ("#656d76", "#6e7681")},
}

try:
    import psutil
    HAS_PSUTIL = True
except ImportError:
    HAS_PSUTIL = False


def _threshold_color(value, high_threshold, med_threshold):
    if value > high_threshold:
        return COLOR_ERROR
    if value > med_threshold:
        return COLOR_WARNING
    return COLOR_SUCCESS


class StatusBarGlobal(ctk.CTkFrame):
    """Bottom bar: subsystem dots + CPU/memory meters + env badge."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color=BG_BOTTOM_BAR, height=STATUS_BAR_HEIGHT, **kwargs)
        self.pack_propagate(False)

        self._indicators = {}
        self._setup_ui()

        if HAS_PSUTIL:
            psutil.cpu_percent(percpu=False)  # prime - first call always returns 0
            self.after(2000, self._poll_system_info)

    def _setup_ui(self):
        inner = ctk.CTkFrame(self, fg_color="transparent")
        inner.pack(fill="both", expand=True, padx=10, pady=3)

        # Left: subsystem indicators
        left = ctk.CTkFrame(inner, fg_color="transparent")
        left.pack(side="left")

        for name in ("Screen", "Arduino", "Telemetry", "Bot"):
            frame = ctk.CTkFrame(left, fg_color="transparent")
            frame.pack(side="left", padx=(0, 12))

            dot = ctk.CTkLabel(
                frame, text="\u25CF", width=10,
                font=ctk.CTkFont(size=8), text_color=COLOR_GRAY,
            )
            dot.pack(side="left")

            ctk.CTkLabel(
                frame, text=name,
                font=ctk.CTkFont(family="Courier", size=9), text_color=TEXT_MUTED,
            ).pack(side="left", padx=(2, 0))

            self._indicators[name] = dot

        # Right: env badge + system meters
        right = ctk.CTkFrame(inner, fg_color="transparent")
        right.pack(side="right")

        self._add_env_badge(right)

        if HAS_PSUTIL:
            self._mem_bar, self._mem_label = self._create_meter(right, "MEM", 12)
            self._cpu_bar, self._cpu_label = self._create_meter(right, "CPU", 0)

    def _create_meter(self, parent, label_text, right_pad):
        frame = ctk.CTkFrame(parent, fg_color="transparent")
        frame.pack(side="right", padx=(right_pad, 8))

        ctk.CTkLabel(
            frame, text=label_text,
            font=ctk.CTkFont(family="Courier", size=9),
            text_color=TEXT_MUTED, width=28,
        ).pack(side="left")

        bar_bg = ctk.CTkFrame(frame, fg_color=BG_INPUT, width=METER_BAR_WIDTH, height=8, corner_radius=2)
        bar_bg.pack(side="left", padx=(2, 0))
        bar_bg.pack_propagate(False)

        bar = ctk.CTkFrame(bar_bg, fg_color=COLOR_SUCCESS, width=1, height=8, corner_radius=2)
        bar.place(x=0, y=0, relheight=1.0)

        label = ctk.CTkLabel(
            frame, text="0%",
            font=ctk.CTkFont(family="Courier", size=9),
            text_color=TEXT_MUTED, width=40,
        )
        label.pack(side="left", padx=(4, 0))

        return bar, label

    def _poll_system_info(self):
        try:
            cpu_percent = psutil.cpu_percent(percpu=False)
            mem_mb = psutil.Process().memory_info().rss / (1024 * 1024)

            cpu_width = max(1, int(METER_BAR_WIDTH * min(cpu_percent, 100) / 100))
            cpu_color = _threshold_color(cpu_percent, CPU_THRESHOLD_HIGH, CPU_THRESHOLD_MED)
            self._cpu_bar.configure(width=cpu_width, fg_color=cpu_color)
            self._cpu_bar.place(x=0, y=0, relheight=1.0)
            self._cpu_label.configure(text=f"{int(cpu_percent)}%")

            mem_ratio = min(mem_mb / MEM_MAX_SCALE_MB, 1.0)
            mem_width = max(1, int(METER_BAR_WIDTH * mem_ratio))
            mem_color = _threshold_color(mem_mb, MEM_THRESHOLD_HIGH_MB, MEM_THRESHOLD_MED_MB)
            self._mem_bar.configure(width=mem_width, fg_color=mem_color)
            self._mem_bar.place(x=0, y=0, relheight=1.0)
            self._mem_label.configure(text=f"{int(mem_mb)}MB")
        except Exception:
            pass

        self.after(SYSTEM_INFO_POLL_MS, self._poll_system_info)

    def set_status(self, name, color):
        color_map = {
            "green": COLOR_SUCCESS,
            "yellow": COLOR_WARNING,
            "red": COLOR_ERROR,
            "gray": COLOR_GRAY,
        }
        dot = self._indicators.get(name)
        if dot:
            dot.configure(text_color=color_map.get(color, COLOR_GRAY))

    def _add_env_badge(self, parent):
        env = os.getenv("TIBIAEYE_ENV", "local")
        colors = ENV_COLORS.get(env, ENV_COLORS["local"])
        ctk.CTkLabel(
            parent,
            text=env.upper(),
            font=ctk.CTkFont(family="Courier", size=8, weight="bold"),
            text_color=colors["text"],
            fg_color=colors["bg"],
            corner_radius=3, width=40, height=18,
        ).pack(side="right")

    def update_from_state(self, screen_ok, arduino_status, telemetry_status, bot_status):
        self.set_status("Screen", "green" if screen_ok else "red")
        self.set_status("Arduino", arduino_status)
        self.set_status("Telemetry", telemetry_status)
        self.set_status("Bot", bot_status)

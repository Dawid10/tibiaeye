"""
Alert System - Sound alerts for critical game events.

Uses system sounds on macOS/Linux/Windows for reliable audio alerts.
"""
import subprocess
import sys
import time
import threading
from typing import Optional


class AlertSystem:
    """
    Sound alert system with cooldown to prevent spam.

    Uses platform-specific methods for reliable sound playback.
    Supports looping alerts for critical situations like being stuck.
    """

    # Platform-specific sound commands
    SOUND_COMMANDS = {
        'darwin': {  # macOS
            'alert': 'afplay /System/Library/Sounds/Glass.aiff',
            'warning': 'afplay /System/Library/Sounds/Sosumi.aiff',
            'critical': 'afplay /System/Library/Sounds/Basso.aiff',
        },
        'linux': {
            'alert': 'paplay /usr/share/sounds/freedesktop/stereo/bell.oga 2>/dev/null || aplay /usr/share/sounds/alsa/Front_Center.wav 2>/dev/null || echo -e "\\a"',
            'warning': 'paplay /usr/share/sounds/freedesktop/stereo/dialog-warning.oga 2>/dev/null || echo -e "\\a"',
            'critical': 'paplay /usr/share/sounds/freedesktop/stereo/dialog-error.oga 2>/dev/null || echo -e "\\a"',
        },
        'win32': {  # Windows
            'alert': 'powershell -c "[console]::beep(1000,500)"',
            'warning': 'powershell -c "[console]::beep(800,800)"',
            'critical': 'powershell -c "[console]::beep(500,1000)"',
        },
    }

    def __init__(self, cooldown: float = 30.0):
        """
        Initialize alert system.

        Args:
            cooldown: Minimum time between alerts of the same type (seconds)
        """
        self.cooldown = cooldown
        self._last_alert_times: dict[str, float] = {}
        self._platform = sys.platform

        # Loop alert control
        self._loop_active = False
        self._loop_thread: Optional[threading.Thread] = None
        self._loop_interval = 0.5  # Seconds between loop sounds

    def _get_sound_command(self, alert_type: str) -> Optional[str]:
        """Get platform-specific sound command."""
        platform_sounds = self.SOUND_COMMANDS.get(self._platform, {})
        return platform_sounds.get(alert_type)

    def _play_sound_sync(self, command: str) -> None:
        """Play sound synchronously (blocking)."""
        try:
            subprocess.run(command, shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        except Exception:
            pass

    def _play_sound_async(self, command: str) -> None:
        """Play sound in background thread to not block game loop."""
        thread = threading.Thread(target=self._play_sound_sync, args=(command,), daemon=True)
        thread.start()

    def _loop_sound(self, command: str) -> None:
        """Loop sound until stopped."""
        while self._loop_active:
            self._play_sound_sync(command)
            # Small sleep between sounds
            time.sleep(self._loop_interval)

    def start_loop_alert(self, alert_type: str = 'critical', message: Optional[str] = None) -> bool:
        """
        Start playing an alert sound in a loop.

        Args:
            alert_type: Type of alert ('alert', 'warning', 'critical')
            message: Optional message to print once

        Returns:
            True if loop started, False if already looping
        """
        if self._loop_active:
            return False  # Already looping

        # Print message if provided
        if message:
            print(f"[ALERT LOOP] {message}")

        # Get sound command
        command = self._get_sound_command(alert_type)
        if not command:
            return False

        # Start loop thread
        self._loop_active = True
        self._loop_thread = threading.Thread(target=self._loop_sound, args=(command,), daemon=True)
        self._loop_thread.start()
        return True

    def stop_loop_alert(self) -> None:
        """Stop the looping alert sound."""
        if self._loop_active:
            self._loop_active = False
            print("[ALERT] Loop stopped - character moved!")

    def is_looping(self) -> bool:
        """Check if alert is currently looping."""
        return self._loop_active

    def alert(self, alert_type: str = 'alert', message: Optional[str] = None, force: bool = False) -> bool:
        """
        Play an alert sound once.

        Args:
            alert_type: Type of alert ('alert', 'warning', 'critical')
            message: Optional message to print
            force: If True, ignore cooldown

        Returns:
            True if alert was played, False if on cooldown
        """
        now = time.time()

        # Check cooldown
        if not force:
            last_time = self._last_alert_times.get(alert_type, 0)
            if now - last_time < self.cooldown:
                return False

        # Update last alert time
        self._last_alert_times[alert_type] = now

        # Print message if provided
        if message:
            print(f"[ALERT] {message}")

        # Play sound
        command = self._get_sound_command(alert_type)
        if command:
            self._play_sound_async(command)
            return True

        # Fallback: terminal bell
        print('\a', end='', flush=True)
        return True

    def stuck_alert(self, duration_seconds: float) -> bool:
        """
        Alert for stuck character - starts looping sound.

        Args:
            duration_seconds: How long the character has been stuck

        Returns:
            True if loop started, False if already looping
        """
        minutes = duration_seconds / 60
        return self.start_loop_alert(
            'critical',
            f"CHARACTER STUCK! No movement for {minutes:.1f} minutes! (sound will loop until movement)"
        )

    def stop_stuck_alert(self) -> None:
        """Stop the stuck alert loop."""
        self.stop_loop_alert()

    def low_supplies_alert(self, item: str) -> bool:
        """Alert for low supplies."""
        return self.alert(
            'warning',
            f"LOW SUPPLIES: {item}"
        )

    def death_alert(self) -> bool:
        """Alert for character death."""
        return self.alert(
            'critical',
            "CHARACTER DIED!",
            force=True  # Always play death alert
        )


# Global alert system instance
_alert_system: Optional[AlertSystem] = None


def get_alert_system() -> AlertSystem:
    """Get or create global alert system."""
    global _alert_system
    if _alert_system is None:
        _alert_system = AlertSystem()
    return _alert_system


def play_stuck_alert(duration_seconds: float) -> bool:
    """Play stuck character alert."""
    return get_alert_system().stuck_alert(duration_seconds)


def play_alert(alert_type: str = 'alert', message: Optional[str] = None) -> bool:
    """Play generic alert."""
    return get_alert_system().alert(alert_type, message)

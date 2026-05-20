"""Tests for error message mapping."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.utils.error_messages import friendly_error


class TestFriendlyError:
    def test_screenshot_none(self):
        """Should map screenshot errors to friendly message."""
        msg, sug = friendly_error("Screenshot returned None")
        assert "Captura de tela" in msg
        assert sug is not None

    def test_battlelist_not_found(self):
        """Should map battlelist errors to friendly message."""
        msg, sug = friendly_error("BattleList not found in screenshot")
        assert "Battle List" in msg
        assert sug is not None

    def test_arduino_connection(self):
        """Should map arduino connection errors to friendly message."""
        msg, sug = friendly_error("Arduino connection error: could not open port /dev/cu.usbmodem1101")
        assert "Arduino" in msg
        assert "USB" in sug

    def test_radar_failed(self):
        """Should map radar errors to friendly message."""
        msg, sug = friendly_error("Radar failed: could not read coordinate from minimap")
        assert "Radar" in msg
        assert "zoom" in sug

    def test_serial_write_failed(self):
        """Should map serial write errors to friendly message."""
        msg, sug = friendly_error("Serial write failed: device not responding")
        assert "comando" in msg
        assert "USB" in sug

    def test_nonetype_attribute_error(self):
        """Should map NoneType attribute errors to friendly message."""
        msg, sug = friendly_error("'NoneType' has no attribute 'shape'")
        assert "interno" in msg
        assert sug is not None

    def test_websocket_closed(self):
        """Should map websocket errors to friendly message."""
        msg, sug = friendly_error("WebSocket closed unexpectedly")
        assert "telemetria" in msg
        assert sug is not None

    def test_unknown_error_passes_through(self):
        """Should pass through unknown errors unchanged."""
        original = "Some completely unknown error XYZ123"
        msg, sug = friendly_error(original)
        assert msg == original
        assert sug is None

    def test_case_insensitive(self):
        """Should match patterns case-insensitively."""
        msg, _ = friendly_error("SCREENSHOT RETURNED NONE")
        assert "Captura de tela" in msg

    def test_license_expired(self):
        """Should map license expired errors."""
        msg, sug = friendly_error("License expired on 2025-01-01")
        assert "Licenca" in msg
        assert "tibiaeye.com" in sug

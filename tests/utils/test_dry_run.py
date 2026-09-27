import pyautogui
import pytest

import src.utils.input as input_module
from src.utils import dry_run


@pytest.fixture
def restore_input(monkeypatch):
    """Register the real input functions so monkeypatch restores them after the test."""
    for name in dry_run.DIRECT_INPUT_FUNCTIONS:
        monkeypatch.setattr(pyautogui, name, getattr(pyautogui, name))
    for name in ('_original_click', '_original_moveTo', '_original_rightClick'):
        monkeypatch.setattr(input_module, name, getattr(input_module, name))
    monkeypatch.setattr(dry_run, '_enabled', False)


class TestDryRun:
    def test_press_is_logged_not_sent(self, restore_input, capsys):
        """pyautogui.press prints the call instead of pressing."""
        dry_run.enable_dry_run()
        pyautogui.press('3')
        assert "[DRY RUN] press('3')" in capsys.readouterr().out
        assert dry_run.is_dry_run()

    def test_click_keeps_screen_offset(self, restore_input, monkeypatch, capsys):
        """Clicks go through the offset wrapper and log absolute coordinates."""
        monkeypatch.setattr(input_module, '_cached_offset', (100, 50))
        dry_run.enable_dry_run()
        pyautogui.click(10, 20)
        assert "[DRY RUN] click(110, 70)" in capsys.readouterr().out

    def test_hotkey_with_kwargs_is_logged(self, restore_input, capsys):
        """Keyword arguments appear in the log line."""
        dry_run.enable_dry_run()
        pyautogui.hotkey('ctrl', 'q', interval=0.1)
        assert "[DRY RUN] hotkey('ctrl', 'q', interval=0.1)" in capsys.readouterr().out

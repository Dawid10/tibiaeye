"""
Click guard: clicks outside the Tibia window (Dock, menu bar, other apps) steal the focus,
so every key press after them goes to the wrong app. They must be refused, not sent.
"""
from unittest.mock import patch

from src.core.screen import Region

TIBIA = [{'title': 'Tibia - Test', 'owner': 'Tibia', 'id': 1,
          'region': Region(x=0, y=30, width=1920, height=973)}]


def _fresh_guard(windows):
    import src.utils.input as input_module
    input_module._tibia_regions_cache = ([], 0.0)
    return patch('src.utils.window.get_tibia_windows', return_value=windows)


def test_click_inside_tibia_is_sent():
    import src.utils.input as input_module
    with _fresh_guard(TIBIA), patch.object(input_module, '_original_click') as click:
        input_module._offset_click(1800, 120)
    click.assert_called_once()


def test_click_on_menu_bar_or_dock_is_refused(capsys):
    import src.utils.input as input_module
    with _fresh_guard(TIBIA), patch.object(input_module, '_original_click') as click:
        input_module._offset_click(1800, 10)
        input_module._offset_click(900, 1060)
    click.assert_not_called()
    assert capsys.readouterr().out.count('[Input] Refused click') == 2


def test_right_click_outside_is_refused():
    import src.utils.input as input_module
    with _fresh_guard(TIBIA), patch.object(input_module, '_original_rightClick') as right_click:
        input_module._offset_rightClick(900, 1060)
    right_click.assert_not_called()


def test_no_tibia_window_found_lets_clicks_through():
    """Capture card PC / no Quartz: the guard can't tell, so it must not block the bot."""
    import src.utils.input as input_module
    with _fresh_guard([]), patch.object(input_module, '_original_click') as click:
        input_module._offset_click(900, 1060)
    click.assert_called_once()


def test_alt_click_releases_option_even_when_click_fails():
    import pytest
    import src.utils.input as input_module
    with patch('pyautogui.keyDown'), patch('pyautogui.keyUp') as key_up, \
            patch('pyautogui.click', side_effect=RuntimeError('boom')):
        with pytest.raises(RuntimeError):
            input_module.alt_click(10, 10)
    key_up.assert_called_once_with('alt')

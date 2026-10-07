"""Focus watchdog: log once when Tibia loses the input, with the bot's last inputs."""
from unittest.mock import patch


def test_logs_once_per_episode_with_recent_inputs(capsys):
    from src.utils.focus_watch import FocusWatch, remember_input
    watch = FocusWatch()
    remember_input('press d')

    watch._report("the Dock has keyboard focus (on 'Discord')", 100.0)
    watch._report("the Dock has keyboard focus (on 'Discord')", 100.5)
    watch._report(None, 102.0)

    out = capsys.readouterr().out
    assert out.count('TIBIA LOST THE INPUT') == 1
    assert 'press d' in out
    assert 'again after 2.0s' in out


def test_bot_key_presses_are_recorded():
    import pyautogui
    import src.utils.input  # noqa: F401 - installs the recording wrappers
    from src.utils import focus_watch
    with patch.object(focus_watch, '_recent_inputs', focus_watch.deque(maxlen=8)):
        with patch('pyautogui._pyautogui_osx._keyDown'), patch('pyautogui._pyautogui_osx._keyUp'):
            pyautogui.press('w')
        assert any(action == 'press w' for _, action, _ in focus_watch._recent_inputs)


def test_watchdog_turns_itself_off_without_appkit(capsys):
    from src.utils.focus_watch import FocusWatch
    watch = FocusWatch()
    with patch('src.utils.focus_watch.find_focus_problem', side_effect=ImportError('no AppKit')):
        watch.check()
        watch._last_check = 0
        watch.check()
    assert capsys.readouterr().out.count('Watchdog off') == 1

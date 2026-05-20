"""
Tests for loot telemetry integration via chat middleware.

Ensures:
1. Chat middleware sends loot telemetry when new messages are detected
2. Item values are looked up and sent with telemetry
3. No telemetry calls when no loot messages or no telemetry client
4. Cavebot on_before_restart/on_complete do NOT send loot (middleware handles it)
"""
from unittest.mock import Mock, patch, MagicMock

from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask


def create_loot_context(loot_messages=None, telemetry=None):
    """Create minimal context for loot telemetry tests."""
    return {
        'cavebot': {
            'isAttackingSomeCreature': False,
            'targetCreature': None,
            'closestCreature': None,
            'waypoints': {
                'items': [],
                'currentIndex': 0,
                'indexBeforeCombat': None,
            },
        },
        'radar': {'coordinate': (32000, 32000, 7)},
        'loot': {'enabled': False},
        'chat': {'lootMessages': loot_messages or []},
        'telemetry': telemetry,
        'gui_logger': None,
    }


class TestChatMiddlewareLootTelemetry:
    """Tests for loot telemetry sent from chat middleware."""

    def _make_gameloop(self):
        """Create GameLoop with mocked dependencies."""
        with patch('src.gameplay.gameloop.TelemetryClient'):
            with patch('src.gameplay.gameloop.LicenseValidator', None):
                from src.gameplay.gameloop import GameLoop
                from src.gameplay.bot_health import BotHealth
                loop = GameLoop.__new__(GameLoop)
                loop._chat_repo = None
                loop._bot_health = BotHealth()
                return loop

    def test_sends_loot_telemetry_for_each_item(self):
        """Should call track_loot for each item in all loot messages."""
        loop = self._make_gameloop()
        telemetry = MagicMock()
        mock_chat_repo = MagicMock()
        mock_chat_repo.get_new_loot_messages.return_value = [
            {
                'creature': 'demon',
                'items': [
                    {'name': 'demon horn', 'quantity': 1},
                    {'name': 'gold coins', 'quantity': 100},
                ],
            }
        ]
        loop._chat_repo = mock_chat_repo

        context = {
            'screenshot': Mock(),
            'chat': {'lootMessages': []},
            'telemetry': telemetry,
        }

        loop._chat_middleware(context)

        assert telemetry.track_loot.call_count == 2
        telemetry.track_loot.assert_any_call(item_name='demon horn', quantity=1, value=1000)
        telemetry.track_loot.assert_any_call(item_name='gold coins', quantity=100, value=1)

    def test_sends_all_messages_not_just_last(self):
        """Should send loot for ALL messages, not just the most recent."""
        loop = self._make_gameloop()
        telemetry = MagicMock()
        mock_chat_repo = MagicMock()
        mock_chat_repo.get_new_loot_messages.return_value = [
            {'creature': 'rat', 'items': [{'name': 'ham', 'quantity': 1}]},
            {'creature': 'demon', 'items': [{'name': 'demon horn', 'quantity': 1}]},
        ]
        loop._chat_repo = mock_chat_repo

        context = {
            'screenshot': Mock(),
            'chat': {'lootMessages': []},
            'telemetry': telemetry,
        }

        loop._chat_middleware(context)

        assert telemetry.track_loot.call_count == 2
        telemetry.track_loot.assert_any_call(item_name='ham', quantity=1, value=4)
        telemetry.track_loot.assert_any_call(item_name='demon horn', quantity=1, value=1000)

    def test_no_telemetry_when_no_messages(self):
        """Should not call track_loot when no loot messages detected."""
        loop = self._make_gameloop()
        telemetry = MagicMock()
        mock_chat_repo = MagicMock()
        mock_chat_repo.get_new_loot_messages.return_value = []
        loop._chat_repo = mock_chat_repo

        context = {
            'screenshot': Mock(),
            'chat': {'lootMessages': []},
            'telemetry': telemetry,
        }

        loop._chat_middleware(context)

        telemetry.track_loot.assert_not_called()

    def test_no_crash_when_telemetry_is_none(self):
        """Should not crash when telemetry client is None."""
        loop = self._make_gameloop()
        mock_chat_repo = MagicMock()
        mock_chat_repo.get_new_loot_messages.return_value = [
            {'creature': 'rat', 'items': [{'name': 'ham', 'quantity': 1}]},
        ]
        loop._chat_repo = mock_chat_repo

        context = {
            'screenshot': Mock(),
            'chat': {'lootMessages': []},
            'telemetry': None,
        }

        # Should not raise
        loop._chat_middleware(context)

    def test_unknown_item_sends_none_value(self):
        """Should send value=None for items not in price database."""
        loop = self._make_gameloop()
        telemetry = MagicMock()
        mock_chat_repo = MagicMock()
        mock_chat_repo.get_new_loot_messages.return_value = [
            {'creature': 'monster', 'items': [{'name': 'unknown artifact', 'quantity': 1}]},
        ]
        loop._chat_repo = mock_chat_repo

        context = {
            'screenshot': Mock(),
            'chat': {'lootMessages': []},
            'telemetry': telemetry,
        }

        loop._chat_middleware(context)

        telemetry.track_loot.assert_called_once_with(
            item_name='unknown artifact', quantity=1, value=None
        )


class TestCavebotDoesNotSendLoot:
    """Verify cavebot tasks no longer send loot telemetry (middleware handles it)."""

    @patch('pyautogui.press')
    def test_on_before_restart_no_track_loot(self, mock_press):
        """on_before_restart should NOT call track_loot (middleware handles loot)."""
        telemetry = MagicMock()
        context = create_loot_context(
            loot_messages=[
                {'creature': 'demon', 'items': [{'name': 'demon horn', 'quantity': 1}]}
            ],
            telemetry=telemetry,
        )
        context['cavebot']['closestCreature'] = Mock(name='next_creature')

        task = AttackClosestCreatureTask()
        task._last_target_name = 'Demon'
        task.on_before_restart(context)

        telemetry.track_loot.assert_not_called()
        # But track_kill should still be called
        telemetry.track_kill.assert_called_once()

    @patch('pyautogui.press')
    def test_on_complete_no_track_loot(self, mock_press):
        """on_complete should NOT call track_loot (middleware handles loot)."""
        telemetry = MagicMock()
        context = create_loot_context(
            loot_messages=[
                {'creature': 'dragon', 'items': [{'name': 'dragon ham', 'quantity': 3}]}
            ],
            telemetry=telemetry,
        )

        task = AttackClosestCreatureTask()
        task._last_target_name = 'Dragon'
        task.on_complete(context)

        telemetry.track_loot.assert_not_called()
        # But track_kill should still be called
        telemetry.track_kill.assert_called_once()

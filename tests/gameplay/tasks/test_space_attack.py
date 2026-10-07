"""
Tests for the battle list + next-target key attack (Real-tibia-heal's method).

Decides from the battle list alone - no radar, game window or pathfinding - so it must:
1. press the key only when nothing is attacked (each press switches creature)
2. respect the press gap and the loot gap
3. give up on an unreachable creature and let the route go on
4. interrupt walking, which the click attack can't do without closestCreature
"""
import time
from unittest.mock import Mock, patch

from src.core.types import CreatureType


def _monster(name='Troll', attacked=False):
    creature = Mock()
    creature.name = name
    creature.is_being_attacked = attacked
    creature.creature_type = CreatureType.MONSTER
    return creature


def _player(name='Someone'):
    creature = _monster(name)
    creature.creature_type = CreatureType.PLAYER
    return creature


def _context(creatures, attacking=False, method='space', **cavebot):
    return {
        'battleList': {'creatures': creatures},
        'cavebot': {'enabled': True, 'attackMethod': method,
                    'isAttackingSomeCreature': attacking, 'closestCreature': None, **cavebot},
        'targeting': {'enabled': True, 'mode': 'all'},
        'loot': {'enabled': True, 'hotkey': 'g'},
    }


class TestHasCreaturesToAttack:

    def test_space_needs_only_battle_list(self):
        from src.gameplay.resolvers import has_creatures_to_attack
        assert has_creatures_to_attack(_context([_monster()])) is True

    def test_space_ignores_players(self):
        from src.gameplay.resolvers import has_creatures_to_attack
        assert has_creatures_to_attack(_context([_player()])) is False

    def test_space_respects_whitelist(self):
        from src.gameplay.resolvers import has_creatures_to_attack
        context = _context([_monster('Rat')])
        context['targeting'] = {'enabled': True, 'mode': 'whitelist', 'whitelist': ['Troll']}
        assert has_creatures_to_attack(context) is False

    def test_space_paused_after_giving_up(self):
        from src.gameplay.resolvers import has_creatures_to_attack
        context = _context([_monster()], spaceAttackPausedUntil=time.time() + 5)
        assert has_creatures_to_attack(context) is False

    def test_click_still_needs_closest_creature(self):
        from src.gameplay.resolvers import has_creatures_to_attack
        assert has_creatures_to_attack(_context([_monster()], method='click')) is False
        context = _context([_monster()], method='click', closestCreature=Mock())
        assert has_creatures_to_attack(context) is True

    def test_resolver_picks_task_by_method(self):
        from src.gameplay.resolvers import resolve_cavebot_tasks
        assert resolve_cavebot_tasks(_context([_monster()])).name == 'SpaceAttack'
        context = _context([_monster()], method='click', closestCreature=Mock())
        assert resolve_cavebot_tasks(context).name == 'AttackClosestCreature'


class TestSpaceAttackTask:

    @patch('pyautogui.press')
    def test_presses_key_when_nothing_attacked(self, mock_press):
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        SpaceAttackTask().do(_context([_monster()]))
        mock_press.assert_called_once_with('space')

    @patch('pyautogui.press')
    def test_uses_configured_key(self, mock_press):
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        SpaceAttackTask().do(_context([_monster()], nextTargetHotkey='tab'))
        mock_press.assert_called_once_with('tab')

    @patch('pyautogui.press')
    def test_never_presses_while_attacking(self, mock_press):
        """A press while attacking would walk the client onto another creature."""
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        SpaceAttackTask().do(_context([_monster(attacked=True)], attacking=True))
        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_waits_min_gap_between_presses(self, mock_press):
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        task = SpaceAttackTask()
        context = _context([_monster()])
        task.do(context)
        task.ping(context)
        assert mock_press.call_count == 1

    @patch('pyautogui.press')
    def test_waits_out_loot_press(self, mock_press):
        """Pressing right after quick loot would cancel the walk to the corpse."""
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        context = _context([_monster()])
        context['loot']['attackAfter'] = time.time() + 0.5
        SpaceAttackTask().do(context)
        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_gives_up_when_presses_never_attack(self, mock_press):
        from src.core.constants import SPACE_ATTACK_MAX_PRESSES
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        task = SpaceAttackTask()
        context = _context([_monster()])
        for _ in range(SPACE_ATTACK_MAX_PRESSES + 1):
            task._last_press = 0.0
            task.ping(context)
        assert mock_press.call_count == SPACE_ATTACK_MAX_PRESSES
        assert task.did(context) is True
        assert context['cavebot']['spaceAttackPausedUntil'] > time.time()

    @patch('pyautogui.press')
    def test_attack_frame_resets_tries(self, mock_press):
        from src.core.constants import SPACE_ATTACK_MAX_PRESSES
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        task = SpaceAttackTask()
        idle = _context([_monster()])
        fighting = _context([_monster(attacked=True)], attacking=True)
        for _ in range(SPACE_ATTACK_MAX_PRESSES * 2):
            task._last_press = 0.0
            task.ping(idle)
            task.ping(fighting)
        assert task.did(idle) is False

    def test_done_when_battle_list_has_nothing_to_attack(self):
        from src.gameplay.core.tasks.cavebot import SpaceAttackTask
        task = SpaceAttackTask()
        assert task.did(_context([])) is True
        assert task.did(_context([_player()])) is True
        assert task.did(_context([_monster()])) is False
        assert task.did(_context([_monster(attacked=True)], attacking=True)) is False


class TestFightWhileWalking:

    @patch('pyautogui.press')
    def test_space_attack_interrupts_walking(self, mock_press):
        """Click attack walked past monsters (no closestCreature while the screen scrolls)."""
        from src.gameplay.cavebot import handle_cavebot

        orchestrator = Mock()
        orchestrator.is_idle = False
        orchestrator.current_task_name = 'WalkToCoordinate'

        handle_cavebot(_context([_monster()]), orchestrator)

        orchestrator.set_root_task.assert_called_once()
        assert orchestrator.set_root_task.call_args[0][0].name == 'SpaceAttack'

    @patch('pyautogui.press')
    def test_ladder_is_not_interrupted(self, mock_press):
        from src.gameplay.cavebot import handle_cavebot

        orchestrator = Mock()
        orchestrator.is_idle = False
        orchestrator.current_task_name = 'UseLadder'

        handle_cavebot(_context([_monster()]), orchestrator)

        orchestrator.set_root_task.assert_not_called()

    @patch('pyautogui.press')
    def test_running_space_attack_is_not_restarted(self, mock_press):
        from src.gameplay.cavebot import handle_cavebot

        orchestrator = Mock()
        orchestrator.is_idle = False
        orchestrator.current_task_name = 'SpaceAttack'

        handle_cavebot(_context([_monster()]), orchestrator)

        orchestrator.set_root_task.assert_not_called()

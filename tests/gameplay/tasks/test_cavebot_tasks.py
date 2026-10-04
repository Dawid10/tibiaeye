"""
Tests for Cavebot Tasks - combat, looting, and navigation tasks.

Ensures:
1. ClickInClosestCreatureTask initiates attack correctly
2. WalkToTargetCreatureTask walks toward target with pathfinding
3. AttackClosestCreatureTask orchestrates click → walk → loot cycle
4. LootCorpseTask triggers loot hotkey
5. SetNextWaypointTask advances waypoints correctly
6. WalkToWaypointTask combines walking and waypoint advancement
7. UseRopeTask, UseShovelTask, UseLadderTask handle floor changes
8. CheckMonstersTask detects creatures
"""
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from src.gameplay.core.tasks.base import TaskState


class TestClickInClosestCreatureTask:
    """Tests for ClickInClosestCreatureTask."""

    def test_task_creation(self):
        """Test ClickInClosestCreatureTask creation."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        assert task.name == "ClickInClosestCreature"
        assert task.delay_of_timeout == 2.0

    def test_should_ignore_when_already_attacking(self):
        """Test should_ignore returns True when already attacking."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        context = {'cavebot': {'isAttackingSomeCreature': True}}

        assert task.should_ignore(context) is True

    def test_should_not_ignore_when_not_attacking(self):
        """Test should_ignore returns False when not attacking."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        context = {'cavebot': {'isAttackingSomeCreature': False}}

        assert task.should_ignore(context) is False

    @patch('pyautogui.keyDown')
    @patch('pyautogui.keyUp')
    @patch('pyautogui.click')
    def test_do_alt_clicks_when_players_present(self, mock_click, mock_keyup, mock_keydown):
        """Test do() uses Alt+Click when players present AND id_method is TM."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        mock_creature = Mock()
        mock_creature.window_coordinate = (400, 300)
        mock_creature.name = "Rotworm"
        mock_creature.id_method = "TM"

        context = {
            'cavebot': {
                'closestCreature': mock_creature,
                'hasPlayers': True,
            }
        }

        task.do(context)

        mock_keydown.assert_called_once_with('alt')
        mock_click.assert_called_once_with(400, 300)
        mock_keyup.assert_called_once_with('alt')

    @patch('pyautogui.press')
    def test_do_space_when_players_and_unknown_method(self, mock_press):
        """Test do() uses Space when players present + unknown method (unidentified creature, could be player)."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        mock_creature = Mock()
        mock_creature.window_coordinate = (400, 300)
        mock_creature.name = "Player"
        mock_creature.id_method = ""

        context = {
            'cavebot': {
                'closestCreature': mock_creature,
                'hasPlayers': True,
            },
            'battleList': {'creatures': []},
        }

        task.do(context)

        mock_press.assert_called_once_with('space')

    @patch('pyautogui.keyDown')
    @patch('pyautogui.keyUp')
    @patch('pyautogui.click')
    def test_do_alt_clicks_creature_when_no_players(self, mock_click, mock_keyup, mock_keydown):
        """Test do() uses Alt+Click on BFS-reachable creature when no players present."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        mock_creature = Mock()
        mock_creature.window_coordinate = (400, 300)
        mock_creature.name = "Rotworm"

        context = {
            'cavebot': {
                'closestCreature': mock_creature,
                'hasPlayers': False,
            }
        }

        task.do(context)

        mock_keydown.assert_called_once_with('alt')
        mock_click.assert_called_once_with(400, 300)
        mock_keyup.assert_called_once_with('alt')
        assert task._click_time > 0

    @patch('pyautogui.press')
    def test_do_presses_space_when_no_creature(self, mock_press):
        """Test do() presses Space as fallback when no closestCreature (pathfinding stale)."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        context = {
            'cavebot': {
                'closestCreature': None,
                'hasPlayers': False,
            }
        }

        task.do(context)

        mock_press.assert_called_once_with('space')

    def test_did_true_when_attacking(self):
        """Test did() returns True when attacking confirmed."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        context = {'cavebot': {'isAttackingSomeCreature': True}}

        assert task.did(context) is True

    def test_did_false_when_not_attacking(self):
        """Test did() returns False when not yet attacking."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        context = {'cavebot': {'isAttackingSomeCreature': False}}

        assert task.did(context) is False

    @patch('pyautogui.press')
    @patch('pyautogui.keyDown')
    @patch('pyautogui.keyUp')
    @patch('pyautogui.click')
    def test_does_not_alt_click_when_no_creature(self, mock_click, mock_keyup, mock_keydown, mock_press):
        """
        Test: No closestCreature → falls back to Space (never Alt+Click).

        Scenario:
        - closestCreature is None (pathfinding hasn't found target yet)
        - Bot presses Space as safe fallback (Tibia attacks nearest)
        - Bot does NOT Alt+Click (no screen coordinate to click on)
        """
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()

        context = {
            'cavebot': {
                'closestCreature': None,
                'hasPlayers': True,
            }
        }

        task.do(context)

        mock_click.assert_not_called()
        mock_keydown.assert_not_called()
        mock_keyup.assert_not_called()
        mock_press.assert_called_once_with('space')

    @patch('pyautogui.press')
    def test_ping_fallback_space_after_grace_period(self, mock_press):
        """Test ping() presses Space as fallback when click didn't register attack."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()
        task._click_time = time.time() - 1.0  # 1s ago, past grace period

        context = {
            'cavebot': {
                'isAttackingSomeCreature': False,
                'hasPlayers': False,
            }
        }

        task.ping(context)

        mock_press.assert_called_once_with('space')
        assert task._click_time == 0

    @patch('pyautogui.press')
    def test_ping_no_fallback_within_grace_period(self, mock_press):
        """Test ping() does NOT press Space within grace period."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()
        task._click_time = time.time()  # Just now

        context = {
            'cavebot': {
                'isAttackingSomeCreature': False,
                'hasPlayers': False,
            }
        }

        task.ping(context)

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_ping_no_fallback_when_already_attacking(self, mock_press):
        """Test ping() skips fallback when attack already confirmed."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()
        task._click_time = time.time() - 1.0

        context = {
            'cavebot': {
                'isAttackingSomeCreature': True,
                'hasPlayers': False,
            }
        }

        task.ping(context)

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_ping_no_fallback_when_players_present(self, mock_press):
        """Test ping() does NOT fall back to Space when players present (avoid PvP)."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()
        task._click_time = time.time() - 1.0

        context = {
            'cavebot': {
                'isAttackingSomeCreature': False,
                'hasPlayers': True,
            }
        }

        task.ping(context)

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_ping_no_fallback_when_no_click(self, mock_press):
        """Test ping() does nothing when no click was made (Space was used directly)."""
        from src.gameplay.core.tasks.cavebot import ClickInClosestCreatureTask

        task = ClickInClosestCreatureTask()
        # _click_time is 0 (default, no click was made)

        context = {
            'cavebot': {
                'isAttackingSomeCreature': False,
                'hasPlayers': False,
            }
        }

        task.ping(context)

        mock_press.assert_not_called()


class TestWalkToTargetCreatureTask:
    """Tests for WalkToTargetCreatureTask."""

    def test_task_creation(self):
        """Test WalkToTargetCreatureTask creation."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        assert task.name == "WalkToTargetCreature"
        assert task.delay_of_timeout == 30.0
        assert task._path == []
        assert task._force_complete is False

    @patch('src.gameplay.cavebot.radar.generate_floor_walkpoints')
    def test_do_calculates_path(self, mock_walkpoints):
        """Test do() calculates path to target creature."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        mock_walkpoints.return_value = [
            (32001, 32000, 7), (32002, 32000, 7), (32003, 32000, 7)
        ]

        task = WalkToTargetCreatureTask()

        mock_target = Mock()
        mock_target.coordinate = (32003, 32000, 7)
        mock_target.is_being_attacked = True

        context = {
            'radar': {'coordinate': (32000, 32000, 7)},
            'cavebot': {'holesOrStairs': []},
            'gameWindow': {'monsters': [mock_target]},
        }

        task.do(context)

        # Path includes the target tile (walk TO creature position)
        assert len(task._path) == 3
        assert task._path_index == 0

    @patch('src.gameplay.cavebot.radar.generate_floor_walkpoints')
    def test_do_single_step_path_not_popped(self, mock_walkpoints):
        """Test do() does not pop last step when path is only 1 step."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        mock_walkpoints.return_value = [(32001, 32000, 7)]

        task = WalkToTargetCreatureTask()

        mock_target = Mock()
        mock_target.coordinate = (32001, 32000, 7)
        mock_target.is_being_attacked = True

        context = {
            'radar': {'coordinate': (32000, 32000, 7)},
            'cavebot': {'holesOrStairs': []},
            'gameWindow': {'monsters': [mock_target]},
        }

        task.do(context)

        assert len(task._path) == 1

    def test_did_true_when_creature_died(self):
        """Test did() returns True when creature died (no longer attacking)."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        context = {'cavebot': {'isAttackingSomeCreature': False}}

        assert task.did(context) is True

    def test_did_false_when_still_attacking(self):
        """Test did() returns False when still attacking and battlelist has creatures."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        context = {
            'cavebot': {'isAttackingSomeCreature': True},
            'battleList': {'creatures': [Mock()]},
        }

        assert task.did(context) is False

    def test_did_true_when_attacking_but_battlelist_empty(self):
        """Test did() returns True when attacking flag is stale but battlelist is empty.

        Bug scenario: creature died, middleware hasn't cleared isAttackingSomeCreature yet,
        but battlelist is empty → creature is dead, complete immediately.
        """
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        context = {
            'cavebot': {'isAttackingSomeCreature': True},
            'battleList': {'creatures': []},
        }

        assert task.did(context) is True

    def test_did_true_when_force_complete(self):
        """Test did() returns True when force_complete."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()
        task._force_complete = True

        context = {'cavebot': {'isAttackingSomeCreature': True}}

        assert task.did(context) is True

    def test_do_waits_when_no_target(self):
        """Test do() waits for target (no force_complete) when no attacked monster."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        context = {
            'radar': {'coordinate': (32000, 32000, 7)},
            'cavebot': {},
            'gameWindow': {'monsters': []},  # No attacked monster
        }

        task.do(context)

        # Should NOT force_complete — ping() will calculate path when target appears
        assert task._force_complete is False
        assert task._path == []
        assert task._last_pos == (32000, 32000, 7)

    @patch('src.gameplay.cavebot.radar.generate_floor_walkpoints')
    @patch('src.gameplay.cavebot.radar.get_direction_between_coords')
    @patch('pyautogui.press')
    def test_ping_recalculates_on_target_move(self, mock_press, mock_direction, mock_walkpoints):
        """Test ping() recalculates path when target creature moves."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()
        task._last_target_coord = (32003, 32000, 7)
        task._path = [(32001, 32000, 7)]
        task._path_index = 0
        task._last_pos = (32000, 32000, 7)
        task._last_progress_time = time.time()

        mock_walkpoints.return_value = [(32001, 32001, 7), (32002, 32001, 7)]
        mock_direction.return_value = 'right'

        mock_target = Mock()
        mock_target.coordinate = (32003, 32001, 7)  # Target moved!
        mock_target.is_being_attacked = True

        context = {
            'radar': {'coordinate': (32000, 32000, 7)},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'holesOrStairs': [],
            },
            'gameWindow': {'monsters': [mock_target]},
            'playerSpeed': 110,
        }

        task.ping(context)

        # Path should have been recalculated
        mock_walkpoints.assert_called_once()
        assert task._last_target_coord == (32003, 32001, 7)

    @patch('src.gameplay.cavebot.radar.generate_floor_walkpoints')
    @patch('src.gameplay.cavebot.radar.get_direction_between_coords')
    @patch('pyautogui.press')
    def test_ping_calculates_path_when_target_appears(self, mock_press, mock_direction, mock_walkpoints):
        """Test ping() calculates path when target first becomes available."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()
        task._last_target_coord = None  # No target yet (do() had no target)
        task._path = []
        task._last_pos = (32000, 32000, 7)
        task._last_progress_time = time.time()

        mock_walkpoints.return_value = [(32001, 32000, 7), (32002, 32000, 7)]
        mock_direction.return_value = 'right'

        mock_target = Mock()
        mock_target.coordinate = (32002, 32000, 7)
        mock_target.is_being_attacked = True

        context = {
            'radar': {'coordinate': (32000, 32000, 7)},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'holesOrStairs': [],
            },
            'gameWindow': {'monsters': [mock_target]},
            'playerSpeed': 110,
        }

        task.ping(context)

        mock_walkpoints.assert_called_once()
        assert task._last_target_coord == (32002, 32000, 7)

    @patch('src.gameplay.cavebot.radar.get_direction_between_coords')
    @patch('pyautogui.press')
    def test_chase_lost_target_walks_toward_last_known(self, mock_press, mock_direction):
        """Test: path exhausted + creature off-screen → walks toward _last_target_coord."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        mock_direction.return_value = 'down'

        task = WalkToTargetCreatureTask()
        task._last_target_coord = (32000, 32003, 7)
        task._path = [(32000, 32001, 7)]
        task._path_index = 1  # Path exhausted
        task._last_pos = (32000, 32001, 7)
        task._last_progress_time = time.time()
        task._last_walk_time = 0  # Cooldown expired

        context = {
            'radar': {'coordinate': (32000, 32001, 7)},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'holesOrStairs': [],
            },
            'gameWindow': {'monsters': []},  # Creature fled off-screen
            'playerSpeed': 110,
        }

        task.ping(context)

        mock_press.assert_called_once_with('s')

    @patch('src.gameplay.cavebot.radar.get_direction_between_coords')
    @patch('pyautogui.press')
    def test_chase_lost_target_resets_progress(self, mock_press, mock_direction):
        """Test: chasing resets _last_progress_time (prevents premature timeout)."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        mock_direction.return_value = 'down'

        task = WalkToTargetCreatureTask()
        task._last_target_coord = (32000, 32003, 7)
        task._path = []
        task._path_index = 0  # Path exhausted (empty)
        task._last_pos = (32000, 32001, 7)
        old_progress_time = time.time() - 10  # 10s ago
        task._last_progress_time = old_progress_time
        task._last_walk_time = 0

        context = {
            'radar': {'coordinate': (32000, 32001, 7)},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'holesOrStairs': [],
            },
            'gameWindow': {'monsters': []},
            'playerSpeed': 110,
        }

        task.ping(context)

        assert task._last_progress_time > old_progress_time

    @patch('src.gameplay.cavebot.radar.generate_floor_walkpoints')
    def test_recalculate_uses_last_target_when_creature_off_screen(self, mock_walkpoints):
        """Test: stuck recalculation uses _last_target_coord instead of force-completing."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        mock_walkpoints.return_value = [(32000, 32002, 7)]

        task = WalkToTargetCreatureTask()
        task._last_target_coord = (32000, 32003, 7)
        task._recalculation_count = 0

        context = {
            'radar': {'coordinate': (32000, 32001, 7)},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'holesOrStairs': [],
            },
            'gameWindow': {'monsters': []},  # Creature off-screen
        }

        result = task._recalculate_path(context, (32000, 32001, 7))

        assert task._force_complete is False
        assert task._recalculation_count == 1
        mock_walkpoints.assert_called_once()

    def test_ping_skips_when_not_attacking(self):
        """Test ping() returns early when not attacking."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()
        task._path = [(32001, 32000, 7)]

        context = {
            'cavebot': {'isAttackingSomeCreature': False},
        }

        task.ping(context)

        # Should not change anything
        assert task._path_index == 0

    def test_get_target_coordinate_fallback_to_closest(self):
        """Test _get_target_coordinate falls back to closestCreature when no monster has is_being_attacked.

        Bug scenario: player + monster on screen, bar assignment wrong → is_being_attacked on wrong bar.
        Battlelist correctly detects isAttackingSomeCreature, so fallback uses closestCreature.
        """
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        mock_closest = Mock()
        mock_closest.coordinate = (32005, 32003, 7)

        mock_monster = Mock()
        mock_monster.is_being_attacked = False  # Wrong bar assignment

        context = {
            'gameWindow': {'monsters': [mock_monster]},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'closestCreature': mock_closest,
            },
        }

        result = task._get_target_coordinate(context)

        assert result == (32005, 32003, 7)

    def test_get_target_coordinate_no_fallback_when_not_attacking(self):
        """Test _get_target_coordinate returns None when not attacking and no is_being_attacked."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        context = {
            'gameWindow': {'monsters': []},
            'cavebot': {
                'isAttackingSomeCreature': False,
                'closestCreature': None,
            },
        }

        result = task._get_target_coordinate(context)

        assert result is None

    def test_get_target_coordinate_prefers_is_being_attacked(self):
        """Test _get_target_coordinate prefers monster with is_being_attacked over fallback."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()

        mock_attacked = Mock()
        mock_attacked.coordinate = (32010, 32010, 7)
        mock_attacked.is_being_attacked = True

        mock_closest = Mock()
        mock_closest.coordinate = (32005, 32003, 7)

        context = {
            'gameWindow': {'monsters': [mock_attacked]},
            'cavebot': {
                'isAttackingSomeCreature': True,
                'closestCreature': mock_closest,
            },
        }

        result = task._get_target_coordinate(context)

        assert result == (32010, 32010, 7)

    def test_ping_progress_timeout_fires_when_no_path(self):
        """Must trigger progress timeout even when path is empty (no early-return bypass)."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()
        task._last_progress_time = time.time() - 10  # 10s ago, well past 5s timeout
        task._path = []
        task._path_index = 0

        context = {
            'cavebot': {'isAttackingSomeCreature': True, '_targetUnreachable': False},
            'radar': {'coordinate': (32000, 32000, 7)},
            'gameWindow': {'monsters': []},
        }

        task.ping(context)

        assert task._force_complete is True

    def test_ping_no_timeout_when_progress_recent(self):
        """Should NOT timeout when progress was recent, even with empty path."""
        from src.gameplay.core.tasks.cavebot import WalkToTargetCreatureTask

        task = WalkToTargetCreatureTask()
        task._last_progress_time = time.time()  # just now
        task._path = []
        task._path_index = 0

        context = {
            'cavebot': {'isAttackingSomeCreature': True, '_targetUnreachable': False},
            'radar': {'coordinate': (32000, 32000, 7)},
            'gameWindow': {'monsters': []},
        }

        task.ping(context)

        assert task._force_complete is False


class TestAttackClosestCreatureTask:
    """Tests for AttackClosestCreatureTask (VectorTask version)."""

    def test_task_creation(self):
        """Test AttackClosestCreatureTask creation."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask
        from src.core.constants import CAVEBOT_ATTACK_STUCK_TIMEOUT

        task = AttackClosestCreatureTask()

        assert task.name == "AttackClosestCreature"
        assert task.max_retries == 100
        assert task.delay_of_timeout == CAVEBOT_ATTACK_STUCK_TIMEOUT

    def test_is_vector_task(self):
        """Test AttackClosestCreatureTask is a VectorTask."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask
        from src.gameplay.core.tasks.base import BaseTask
        from src.gameplay.core.tasks.vector import VectorTask

        task = AttackClosestCreatureTask()

        assert isinstance(task, VectorTask)
        assert isinstance(task, BaseTask)

    def test_on_before_start_saves_index(self):
        """Test on_before_start saves current waypoint index."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [],
                    'currentIndex': 5,
                    'indexBeforeCombat': None,
                }
            }
        }

        result = task.on_before_start(context)

        assert result['cavebot']['waypoints']['indexBeforeCombat'] == 5

    def test_on_before_start_creates_children(self):
        """Test on_before_start creates ClickInClosestCreature and WalkToTargetCreature."""
        from src.gameplay.core.tasks.cavebot import (
            AttackClosestCreatureTask,
            ClickInClosestCreatureTask,
            WalkToTargetCreatureTask,
        )

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [],
                    'currentIndex': 0,
                    'indexBeforeCombat': None,
                }
            }
        }

        task.on_before_start(context)

        assert len(task.tasks) == 2
        assert isinstance(task.tasks[0], ClickInClosestCreatureTask)
        assert isinstance(task.tasks[1], WalkToTargetCreatureTask)

    def test_should_restart_with_creatures(self):
        """Test should_restart returns True when battlelist has creatures."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'battleList': {'creatures': [Mock()]},
            'cavebot': {},
        }

        assert task.should_restart(context) is True

    def test_should_restart_no_creatures(self):
        """Test should_restart returns False when battlelist is empty."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'battleList': {'creatures': []},
            'cavebot': {},
        }

        assert task.should_restart(context) is False

    def test_should_restart_uses_battlelist_not_closest_creature(self):
        """Test should_restart uses battlelist (stable) even when closestCreature is None.

        Bug scenario: creature dies, closestCreature becomes None (gamewindow freq 2),
        but battlelist still has creatures → should restart to attack next creature.
        """
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'battleList': {'creatures': [Mock()]},
            'cavebot': {'closestCreature': None},
        }

        assert task.should_restart(context) is True

    @patch('pyautogui.press')
    def test_on_before_restart_does_not_loot(self, mock_press):
        """Looting belongs to the battle list middleware (loot_on_kill), which sees real kills only."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()
        # Need children for reset_children
        task.on_before_start({'cavebot': {'waypoints': {'currentIndex': 0}}})

        context = {
            'cavebot': {'waypoints': {'currentIndex': 0}},
            'loot': {'enabled': True, 'hotkey': 'g'}
        }

        task.on_before_restart(context)

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_on_before_restart_next_click_waits_out_loot(self, mock_press):
        """The next attack click waits for the last loot press - attacking cancels the walk to the corpse."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()
        task.on_before_start({'cavebot': {'waypoints': {'currentIndex': 0}}})

        context = {
            'cavebot': {'waypoints': {'currentIndex': 0}},
            'loot': {'enabled': True, 'hotkey': 'g', 'attackAfter': time.time() + 0.5},
        }

        task.on_before_restart(context)

        assert 0.4 < task.tasks[0].delay_before_start <= 0.5

    @patch('pyautogui.press')
    def test_on_before_restart_recreates_children(self, mock_press):
        """Test on_before_restart recreates children for next cycle."""
        from src.gameplay.core.tasks.cavebot import (
            AttackClosestCreatureTask,
            ClickInClosestCreatureTask,
            WalkToTargetCreatureTask,
        )

        task = AttackClosestCreatureTask()
        task.on_before_start({'cavebot': {'waypoints': {'currentIndex': 0}}})

        context = {
            'cavebot': {'waypoints': {'currentIndex': 0}},
            'loot': {'enabled': False},
        }

        task.on_before_restart(context)

        assert len(task.tasks) == 2
        assert isinstance(task.tasks[0], ClickInClosestCreatureTask)
        assert isinstance(task.tasks[1], WalkToTargetCreatureTask)

    @patch('pyautogui.press')
    def test_on_complete_does_not_loot_when_no_more_creatures(self, mock_press):
        """The last kill was already looted by loot_on_kill; on_complete only cleans up."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': Mock(),
                'closestCreature': None,
                'waypoints': {
                    'items': [],
                    'currentIndex': 0,
                    'indexBeforeCombat': None,
                }
            },
            'battleList': {'creatures': []},  # No more creatures
            'radar': {'coordinate': None},
            'loot': {'enabled': True, 'hotkey': 'g'}
        }

        result = task.on_complete(context)

        mock_press.assert_not_called()
        assert result['cavebot']['targetCreature'] is None

    @patch('pyautogui.press')
    def test_on_complete_skips_loot_when_restarting(self, mock_press):
        """Test on_complete skips loot when battlelist has creatures (will restart)."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': Mock(),
                'closestCreature': None,
                'waypoints': {
                    'items': [],
                    'currentIndex': 0,
                    'indexBeforeCombat': None,
                }
            },
            'battleList': {'creatures': [Mock()]},  # More creatures — will restart
            'radar': {'coordinate': None},
            'loot': {'enabled': True, 'hotkey': 'g'}
        }

        result = task.on_complete(context)

        mock_press.assert_not_called()
        # targetCreature NOT cleared — will restart
        assert result['cavebot']['targetCreature'] is not None

    @patch('pyautogui.press')
    def test_on_timeout_clears_target(self, mock_press):
        """Test on_timeout clears targetCreature and isAttackingSomeCreature."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': Mock(),
                'isAttackingSomeCreature': True,
                'waypoints': {
                    'items': [],
                    'currentIndex': 0,
                    'indexBeforeCombat': None,
                }
            },
            'radar': {'coordinate': None},
        }

        result = task.on_timeout(context)

        assert result['cavebot']['targetCreature'] is None
        assert result['cavebot']['isAttackingSomeCreature'] is False

    @patch('pyautogui.press')
    def test_on_timeout_presses_escape(self, mock_press):
        """Test on_timeout presses Escape to deselect creature."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': Mock(),
                'isAttackingSomeCreature': True,
                'waypoints': {
                    'items': [],
                    'currentIndex': 0,
                    'indexBeforeCombat': None,
                }
            },
            'radar': {'coordinate': None},
        }

        task.on_timeout(context)

        mock_press.assert_called_once_with('escape')

    @patch('pyautogui.press')
    def test_on_timeout_restores_waypoint(self, mock_press):
        """Test on_timeout restores waypoint index via _restore_waypoint_index."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        with patch.object(task, '_restore_waypoint_index') as mock_restore:
            context = {
                'cavebot': {
                    'targetCreature': Mock(),
                    'isAttackingSomeCreature': True,
                    'waypoints': {
                        'items': [],
                        'currentIndex': 0,
                        'indexBeforeCombat': 3,
                    }
                },
                'radar': {'coordinate': None},
            }

            task.on_timeout(context)

            mock_restore.assert_called_once_with(context)


class TestWaypointRestore:
    """Tests for waypoint restore after combat (closest forward with max skip)."""

    def test_on_before_start_saves_index(self):
        """Test on_before_start saves current waypoint index."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [],
                    'currentIndex': 5,
                    'indexBeforeCombat': None,
                }
            }
        }

        result = task.on_before_start(context)

        assert result['cavebot']['waypoints']['indexBeforeCombat'] == 5

    def test_calculate_best_index_closest_behind_saved_uses_saved(self):
        """Test: closest=3, saved=5, total=50 -> uses 5 (48 forward = too far)."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        result = task._calculate_best_index(saved=5, closest=3, max_skip=5, total=50)

        assert result == 5

    def test_calculate_best_index_closest_within_max_skip_uses_closest(self):
        """Test: closest=7, saved=5, max=5, total=50 -> uses 7 (within range)."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        result = task._calculate_best_index(saved=5, closest=7, max_skip=5, total=50)

        assert result == 7

    def test_calculate_best_index_closest_at_max_skip_boundary_uses_closest(self):
        """Test: closest=10, saved=5, max=5, total=50 -> uses 10 (exactly at boundary)."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        result = task._calculate_best_index(saved=5, closest=10, max_skip=5, total=50)

        assert result == 10

    def test_calculate_best_index_closest_beyond_max_skip_uses_saved(self):
        """Test: closest=15, saved=5, max=5, total=50 -> uses 5 (too far ahead)."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        result = task._calculate_best_index(saved=5, closest=15, max_skip=5, total=50)

        assert result == 5

    def test_calculate_best_index_closest_equals_saved(self):
        """Test: closest=5, saved=5 -> uses 5."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        result = task._calculate_best_index(saved=5, closest=5, max_skip=5, total=50)

        assert result == 5

    def test_calculate_best_index_circular_wrap(self):
        """Test: saved=48, closest=2, total=50, max=5 -> uses 2 (4 forward via wrap)."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        result = task._calculate_best_index(saved=48, closest=2, max_skip=5, total=50)

        assert result == 2

    @patch('pyautogui.press')
    def test_restore_waypoint_index_no_saved_index(self, mock_press):
        """Test restore does nothing if no saved index."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': None,
                'closestCreature': None,
                'waypoints': {
                    'items': [{'coordinate': (32000, 32000, 7)}],
                    'currentIndex': 2,
                    'indexBeforeCombat': None,  # No saved index
                }
            },
            'radar': {'coordinate': (32000, 32000, 7)},
            'loot': {'enabled': False}
        }

        task.on_complete(context)

        assert context['cavebot']['waypoints']['currentIndex'] == 2

    @patch('pyautogui.press')
    @patch('src.repositories.radar.get_closest_waypoint_index')
    def test_restore_waypoint_index_updates_correctly(self, mock_get_closest, mock_press):
        """Test restore updates waypoint index correctly."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        mock_get_closest.return_value = 7

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': None,
                'closestCreature': None,
                'waypoints': {
                    'items': [
                        {'coordinate': (32000, 32000, 7)},
                        {'coordinate': (32010, 32000, 7)},
                        {'coordinate': (32020, 32000, 7)},
                        {'coordinate': (32030, 32000, 7)},
                        {'coordinate': (32040, 32000, 7)},
                        {'coordinate': (32050, 32000, 7)},
                        {'coordinate': (32060, 32000, 7)},
                        {'coordinate': (32070, 32000, 7)},
                    ],
                    'currentIndex': 2,
                    'indexBeforeCombat': 5,
                }
            },
            'radar': {'coordinate': (32070, 32000, 7)},
            'loot': {'enabled': False}
        }

        task.on_complete(context)

        assert context['cavebot']['waypoints']['currentIndex'] == 7
        assert context['cavebot']['waypoints']['indexBeforeCombat'] is None

    @patch('pyautogui.press')
    @patch('src.repositories.radar.get_closest_waypoint_index')
    def test_restore_waypoint_index_clears_saved_index(self, mock_get_closest, mock_press):
        """Test restore clears indexBeforeCombat after use."""
        from src.gameplay.core.tasks.cavebot import AttackClosestCreatureTask

        mock_get_closest.return_value = 6

        task = AttackClosestCreatureTask()

        context = {
            'cavebot': {
                'targetCreature': None,
                'closestCreature': None,
                'waypoints': {
                    'items': [{'coordinate': (32000, 32000, 7)} for _ in range(10)],
                    'currentIndex': 2,
                    'indexBeforeCombat': 5,
                }
            },
            'radar': {'coordinate': (32000, 32000, 7)},
            'loot': {'enabled': False}
        }

        task.on_complete(context)

        assert context['cavebot']['waypoints']['indexBeforeCombat'] is None


class TestLootCorpseTask:
    """Tests for LootCorpseTask."""

    def test_task_creation(self):
        """Test LootCorpseTask creation."""
        from src.gameplay.core.tasks.cavebot import LootCorpseTask

        task = LootCorpseTask(hotkey='h')

        assert task.name == "LootCorpse"
        assert task.hotkey == 'h'
        assert task.delay_after_complete == 0.3

    def test_default_hotkey(self):
        """Test LootCorpseTask default hotkey."""
        from src.gameplay.core.tasks.cavebot import LootCorpseTask

        task = LootCorpseTask()

        assert task.hotkey == 'g'

    @patch('pyautogui.press')
    def test_do_presses_hotkey(self, mock_press):
        """Test LootCorpseTask do() presses hotkey."""
        from src.gameplay.core.tasks.cavebot import LootCorpseTask

        task = LootCorpseTask(hotkey='f')
        context = {}

        result = task.do(context)

        mock_press.assert_called_once_with('f')
        assert result == context


class TestSetNextWaypointTask:
    """Tests for SetNextWaypointTask."""

    def test_task_creation(self):
        """Test SetNextWaypointTask creation."""
        from src.gameplay.core.tasks.cavebot import SetNextWaypointTask

        task = SetNextWaypointTask()

        assert task.name == "SetNextWaypoint"

    def test_do_advances_index(self):
        """Test SetNextWaypointTask advances waypoint index."""
        from src.gameplay.core.tasks.cavebot import SetNextWaypointTask

        task = SetNextWaypointTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [
                        {'coordinate': (32000, 32000, 7)},
                        {'coordinate': (32010, 32000, 7)},
                        {'coordinate': (32020, 32000, 7)},
                    ],
                    'currentIndex': 0
                }
            }
        }

        result = task.do(context)

        assert result['cavebot']['waypoints']['currentIndex'] == 1

    def test_do_wraps_around(self):
        """Test SetNextWaypointTask wraps to start."""
        from src.gameplay.core.tasks.cavebot import SetNextWaypointTask

        task = SetNextWaypointTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [
                        {'coordinate': (32000, 32000, 7)},
                        {'coordinate': (32010, 32000, 7)},
                    ],
                    'currentIndex': 1  # At last waypoint
                }
            }
        }

        result = task.do(context)

        assert result['cavebot']['waypoints']['currentIndex'] == 0


class TestWalkToWaypointTask:
    """Tests for WalkToWaypointTask."""

    def test_task_creation(self):
        """Test WalkToWaypointTask creation."""
        from src.gameplay.core.tasks.cavebot import WalkToWaypointTask

        coord = (32000, 32000, 7)
        task = WalkToWaypointTask(coord)

        assert f"WalkToWaypoint({coord})" in task.name
        assert len(task.tasks) == 2

    def test_subtasks_are_correct(self):
        """Test WalkToWaypointTask has correct subtasks."""
        from src.gameplay.core.tasks.cavebot import WalkToWaypointTask, SetNextWaypointTask
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        coord = (32000, 32000, 7)
        task = WalkToWaypointTask(coord)

        assert isinstance(task.tasks[0], WalkToCoordinateTask)
        assert isinstance(task.tasks[1], SetNextWaypointTask)


class TestUseLadderTask:
    """Tests for UseLadderTask."""

    def test_task_creation(self):
        """Test UseLadderTask creation."""
        from src.gameplay.core.tasks.cavebot import UseLadderTask

        task = UseLadderTask(direction='north')

        assert "UseLadder(north)" in task.name
        assert task.direction == 'north'
        assert task.delay_after_complete == 0.8

    def test_default_direction(self):
        """Test UseLadderTask default direction."""
        from src.gameplay.core.tasks.cavebot import UseLadderTask

        task = UseLadderTask()

        assert task.direction == 'south'

    @patch('pyautogui.press')
    def test_do_presses_wasd_key(self, mock_press):
        """Test UseLadderTask do() presses WASD key."""
        from src.gameplay.core.tasks.cavebot import UseLadderTask

        task = UseLadderTask(direction='north')
        context = {}

        task.do(context)

        mock_press.assert_called_once_with('w')


class TestCheckMonstersTask:
    """Tests for CheckMonstersTask."""

    def test_task_creation(self):
        """Test CheckMonstersTask creation."""
        from src.gameplay.core.tasks.cavebot import CheckMonstersTask

        task = CheckMonstersTask()

        assert task.name == "CheckMonsters"
        assert task._has_monsters == False

    def test_do_detects_creatures(self):
        """Test CheckMonstersTask do() detects creatures."""
        from src.gameplay.core.tasks.cavebot import CheckMonstersTask

        task = CheckMonstersTask()

        context = {
            'gameWindow': {
                'creatures': [Mock()],
                'monsters': [],
                'monstersBars': []
            }
        }

        task.do(context)

        assert task._has_monsters == True
        assert task.has_monsters == True

    def test_do_no_monsters(self):
        """Test CheckMonstersTask do() with no monsters."""
        from src.gameplay.core.tasks.cavebot import CheckMonstersTask

        task = CheckMonstersTask()

        context = {
            'gameWindow': {
                'creatures': [],
                'monsters': [],
                'monstersBars': []
            }
        }

        task.do(context)

        assert task._has_monsters == False
        assert task.has_monsters == False


class TestWalkToCoordinateCrossFloor:
    """Tests for WalkToCoordinateTask cross-floor instant fail."""

    def test_different_floor_fails_instantly(self):
        """WalkTo must fail immediately when goal is on a different floor."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        task = WalkToCoordinateTask((33008, 32073, 9))
        context = {
            'radar': {'coordinate': (33008, 32077, 8)},
            'cavebot': {'holesOrStairs': []},
            'gameWindow': {'monsters': []},
        }

        task.do(context)

        assert task._force_complete is True

    def test_same_floor_does_not_fail(self):
        """WalkTo must NOT fail when goal is on the same floor."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        task = WalkToCoordinateTask((33016, 32080, 8))
        context = {
            'radar': {'coordinate': (33008, 32077, 8)},
            'cavebot': {'holesOrStairs': []},
            'gameWindow': {'monsters': []},
        }

        with patch('src.gameplay.cavebot.radar.generate_floor_walkpoints', return_value=[(33016, 32080, 8)]):
            task.do(context)

        # Floor check passed, pathfinding ran normally
        assert task._force_complete is False


class TestWalkToCoordinateConsecutiveSkips:
    """Tests for consecutive waypoint skip circuit breaker."""

    def test_first_skip_increments_counter(self):
        """First skip should set counter to 1."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        task = WalkToCoordinateTask((33016, 32080, 8))
        task._force_complete = True
        context = {
            'radar': {'coordinate': (33008, 32077, 8)},
            'cavebot': {'waypoints': {'items': [], 'currentIndex': 0}},
        }

        with patch.object(task, '_jump_to_closest_waypoint'):
            task.on_complete(context)

        assert context['cavebot']['_skipState']['count'] == 1

    def test_consecutive_skips_accumulate(self):
        """Skips from same position should accumulate."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        context = {
            'radar': {'coordinate': (33008, 32077, 8)},
            'cavebot': {
                'waypoints': {'items': [], 'currentIndex': 0},
                '_skipState': {'position': (33008, 32077, 8), 'count': 3},
            },
        }

        task = WalkToCoordinateTask((33029, 32089, 8))
        task._force_complete = True

        with patch.object(task, '_jump_to_closest_waypoint'):
            task.on_complete(context)

        assert context['cavebot']['_skipState']['count'] == 4

    def test_position_change_resets_counter(self):
        """Counter resets when position changes between skips."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        context = {
            'radar': {'coordinate': (33010, 32077, 8)},  # Different position
            'cavebot': {
                'waypoints': {'items': [], 'currentIndex': 0},
                '_skipState': {'position': (33008, 32077, 8), 'count': 4},
            },
        }

        task = WalkToCoordinateTask((33029, 32089, 8))
        task._force_complete = True

        with patch.object(task, '_jump_to_closest_waypoint'):
            task.on_complete(context)

        assert context['cavebot']['_skipState']['count'] == 1

    @patch('src.gameplay.core.tasks.common.pyautogui')
    @patch('src.gameplay.core.tasks.common.time')
    def test_circuit_breaker_fires_at_threshold(self, mock_time, mock_pyautogui):
        """Emergency random walk should fire at WALK_MAX_CONSECUTIVE_SKIPS."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask
        from src.core.constants import WALK_MAX_CONSECUTIVE_SKIPS

        mock_time.time.return_value = 100.0
        mock_time.sleep = Mock()

        context = {
            'radar': {'coordinate': (33008, 32077, 8)},
            'cavebot': {
                'waypoints': {'items': [], 'currentIndex': 0},
                '_skipState': {
                    'position': (33008, 32077, 8),
                    'count': WALK_MAX_CONSECUTIVE_SKIPS - 1,
                },
            },
        }

        task = WalkToCoordinateTask((33029, 32089, 8))
        task._force_complete = True

        task.on_complete(context)

        # Counter resets after circuit breaker fires
        assert context['cavebot']['_skipState']['count'] == 0
        # Random walk was triggered (3 key presses)
        assert mock_pyautogui.press.call_count == 3

    def test_successful_walk_clears_skip_state(self):
        """Successful walk should clear skip state."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask

        context = {
            'radar': {'coordinate': (33016, 32080, 8)},
            'cavebot': {
                '_skipState': {'position': (33008, 32077, 8), 'count': 3},
            },
        }

        task = WalkToCoordinateTask((33016, 32080, 8))
        task._force_complete = False  # Successful walk

        task.on_complete(context)

        assert '_skipState' not in context['cavebot']


class TestStuckRecoveryTierReset:
    """Tests for stuck recovery tier reset after Tier 3."""

    @patch('src.gameplay.stuck_detector.time')
    @patch('src.gameplay.stuck_detector.random')
    @patch('src.gameplay.stuck_detector.pyautogui')
    def test_tier_3_resets_to_zero(self, mock_pyautogui, mock_random, mock_time):
        """Tier 3 should reset recovery_tier to 0 so recovery cycle repeats."""
        from src.gameplay.stuck_detector import StuckDetector

        mock_time.time.return_value = 200.0
        mock_time.sleep = Mock()
        mock_random.choice.return_value = 'w'

        detector = StuckDetector()
        detector._recovery_tier = 2  # Was at tier 2
        context = {'cavebot': {'enabled': True}}

        alert_system = Mock()
        detector._execute_tier_3(context, (100, 200, 7), 120, alert_system)

        assert detector._recovery_tier == 0

    @patch('src.gameplay.stuck_detector.time')
    @patch('src.gameplay.stuck_detector.random')
    @patch('src.gameplay.stuck_detector.pyautogui')
    def test_tier_3_fires_again_after_reset(self, mock_pyautogui, mock_random, mock_time):
        """After tier reset, tier 3 should fire again on next cooldown check."""
        from src.gameplay.stuck_detector import StuckDetector, STUCK_RECOVERY_COOLDOWN

        current_time = 300.0
        mock_time.time.return_value = current_time
        mock_time.sleep = Mock()
        mock_random.choice.return_value = 'w'

        detector = StuckDetector()
        detector._last_known_position = (100, 200, 7)
        detector._last_position_change_time = current_time - 150  # 150s stuck
        detector._recovery_tier = 0  # After reset
        detector._last_recovery_time = current_time - STUCK_RECOVERY_COOLDOWN - 1  # Cooldown passed
        detector._is_stuck = True

        orchestrator = Mock()
        context = {
            'cavebot': {'enabled': True},
            'radar': {'coordinate': (100, 200, 7)},
        }

        alert_system = Mock()
        alert_system.is_looping.return_value = False

        with patch('src.gameplay.stuck_detector.get_alert_system', return_value=alert_system):
            detector.check_and_recover(context, orchestrator)

        # Should have fired tier 3 (150s >= 120s, tier 0 < 3)
        assert mock_pyautogui.press.called
        alert_system.stuck_alert.assert_called_once()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])


def _bl_creature(name, attacked=False):
    creature = Mock()
    creature.name = name
    creature.is_being_attacked = attacked
    return creature


def _loot_context(creatures, target=None, loot=None, cavebot_on=True):
    return {
        'battleList': {'creatures': creatures},
        'cavebot': {'enabled': cavebot_on, 'targetCreature': target},
        'loot': loot if loot is not None else {'enabled': True, 'hotkey': 'g'},
    }


class TestLootOnKill:
    """Quick loot only when the attacked creature really left the battle list."""

    @patch('pyautogui.press')
    def test_loots_when_attacked_creature_disappears(self, mock_press):
        from src.gameplay.core.tasks.cavebot import loot_on_kill

        troll = _bl_creature('Troll', attacked=True)
        context = loot_on_kill(_loot_context([troll, _bl_creature('Rat')], target=troll))
        mock_press.assert_not_called()

        loot_on_kill(_loot_context([_bl_creature('Rat')], loot=context['loot']))

        mock_press.assert_called_once_with('g')
        assert context['loot']['attackAfter'] > time.time()

    @patch('pyautogui.press')
    def test_no_loot_when_attack_ends_but_creature_stays(self, mock_press):
        """Missed click, escape or timeout: the row is still there, nothing died."""
        from src.gameplay.core.tasks.cavebot import loot_on_kill

        troll = _bl_creature('Troll', attacked=True)
        context = loot_on_kill(_loot_context([troll], target=troll))

        loot_on_kill(_loot_context([_bl_creature('Troll')], loot=context['loot']))

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_no_loot_when_another_same_name_creature_leaves(self, mock_press):
        """Still attacking our troll - a second troll walking off screen is no kill."""
        from src.gameplay.core.tasks.cavebot import loot_on_kill

        troll = _bl_creature('Troll', attacked=True)
        context = loot_on_kill(_loot_context([troll, _bl_creature('Troll')], target=troll))

        loot_on_kill(_loot_context([troll], target=troll, loot=context['loot']))

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_loots_when_client_switches_to_next_creature(self, mock_press):
        """Target died and the attack frame jumped to another monster in the same reading."""
        from src.gameplay.core.tasks.cavebot import loot_on_kill

        troll = _bl_creature('Troll', attacked=True)
        rat = _bl_creature('Rat', attacked=True)
        context = loot_on_kill(_loot_context([troll, _bl_creature('Rat')], target=troll))

        loot_on_kill(_loot_context([rat], target=rat, loot=context['loot']))

        mock_press.assert_called_once_with('g')

    @patch('pyautogui.press')
    def test_no_loot_with_cavebot_off(self, mock_press):
        """Healing-only run: the player's own kills are left alone."""
        from src.gameplay.core.tasks.cavebot import loot_on_kill

        troll = _bl_creature('Troll', attacked=True)
        context = loot_on_kill(_loot_context([troll], target=troll, cavebot_on=False))

        loot_on_kill(_loot_context([], loot=context['loot'], cavebot_on=False))

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_no_loot_when_loot_disabled(self, mock_press):
        from src.gameplay.core.tasks.cavebot import loot_on_kill

        troll = _bl_creature('Troll', attacked=True)
        loot = {'enabled': False, 'hotkey': 'g'}
        loot_on_kill(_loot_context([troll], target=troll, loot=loot))

        loot_on_kill(_loot_context([], loot=loot))

        mock_press.assert_not_called()

    def test_loot_gap_left(self):
        from src.gameplay.core.tasks.cavebot import loot_gap_left

        assert loot_gap_left({}) == 0.0
        assert loot_gap_left({'loot': {'attackAfter': time.time() - 1}}) == 0.0
        assert 0.9 < loot_gap_left({'loot': {'attackAfter': time.time() + 1}}) <= 1.0

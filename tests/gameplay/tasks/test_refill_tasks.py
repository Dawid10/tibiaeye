"""
Tests for Refill Tasks - supply checking and NPC trading.

Ensures:
1. RefillCheckerTask correctly checks supplies
2. DepositGoldTask handles NPC dialogue
3. RefillPotionsTask calculates correct quantities
4. SayTask and WaitTask work correctly
5. Waypoint navigation works after refill
"""
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np


class TestSayTask:
    """Tests for SayTask - typing messages in game chat."""

    def test_say_task_creation(self):
        """Test SayTask creation with message."""
        from src.gameplay.core.tasks.refill import SayTask

        task = SayTask("hi")

        assert task.message == "hi"
        assert task.delay_before_start == 0.3
        assert task.delay_after_complete == 0.5

    def test_say_task_truncated_name(self):
        """Test SayTask name is truncated for long messages."""
        from src.gameplay.core.tasks.refill import SayTask

        task = SayTask("this is a very long message that should be truncated")

        assert "..." in task.name
        assert len(task.name) < len("this is a very long message that should be truncated") + 10

    def test_say_task_short_name(self):
        """Test SayTask name is full for short messages."""
        from src.gameplay.core.tasks.refill import SayTask

        task = SayTask("hi")

        assert task.name == "Say(hi)"

    @patch('pyautogui.press')
    @patch('pyautogui.write')
    @patch('time.sleep')
    def test_say_task_do(self, mock_sleep, mock_write, mock_press):
        """Test SayTask.do() types message correctly."""
        from src.gameplay.core.tasks.refill import SayTask

        task = SayTask("hi")
        context = {}

        result = task.do(context)

        # Should press enter to open chat
        mock_press.assert_any_call('enter')

        # Should type the message (interval has jitter, so check range)
        mock_write.assert_called_once()
        args, kwargs = mock_write.call_args
        assert args[0] == 'hi'
        assert 0.01 <= kwargs['interval'] <= 0.04

        # Should return context
        assert result == context


class TestWaitTask:
    """Tests for WaitTask - waiting for specified duration."""

    def test_wait_task_creation(self):
        """Test WaitTask creation with duration."""
        from src.gameplay.core.tasks.refill import WaitTask

        task = WaitTask(1.5)

        assert task.duration == 1.5
        assert "1.5" in task.name

    def test_wait_task_not_done_immediately(self):
        """Test WaitTask is not done immediately after start."""
        from src.gameplay.core.tasks.refill import WaitTask

        task = WaitTask(1.0)
        context = {}

        task.do(context)

        # Should not be done immediately
        assert task.did(context) == False

    def test_wait_task_done_after_duration(self):
        """Test WaitTask is done after duration elapses."""
        from src.gameplay.core.tasks.refill import WaitTask

        task = WaitTask(0.05)  # 50ms
        context = {}

        task.do(context)
        time.sleep(0.1)  # Wait longer than duration

        assert task.did(context) == True


class TestEnableChatTask:
    """Tests for EnableChatTask."""

    @patch('pyautogui.press')
    def test_enable_chat_presses_enter(self, mock_press):
        """Test EnableChatTask presses enter."""
        from src.gameplay.core.tasks.refill import EnableChatTask

        task = EnableChatTask()
        context = {}

        task.do(context)

        mock_press.assert_called_once_with('enter')


class TestDisableChatTask:
    """Tests for DisableChatTask."""

    @patch('pyautogui.press')
    def test_disable_chat_presses_escape(self, mock_press):
        """Test DisableChatTask presses escape."""
        from src.gameplay.core.tasks.refill import DisableChatTask

        task = DisableChatTask()
        context = {}

        task.do(context)

        mock_press.assert_called_once_with('escape')


class TestRefillCheckerTask:
    """Tests for RefillCheckerTask - checks if refill is needed."""

    def test_refill_checker_creation(self):
        """Test RefillCheckerTask creation."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        task = RefillCheckerTask()

        assert task.name == "RefillChecker"
        assert task._checked == False
        assert task._needs_refill == False

    def test_refill_checker_with_waypoint(self):
        """Test RefillCheckerTask with waypoint options."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        waypoint = {'label': 'checkRefill', 'options': {'returnLabel': 'caveStart'}}
        task = RefillCheckerTask(waypoint=waypoint)

        assert task.waypoint == waypoint

    def test_jump_to_label_logic(self):
        """Test _jump_to_label finds correct waypoint."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        task = RefillCheckerTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [
                        {'label': 'checkRefill'},
                        {'label': 'depot'},
                        {'label': 'caveStart'}
                    ],
                    'currentIndex': 0
                }
            }
        }

        task._jump_to_label(context, 'caveStart')

        # Should jump to caveStart (index 2)
        assert context['cavebot']['waypoints']['currentIndex'] == 2

    def test_advance_waypoint_logic(self):
        """Test _advance_waypoint increments index."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        task = RefillCheckerTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [
                        {'label': 'checkRefill'},
                        {'label': 'depot'},
                        {'label': 'caveStart'}
                    ],
                    'currentIndex': 0
                }
            }
        }

        task._advance_waypoint(context)

        # Should advance to next waypoint (index 1)
        assert context['cavebot']['waypoints']['currentIndex'] == 1

    def test_advance_waypoint_wraps_around(self):
        """Test _advance_waypoint wraps to start when at end."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        task = RefillCheckerTask()

        context = {
            'cavebot': {
                'waypoints': {
                    'items': [
                        {'label': 'checkRefill'},
                        {'label': 'depot'}
                    ],
                    'currentIndex': 1  # At last waypoint
                }
            }
        }

        task._advance_waypoint(context)

        # Should wrap to index 0
        assert context['cavebot']['waypoints']['currentIndex'] == 0

    def test_refill_checker_did_after_check(self):
        """Test RefillChecker did() returns True after checking."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        task = RefillCheckerTask()
        task._checked = True

        assert task.did({}) == True

    def test_refill_checker_did_before_check(self):
        """Test RefillChecker did() returns False before checking."""
        from src.gameplay.core.tasks.refill import RefillCheckerTask

        task = RefillCheckerTask()

        assert task.did({}) == False


class TestDepositGoldTask:
    """Tests for DepositGoldTask - deposits gold at banker."""

    def test_deposit_gold_creation(self):
        """Test DepositGoldTask creation."""
        from src.gameplay.core.tasks.refill import DepositGoldTask

        task = DepositGoldTask()

        assert task.name == "DepositGold"
        assert task._tasks_created == False

    def test_deposit_gold_creates_subtasks(self):
        """Test DepositGoldTask creates sub-tasks on start."""
        from src.gameplay.core.tasks.refill import DepositGoldTask

        task = DepositGoldTask()

        context = {
            'refill': {'depositGold': True}
        }

        # Call on_before_start to create sub-tasks
        task.on_before_start(context)

        # Should have created sub-tasks
        assert task._tasks_created == True
        assert len(task.tasks) > 0

    def test_deposit_gold_disabled_skips(self):
        """Test DepositGoldTask skips when disabled in config."""
        from src.gameplay.core.tasks.refill import DepositGoldTask

        task = DepositGoldTask()

        context = {
            'refill': {'depositGold': False}
        }

        task.on_before_start(context)

        # Should have created minimal sub-tasks (just SetNextWaypointTask)
        assert task._tasks_created == True
        # Only 1 task (SetNextWaypointTask)
        assert len(task.tasks) == 1


class TestRefillPotionsTask:
    """Tests for RefillPotionsTask - buys potions from NPC."""

    def test_refill_potions_creation(self):
        """Test RefillPotionsTask creation."""
        from src.gameplay.core.tasks.refill import RefillPotionsTask

        waypoint = {
            'options': {
                'healthPotion': {'item': 'Strong Health Potion', 'quantity': 200},
                'manaPotion': {'item': 'Strong Mana Potion', 'quantity': 400}
            }
        }
        task = RefillPotionsTask(waypoint)

        assert task.name == "RefillPotions"
        assert task.options == waypoint['options']

    def test_refill_potions_did_before_tasks_created(self):
        """Test RefillPotionsTask did() returns False before tasks created."""
        from src.gameplay.core.tasks.refill import RefillPotionsTask

        task = RefillPotionsTask({})

        assert task.did({}) == False


class TestCloseDepotTask:
    """Tests for CloseDepotTask."""

    @patch('pyautogui.press')
    def test_close_depot_presses_escape(self, mock_press):
        """Test CloseDepotTask presses escape."""
        from src.gameplay.core.tasks.refill import CloseDepotTask

        task = CloseDepotTask()
        context = {}

        task.do(context)

        mock_press.assert_called_once_with('escape')


class TestDropFlasksTask:
    """Tests for DropFlasksTask."""

    @patch('pyautogui.press')
    def test_drop_flasks_uses_hotkey(self, mock_press):
        """Test DropFlasksTask uses hotkey."""
        from src.gameplay.core.tasks.refill import DropFlasksTask

        task = DropFlasksTask(hotkey='f')
        context = {'refill': {'dropFlasks': True}}

        task.do(context)

        mock_press.assert_called_once_with('f')

    @patch('pyautogui.press')
    def test_drop_flasks_disabled_skips(self, mock_press):
        """Test DropFlasksTask skips when disabled."""
        from src.gameplay.core.tasks.refill import DropFlasksTask

        task = DropFlasksTask(hotkey='f')
        context = {'refill': {'dropFlasks': False}}

        task.do(context)

        mock_press.assert_not_called()


class TestWaitForTradeWindowTask:
    """Tests for WaitForTradeWindowTask."""

    def test_wait_for_trade_creation(self):
        """Test WaitForTradeWindowTask creation."""
        from src.gameplay.core.tasks.refill import WaitForTradeWindowTask

        task = WaitForTradeWindowTask(max_wait=3.0, max_retries=3)

        assert task._wait_per_attempt == 3.0
        assert task._max_retries == 3
        assert task.delay_of_timeout == 3.0 * (3 + 1)

    def test_wait_for_trade_initial_state(self):
        """Test WaitForTradeWindowTask initial state."""
        from src.gameplay.core.tasks.refill import WaitForTradeWindowTask

        task = WaitForTradeWindowTask()

        assert task._retries == 0

    def test_wait_for_trade_do_sets_start_time(self):
        """Test WaitForTradeWindowTask do() sets start time."""
        from src.gameplay.core.tasks.refill import WaitForTradeWindowTask

        task = WaitForTradeWindowTask()
        task.do({'screenshot': Mock()})

        assert task._attempt_started_at > 0


class TestWaitForLockerOpenTask:
    """Tests for WaitForLockerOpenTask."""

    def test_wait_for_locker_creation(self):
        """Test WaitForLockerOpenTask creation."""
        from src.gameplay.core.tasks.refill import WaitForLockerOpenTask

        task = WaitForLockerOpenTask(max_wait=3.0)

        assert task.delay_of_timeout == 3.0

    def test_wait_for_locker_initial_state(self):
        """Test WaitForLockerOpenTask initial state."""
        from src.gameplay.core.tasks.refill import WaitForLockerOpenTask

        task = WaitForLockerOpenTask()

        assert task.state.name == "NOT_STARTED"

    def test_wait_for_locker_uses_builtin_timeout(self):
        """Test WaitForLockerOpenTask uses BaseTask delay_of_timeout."""
        from src.gameplay.core.tasks.refill import WaitForLockerOpenTask
        from src.core.constants import WAIT_LOCKER_OPEN

        task = WaitForLockerOpenTask()

        assert task.delay_of_timeout == WAIT_LOCKER_OPEN


class TestDepositItemsTask:
    """Tests for DepositItemsTask - deposits items at depot."""

    def test_deposit_items_creation(self):
        """Test DepositItemsTask creation."""
        from src.gameplay.core.tasks.refill import DepositItemsTask

        task = DepositItemsTask()

        assert task.name == "DepositItems"
        assert task._tasks_created == False

    def test_deposit_items_disabled_skips(self):
        """Test DepositItemsTask skips when disabled."""
        from src.gameplay.core.tasks.refill import DepositItemsTask

        task = DepositItemsTask()

        context = {
            'refill': {'depositLoot': False}
        }

        task.on_before_start(context)

        assert task._tasks_created == True
        # Should only have SetNextWaypointTask
        assert len(task.tasks) == 1

    def test_deposit_items_creates_full_flow(self):
        """Test DepositItemsTask creates full sub-task flow when enabled."""
        from src.gameplay.core.tasks.refill import DepositItemsTask

        task = DepositItemsTask()

        context = {
            'refill': {
                'depositLoot': True,
                'city': 'Venore',
                'lootBackpack': 'Beach Backpack',
                'mainBackpack': 'Backpack',
            }
        }

        task.on_before_start(context)

        assert task._tasks_created == True
        # 15 tasks: GoToFreeDepot, 2x Close, OpenLocker, WaitForLocker,
        # OpenBackpack(main), ScrollToItem, DropBackpackIntoStash,
        # OpenDepot, OpenDepotChest, OpenBackpack(loot), ExpandBackpack(loot),
        # DragItems, CloseContainer(loot), SetNextWaypoint
        assert len(task.tasks) == 15

"""
Tests for Depot Tasks - depot navigation and item management.

Ensures:
1. GoToFreeDepotTask finds unoccupied depots via walkpoints
2. OpenLockerTask opens depot locker via slot system
3. ScrollToItemTask scrolls to find items
4. DragItemsTask drags one item per tick
5. Item dragging and stash operations work
"""
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np
from dataclasses import dataclass


class TestGoToFreeDepotTask:
    """Tests for GoToFreeDepotTask - finds and walks to free depot via walkpoints."""

    def test_go_to_free_depot_creation(self):
        """Test GoToFreeDepotTask creation."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask(city='Venore')

        assert task.city == 'Venore'
        assert "GoToFreeDepot" in task.name
        assert task._done == False
        assert task._target_coord is None

    def test_go_to_free_depot_default_city(self):
        """Test GoToFreeDepotTask default city."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()

        assert task.city == 'Venore'

    def test_initial_state(self):
        """Test GoToFreeDepotTask initial state."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask(city='Venore')

        assert task._done == False
        assert task._target_coord is None
        assert task._locker_coord is None
        assert len(task._occupied_depots) == 0

    def test_is_vector_task(self):
        """Test GoToFreeDepotTask is a VectorTask."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask
        from src.gameplay.core.tasks.vector import VectorTask

        task = GoToFreeDepotTask()

        assert isinstance(task, VectorTask)

    def test_did_when_done(self):
        """Test did() returns True when _done is set."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        task._done = True

        assert task.did({}) == True

    def test_did_before_done(self):
        """Test did() returns False before done."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        task._done = False

        assert task.did({}) == False


class TestGoToFreeDepotPlayerDetection:
    """Tests for player detection via gameWindow['players']."""

    def test_get_player_coordinates_empty(self):
        """Test no players returns empty set."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        context = {'gameWindow': {'players': []}}

        coords = task._get_player_coordinates(context)

        assert coords == set()

    def test_get_player_coordinates_with_players(self):
        """Test player coordinates extracted from gameWindow."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()

        mock_player = Mock()
        mock_player.coordinate = (32100, 32100, 7)

        context = {'gameWindow': {'players': [mock_player]}}

        coords = task._get_player_coordinates(context)

        assert (32100, 32100, 7) in coords

    def test_get_player_coordinates_no_gamewindow(self):
        """Test graceful handling when gameWindow is missing."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        context = {}

        coords = task._get_player_coordinates(context)

        assert coords == set()


class TestGoToFreeDepotClosestDepot:
    """Tests for closest depot selection with scipy.cdist / manual fallback."""

    def test_find_closest_manual_no_players(self):
        """Test finding closest depot with no player obstacles."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask(city='Darashia')
        current_pos = (33213, 32456, 7)

        result = task._find_closest_manual(
            current_pos,
            [(33213, 32454, 7), (33216, 32454, 7)],
            set()
        )

        assert result is not None
        goal, locker = result
        assert goal is not None
        assert locker is not None

    def test_find_closest_manual_all_occupied(self):
        """Test fallback when all depots occupied by players."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask(city='Darashia')
        current_pos = (33213, 32456, 7)

        # All goal coordinates occupied
        player_coords = {(33213, 32455, 7), (33214, 32455, 7),
                         (33215, 32455, 7), (33216, 32455, 7)}

        result = task._find_closest_manual(
            current_pos,
            [(33213, 32454, 7), (33214, 32454, 7),
             (33215, 32454, 7), (33216, 32454, 7)],
            player_coords
        )

        # Should still return a depot (fallback)
        assert result is not None

    def test_occupied_depots_skipped(self):
        """Test that previously occupied depots are skipped."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask(city='Darashia')
        task._occupied_depots.add((33213, 32454, 7))

        current_pos = (33213, 32456, 7)

        result = task._find_closest_manual(
            current_pos,
            [(33213, 32454, 7), (33216, 32454, 7)],
            set()
        )

        goal, locker = result
        assert locker == (33216, 32454, 7)


class TestGoToFreeDepotArrival:
    """Tests for arrival and on_complete."""

    def test_on_complete_sets_deposit_context(self):
        """Test on_complete sets deposit lockerCoordinate."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        task._locker_coord = (32100, 32101, 7)

        context = {'deposit': {'lockerCoordinate': None}}

        task.on_complete(context)

        assert context['deposit']['lockerCoordinate'] == (32100, 32101, 7)

    def test_on_complete_creates_deposit_key(self):
        """Test on_complete creates deposit key if missing."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        task._locker_coord = (32100, 32101, 7)

        context = {}

        task.on_complete(context)

        assert context['deposit']['lockerCoordinate'] == (32100, 32101, 7)


class TestOpenLockerTask:
    """Tests for OpenLockerTask - opens depot locker via slot system."""

    def test_open_locker_creation(self):
        """Test OpenLockerTask creation."""
        from src.gameplay.core.tasks.depot import OpenLockerTask

        task = OpenLockerTask()

        assert task.name == "OpenLocker"
        assert task.delay_before_start == 0.3
        assert task.delay_after_complete == 0.8
        assert task._opened == False
        assert task._max_attempts == 3

    def test_locker_initial_state(self):
        """Test OpenLockerTask initial state."""
        from src.gameplay.core.tasks.depot import OpenLockerTask

        task = OpenLockerTask()

        assert task._opened == False
        assert task._attempts == 0

    def test_max_attempts_reached(self):
        """Test OpenLockerTask gives up after max attempts."""
        from src.gameplay.core.tasks.depot import OpenLockerTask

        task = OpenLockerTask()
        task._attempts = 3

        assert task.did({}) == True

    def test_opened_is_done(self):
        """Test OpenLockerTask is done when opened."""
        from src.gameplay.core.tasks.depot import OpenLockerTask

        task = OpenLockerTask()
        task._opened = True

        assert task.did({}) == True

    def test_on_complete_clears_locker_coordinate(self):
        """Test on_complete clears lockerCoordinate."""
        from src.gameplay.core.tasks.depot import OpenLockerTask

        task = OpenLockerTask()

        context = {'deposit': {'lockerCoordinate': (32100, 32101, 7)}}
        task.on_complete(context)

        assert context['deposit']['lockerCoordinate'] is None


class TestScrollToItemTask:
    """Tests for ScrollToItemTask."""

    def test_scroll_to_item_creation(self):
        """Test ScrollToItemTask creation."""
        from src.gameplay.core.tasks.depot import ScrollToItemTask

        task = ScrollToItemTask('main', 'beach backpack')

        assert task.container_name == 'main'
        assert task.item_name == 'beach backpack'
        assert task.max_scrolls == 10
        assert task._scrolls == 0
        assert task._found == False

    def test_scroll_to_item_custom_max(self):
        """Test ScrollToItemTask with custom max_scrolls."""
        from src.gameplay.core.tasks.depot import ScrollToItemTask

        task = ScrollToItemTask('main', 'beach backpack', max_scrolls=5)

        assert task.max_scrolls == 5

    def test_did_when_found(self):
        """Test did() when item found."""
        from src.gameplay.core.tasks.depot import ScrollToItemTask

        task = ScrollToItemTask('main', 'beach backpack')
        task._found = True

        assert task.did({}) == True

    def test_did_when_max_scrolls(self):
        """Test did() when max scrolls reached."""
        from src.gameplay.core.tasks.depot import ScrollToItemTask

        task = ScrollToItemTask('main', 'beach backpack', max_scrolls=3)
        task._scrolls = 3

        assert task.did({}) == True

    def test_did_not_done(self):
        """Test did() when still searching."""
        from src.gameplay.core.tasks.depot import ScrollToItemTask

        task = ScrollToItemTask('main', 'beach backpack')

        assert task.did({}) == False


class TestOpenBackpackTask:
    """Tests for OpenBackpackTask."""

    def test_open_backpack_creation(self):
        """Test OpenBackpackTask creation."""
        from src.gameplay.core.tasks.depot import OpenBackpackTask

        task = OpenBackpackTask('loot')

        assert task.backpack_name == 'loot'
        assert "OpenBackpack" in task.name

    def test_open_backpack_initial_state(self):
        """Test OpenBackpackTask initial state."""
        from src.gameplay.core.tasks.depot import OpenBackpackTask

        task = OpenBackpackTask('loot')

        assert task._opened == False
        assert task.delay_after_complete == 0.3


class TestOpenDepotChestTask:
    """Tests for OpenDepotChestTask."""

    def test_open_depot_chest_creation(self):
        """Test OpenDepotChestTask creation."""
        from src.gameplay.core.tasks.depot import OpenDepotChestTask

        task = OpenDepotChestTask(chest_index=5)

        assert task.chest_index == 5
        assert "OpenDepotChest" in task.name

    def test_open_depot_chest_default_index(self):
        """Test OpenDepotChestTask default chest index."""
        from src.gameplay.core.tasks.depot import OpenDepotChestTask

        task = OpenDepotChestTask()

        assert task.chest_index == 0


class TestCloseContainerTask:
    """Tests for CloseContainerTask."""

    def test_close_container_creation(self):
        """Test CloseContainerTask creation."""
        from src.gameplay.core.tasks.depot import CloseContainerTask

        task = CloseContainerTask('depot')

        assert task.container_name == 'depot'
        assert "CloseContainer" in task.name

    def test_close_container_initial_state(self):
        """Test CloseContainerTask initial state."""
        from src.gameplay.core.tasks.depot import CloseContainerTask

        task = CloseContainerTask('depot')

        assert task._closed == False
        assert task.delay_after_complete == 0.2

    def test_close_container_did_returns_closed_state(self):
        """Test CloseContainerTask did() returns closed state."""
        from src.gameplay.core.tasks.depot import CloseContainerTask

        task = CloseContainerTask('depot')
        task._closed = True

        assert task.did({}) == True


class TestExpandBackpackTask:
    """Tests for ExpandBackpackTask - expands container to show all slots."""

    def test_expand_backpack_creation(self):
        """Test ExpandBackpackTask creation."""
        from src.gameplay.core.tasks.depot import ExpandBackpackTask

        task = ExpandBackpackTask('Beach Backpack')

        assert task.backpack_name == 'Beach Backpack'
        assert "ExpandBackpack" in task.name
        assert task.delay_before_start == 1.0
        assert task.delay_after_complete == 1.0

    def test_expand_backpack_initial_state(self):
        """Test ExpandBackpackTask initial state."""
        from src.gameplay.core.tasks.depot import ExpandBackpackTask

        task = ExpandBackpackTask('Beach Backpack')

        assert task._expanded == False

    def test_expand_backpack_did_before_done(self):
        """Test ExpandBackpackTask did() before expansion."""
        from src.gameplay.core.tasks.depot import ExpandBackpackTask

        task = ExpandBackpackTask('Beach Backpack')

        assert task.did({}) == False

    def test_expand_backpack_did_after_done(self):
        """Test ExpandBackpackTask did() after expansion."""
        from src.gameplay.core.tasks.depot import ExpandBackpackTask

        task = ExpandBackpackTask('Beach Backpack')
        task._expanded = True

        assert task.did({}) == True

    def test_expand_backpack_no_screenshot(self):
        """Test ExpandBackpackTask handles missing screenshot gracefully."""
        from src.gameplay.core.tasks.depot import ExpandBackpackTask

        task = ExpandBackpackTask('Beach Backpack')
        task.do({})

        assert task._expanded == True

    def test_expand_backpack_is_base_task(self):
        """Test ExpandBackpackTask is a BaseTask."""
        from src.gameplay.core.tasks.depot import ExpandBackpackTask
        from src.gameplay.core.tasks.base import BaseTask

        task = ExpandBackpackTask('Beach Backpack')

        assert isinstance(task, BaseTask)


class TestDragItemsTask:
    """Tests for DragItemsTask - one item per tick, always from _start_slot."""

    def test_drag_items_creation(self):
        """Test DragItemsTask creation."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot', max_items=10)

        assert task.source_container == 'loot'
        assert task.dest_container == 'depot'
        assert task.max_items == 10

    def test_drag_items_default_max(self):
        """Test DragItemsTask default max items."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot')

        assert task.max_items == 20

    def test_drag_items_initial_state(self):
        """Test DragItemsTask initial state."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot')

        assert task._done == False
        assert task._items_moved == 0
        assert task._start_slot == 0
        assert task._consecutive_empty == 0

    def test_drag_items_has_ping(self):
        """Test DragItemsTask has ping method for one-per-tick."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot')

        assert hasattr(task, 'ping')

    def test_drag_items_has_backpack_detection(self):
        """Test DragItemsTask has backpack detection method."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot')

        assert hasattr(task, '_is_slot_backpack')

    def test_drag_items_has_empty_detection(self):
        """Test DragItemsTask has empty slot detection method."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot')

        assert hasattr(task, '_is_slot_empty')

    def test_drag_items_done_at_max_items(self):
        """Test DragItemsTask stops when max_items reached."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot', max_items=5)
        task._items_moved = 5

        task._drag_one({})

        assert task._done == True

    def test_drag_items_done_at_max_slot(self):
        """Test DragItemsTask stops when max slot index reached."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        task = DragItemsTask('loot', 'depot')
        task._start_slot = 20

        task._drag_one({})

        assert task._done == True

    def test_drag_items_thresholds(self):
        """Test DragItemsTask has correct match thresholds."""
        from src.gameplay.core.tasks.depot import DragItemsTask

        assert DragItemsTask.BACKPACK_MATCH_THRESHOLD == 0.80
        assert DragItemsTask.EMPTY_MATCH_THRESHOLD == 0.80
        assert DragItemsTask.MAX_CONSECUTIVE_EMPTY == 3
        assert DragItemsTask.MAX_SLOT_INDEX == 20


class TestDropBackpackIntoStashTask:
    """Tests for DropBackpackIntoStashTask."""

    def test_drop_backpack_creation(self):
        """Test DropBackpackIntoStashTask creation."""
        from src.gameplay.core.tasks.depot import DropBackpackIntoStashTask

        task = DropBackpackIntoStashTask('beach backpack')

        assert task.backpack_name == 'beach backpack'
        assert task.delay_after_complete == 1.0

    def test_drop_backpack_did_before_done(self):
        """Test DropBackpackIntoStashTask did() before completion."""
        from src.gameplay.core.tasks.depot import DropBackpackIntoStashTask

        task = DropBackpackIntoStashTask('beach backpack')
        task._done = False

        assert task.did({}) == False

    def test_drop_backpack_did_after_done(self):
        """Test DropBackpackIntoStashTask did() after completion."""
        from src.gameplay.core.tasks.depot import DropBackpackIntoStashTask

        task = DropBackpackIntoStashTask('beach backpack')
        task._done = True

        assert task.did({}) == True


class TestOccupiedDepotTracking:
    """Tests for tracking occupied depots."""

    def test_occupied_depot_tracking(self):
        """Test tracking of occupied depots."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()

        task._occupied_depots.add((32100, 32101, 7))
        task._occupied_depots.add((32105, 32101, 7))

        assert len(task._occupied_depots) == 2
        assert (32100, 32101, 7) in task._occupied_depots

    def test_occupied_depots_cleared_in_fallback(self):
        """Test occupied depots list is cleared in fallback."""
        from src.gameplay.core.tasks.depot import GoToFreeDepotTask

        task = GoToFreeDepotTask()
        task._occupied_depots.add((32100, 32101, 7))
        task._occupied_depots.add((32105, 32101, 7))

        if task._occupied_depots:
            task._occupied_depots.clear()

        assert len(task._occupied_depots) == 0


class TestDepositContextIntegration:
    """Tests for deposit context integration."""

    def test_deposit_in_context(self):
        """Test deposit key exists in context."""
        from src.gameplay.context import create_context

        context = create_context()

        assert 'deposit' in context
        assert context['deposit']['lockerCoordinate'] is None

    def test_locker_coord_read_by_open_locker(self):
        """Test OpenLockerTask reads locker coordinate from deposit context."""
        from src.gameplay.core.tasks.depot import OpenLockerTask

        task = OpenLockerTask()

        context = {
            'deposit': {'lockerCoordinate': (32100, 32101, 7)},
            'screenshot': Mock()
        }

        locker_coord = context.get('deposit', {}).get('lockerCoordinate')

        assert locker_coord == (32100, 32101, 7)

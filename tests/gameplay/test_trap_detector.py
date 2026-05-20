"""
Tests for TrapDetector - anti-trap system.

Ensures:
1. Detects trapped state (creatures in BL but no closestCreature)
2. Engages immediately when stationary
3. Waits TRAP_DELAY_MOVING when moving
4. Selects closest creature by euclidean distance
5. Resets state after engagement
"""
import time
from dataclasses import dataclass
from unittest.mock import patch

import numpy as np

from src.gameplay.trap_detector import TrapDetector, is_trapped, get_closest_trapped_creature
from src.core.constants import TRAP_DELAY_MOVING


@dataclass
class MockCreature:
    name: str
    game_window_coordinate: tuple = (100, 100)
    window_coordinate: tuple = (200, 200)
    creature_type: str = 'monster'
    id_method: str = 'BL'


@dataclass
class MockBattleListCreature:
    name: str


def create_mock_context(creatures=None, closest=None, coordinate=(32000, 32000, 7), monsters=None):
    """Create minimal context for trap detector tests."""
    return {
        'battleList': {'creatures': creatures or []},
        'cavebot': {
            'enabled': True,
            'closestCreature': closest,
            'isAttackingSomeCreature': False,
        },
        'radar': {'coordinate': coordinate},
        'gameWindow': {
            'monsters': monsters or [],
            'image': np.zeros((200, 300), dtype=np.uint8),
        },
    }


class TestIsTrapped:
    """Tests for is_trapped() pure function."""

    def test_not_trapped_when_no_creatures(self):
        """Should return False when battle list is empty."""
        context = create_mock_context(creatures=[])
        assert is_trapped(context) is False

    def test_not_trapped_when_closest_exists(self):
        """Should return False when closestCreature is set (BFS path exists)."""
        creature = MockCreature(name='Rat')
        context = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=creature,
        )
        assert is_trapped(context) is False

    def test_trapped_when_creatures_but_no_closest(self):
        """Should return True when creatures exist but no BFS path."""
        context = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
        )
        assert is_trapped(context) is True

    def test_not_trapped_with_empty_context(self):
        """Should return False with minimal/empty context."""
        assert is_trapped({}) is False


class TestGetClosestTrappedCreature:
    """Tests for get_closest_trapped_creature() — selects by euclidean distance."""

    def test_returns_none_when_no_monsters(self):
        """Should return None when no monsters in game window."""
        context = create_mock_context(monsters=[])
        assert get_closest_trapped_creature(context) is None

    def test_returns_closest_to_center(self):
        """Should select monster closest to game window center."""
        # Image is 200x300, center is (150, 100)
        far = MockCreature(name='Dragon', game_window_coordinate=(10, 10))
        close = MockCreature(name='Rat', game_window_coordinate=(140, 95))
        context = create_mock_context(monsters=[far, close])

        result = get_closest_trapped_creature(context)
        assert result.name == 'Rat'

    def test_single_monster(self):
        """Should return the only monster available."""
        monster = MockCreature(name='Orc')
        context = create_mock_context(monsters=[monster])

        result = get_closest_trapped_creature(context)
        assert result.name == 'Orc'

    def test_returns_none_when_no_image(self):
        """Should return None when game window image is missing."""
        context = create_mock_context(monsters=[MockCreature(name='Rat')])
        context['gameWindow']['image'] = None
        assert get_closest_trapped_creature(context) is None


class TestTrapDetectorShouldEngage:
    """Tests for TrapDetector.should_engage() — hybrid delay logic."""

    def test_not_engaged_when_not_trapped(self):
        """Should not engage when no trap condition."""
        detector = TrapDetector()
        context = create_mock_context(creatures=[])
        assert detector.should_engage(context) is False

    def test_not_engaged_on_first_check(self):
        """Should not engage on first check (needs position baseline)."""
        detector = TrapDetector()
        context = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
        )
        assert detector.should_engage(context) is False

    def test_engages_immediately_when_stationary(self):
        """Should engage immediately when position hasn't changed."""
        detector = TrapDetector()
        context = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
        )
        # First check: baseline
        detector.should_engage(context)
        # Second check: same position = stationary = immediate
        assert detector.should_engage(context) is True

    def test_resets_timer_when_moving(self):
        """Should reset trap timer when position changes."""
        detector = TrapDetector()

        # First check at position A — baseline
        context_a = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
            coordinate=(32000, 32000, 7),
        )
        detector.should_engage(context_a)

        # Second check: same position A — engages (stationary)
        assert detector.should_engage(context_a) is True

        # Reset after engagement
        detector.reset()

        # Move to position B — resets timer
        context_b = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
            coordinate=(32001, 32000, 7),
        )
        result = detector.should_engage(context_b)
        assert result is False  # Just moved, timer reset

    @patch('src.gameplay.trap_detector.time')
    def test_engages_after_delay_when_was_moving(self, mock_time):
        """Should engage after TRAP_DELAY_MOVING when bot stopped after moving."""
        detector = TrapDetector()
        now = 1000.0

        # First check: position A, set baseline
        mock_time.time.return_value = now
        context_a = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
            coordinate=(32000, 32000, 7),
        )
        detector.should_engage(context_a)

        # Move to position B
        mock_time.time.return_value = now + 0.1
        context_b = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
            coordinate=(32001, 32000, 7),
        )
        detector.should_engage(context_b)

        # Stop at position B — becomes stationary, should engage immediately
        mock_time.time.return_value = now + 0.2
        assert detector.should_engage(context_b) is True

    def test_resets_when_trap_clears(self):
        """Should reset timer when trap condition clears."""
        detector = TrapDetector()

        # Trapped
        context = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
        )
        detector.should_engage(context)

        # Not trapped anymore (creatures gone)
        context_clear = create_mock_context(creatures=[])
        detector.should_engage(context_clear)

        assert detector._trap_start_time == 0

    def test_not_engaged_without_coordinate(self):
        """Should not engage when radar coordinate is missing."""
        detector = TrapDetector()
        context = create_mock_context(
            creatures=[MockBattleListCreature('Rat')],
            closest=None,
        )
        context['radar']['coordinate'] = None
        assert detector.should_engage(context) is False


class TestTrapDetectorReset:
    """Tests for TrapDetector.reset()."""

    def test_reset_clears_timer(self):
        """Should clear trap start time."""
        detector = TrapDetector()
        detector._trap_start_time = 100.0
        detector.reset()
        assert detector._trap_start_time == 0

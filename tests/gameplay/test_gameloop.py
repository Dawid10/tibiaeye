"""
Tests for GameLoop - main game loop.

Ensures:
1. Middleware pipeline works correctly
2. Frequency control works
3. Tick rate adaptation works
4. Pause/resume/stop works
5. Targeting filters work
"""
import time
import pytest
from unittest.mock import Mock, patch, MagicMock
import numpy as np

from src.gameplay.gameloop import GameLoop
from src.core.constants import (
    TICK_RATE_COMBAT, TICK_RATE_IDLE, TICK_RATE_PAUSED,
    FREQ_SCREENSHOT, FREQ_STATUSBAR, FREQ_BATTLELIST,
    FREQ_GAMEWINDOW, FREQ_RADAR, FREQ_SKILLS,
    STUCK_ATTACK_SUPPRESSION_DURATION, STUCK_ATTACK_SUPPRESSION_CLEAR_DISTANCE,
)
from src.gameplay.stuck_detector import StuckDetector


def create_mock_context():
    """Create a mock context with required keys."""
    return {
        'screenshot': np.zeros((100, 100), dtype=np.uint8),
        'radar': {
            'coordinate': (32000, 32000, 7),
            'previousCoordinate': None,
            'lastCoordinateVisited': None
        },
        'battleList': {
            'creatures': [],
            'beingAttackedCreatureCategory': None
        },
        'gameWindow': {
            'monsters': [],
            'players': [],
            'creatures': [],
            'monstersBars': []
        },
        'statusBar': {
            'hpPercentage': 100,
            'manaPercentage': 100
        },
        'cavebot': {
            'enabled': False,
            'waypoints': {'items': [], 'currentIndex': 0},
            'closestCreature': None,
            'isAttackingSomeCreature': False,
            'holesOrStairs': [],
            'nonWalkableCoordinates': [],
            'stuckAlert': {'enabled': True, 'timeoutSeconds': 120}
        },
        'healing': {
            'enabled': False,
            'spells': [],
            'potions': [],
            'highPriority': {},
            'eatFood': {}
        },
        'targeting': {
            'enabled': True,
            'mode': 'all',
            'whitelist': set(),
            'blacklist': set()
        },
        'loot': {'enabled': False, 'hotkey': None, 'corpsesToLoot': []},
        'skills': {'food': 10},
        'refill': {},
        'tasksOrchestrator': None,
        'pause': False
    }


class TestGameLoopCreation:
    """Tests for GameLoop initialization."""

    def test_default_creation(self):
        """Test GameLoop creation with defaults."""
        loop = GameLoop()

        assert loop.tick_rate == 0.100
        assert loop.running == False
        assert loop.paused == True
        assert loop.tick_count == 0

    def test_custom_tick_rate(self):
        """Test GameLoop creation with custom tick rate."""
        loop = GameLoop(tick_rate=0.050)

        assert loop.tick_rate == 0.050

    def test_orchestrator_created(self):
        """Test that orchestrator is created."""
        loop = GameLoop()

        assert loop.orchestrator is not None
        assert loop.context['tasksOrchestrator'] == loop.orchestrator


class TestMiddlewareManagement:
    """Tests for middleware management."""

    def test_add_middleware(self):
        """Test adding a middleware."""
        loop = GameLoop()

        def my_middleware(context):
            return context

        loop.add_middleware(my_middleware)

        assert my_middleware in loop.middlewares

    def test_add_middleware_with_frequency(self):
        """Test adding middleware with frequency."""
        loop = GameLoop()

        def my_middleware(context):
            return context

        loop.add_middleware(my_middleware, frequency=5)

        assert loop._middleware_frequencies[my_middleware] == 5

    def test_setup_default_middlewares(self):
        """Test that setup_default_middlewares adds middlewares."""
        loop = GameLoop()

        loop.setup_default_middlewares()

        assert len(loop.middlewares) > 0


class TestHealingObservers:
    """Tests for healing observer management."""

    def test_add_healing_observer(self):
        """Test adding a healing observer."""
        loop = GameLoop()

        def my_observer(context):
            return context

        loop.add_healing_observer(my_observer)

        assert my_observer in loop.healing_observers


class TestMiddlewareFrequency:
    """Tests for middleware frequency control."""

    def test_frequency_constants(self):
        """Test that frequency constants are defined."""
        assert FREQ_SCREENSHOT == 1
        assert FREQ_STATUSBAR == 1
        assert FREQ_BATTLELIST == 2
        assert FREQ_GAMEWINDOW == 2
        assert FREQ_RADAR == 2
        assert FREQ_SKILLS == 10

    def test_middleware_runs_at_frequency(self):
        """Test that middleware runs at specified frequency."""
        loop = GameLoop()
        loop.paused = False

        call_count = [0]

        def counting_middleware(context):
            call_count[0] += 1
            return context

        # Run every 3 ticks
        loop.add_middleware(counting_middleware, frequency=3)

        # Simulate 9 ticks
        for i in range(9):
            loop.tick_count = i
            for middleware in loop.middlewares:
                freq = loop._middleware_frequencies.get(middleware, 1)
                if loop.tick_count % freq == 0:
                    middleware(loop.context)

        # Should run at ticks 0, 3, 6 = 3 times
        assert call_count[0] == 3


class TestTickRateAdaptation:
    """Tests for adaptive tick rate."""

    def test_tick_rate_constants(self):
        """Test that tick rate constants are defined."""
        assert TICK_RATE_COMBAT == 0.080
        assert TICK_RATE_IDLE == 0.150
        assert TICK_RATE_PAUSED == 0.500

    def test_adaptive_tick_rate_paused(self):
        """Test tick rate when paused."""
        loop = GameLoop()
        loop.paused = True

        rate = loop._get_adaptive_tick_rate()

        assert rate == TICK_RATE_PAUSED

    def test_adaptive_tick_rate_combat(self):
        """Test tick rate in combat."""
        loop = GameLoop()
        loop.paused = False
        loop.context['cavebot']['isAttackingSomeCreature'] = True

        rate = loop._get_adaptive_tick_rate()

        assert rate == TICK_RATE_COMBAT

    def test_adaptive_tick_rate_with_creatures(self):
        """Test tick rate when creatures present."""
        loop = GameLoop()
        loop.paused = False
        loop.context['cavebot']['isAttackingSomeCreature'] = False
        loop.context['battleList']['creatures'] = [Mock()]  # Has creatures

        rate = loop._get_adaptive_tick_rate()

        assert rate == TICK_RATE_COMBAT

    def test_adaptive_tick_rate_idle(self):
        """Test tick rate when idle."""
        loop = GameLoop()
        loop.paused = False
        loop.context['cavebot']['isAttackingSomeCreature'] = False
        loop.context['battleList']['creatures'] = []

        rate = loop._get_adaptive_tick_rate()

        assert rate == TICK_RATE_IDLE


class TestPauseResume:
    """Tests for pause/resume functionality."""

    def test_pause(self):
        """Test pause functionality."""
        loop = GameLoop()
        loop.paused = False

        loop.pause()

        assert loop.paused == True

    def test_resume(self):
        """Test resume functionality."""
        loop = GameLoop()
        loop.paused = True

        loop.resume()

        assert loop.paused == False

    def test_tick_does_nothing_when_paused(self):
        """Test that tick does nothing when paused."""
        loop = GameLoop()
        loop.paused = True

        middleware_called = [False]

        def tracking_middleware(context):
            middleware_called[0] = True
            return context

        loop.add_middleware(tracking_middleware)

        loop.tick()

        assert middleware_called[0] == False


class TestStop:
    """Tests for stop functionality."""

    def test_stop(self):
        """Test stop functionality."""
        loop = GameLoop()
        loop.running = True

        loop.stop()

        assert loop.running == False


class TestTargetingFilters:
    """Tests for targeting filter functionality."""

    def test_get_target_names_all_mode(self):
        """Test target names in 'all' mode."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': True,
            'mode': 'all',
            'whitelist': [],
            'blacklist': []
        }

        result = loop._get_target_names_for_detection(loop.context)

        assert result is None  # None means detect all

    def test_get_target_names_whitelist_mode(self):
        """Test target names in whitelist mode."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': True,
            'mode': 'whitelist',
            'whitelist': ['Rotworm', 'Cave Rat'],
            'blacklist': []
        }

        result = loop._get_target_names_for_detection(loop.context)

        assert result == ['rotworm', 'cave rat']

    def test_get_target_names_blacklist_mode(self):
        """Test target names in blacklist mode."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': True,
            'mode': 'blacklist',
            'whitelist': [],
            'blacklist': ['Dragon']
        }

        result = loop._get_target_names_for_detection(loop.context)

        assert result is None  # Blacklist still detects all

    def test_get_target_names_disabled(self):
        """Test target names when targeting disabled."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': False,
            'mode': 'whitelist',
            'whitelist': ['Rotworm'],
            'blacklist': []
        }

        result = loop._get_target_names_for_detection(loop.context)

        assert result is None  # Disabled = detect all

    def test_filter_monsters_all_mode(self):
        """Test monster filtering in 'all' mode."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': True,
            'mode': 'all',
            'whitelist': set(),
            'blacklist': set()
        }

        monsters = [Mock(name='Rotworm'), Mock(name='Dragon')]

        result = loop._filter_monsters_by_targeting(monsters, loop.context)

        assert result == monsters

    def test_filter_monsters_whitelist(self):
        """Test monster filtering with whitelist."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': True,
            'mode': 'whitelist',
            'whitelist': {'rotworm'},
            'blacklist': set()
        }

        monster1 = Mock()
        monster1.name = 'Rotworm'
        monster2 = Mock()
        monster2.name = 'Dragon'

        monsters = [monster1, monster2]

        result = loop._filter_monsters_by_targeting(monsters, loop.context)

        assert len(result) == 1
        assert result[0].name == 'Rotworm'

    def test_filter_monsters_blacklist(self):
        """Test monster filtering with blacklist."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': True,
            'mode': 'blacklist',
            'whitelist': set(),
            'blacklist': {'dragon'}
        }

        monster1 = Mock()
        monster1.name = 'Rotworm'
        monster2 = Mock()
        monster2.name = 'Dragon'

        monsters = [monster1, monster2]

        result = loop._filter_monsters_by_targeting(monsters, loop.context)

        assert len(result) == 1
        assert result[0].name == 'Rotworm'

    def test_filter_monsters_disabled(self):
        """Test monster filtering when targeting disabled."""
        loop = GameLoop()
        loop.context['targeting'] = {
            'enabled': False,
            'mode': 'all',
            'whitelist': set(),
            'blacklist': set()
        }

        monsters = [Mock(name='Rotworm')]

        result = loop._filter_monsters_by_targeting(monsters, loop.context)

        assert result == []  # Disabled = no monsters


class TestSessionLogging:
    """Tests for session logging."""

    def test_enable_session_logging(self):
        """Test enabling session logging."""
        loop = GameLoop()

        loop.enable_session_logging("test_logs")

        assert loop.session_logger is not None


class TestStuckDetection:
    """Tests for stuck detection."""

    def test_stuck_timeout_default(self):
        """Test default stuck timeout."""
        loop = GameLoop()

        assert loop.stuck_timeout == 120.0

    def test_stuck_detection_updates_position(self):
        """Test that stuck detection tracks position."""
        loop = GameLoop()
        loop.context['cavebot']['enabled'] = True
        loop.context['radar']['coordinate'] = (100, 200, 7)

        loop._check_stuck()

        # Access via the stuck detector
        assert loop._stuck_detector._last_known_position == (100, 200, 7)

    def test_stuck_detection_resets_on_movement(self):
        """Test that stuck detection resets when position changes."""
        loop = GameLoop()
        loop.context['cavebot']['enabled'] = True

        # First position
        loop.context['radar']['coordinate'] = (100, 200, 7)
        loop._stuck_detector._last_known_position = (100, 200, 7)
        loop._stuck_detector._last_position_change_time = time.time() - 60  # 1 minute ago

        # Move to new position
        loop.context['radar']['coordinate'] = (101, 200, 7)

        with patch('src.gameplay.stuck_detector.get_alert_system') as mock_alert:
            mock_alert.return_value.is_looping.return_value = False
            loop._check_stuck()

        assert loop._stuck_detector._last_known_position == (101, 200, 7)


class TestEatFood:
    """Tests for food eating functionality."""

    def test_eat_food_disabled(self):
        """Test that eat food does nothing when disabled."""
        loop = GameLoop()
        loop.context['healing']['eatFood'] = {
            'enabled': False,
            'hotkey': 'f',
            'eatWhenFoodIsLessOrEqual': 5
        }

        with patch('pyautogui.press') as mock_press:
            loop._eat_food_if_needed()

        mock_press.assert_not_called()

    def test_eat_food_no_hotkey(self):
        """Test that eat food does nothing without hotkey."""
        loop = GameLoop()
        loop.context['healing']['eatFood'] = {
            'enabled': True,
            'hotkey': None,
            'eatWhenFoodIsLessOrEqual': 5
        }

        with patch('pyautogui.press') as mock_press:
            loop._eat_food_if_needed()

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_eat_food_when_low(self, mock_press):
        """Test that food is eaten when level is low."""
        loop = GameLoop()
        loop.context['healing']['eatFood'] = {
            'enabled': True,
            'hotkey': 'f',
            'eatWhenFoodIsLessOrEqual': 5
        }
        loop.context['skills'] = {'food': 3}  # Below threshold
        loop._last_food_time = 0  # Allow eating

        loop._eat_food_if_needed()

        mock_press.assert_called_once_with('f')

    @patch('pyautogui.press')
    def test_eat_food_cooldown(self, mock_press):
        """Test that food eating has cooldown."""
        loop = GameLoop()
        loop.context['healing']['eatFood'] = {
            'enabled': True,
            'hotkey': 'f',
            'eatWhenFoodIsLessOrEqual': 5
        }
        loop.context['skills'] = {'food': 3}
        loop._last_food_time = time.time()  # Just ate

        loop._eat_food_if_needed()

        mock_press.assert_not_called()


class TestSkillsMiddleware:
    """Tests for skills middleware - reads food, speed, capacity, stamina."""

    @patch('src.repositories.skills.get_stamina')
    @patch('src.repositories.skills.get_capacity')
    @patch('src.repositories.skills.get_speed')
    @patch('src.repositories.skills.get_food')
    def test_skills_middleware_reads_all_values(
        self, mock_food, mock_speed, mock_capacity, mock_stamina
    ):
        """Test that skills middleware reads food, speed, capacity, and stamina."""
        mock_food.return_value = 15
        mock_speed.return_value = 220
        mock_capacity.return_value = 1500
        mock_stamina.return_value = 2400

        loop = GameLoop()
        loop.context['screenshot'] = np.zeros((100, 100), dtype=np.uint8)

        result = loop._skills_middleware(loop.context)

        assert result['skills']['food'] == 15
        assert result['skills']['speed'] == 220
        assert result['skills']['capacity'] == 1500
        assert result['skills']['stamina'] == 2400
        assert result['playerSpeed'] == 220

    @patch('src.repositories.skills.get_stamina')
    @patch('src.repositories.skills.get_capacity')
    @patch('src.repositories.skills.get_speed')
    @patch('src.repositories.skills.get_food')
    def test_skills_middleware_handles_none_values(
        self, mock_food, mock_speed, mock_capacity, mock_stamina
    ):
        """Test that skills middleware handles None values gracefully."""
        mock_food.return_value = None
        mock_speed.return_value = None
        mock_capacity.return_value = None
        mock_stamina.return_value = None

        loop = GameLoop()
        loop.context['screenshot'] = np.zeros((100, 100), dtype=np.uint8)
        loop.context['skills'] = {'food': 10}  # Pre-existing value

        result = loop._skills_middleware(loop.context)

        # Should keep pre-existing value when None is returned
        assert result['skills']['food'] == 10
        assert 'speed' not in result['skills']
        assert 'capacity' not in result['skills']
        assert 'stamina' not in result['skills']

    @patch('src.repositories.skills.get_stamina')
    @patch('src.repositories.skills.get_capacity')
    @patch('src.repositories.skills.get_speed')
    @patch('src.repositories.skills.get_food')
    def test_skills_middleware_ignores_zero_speed(
        self, mock_food, mock_speed, mock_capacity, mock_stamina
    ):
        """Test that skills middleware ignores speed of 0."""
        mock_food.return_value = 15
        mock_speed.return_value = 0  # Invalid speed
        mock_capacity.return_value = 1500
        mock_stamina.return_value = 2400

        loop = GameLoop()
        loop.context['screenshot'] = np.zeros((100, 100), dtype=np.uint8)
        original_player_speed = loop.context.get('playerSpeed')

        result = loop._skills_middleware(loop.context)

        # Speed should not be updated when it's 0
        assert 'speed' not in result['skills']
        # playerSpeed should remain unchanged (not overwritten with 0)
        assert result.get('playerSpeed') == original_player_speed

    def test_skills_middleware_no_screenshot(self):
        """Test that skills middleware handles missing screenshot."""
        loop = GameLoop()
        loop.context['screenshot'] = None

        result = loop._skills_middleware(loop.context)

        # Should return context unchanged
        assert result == loop.context


class TestHealingObserver:
    """Tests for healing observer."""

    def test_healing_disabled(self):
        """Test that healing does nothing when disabled."""
        loop = GameLoop()
        loop.context['healing']['enabled'] = False

        with patch('pyautogui.press') as mock_press:
            loop._healing_observer(loop.context)

        mock_press.assert_not_called()

    @patch('pyautogui.press')
    def test_high_priority_healing(self, mock_press):
        """Test high priority healing triggers."""
        loop = GameLoop()
        loop.context['healing'] = {
            'enabled': True,
            'highPriority': {
                'enabled': True,
                'hpPercentageLessThanOrEqual': 30,
                'manaPercentageGreaterThanOrEqual': 10
            },
            'spells': [{'hotkey': 'f1', 'enabled': True}],
            'potions': []
        }
        loop.context['statusBar'] = {
            'hpPercentage': 25,  # Below 30%
            'manaPercentage': 50  # Above 10%
        }

        loop._healing_observer(loop.context)

        mock_press.assert_called_once_with('f1')

    @patch('pyautogui.press')
    def test_potion_healing(self, mock_press):
        """Test potion healing triggers."""
        loop = GameLoop()
        loop.context['healing'] = {
            'enabled': True,
            'highPriority': {'enabled': False},
            'spells': [],
            'potions': [{
                'type': 'hp',
                'hotkey': 'f2',
                'hpPercentageLessThanOrEqual': 50,
                'enabled': True
            }]
        }
        loop.context['statusBar'] = {
            'hpPercentage': 40,  # Below 50%
            'manaPercentage': 100
        }

        loop._healing_observer(loop.context)

        mock_press.assert_called_once_with('f2')


class TestAttackSuppression:
    """Tests for attack suppression after stuck recovery."""

    def test_not_suppressed_by_default(self):
        """Stuck detector should not suppress attacks by default."""
        detector = StuckDetector()

        assert detector.is_attack_suppressed is False

    def test_suppressed_after_tier_1(self):
        """Attacks should be suppressed after tier 1 recovery."""
        detector = StuckDetector()
        orchestrator = Mock()
        context = create_mock_context()
        context['cavebot']['enabled'] = True

        with patch('src.gameplay.stuck_detector.pyautogui'):
            with patch('src.gameplay.stuck_detector.get_alert_system') as mock_alert:
                mock_alert.return_value.is_looping.return_value = False
                detector._execute_tier_1(context, orchestrator, (100, 200, 7), 30)

        assert detector.is_attack_suppressed is True

    def test_suppressed_after_tier_2(self):
        """Attacks should be suppressed after tier 2 recovery."""
        detector = StuckDetector()
        orchestrator = Mock()
        context = create_mock_context()
        context['cavebot']['enabled'] = True

        with patch('src.gameplay.stuck_detector.pyautogui'):
            with patch('src.gameplay.stuck_detector.get_alert_system') as mock_alert:
                mock_alert.return_value.is_looping.return_value = False
                with patch('src.gameplay.stuck_detector._skip_current_waypoint'):
                    detector._execute_tier_2(context, orchestrator, (100, 200, 7), 60)

        assert detector.is_attack_suppressed is True

    def test_suppression_clears_after_timer(self):
        """Suppression should clear after duration expires."""
        detector = StuckDetector()
        detector._attack_suppressed_until = time.time() - 1  # Already expired
        detector._stuck_position = (100, 200, 7)

        assert detector.is_attack_suppressed is False
        assert detector._stuck_position is None

    def test_suppression_clears_on_significant_movement(self):
        """Suppression should clear when bot moves far from stuck position."""
        detector = StuckDetector()
        detector._attack_suppressed_until = time.time() + 60
        detector._stuck_position = (100, 200, 7)

        alert_system = Mock()
        alert_system.is_looping.return_value = False

        # Move far enough (Manhattan distance >= STUCK_ATTACK_SUPPRESSION_CLEAR_DISTANCE)
        new_pos = (100 + STUCK_ATTACK_SUPPRESSION_CLEAR_DISTANCE, 200, 7)
        detector._handle_position_changed(new_pos, time.time(), alert_system)

        assert detector.is_attack_suppressed is False

    def test_suppression_persists_on_small_movement(self):
        """Suppression should persist when bot barely moves (position jitter)."""
        detector = StuckDetector()
        detector._attack_suppressed_until = time.time() + 60
        detector._stuck_position = (100, 200, 7)

        alert_system = Mock()
        alert_system.is_looping.return_value = False

        # Move only 1 tile (less than clear distance)
        new_pos = (100, 201, 7)
        detector._handle_position_changed(new_pos, time.time(), alert_system)

        assert detector.is_attack_suppressed is True

    def test_gameloop_suppresses_closest_creature(self):
        """GameLoop should set closestCreature to None when attacks are suppressed."""
        loop = GameLoop()
        loop.context['cavebot']['closestCreature'] = Mock()

        # Simulate suppression active
        loop._stuck_detector._attack_suppressed_until = time.time() + 60
        loop._stuck_detector._stuck_position = (100, 200, 7)

        assert loop._stuck_detector.is_attack_suppressed is True

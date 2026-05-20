"""Tests for TileFrictionCalculator."""
import pytest

from src.repositories.radar.friction import (
    TileFrictionCalculator,
    _find_closest_friction,
    _calculate_speed_tier,
    DEFAULT_FRICTION,
    DEFAULT_MOVEMENT_TIME_MS,
)


class TestTileFrictionCalculator:
    """Test cases for TileFrictionCalculator class."""

    @pytest.fixture
    def calculator(self):
        return TileFrictionCalculator()

    def test_normal_tile_friction_base_speed(self, calculator):
        """Test movement time on normal tile with base speed."""
        time = calculator.get_movement_time(110, 100)
        assert 200 <= time <= 500

    def test_sand_tile_slower_than_normal(self, calculator):
        """Test that sand (friction 150) is slower than normal (friction 100)."""
        normal_time = calculator.get_movement_time(110, 100)
        sand_time = calculator.get_movement_time(110, 150)
        assert sand_time >= normal_time

    def test_ice_tile_faster_than_normal(self, calculator):
        """Test that ice (friction 70) is faster than normal (friction 100)."""
        normal_time = calculator.get_movement_time(150, 100)
        ice_time = calculator.get_movement_time(150, 70)
        assert ice_time <= normal_time

    def test_high_speed_faster_than_low_speed(self, calculator):
        """Test that higher player speed results in faster movement."""
        slow = calculator.get_movement_time(100, 100)
        fast = calculator.get_movement_time(200, 100)
        assert fast <= slow

    def test_unknown_friction_uses_closest(self, calculator):
        """Test that unknown friction values use the closest known value."""
        time_105 = calculator.get_movement_time(110, 105)
        time_100 = calculator.get_movement_time(110, 100)
        assert time_105 == time_100

    def test_zero_speed_returns_default(self, calculator):
        """Test that zero speed returns default movement time."""
        time = calculator.get_movement_time(0, 100)
        assert time == DEFAULT_MOVEMENT_TIME_MS

    def test_negative_speed_returns_default(self, calculator):
        """Test that negative speed returns default movement time."""
        time = calculator.get_movement_time(-50, 100)
        assert time == DEFAULT_MOVEMENT_TIME_MS

    def test_get_movement_time_seconds(self, calculator):
        """Test that seconds conversion is correct."""
        time_ms = calculator.get_movement_time(110, 100)
        time_s = calculator.get_movement_time_seconds(110, 100)
        assert abs(time_s - time_ms / 1000.0) < 0.001

    def test_very_high_speed_minimum_time(self, calculator):
        """Test that very high speed produces minimum movement time."""
        time = calculator.get_movement_time(2000, 100)
        assert time <= 100

    def test_very_low_speed_has_valid_time(self, calculator):
        """Test that very low speed produces valid movement time."""
        time = calculator.get_movement_time(10, 100)
        assert 50 <= time <= 850

    def test_all_friction_values_work(self, calculator):
        """Test that all known friction values produce valid times."""
        friction_values = [70, 90, 95, 100, 110, 125, 140, 150, 160, 200, 250]
        for friction in friction_values:
            time = calculator.get_movement_time(110, friction)
            assert 50 <= time <= 850

    def test_swamp_very_slow(self, calculator):
        """Test that swamp terrain (friction 160) is very slow."""
        normal_time = calculator.get_movement_time(110, 100)
        swamp_time = calculator.get_movement_time(110, 160)
        assert swamp_time >= normal_time

    def test_energy_field_slowest(self, calculator):
        """Test that energy field (friction 250) is the slowest terrain."""
        normal_time = calculator.get_movement_time(110, 100)
        energy_time = calculator.get_movement_time(110, 250)
        assert energy_time >= normal_time


class TestFindClosestFriction:
    """Test cases for _find_closest_friction helper."""

    def test_exact_match(self):
        """Test that exact matches return the same value."""
        assert _find_closest_friction(100) == 100
        assert _find_closest_friction(70) == 70
        assert _find_closest_friction(250) == 250

    def test_between_values_rounds_to_closest(self):
        """Test that values between frictions round to closest."""
        assert _find_closest_friction(105) == 100
        assert _find_closest_friction(115) == 110
        assert _find_closest_friction(85) == 90

    def test_below_minimum_rounds_to_minimum(self):
        """Test that values below minimum round up to 70."""
        assert _find_closest_friction(50) == 70
        assert _find_closest_friction(1) == 70

    def test_above_maximum_rounds_to_maximum(self):
        """Test that values above maximum round down to 250."""
        assert _find_closest_friction(300) == 250
        assert _find_closest_friction(1000) == 250


class TestCalculateSpeedTier:
    """Test cases for _calculate_speed_tier helper."""

    def test_minimum_speed_has_valid_tier(self):
        """Test that very low speed results in valid tier based on breakpoints."""
        tier = _calculate_speed_tier(1, 100)
        assert tier >= 1

    def test_high_speed_high_tier(self):
        """Test that high speed results in high tier."""
        tier = _calculate_speed_tier(500, 100)
        assert tier >= 10

    def test_tier_never_zero(self):
        """Test that tier is always at least 1."""
        tier = _calculate_speed_tier(0, 100)
        assert tier >= 1


class TestGetTileFriction:
    """Test cases for get_tile_friction method."""

    @pytest.fixture
    def calculator(self):
        return TileFrictionCalculator()

    def test_none_coordinate_returns_default(self, calculator):
        """Test that None coordinate returns default friction."""
        friction = calculator.get_tile_friction(None)
        assert friction == DEFAULT_FRICTION

    def test_valid_coordinate_returns_friction(self, calculator):
        """Test that valid coordinates return a friction value."""
        coord = (32000, 31000, 7)
        friction = calculator.get_tile_friction(coord)
        assert friction > 0


class TestWalkTaskIntegration:
    """Integration tests for WalkTask with friction system."""

    def test_walk_task_has_friction_calculator(self):
        """Test that WalkTask has a friction calculator."""
        from src.gameplay.core.tasks.common import WalkTask
        task = WalkTask('up')
        assert hasattr(task, '_friction_calculator')
        assert isinstance(task._friction_calculator, TileFrictionCalculator)

    def test_walk_task_calculates_destination(self):
        """Test that WalkTask correctly calculates destination coordinate."""
        from src.gameplay.core.tasks.common import WalkTask

        task = WalkTask('up')
        context = {'radar': {'coordinate': (32000, 31000, 7)}}
        dest = task._get_destination_coordinate(context)
        assert dest == (32000, 30999, 7)

        task = WalkTask('down')
        dest = task._get_destination_coordinate(context)
        assert dest == (32000, 31001, 7)

        task = WalkTask('left')
        dest = task._get_destination_coordinate(context)
        assert dest == (31999, 31000, 7)

        task = WalkTask('right')
        dest = task._get_destination_coordinate(context)
        assert dest == (32001, 31000, 7)

    def test_walk_task_none_coordinate(self):
        """Test WalkTask handles None coordinate gracefully."""
        from src.gameplay.core.tasks.common import WalkTask

        task = WalkTask('up')
        context = {'radar': {'coordinate': None}}
        dest = task._get_destination_coordinate(context)
        assert dest is None


class TestMovementTimeBreakpoints:
    """Test specific breakpoint behaviors."""

    @pytest.fixture
    def calculator(self):
        return TileFrictionCalculator()

    def test_speed_breakpoint_boundaries(self, calculator):
        """Test movement times at speed breakpoint boundaries."""
        time_at_100 = calculator.get_movement_time(100, 100)
        time_at_135 = calculator.get_movement_time(135, 100)

        assert time_at_135 <= time_at_100

    def test_friction_affects_breakpoints(self, calculator):
        """Test that different frictions have different breakpoint effects."""
        ice_time = calculator.get_movement_time(150, 70)
        sand_time = calculator.get_movement_time(150, 150)

        assert ice_time < sand_time


class TestEndToEndIntegration:
    """E2E tests for friction system integration with WalkToCoordinateTask."""

    def test_walk_to_coordinate_task_has_friction_calculator(self):
        """Test that WalkToCoordinateTask has friction calculator."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask
        task = WalkToCoordinateTask((32000, 31000, 7))
        assert hasattr(task, '_friction_calculator')
        assert isinstance(task._friction_calculator, TileFrictionCalculator)

    def test_walk_to_coordinate_task_updates_cooldown(self):
        """Test that WalkToCoordinateTask updates cooldown based on friction."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask, WALK_COOLDOWN
        task = WalkToCoordinateTask((32000, 31000, 7))

        initial_cooldown = task._walk_cooldown
        assert initial_cooldown == WALK_COOLDOWN

        context = {'playerSpeed': 150}
        target = (32000, 31000, 7)
        task._update_walk_cooldown(target, context)

        assert task._walk_cooldown != initial_cooldown
        assert task._walk_cooldown > 0

    def test_higher_speed_means_lower_cooldown(self):
        """Test that higher player speed results in lower walk cooldown."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask
        task = WalkToCoordinateTask((32000, 31000, 7))
        target = (32000, 31000, 7)

        task._update_walk_cooldown(target, {'playerSpeed': 100})
        slow_cooldown = task._walk_cooldown

        task._update_walk_cooldown(target, {'playerSpeed': 300})
        fast_cooldown = task._walk_cooldown

        assert fast_cooldown < slow_cooldown

    def test_context_player_speed_flows_to_cooldown(self):
        """Test complete flow: context playerSpeed -> friction calc -> cooldown."""
        from src.gameplay.core.tasks.common import WalkToCoordinateTask
        from src.gameplay.context import create_context

        context = create_context()
        assert context.get('playerSpeed') == 110

        context['playerSpeed'] = 180

        task = WalkToCoordinateTask((32000, 31000, 7))
        target = (32001, 31000, 7)
        task._update_walk_cooldown(target, context)

        assert 0.1 < task._walk_cooldown < 0.5

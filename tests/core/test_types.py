"""
Tests for core types and data classes.

Ensures:
1. Direction enum works correctly with relative positions
2. Coordinate distance calculations are accurate
3. Creature attack priority is correctly computed
4. GameContext filtering methods work
"""
import math
import pytest
from dataclasses import dataclass
from typing import List

from src.core.types import (
    Direction,
    CreatureType,
    HPColor,
    TaskStatus,
    BotMode,
    Coordinate,
    Creature,
    Marker,
    PlayerStatus,
    GameContext
)


class TestDirection:
    """Tests for Direction enum."""

    def test_direction_values_exist(self):
        """Test that all direction values exist."""
        assert Direction.NORTH is not None
        assert Direction.SOUTH is not None
        assert Direction.EAST is not None
        assert Direction.WEST is not None
        assert Direction.NORTHEAST is not None
        assert Direction.NORTHWEST is not None
        assert Direction.SOUTHEAST is not None
        assert Direction.SOUTHWEST is not None
        assert Direction.CENTER is not None

    def test_from_relative_position_north(self):
        """Test direction detection for north."""
        direction = Direction.from_relative_position(0, -10)
        assert direction == Direction.NORTH

    def test_from_relative_position_south(self):
        """Test direction detection for south."""
        direction = Direction.from_relative_position(0, 10)
        assert direction == Direction.SOUTH

    def test_from_relative_position_east(self):
        """Test direction detection for east."""
        direction = Direction.from_relative_position(10, 0)
        assert direction == Direction.EAST

    def test_from_relative_position_west(self):
        """Test direction detection for west."""
        direction = Direction.from_relative_position(-10, 0)
        assert direction == Direction.WEST

    def test_from_relative_position_northeast(self):
        """Test direction detection for northeast."""
        direction = Direction.from_relative_position(10, -10)
        assert direction == Direction.NORTHEAST

    def test_from_relative_position_northwest(self):
        """Test direction detection for northwest."""
        direction = Direction.from_relative_position(-10, -10)
        assert direction == Direction.NORTHWEST

    def test_from_relative_position_southeast(self):
        """Test direction detection for southeast."""
        direction = Direction.from_relative_position(10, 10)
        assert direction == Direction.SOUTHEAST

    def test_from_relative_position_southwest(self):
        """Test direction detection for southwest."""
        direction = Direction.from_relative_position(-10, 10)
        assert direction == Direction.SOUTHWEST

    def test_from_relative_position_center(self):
        """Test direction detection when within threshold."""
        direction = Direction.from_relative_position(0, 0)
        assert direction == Direction.CENTER

        # Also test with small values within default threshold (5)
        direction = Direction.from_relative_position(3, 3)
        assert direction == Direction.CENTER

    def test_from_relative_position_custom_threshold(self):
        """Test direction detection with custom threshold."""
        # With threshold of 10, (8, 0) should be center
        direction = Direction.from_relative_position(8, 0, threshold=10)
        assert direction == Direction.CENTER

        # But (12, 0) should be east
        direction = Direction.from_relative_position(12, 0, threshold=10)
        assert direction == Direction.EAST

    def test_opposite_directions(self):
        """Test opposite direction property."""
        assert Direction.NORTH.opposite == Direction.SOUTH
        assert Direction.SOUTH.opposite == Direction.NORTH
        assert Direction.EAST.opposite == Direction.WEST
        assert Direction.WEST.opposite == Direction.EAST
        assert Direction.NORTHEAST.opposite == Direction.SOUTHWEST
        assert Direction.SOUTHWEST.opposite == Direction.NORTHEAST
        assert Direction.NORTHWEST.opposite == Direction.SOUTHEAST
        assert Direction.SOUTHEAST.opposite == Direction.NORTHWEST
        assert Direction.CENTER.opposite == Direction.CENTER

    def test_short_name(self):
        """Test direction short names."""
        assert Direction.NORTH.short_name == "N"
        assert Direction.SOUTH.short_name == "S"
        assert Direction.EAST.short_name == "E"
        assert Direction.WEST.short_name == "W"
        assert Direction.NORTHEAST.short_name == "NE"
        assert Direction.NORTHWEST.short_name == "NW"
        assert Direction.SOUTHEAST.short_name == "SE"
        assert Direction.SOUTHWEST.short_name == "SW"
        assert Direction.CENTER.short_name == "."


class TestHPColor:
    """Tests for HPColor enum."""

    def test_hp_color_priority(self):
        """Test that HP colors have correct attack priority."""
        # RED should have highest priority (1)
        assert HPColor.RED.priority == 1
        # YELLOW medium (2)
        assert HPColor.YELLOW.priority == 2
        # GREEN lowest (3)
        assert HPColor.GREEN.priority == 3
        # UNKNOWN last (4)
        assert HPColor.UNKNOWN.priority == 4

    def test_hp_color_priority_ordering(self):
        """Test that HP colors sort correctly by priority."""
        colors = [HPColor.GREEN, HPColor.RED, HPColor.YELLOW, HPColor.UNKNOWN]
        sorted_colors = sorted(colors, key=lambda c: c.priority)

        assert sorted_colors[0] == HPColor.RED
        assert sorted_colors[1] == HPColor.YELLOW
        assert sorted_colors[2] == HPColor.GREEN
        assert sorted_colors[3] == HPColor.UNKNOWN


class TestCoordinate:
    """Tests for Coordinate dataclass."""

    def test_coordinate_creation(self):
        """Test coordinate creation with defaults."""
        coord = Coordinate(100, 200)
        assert coord.x == 100
        assert coord.y == 200
        assert coord.z == 7  # Default floor

    def test_coordinate_with_floor(self):
        """Test coordinate creation with specific floor."""
        coord = Coordinate(100, 200, 5)
        assert coord.z == 5

    def test_distance_same_point(self):
        """Test distance to same point is zero."""
        coord = Coordinate(100, 100)
        distance = coord.distance_to(Coordinate(100, 100))
        assert distance == 0.0

    def test_distance_horizontal(self):
        """Test horizontal distance calculation."""
        coord1 = Coordinate(0, 0)
        coord2 = Coordinate(10, 0)
        assert coord1.distance_to(coord2) == 10.0

    def test_distance_vertical(self):
        """Test vertical distance calculation."""
        coord1 = Coordinate(0, 0)
        coord2 = Coordinate(0, 10)
        assert coord1.distance_to(coord2) == 10.0

    def test_distance_diagonal(self):
        """Test diagonal distance calculation (Pythagorean)."""
        coord1 = Coordinate(0, 0)
        coord2 = Coordinate(3, 4)
        # 3-4-5 triangle
        assert coord1.distance_to(coord2) == 5.0

    def test_distance_ignores_z(self):
        """Test that distance calculation ignores Z coordinate."""
        coord1 = Coordinate(0, 0, 0)
        coord2 = Coordinate(3, 4, 10)
        # Should still be 5.0, ignoring Z difference
        assert coord1.distance_to(coord2) == 5.0

    def test_to_tuple(self):
        """Test conversion to tuple."""
        coord = Coordinate(100, 200, 7)
        assert coord.to_tuple() == (100, 200, 7)


class TestCreature:
    """Tests for Creature dataclass."""

    def test_creature_creation(self):
        """Test creature creation with defaults."""
        creature = Creature(
            name="Rotworm",
            x=100,
            y=200,
            width=32,
            height=32
        )

        assert creature.name == "Rotworm"
        assert creature.hp_color == HPColor.UNKNOWN
        assert creature.creature_type == CreatureType.UNKNOWN
        assert creature.is_being_attacked == False

    def test_creature_center(self):
        """Test creature center calculation."""
        creature = Creature(
            name="Rotworm",
            x=100,
            y=100,
            width=32,
            height=32
        )

        assert creature.center == (116, 116)  # 100 + 16, 100 + 16

    def test_creature_attack_priority(self):
        """Test creature attack priority calculation."""
        # Red HP, high Y
        red_creature = Creature(
            name="Monster1",
            x=0, y=100, width=32, height=32,
            hp_color=HPColor.RED
        )

        # Green HP, low Y
        green_creature = Creature(
            name="Monster2",
            x=0, y=50, width=32, height=32,
            hp_color=HPColor.GREEN
        )

        # Red should have higher priority (lower value)
        assert red_creature.attack_priority < green_creature.attack_priority

    def test_creatures_sort_by_priority(self):
        """Test that creatures sort correctly by attack priority."""
        creatures = [
            Creature(name="Green1", x=0, y=100, width=32, height=32, hp_color=HPColor.GREEN),
            Creature(name="Red1", x=0, y=50, width=32, height=32, hp_color=HPColor.RED),
            Creature(name="Yellow1", x=0, y=75, width=32, height=32, hp_color=HPColor.YELLOW),
            Creature(name="Red2", x=0, y=150, width=32, height=32, hp_color=HPColor.RED),
        ]

        sorted_creatures = sorted(creatures, key=lambda c: c.attack_priority)

        # First two should be RED (sorted by Y within same HP color)
        assert sorted_creatures[0].name == "Red1"  # y=50
        assert sorted_creatures[1].name == "Red2"  # y=150
        # Then YELLOW
        assert sorted_creatures[2].name == "Yellow1"
        # Then GREEN
        assert sorted_creatures[3].name == "Green1"


class TestPlayerStatus:
    """Tests for PlayerStatus dataclass."""

    def test_player_status_defaults(self):
        """Test player status default values."""
        status = PlayerStatus()

        assert status.hp_percent == 100.0
        assert status.mp_percent == 100.0
        assert status.is_attacking == False
        assert status.current_target is None

    def test_player_status_custom(self):
        """Test player status with custom values."""
        target = Creature(name="Target", x=0, y=0, width=32, height=32)
        status = PlayerStatus(
            hp_percent=75.5,
            mp_percent=50.0,
            is_attacking=True,
            current_target=target
        )

        assert status.hp_percent == 75.5
        assert status.mp_percent == 50.0
        assert status.is_attacking == True
        assert status.current_target.name == "Target"


class TestGameContext:
    """Tests for GameContext dataclass."""

    def test_game_context_defaults(self):
        """Test game context default values."""
        ctx = GameContext()

        assert ctx.screenshot is None
        assert ctx.creatures == []
        assert ctx.creature_count == 0
        assert ctx.mode == BotMode.IDLE
        assert ctx.player.hp_percent == 100.0

    def test_get_valid_targets_filters_monsters(self):
        """Test that get_valid_targets only returns monsters."""
        monster = Creature(
            name="Rotworm",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER
        )
        player = Creature(
            name="OtherPlayer",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.PLAYER
        )
        npc = Creature(
            name="Shopkeeper",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.NPC
        )

        ctx = GameContext(creatures=[monster, player, npc])
        targets = ctx.get_valid_targets()

        assert len(targets) == 1
        assert targets[0].name == "Rotworm"

    def test_get_valid_targets_with_blacklist(self):
        """Test that get_valid_targets respects blacklist."""
        rotworm = Creature(
            name="Rotworm",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER
        )
        cave_rat = Creature(
            name="Cave Rat",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER
        )

        ctx = GameContext(creatures=[rotworm, cave_rat])

        # Without blacklist
        targets = ctx.get_valid_targets()
        assert len(targets) == 2

        # With blacklist (case insensitive)
        targets = ctx.get_valid_targets(blacklist=["rotworm"])
        assert len(targets) == 1
        assert targets[0].name == "Cave Rat"

    def test_get_best_target_returns_highest_priority(self):
        """Test that get_best_target returns creature with highest priority."""
        green_monster = Creature(
            name="Green",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER,
            hp_color=HPColor.GREEN
        )
        red_monster = Creature(
            name="Red",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER,
            hp_color=HPColor.RED
        )

        ctx = GameContext(creatures=[green_monster, red_monster])
        best = ctx.get_best_target()

        assert best.name == "Red"  # RED has higher priority

    def test_get_best_target_empty_returns_none(self):
        """Test that get_best_target returns None when no valid targets."""
        ctx = GameContext(creatures=[])
        assert ctx.get_best_target() is None

        # Also test with only non-monsters
        player = Creature(
            name="Player",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.PLAYER
        )
        ctx = GameContext(creatures=[player])
        assert ctx.get_best_target() is None

    def test_get_best_target_with_blacklist(self):
        """Test get_best_target respects blacklist."""
        red_rotworm = Creature(
            name="Rotworm",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER,
            hp_color=HPColor.RED
        )
        green_cave_rat = Creature(
            name="Cave Rat",
            x=0, y=0, width=32, height=32,
            creature_type=CreatureType.MONSTER,
            hp_color=HPColor.GREEN
        )

        ctx = GameContext(creatures=[red_rotworm, green_cave_rat])

        # Without blacklist, should get Rotworm (RED)
        best = ctx.get_best_target()
        assert best.name == "Rotworm"

        # With blacklist, should get Cave Rat
        best = ctx.get_best_target(blacklist=["Rotworm"])
        assert best.name == "Cave Rat"


class TestMarker:
    """Tests for Marker dataclass."""

    def test_marker_from_detection(self):
        """Test marker creation from detection result."""
        marker = Marker.from_detection(
            x=100,
            y=50,
            center_x=80,
            center_y=80,
            region_x=200,
            region_y=100,
            confidence=0.95
        )

        # Check relative position
        assert marker.rel_x == 20   # 100 - 80
        assert marker.rel_y == -30  # 50 - 80

        # Check screen position
        assert marker.screen_x == 300  # 200 + 100
        assert marker.screen_y == 150  # 100 + 50

        # Check distance (sqrt(20^2 + 30^2) = sqrt(400 + 900) = sqrt(1300))
        expected_distance = math.sqrt(20**2 + 30**2)
        assert abs(marker.distance - expected_distance) < 0.001

        # Check direction (positive X, negative Y = NORTHEAST)
        assert marker.direction == Direction.NORTHEAST

        assert marker.confidence == 0.95


class TestTaskStatus:
    """Tests for TaskStatus enum."""

    def test_task_status_values(self):
        """Test that all task status values exist."""
        assert TaskStatus.NOT_STARTED is not None
        assert TaskStatus.AWAITING_DELAY is not None
        assert TaskStatus.RUNNING is not None
        assert TaskStatus.COMPLETED is not None
        assert TaskStatus.FAILED is not None
        assert TaskStatus.TIMEOUT is not None


class TestBotMode:
    """Tests for BotMode enum."""

    def test_bot_mode_values(self):
        """Test that all bot mode values exist."""
        assert BotMode.IDLE is not None
        assert BotMode.EXPLORING is not None
        assert BotMode.COMBAT is not None
        assert BotMode.HEALING is not None
        assert BotMode.LOOTING is not None
        assert BotMode.WALKING is not None

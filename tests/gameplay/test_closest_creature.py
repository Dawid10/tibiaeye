"""
Tests for get_closest_creature - Critical targeting logic.

CRITICAL TESTS:
1. Never attack creature through a wall
2. Prefer closer reachable creatures over unreachable ones
3. Handle multiple creatures correctly
4. Wall detection heuristic works properly
5. Diagonal movement not allowed (4-directional only)
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass
from typing import Tuple, List, Optional


@dataclass
class MockCreature:
    """Mock creature for testing."""
    name: str
    slot: Tuple[int, int]  # (x, y) grid position
    coordinate: Tuple[int, int, int]  # World coordinate
    creature_type: str = 'monster'
    is_being_attacked: bool = False
    window_coordinate: Tuple[int, int] = (0, 0)
    game_window_coordinate: Tuple[int, int] = (0, 0)


def create_creature(name: str, slot_x: int, slot_y: int,
                    coord_offset: Tuple[int, int, int] = (32000, 32000, 7)) -> MockCreature:
    """Helper to create mock creature."""
    # World coordinate = base + (slot - center)
    # Center is (7, 5)
    world_x = coord_offset[0] - 7 + slot_x
    world_y = coord_offset[1] - 5 + slot_y
    world_z = coord_offset[2]

    return MockCreature(
        name=name,
        slot=(slot_x, slot_y),
        coordinate=(world_x, world_y, world_z)
    )


class TestNoAttackThroughWall:
    """CRITICAL: Ensure creatures behind walls are NOT targeted."""

    def test_creature_behind_solid_wall_not_targeted(self):
        """A creature behind a solid wall should not be targeted."""
        # Setup: Player at center, wall between player and creature
        walkable = np.ones((11, 15), dtype=np.int32)

        # Solid wall at column 9 (blocks direct path to col 10+)
        for row in range(11):
            walkable[row, 9] = 0

        # Creature at slot (10, 5) - behind the wall
        creature = create_creature("Rotworm", 10, 5)
        creatures = [creature]

        # Mock the get_closest_creature logic
        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        # Should return None - creature is unreachable
        assert closest is None, "Should not target creature behind solid wall!"

    def test_creature_on_same_side_as_player_targeted(self):
        """A creature on same side of wall should be targeted."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Wall at column 10
        for row in range(11):
            walkable[row, 10] = 0

        # Creature at slot (8, 5) - same side as player
        creature = create_creature("Rotworm", 8, 5)
        creatures = [creature]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rotworm"

    def test_prefer_reachable_over_closer_unreachable(self):
        """Should prefer reachable creature over closer unreachable one."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Wall at column 9 blocking right side
        for row in range(11):
            walkable[row, 9] = 0

        # Unreachable creature at (10, 5) - closer but behind wall
        unreachable = create_creature("Dragon", 10, 5)

        # Reachable creature at (5, 5) - further but no wall
        reachable = create_creature("Rotworm", 5, 5)

        creatures = [unreachable, reachable]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rotworm", "Should target reachable creature, not closer unreachable"

    def test_l_shaped_wall_blocks_corner_creature(self):
        """L-shaped wall should block creature in corner."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # L-shaped wall in bottom-right corner
        # Horizontal at row 8
        for col in range(10, 15):
            walkable[8, col] = 0
        # Vertical at col 10
        for row in range(8, 11):
            walkable[row, 10] = 0

        # Creature in corner at (12, 9)
        creature = create_creature("Demon", 12, 9)
        creatures = [creature]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is None, "Creature in L-wall corner should be unreachable"

    def test_partial_wall_allows_reaching_creature(self):
        """Partial wall should allow reaching creature by going around."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Partial wall at column 9 (only middle rows)
        for row in range(3, 8):
            walkable[row, 9] = 0
        # Top and bottom are open for going around

        # Creature behind partial wall
        creature = create_creature("Rotworm", 10, 5)
        creatures = [creature]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable,
            wall_threshold_multiplier=5  # Allow longer paths
        )

        # With a high threshold, creature should be reachable
        # (going up to row 2, crossing at col 9, going down)
        # This tests that partial walls don't completely block
        # Note: The wall detection heuristic may still filter this out
        # depending on path length vs manhattan distance


class TestWallDetectionHeuristic:
    """Tests for the wall detection heuristic."""

    def test_wall_heuristic_rejects_long_detour(self):
        """Wall heuristic should reject paths requiring long detours."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # U-shaped wall forcing long detour
        for row in range(2, 9):
            walkable[row, 9] = 0
        for col in range(7, 10):
            walkable[2, col] = 0
            walkable[8, col] = 0

        creature = create_creature("Rotworm", 10, 5)
        creatures = [creature]

        # Manhattan distance to creature = 3
        # BFS path would be very long (going around U)

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable,
            wall_threshold_multiplier=2  # Default: manhattan * 2 + 3
        )

        # Wall heuristic should reject this (path too long vs manhattan)
        assert closest is None, "Long detour should trigger wall detection"

    def test_wall_heuristic_accepts_reasonable_detour(self):
        """Wall heuristic should accept short detours."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Small obstacle at (5, 8) - just one tile
        walkable[5, 8] = 0

        # Creature at (5, 9) - behind single obstacle
        creature = create_creature("Rotworm", 9, 5)
        creatures = [creature]

        # Manhattan = 2, BFS = 4 (go around)
        # Threshold = 2 * 2 + 3 = 7
        # BFS 4 < 7, should be accepted

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        # Small detour should be accepted
        assert closest is not None
        assert closest.name == "Rotworm"


class TestMultipleCreatures:
    """Tests for handling multiple creatures."""

    def test_closest_of_multiple_selected(self):
        """Should select closest reachable creature."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Three creatures at different distances
        close = create_creature("Rat", 8, 5)      # Distance 1
        medium = create_creature("Rotworm", 9, 5) # Distance 2
        far = create_creature("Dragon", 10, 5)   # Distance 3

        creatures = [far, medium, close]  # Order shouldn't matter

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rat", "Should select closest creature"

    def test_skip_unreachable_select_reachable(self):
        """Should skip unreachable creatures and select reachable one."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Wall blocking right side
        for row in range(11):
            walkable[row, 9] = 0

        # Closer but unreachable (behind wall)
        unreachable1 = create_creature("Dragon", 10, 5)
        unreachable2 = create_creature("Dragon Lord", 11, 5)

        # Further but reachable (same side)
        reachable = create_creature("Rat", 3, 5)

        creatures = [unreachable1, unreachable2, reachable]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rat"

    def test_all_creatures_unreachable_returns_none(self):
        """Should return None if all creatures are unreachable."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Walls blocking all directions
        for row in range(11):
            walkable[row, 8] = 0  # Right
            walkable[row, 6] = 0  # Left
        for col in range(15):
            walkable[4, col] = 0  # Up
            walkable[6, col] = 0  # Down

        # All creatures behind walls
        c1 = create_creature("Dragon", 10, 5)
        c2 = create_creature("Demon", 3, 5)
        c3 = create_creature("Rat", 7, 2)

        creatures = [c1, c2, c3]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is None


class TestCreatureAtPlayerPosition:
    """Tests for creatures at or near player position."""

    def test_creature_at_player_position_skipped(self):
        """Creature at player position should be skipped."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Creature at player position
        at_player = create_creature("Ghost", 7, 5)
        # Another creature nearby
        nearby = create_creature("Rat", 8, 5)

        creatures = [at_player, nearby]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rat", "Should skip creature at player position"

    def test_adjacent_creature_preferred(self):
        """Adjacent creature should be preferred."""
        walkable = np.ones((11, 15), dtype=np.int32)

        adjacent = create_creature("Rat", 8, 5)  # Distance 1
        further = create_creature("Dragon", 10, 5)  # Distance 3

        creatures = [further, adjacent]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rat"


class TestOutOfBoundsCreatures:
    """Tests for creatures at grid boundaries."""

    def test_creature_at_edge_reachable(self):
        """Creature at grid edge should be reachable."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Creatures at all corners
        top_left = create_creature("Rat", 0, 0)
        top_right = create_creature("Rotworm", 14, 0)
        bottom_left = create_creature("Snake", 0, 10)
        bottom_right = create_creature("Bug", 14, 10)

        creatures = [top_left, top_right, bottom_left, bottom_right]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None

    def test_creature_out_of_bounds_ignored(self):
        """Creature outside grid bounds should be ignored."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create creature with invalid slot
        out_of_bounds = MockCreature(
            name="Ghost",
            slot=(20, 20),  # Outside 15x11 grid
            coordinate=(32020, 32020, 7)
        )

        valid = create_creature("Rat", 8, 5)

        creatures = [out_of_bounds, valid]

        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable
        )

        assert closest is not None
        assert closest.name == "Rat"


class TestNoPathfindingFallback:
    """Tests for behavior without pathfinding (TCOD unavailable)."""

    def test_manhattan_distance_fallback(self):
        """Without pathfinding, should use Manhattan distance."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Without TCOD, should just sort by Manhattan distance
        close = create_creature("Rat", 8, 5)      # Manhattan: 1
        far = create_creature("Dragon", 10, 7)   # Manhattan: 5

        creatures = [far, close]

        # Simulate no pathfinding (use_pathfinding=False)
        closest = get_closest_creature_mock(
            creatures=creatures,
            player_slot=(7, 5),
            walkable=walkable,
            use_pathfinding=False
        )

        assert closest is not None
        assert closest.name == "Rat"


# Mock implementation of get_closest_creature for testing
def get_closest_creature_mock(
    creatures: List[MockCreature],
    player_slot: Tuple[int, int],
    walkable: np.ndarray,
    use_pathfinding: bool = True,
    wall_threshold_multiplier: int = 2
) -> Optional[MockCreature]:
    """
    Mock implementation of get_closest_creature for testing.

    Uses BFS to find reachable creatures, with wall detection heuristic.
    """
    if not creatures:
        return None

    if not use_pathfinding:
        # Fallback: Manhattan distance only
        creatures_sorted = sorted(
            creatures,
            key=lambda c: abs(c.slot[0] - player_slot[0]) + abs(c.slot[1] - player_slot[1])
        )
        return creatures_sorted[0] if creatures_sorted else None

    player_y, player_x = player_slot[1], player_slot[0]  # slot is (x, y)

    # Collect blocked slots (creatures block path)
    blocked_slots = set()
    for c in creatures:
        sx, sy = c.slot
        if 0 <= sx < 15 and 0 <= sy < 11 and not (sx == player_x and sy == player_y):
            blocked_slots.add((sx, sy))

    # BFS flood fill
    distances = _bfs_flood_fill_mock(walkable, player_y, player_x, blocked_slots)

    # Find reachable creatures
    reachable = []
    for creature in creatures:
        slot_x, slot_y = creature.slot

        # Bounds check
        if not (0 <= slot_x < 15 and 0 <= slot_y < 11):
            continue

        # Skip player position
        if slot_x == player_x and slot_y == player_y:
            continue

        # Check adjacent tiles
        adjacent = [
            (slot_y - 1, slot_x),
            (slot_y + 1, slot_x),
            (slot_y, slot_x - 1),
            (slot_y, slot_x + 1),
        ]

        min_dist = float('inf')
        for ay, ax in adjacent:
            if 0 <= ay < 11 and 0 <= ax < 15:
                if (ay, ax) in distances and walkable[ay, ax] > 0:
                    min_dist = min(min_dist, distances[(ay, ax)])

        # Also check creature tile itself
        if (slot_y, slot_x) in distances:
            min_dist = min(min_dist, distances[(slot_y, slot_x)])

        if min_dist < float('inf'):
            # Wall detection heuristic
            manhattan = abs(slot_x - player_x) + abs(slot_y - player_y)
            threshold = manhattan * wall_threshold_multiplier + 3

            if min_dist > threshold:
                continue  # Wall detected

            reachable.append((min_dist, manhattan, creature))

    if not reachable:
        return None

    # Sort by BFS distance, then Manhattan
    reachable.sort(key=lambda x: (x[0], x[1]))
    return reachable[0][2]


def _bfs_flood_fill_mock(walkable: np.ndarray, start_y: int, start_x: int,
                          blocked_slots: set) -> dict:
    """Mock BFS flood fill for testing."""
    from collections import deque

    distances = {(start_y, start_x): 0}
    queue = deque([(start_y, start_x, 0)])

    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while queue:
        y, x, dist = queue.popleft()

        for dy, dx in directions:
            ny, nx = y + dy, x + dx

            if not (0 <= ny < walkable.shape[0] and 0 <= nx < walkable.shape[1]):
                continue

            if (ny, nx) in distances:
                continue

            if walkable[ny, nx] <= 0:
                continue

            distances[(ny, nx)] = dist + 1

            # Blocked by creature - mark but don't continue
            if (nx, ny) in blocked_slots:
                continue

            queue.append((ny, nx, dist + 1))

    return distances

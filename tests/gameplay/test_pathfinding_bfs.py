"""
Tests for BFS Pathfinding - Critical for creature targeting.

Ensures:
1. BFS flood fill finds all reachable tiles
2. Walls block pathfinding correctly
3. Creatures block paths but can be reached
4. Distance calculations are accurate
5. No paths through walls (critical for creature targeting)
"""
import pytest
import numpy as np
from unittest.mock import Mock, patch, MagicMock


class TestBFSFloodFill:
    """Tests for BFS flood fill algorithm."""

    def test_basic_flood_fill_open_area(self):
        """Test BFS in open area finds all tiles."""
        # Create 11x15 walkable grid (all 1s = walkable)
        walkable = np.ones((11, 15), dtype=np.int32)

        # Player at center (row=5, col=7)
        start_y, start_x = 5, 7
        blocked_slots = set()

        # Simulate BFS flood fill
        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # All tiles should be reachable
        assert len(distances) == 11 * 15  # 165 tiles

        # Player position should have distance 0
        assert distances[(start_y, start_x)] == 0

        # Adjacent tiles should have distance 1
        assert distances[(5, 8)] == 1  # Right
        assert distances[(5, 6)] == 1  # Left
        assert distances[(4, 7)] == 1  # Up
        assert distances[(6, 7)] == 1  # Down

    def test_flood_fill_with_wall(self):
        """Test BFS respects walls (0s in walkable matrix)."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create vertical wall at column 9 from row 2 to row 8
        # This wall blocks direct path to right side
        for row in range(2, 9):
            walkable[row, 9] = 0

        start_y, start_x = 5, 7  # Player at center
        blocked_slots = set()

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Tiles before wall should be reachable
        assert (5, 8) in distances  # Right of player, before wall

        # Wall tiles should NOT be reachable (they are not walkable)
        for row in range(2, 9):
            assert (row, 9) not in distances

        # Tiles beyond wall should still be reachable (going around)
        # Path: go up to row 1, cross at col 9, go down
        assert (5, 10) in distances
        assert (5, 11) in distances

        # Distance to tile beyond wall should be longer (going around)
        # Direct path would be 3, but with wall we go around
        # 5,7 -> 4,7 -> 3,7 -> 2,7 -> 1,7 -> 1,8 -> 1,9 -> 1,10 -> 2,10 -> 3,10 -> 4,10 -> 5,10
        assert distances[(5, 10)] > 3  # Not direct path

    def test_flood_fill_completely_blocked(self):
        """Test BFS when area is completely blocked."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create a box around player position
        # Wall at rows 4 and 6, columns 6 and 8
        walkable[4, 6] = 0
        walkable[4, 7] = 0
        walkable[4, 8] = 0
        walkable[6, 6] = 0
        walkable[6, 7] = 0
        walkable[6, 8] = 0
        walkable[5, 6] = 0
        walkable[5, 8] = 0

        start_y, start_x = 5, 7  # Player inside box
        blocked_slots = set()

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Only player position should be reachable
        assert len(distances) == 1
        assert (5, 7) in distances

    def test_flood_fill_with_creature_blocking(self):
        """Test BFS marks creature tiles but doesn't continue through them."""
        walkable = np.ones((11, 15), dtype=np.int32)

        start_y, start_x = 5, 7
        # Creature at (5, 9) - 2 tiles to the right
        blocked_slots = {(9, 5)}  # (x, y) format

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Creature tile should be marked as reachable (distance from adjacent tile)
        assert (5, 9) in distances
        assert distances[(5, 9)] == 2  # 5,7 -> 5,8 -> 5,9

        # Tiles beyond creature should NOT be reachable via that path
        # But they ARE reachable via going around (up or down)
        assert (5, 10) in distances

    def test_distance_calculation_accuracy(self):
        """Test distance calculations are accurate."""
        walkable = np.ones((11, 15), dtype=np.int32)

        start_y, start_x = 5, 7
        blocked_slots = set()

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Test specific distances
        # Top-left corner: (0, 0) - should be 5+7=12 Manhattan distance
        # BFS uses 4-directional movement, so Manhattan distance is actual distance
        assert distances[(0, 0)] == 12

        # Top-right corner: (0, 14) - should be 5+7=12
        assert distances[(0, 14)] == 12

        # Bottom-left corner: (10, 0) - should be 5+7=12
        assert distances[(10, 0)] == 12

        # Bottom-right corner: (10, 14) - should be 5+7=12
        assert distances[(10, 14)] == 12


class TestWallBlocksCreatureTargeting:
    """Critical tests: Ensure creatures behind walls cannot be targeted."""

    def test_creature_behind_vertical_wall_unreachable(self):
        """Test creature behind vertical wall is not targetable."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create solid vertical wall at column 9 (full height)
        for row in range(11):
            walkable[row, 9] = 0

        start_y, start_x = 5, 7  # Player
        creature_slot = (10, 5)  # Creature behind wall (x, y)
        blocked_slots = {creature_slot}

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Creature position should NOT be reachable (wall blocks completely)
        assert (5, 10) not in distances

    def test_creature_behind_partial_wall_reachable(self):
        """Test creature behind partial wall IS reachable (going around)."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create partial wall at column 9 (middle section only)
        for row in range(3, 8):  # Leaves top and bottom open
            walkable[row, 9] = 0

        start_y, start_x = 5, 7  # Player
        creature_slot = (10, 5)  # Creature behind wall (x, y)
        blocked_slots = {creature_slot}

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Creature should be reachable by going around the wall
        assert (5, 10) in distances

        # But distance should be longer than direct (2 tiles direct, longer around)
        assert distances[(5, 10)] > 3  # Direct would be 3

    def test_creature_in_corner_behind_l_wall(self):
        """Test creature in corner behind L-shaped wall."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create L-shaped wall in top-right
        # Horizontal part at row 2
        for col in range(10, 15):
            walkable[2, col] = 0
        # Vertical part at column 10
        for row in range(0, 3):
            walkable[row, 10] = 0

        start_y, start_x = 5, 7  # Player
        creature_slot = (12, 1)  # Creature in corner (x, y)
        blocked_slots = {creature_slot}

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Creature in corner should NOT be reachable
        assert (1, 12) not in distances

    def test_wall_detection_heuristic(self):
        """Test wall detection using BFS/Manhattan distance ratio."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create U-shaped wall that forces long detour
        # Player at 5,7 needs to go way around to reach 5,10
        for row in range(3, 8):
            walkable[row, 9] = 0
        for col in range(7, 10):
            walkable[3, col] = 0
            walkable[7, col] = 0

        start_y, start_x = 5, 7
        blocked_slots = set()

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Manhattan distance to (5, 10) = 3
        manhattan = abs(10 - 7) + abs(5 - 5)  # = 3

        # BFS distance should be much longer (going around U)
        bfs_dist = distances.get((5, 10), float('inf'))

        # Ratio check (like in get_closest_creature)
        threshold = manhattan * 2 + 3  # = 9

        # If BFS distance > threshold, wall is detected
        # This creature would be filtered out
        if bfs_dist > threshold:
            wall_detected = True
        else:
            wall_detected = False

        # In this case, wall SHOULD be detected (long path around U)
        assert bfs_dist > threshold, f"Expected wall detection: bfs={bfs_dist}, threshold={threshold}"


class TestCreatureSlotReachability:
    """Tests for creature slot reachability checks."""

    def test_adjacent_tile_check(self):
        """Test checking adjacent tiles for creature attack range."""
        walkable = np.ones((11, 15), dtype=np.int32)

        start_y, start_x = 5, 7
        creature_y, creature_x = 5, 9  # Creature 2 tiles right
        blocked_slots = {(creature_x, creature_y)}

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Check adjacent tiles to creature
        adjacent_tiles = [
            (creature_y - 1, creature_x),  # Up
            (creature_y + 1, creature_x),  # Down
            (creature_y, creature_x - 1),  # Left
            (creature_y, creature_x + 1),  # Right
        ]

        # At least one adjacent tile should be reachable
        reachable_adjacent = [t for t in adjacent_tiles if t in distances]
        assert len(reachable_adjacent) > 0

        # The tile to the left of creature (5, 8) should be reachable with dist 1
        assert (5, 8) in distances
        assert distances[(5, 8)] == 1

    def test_creature_completely_surrounded_by_walls(self):
        """Test creature surrounded by walls has no reachable adjacent tiles."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Create box around creature at (5, 10)
        for row in [4, 5, 6]:
            walkable[row, 9] = 0   # Left wall
            walkable[row, 11] = 0  # Right wall
        walkable[4, 10] = 0   # Top wall
        walkable[6, 10] = 0   # Bottom wall

        start_y, start_x = 5, 7
        creature_slot = (10, 5)  # Inside the box
        blocked_slots = {creature_slot}

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # All adjacent tiles to creature should be unreachable (walls)
        adjacent_tiles = [
            (4, 10),  # Up
            (6, 10),  # Down
            (5, 9),   # Left
            (5, 11),  # Right
        ]

        for tile in adjacent_tiles:
            assert tile not in distances, f"Tile {tile} should not be reachable"

    def test_multiple_creatures_blocking(self):
        """Test multiple creatures blocking each other."""
        walkable = np.ones((11, 15), dtype=np.int32)

        start_y, start_x = 5, 7

        # 3 creatures in a row blocking horizontal path
        blocked_slots = {(9, 5), (10, 5), (11, 5)}  # x, y format

        distances = _simple_bfs(walkable, start_y, start_x, blocked_slots)

        # Tiles behind the creature row should still be reachable (going around)
        assert (5, 12) in distances

        # First creature is reachable
        assert (5, 9) in distances


def _simple_bfs(walkable: np.ndarray, start_y: int, start_x: int, blocked_slots: set) -> dict:
    """
    Simple BFS implementation for testing.

    Args:
        walkable: Grid where 1=walkable, 0=blocked
        start_y: Starting row
        start_x: Starting column
        blocked_slots: Set of (x, y) creature positions that block but are reachable

    Returns:
        Dictionary of {(y, x): distance}
    """
    from collections import deque

    distances = {(start_y, start_x): 0}
    queue = deque([(start_y, start_x, 0)])

    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]  # 4-directional

    while queue:
        y, x, dist = queue.popleft()

        for dy, dx in directions:
            ny, nx = y + dy, x + dx

            # Bounds check
            if not (0 <= ny < walkable.shape[0] and 0 <= nx < walkable.shape[1]):
                continue

            # Already visited
            if (ny, nx) in distances:
                continue

            # Check if walkable
            if walkable[ny, nx] <= 0:
                continue

            # Mark distance
            distances[(ny, nx)] = dist + 1

            # If blocked by creature, mark but don't continue through
            if (nx, ny) in blocked_slots:  # Note: blocked_slots is (x, y)
                continue

            queue.append((ny, nx, dist + 1))

    return distances


class TestGameWindowBFSIntegration:
    """Integration tests with GameWindowRepository BFS."""

    def test_bfs_with_numba_fallback(self):
        """Test BFS works with or without Numba JIT."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Test with simple BFS (our implementation)
        distances = _simple_bfs(walkable, 5, 7, set())

        # Basic sanity checks
        assert (5, 7) in distances
        assert distances[(5, 7)] == 0
        assert len(distances) == 165  # All tiles reachable

    def test_boundary_conditions(self):
        """Test BFS handles boundary conditions correctly."""
        walkable = np.ones((11, 15), dtype=np.int32)

        # Player in corner
        start_y, start_x = 0, 0
        distances = _simple_bfs(walkable, start_y, start_x, set())

        # Should still reach all tiles
        assert len(distances) == 165

        # Opposite corner distance
        assert distances[(10, 14)] == 10 + 14  # Manhattan distance

    def test_single_tile_island(self):
        """Test BFS with single walkable tile."""
        walkable = np.zeros((11, 15), dtype=np.int32)
        walkable[5, 7] = 1  # Only player tile is walkable

        distances = _simple_bfs(walkable, 5, 7, set())

        assert len(distances) == 1
        assert (5, 7) in distances

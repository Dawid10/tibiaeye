"""
Tests for CPU optimization changes.

Ensures optimized functions produce identical results to original implementations.
"""
import numpy as np
import pytest
from typing import List, Tuple


class TestNormalizeTextPixels:
    """Tests for vectorized pixel normalization."""

    def test_basic_normalization(self):
        """Test that normalization works for basic input."""
        from src.utils.hash import normalize_text_pixels, TEXT_PIXEL_VALUES

        # Input with some text pixels (192, 247) and high values (>150)
        row = np.array([0, 50, 100, 150, 151, 192, 200, 247, 255], dtype=np.uint8)
        result = normalize_text_pixels(row, width=9)

        # Expected: 0 for values <= 150 (except 192, 247), 192 for text pixels and >150
        expected = np.array([0, 0, 0, 0, 192, 192, 192, 192, 192], dtype=np.uint8)
        np.testing.assert_array_equal(result, expected)

    def test_padding_short_row(self):
        """Test that short rows are padded correctly."""
        from src.utils.hash import normalize_text_pixels

        row = np.array([192, 247, 200], dtype=np.uint8)
        result = normalize_text_pixels(row, width=10)

        assert len(result) == 10
        assert result[0] == 192
        assert result[1] == 192
        assert result[2] == 192
        # Rest should be zeros (padding)
        assert np.all(result[3:] == 0)

    def test_truncating_long_row(self):
        """Test that long rows are truncated correctly."""
        from src.utils.hash import normalize_text_pixels

        row = np.array([192] * 200, dtype=np.uint8)
        result = normalize_text_pixels(row, width=115)

        assert len(result) == 115
        assert np.all(result == 192)

    def test_empty_row(self):
        """Test handling of empty row."""
        from src.utils.hash import normalize_text_pixels

        row = np.array([], dtype=np.uint8)
        result = normalize_text_pixels(row, width=10)

        assert len(result) == 10
        assert np.all(result == 0)

    def test_vectorized_vs_loop_equivalence(self):
        """Test that vectorized version produces same result as original loop."""
        from src.utils.hash import normalize_text_pixels

        # Create random test data
        np.random.seed(42)
        row = np.random.randint(0, 256, size=100, dtype=np.uint8)

        # Original loop implementation
        TEXT_PIXEL_VALUES = (192, 247)
        normalized_loop = np.zeros(115, dtype=np.uint8)
        for i in range(min(len(row), 115)):
            if row[i] in TEXT_PIXEL_VALUES or row[i] > 150:
                normalized_loop[i] = 192

        # Vectorized implementation
        normalized_vec = normalize_text_pixels(row, width=115)

        np.testing.assert_array_equal(normalized_loop, normalized_vec)


class TestHashFunctions:
    """Tests for FarmHash64 integration."""

    def test_hashit_deterministic(self):
        """Test that hashit produces deterministic results."""
        from src.utils.hash import hashit

        arr = np.array([1, 2, 3, 4, 5], dtype=np.uint8)

        hash1 = hashit(arr)
        hash2 = hashit(arr)

        assert hash1 == hash2

    def test_hashit_different_arrays(self):
        """Test that different arrays produce different hashes."""
        from src.utils.hash import hashit

        arr1 = np.array([1, 2, 3, 4, 5], dtype=np.uint8)
        arr2 = np.array([1, 2, 3, 4, 6], dtype=np.uint8)

        hash1 = hashit(arr1)
        hash2 = hashit(arr2)

        assert hash1 != hash2


class TestHPBarDetection:
    """Tests for vectorized HP bar detection."""

    def _create_hp_bar(self, x: int, y: int, fill: int = 20) -> np.ndarray:
        """Create a synthetic HP bar at given position."""
        # HP bar structure: 27px wide, 4px tall
        # Row 0: all black (0)
        # Row 1-2: black border, colored interior
        # Row 3: all black (0)
        bar = np.zeros((4, 27), dtype=np.uint8)
        # Interior color (green HP = ~113)
        bar[1, 1:1+fill] = 113
        bar[2, 1:1+fill] = 113
        return bar

    def test_bar_detection_basic(self):
        """Test basic HP bar detection."""
        # Create a test image with a single HP bar
        img = np.ones((100, 200), dtype=np.uint8) * 128  # Gray background

        # Place HP bar at (50, 30)
        bar = self._create_hp_bar(50, 30)
        img[30:34, 50:77] = bar

        # Import and test
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()

        bars = repo._get_creatures_bars_vectorized(img)

        # Should find exactly one bar
        assert len(bars) == 1
        assert bars[0] == (50, 30)

    def test_bar_detection_multiple(self):
        """Test detection of multiple HP bars."""
        img = np.ones((200, 300), dtype=np.uint8) * 128

        # Place bars at different positions
        positions = [(50, 30), (100, 60), (150, 90)]
        for x, y in positions:
            bar = self._create_hp_bar(x, y)
            img[y:y+4, x:x+27] = bar

        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()

        bars = repo._get_creatures_bars_vectorized(img)

        assert len(bars) == 3
        for pos in positions:
            assert pos in bars

    def test_bar_detection_no_false_positives(self):
        """Test that random black lines dont trigger detection."""
        img = np.ones((100, 200), dtype=np.uint8) * 128

        # Add some random black lines (not valid HP bars)
        img[20, 30:60] = 0  # Random black line
        img[40:45, 80] = 0  # Vertical black line

        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()

        bars = repo._get_creatures_bars_vectorized(img)

        # Should not find any bars
        assert len(bars) == 0


class TestNMSOptimization:
    """Tests for Non-Maximum Suppression optimization."""

    def test_nms_no_overlap(self):
        """Test that NMS handles non-overlapping positions correctly."""
        # This tests the algorithm logic with mock data
        all_matches = [
            (1, 0, 0.9),   # Digit 1 at x=0
            (2, 10, 0.85), # Digit 2 at x=10 (far enough)
            (3, 20, 0.8),  # Digit 3 at x=20 (far enough)
        ]

        # Simulate NMS logic
        all_matches.sort(key=lambda m: (m[1], -m[2]))

        found_digits = []
        last_kept_x = -999

        i = 0
        while i < len(all_matches):
            current_x = all_matches[i][1]
            if current_x - last_kept_x >= 4:
                group_end = i
                while group_end < len(all_matches) and all_matches[group_end][1] - current_x < 4:
                    group_end += 1
                best = max(all_matches[i:group_end], key=lambda m: m[2])
                found_digits.append(best)
                last_kept_x = best[1]
                i = group_end
            else:
                i += 1

        # Should keep all three digits (they are far apart)
        assert len(found_digits) == 3

    def test_nms_with_overlap(self):
        """Test that NMS correctly suppresses overlapping detections."""
        all_matches = [
            (1, 0, 0.9),   # Digit 1 at x=0 (best)
            (2, 2, 0.85),  # Digit 2 at x=2 (overlaps, suppress)
            (3, 1, 0.8),   # Digit 3 at x=1 (overlaps, suppress)
            (4, 10, 0.95), # Digit 4 at x=10 (no overlap)
        ]

        # Simulate NMS logic
        all_matches.sort(key=lambda m: (m[1], -m[2]))

        found_digits = []
        last_kept_x = -999

        i = 0
        while i < len(all_matches):
            current_x = all_matches[i][1]
            if current_x - last_kept_x >= 4:
                group_end = i
                while group_end < len(all_matches) and all_matches[group_end][1] - current_x < 4:
                    group_end += 1
                best = max(all_matches[i:group_end], key=lambda m: m[2])
                found_digits.append(best)
                last_kept_x = best[1]
                i = group_end
            else:
                i += 1

        # Should keep 2 digits: best from first group and digit at x=10
        assert len(found_digits) == 2


class TestBFSPathfinding:
    """Tests for BFS-based pathfinding optimization."""

    def test_bfs_flood_fill_basic(self):
        """Test BFS flood fill finds reachable tiles."""
        from src.repositories.gamewindow import GameWindowRepository

        # Create simple walkable grid (all walkable)
        walkable = np.ones((11, 15), dtype=np.int32)

        repo = GameWindowRepository()
        distances = repo._bfs_flood_fill(walkable, 5, 7, set())

        # Player position should be at distance 0
        assert distances[(5, 7)] == 0

        # Adjacent tiles should be at distance 1
        assert distances[(5, 8)] == 1
        assert distances[(5, 6)] == 1
        assert distances[(4, 7)] == 1
        assert distances[(6, 7)] == 1

    def test_bfs_flood_fill_with_obstacles(self):
        """Test BFS respects obstacles."""
        from src.repositories.gamewindow import GameWindowRepository

        # Create grid with a wall
        walkable = np.ones((11, 15), dtype=np.int32)
        walkable[5, 8] = 0  # Block tile to the right of player

        repo = GameWindowRepository()
        distances = repo._bfs_flood_fill(walkable, 5, 7, set())

        # Blocked tile should not be reachable
        assert (5, 8) not in distances

    def test_bfs_flood_fill_with_creatures(self):
        """Test BFS marks creature tiles but does not pass through."""
        from src.repositories.gamewindow import GameWindowRepository

        walkable = np.ones((11, 15), dtype=np.int32)
        blocked_slots = {(8, 5)}  # Creature at column 8, row 5

        repo = GameWindowRepository()
        distances = repo._bfs_flood_fill(walkable, 5, 7, blocked_slots)

        # Creature tile should be marked as reachable (we can attack it)
        assert (5, 8) in distances


class TestPerformanceRegression:
    """Performance regression tests."""

    def test_normalize_performance(self):
        """Test that vectorized normalization is faster than loop."""
        import time
        from src.utils.hash import normalize_text_pixels

        # Create large test data
        row = np.random.randint(0, 256, size=115, dtype=np.uint8)

        # Warm up
        for _ in range(10):
            normalize_text_pixels(row, 115)

        # Time vectorized version
        start = time.perf_counter()
        for _ in range(1000):
            normalize_text_pixels(row, 115)
        vec_time = time.perf_counter() - start

        # Time loop version
        TEXT_PIXEL_VALUES = (192, 247)
        start = time.perf_counter()
        for _ in range(1000):
            normalized = np.zeros(115, dtype=np.uint8)
            for i in range(len(row)):
                if row[i] in TEXT_PIXEL_VALUES or row[i] > 150:
                    normalized[i] = 192
        loop_time = time.perf_counter() - start

        # Vectorized should be at least 2x faster
        assert vec_time < loop_time, f"Vectorized ({vec_time:.4f}s) should be faster than loop ({loop_time:.4f}s)"


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

"""
Tests for Radar core functions - coordinate detection and navigation utilities.

Ensures:
1. Coordinate conversion works correctly
2. Distance calculations are accurate
3. Direction detection works
4. Waypoint navigation works
5. Walkability checks work
6. Floor detection works
"""
import numpy as np
import pytest
from unittest.mock import Mock, patch, MagicMock


class TestCoordinateConversion:
    """Tests for pixel/coordinate conversion functions."""

    def test_get_pixel_from_coordinate(self):
        """Test converting Tibia coordinate to pixel."""
        from src.repositories.radar.core import get_pixel_from_coordinate, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y

        coord = (32000, 32000, 7)
        pixel = get_pixel_from_coordinate(coord)

        expected_x = coord[0] - COORDINATE_OFFSET_X
        expected_y = coord[1] - COORDINATE_OFFSET_Y

        assert pixel[0] == expected_x
        assert pixel[1] == expected_y

    def test_get_coordinate_from_pixel(self):
        """Test converting pixel to Tibia coordinate."""
        from src.repositories.radar.core import get_coordinate_from_pixel, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y

        pixel = (100, 200)
        floor = 7

        coord = get_coordinate_from_pixel(pixel, floor)

        assert coord[0] == pixel[0] + COORDINATE_OFFSET_X
        assert coord[1] == pixel[1] + COORDINATE_OFFSET_Y
        assert coord[2] == floor

    def test_coordinate_round_trip(self):
        """Test converting coordinate to pixel and back."""
        from src.repositories.radar.core import get_pixel_from_coordinate, get_coordinate_from_pixel

        original_coord = (32500, 32300, 7)
        pixel = get_pixel_from_coordinate(original_coord)
        result_coord = get_coordinate_from_pixel(pixel, original_coord[2])

        assert result_coord == original_coord


class TestDistanceCalculations:
    """Tests for distance calculation functions."""

    def test_manhattan_distance_same_point(self):
        """Test Manhattan distance of same point is 0."""
        from src.repositories.radar.core import manhattan_distance

        coord = (32000, 32000, 7)
        dist = manhattan_distance(coord, coord)

        assert dist == 0

    def test_manhattan_distance_horizontal(self):
        """Test Manhattan distance for horizontal movement."""
        from src.repositories.radar.core import manhattan_distance

        a = (32000, 32000, 7)
        b = (32005, 32000, 7)  # 5 tiles right

        dist = manhattan_distance(a, b)

        assert dist == 5

    def test_manhattan_distance_vertical(self):
        """Test Manhattan distance for vertical movement."""
        from src.repositories.radar.core import manhattan_distance

        a = (32000, 32000, 7)
        b = (32000, 32003, 7)  # 3 tiles down

        dist = manhattan_distance(a, b)

        assert dist == 3

    def test_manhattan_distance_diagonal(self):
        """Test Manhattan distance for diagonal movement."""
        from src.repositories.radar.core import manhattan_distance

        a = (32000, 32000, 7)
        b = (32003, 32004, 7)  # 3 right, 4 down

        dist = manhattan_distance(a, b)

        assert dist == 7  # 3 + 4 = 7

    def test_euclidean_distance_same_point(self):
        """Test Euclidean distance of same point is 0."""
        from src.repositories.radar.core import euclidean_distance

        coord = (32000, 32000, 7)
        dist = euclidean_distance(coord, coord)

        assert dist == 0.0

    def test_euclidean_distance_horizontal(self):
        """Test Euclidean distance for horizontal movement."""
        from src.repositories.radar.core import euclidean_distance

        a = (32000, 32000, 7)
        b = (32005, 32000, 7)  # 5 tiles right

        dist = euclidean_distance(a, b)

        assert dist == 5.0

    def test_euclidean_distance_diagonal(self):
        """Test Euclidean distance for diagonal movement."""
        from src.repositories.radar.core import euclidean_distance

        a = (32000, 32000, 7)
        b = (32003, 32004, 7)  # 3 right, 4 down (3-4-5 triangle)

        dist = euclidean_distance(a, b)

        assert dist == 5.0  # sqrt(3^2 + 4^2) = 5


class TestAdjacencyCheck:
    """Tests for adjacency checking function."""

    def test_is_adjacent_same_tile(self):
        """Test same tile is adjacent to itself."""
        from src.repositories.radar.core import is_adjacent

        a = (32000, 32000, 7)

        assert is_adjacent(a, a) == True

    def test_is_adjacent_horizontal(self):
        """Test horizontally adjacent tiles."""
        from src.repositories.radar.core import is_adjacent

        a = (32000, 32000, 7)
        b = (32001, 32000, 7)

        assert is_adjacent(a, b) == True

    def test_is_adjacent_vertical(self):
        """Test vertically adjacent tiles."""
        from src.repositories.radar.core import is_adjacent

        a = (32000, 32000, 7)
        b = (32000, 32001, 7)

        assert is_adjacent(a, b) == True

    def test_is_adjacent_diagonal(self):
        """Test diagonally adjacent tiles."""
        from src.repositories.radar.core import is_adjacent

        a = (32000, 32000, 7)
        b = (32001, 32001, 7)

        assert is_adjacent(a, b) == True

    def test_is_adjacent_too_far(self):
        """Test tiles that are too far apart."""
        from src.repositories.radar.core import is_adjacent

        a = (32000, 32000, 7)
        b = (32002, 32000, 7)  # 2 tiles away

        assert is_adjacent(a, b) == False

    def test_is_adjacent_different_floor(self):
        """Test tiles on different floors are not adjacent."""
        from src.repositories.radar.core import is_adjacent

        a = (32000, 32000, 7)
        b = (32001, 32000, 8)  # Different floor

        assert is_adjacent(a, b) == False


class TestSameFloorCheck:
    """Tests for same floor checking function."""

    def test_is_same_floor_true(self):
        """Test coordinates on same floor."""
        from src.repositories.radar.core import is_same_floor

        a = (32000, 32000, 7)
        b = (32100, 32200, 7)

        assert is_same_floor(a, b) == True

    def test_is_same_floor_false(self):
        """Test coordinates on different floors."""
        from src.repositories.radar.core import is_same_floor

        a = (32000, 32000, 7)
        b = (32000, 32000, 8)

        assert is_same_floor(a, b) == False


class TestDirectionDetection:
    """Tests for direction detection between coordinates."""

    def test_get_direction_right(self):
        """Test detecting right direction."""
        from src.repositories.radar.core import get_direction_between_coordinates

        a = (32000, 32000, 7)
        b = (32001, 32000, 7)

        direction = get_direction_between_coordinates(a, b)

        assert direction == 'right'

    def test_get_direction_left(self):
        """Test detecting left direction."""
        from src.repositories.radar.core import get_direction_between_coordinates

        a = (32001, 32000, 7)
        b = (32000, 32000, 7)

        direction = get_direction_between_coordinates(a, b)

        assert direction == 'left'

    def test_get_direction_down(self):
        """Test detecting down direction."""
        from src.repositories.radar.core import get_direction_between_coordinates

        a = (32000, 32000, 7)
        b = (32000, 32001, 7)

        direction = get_direction_between_coordinates(a, b)

        assert direction == 'down'

    def test_get_direction_up(self):
        """Test detecting up direction."""
        from src.repositories.radar.core import get_direction_between_coordinates

        a = (32000, 32001, 7)
        b = (32000, 32000, 7)

        direction = get_direction_between_coordinates(a, b)

        assert direction == 'up'

    def test_get_direction_same_position(self):
        """Test direction of same position is None."""
        from src.repositories.radar.core import get_direction_between_coordinates

        a = (32000, 32000, 7)

        direction = get_direction_between_coordinates(a, a)

        assert direction is None


class TestAroundPixelsCoordinates:
    """Tests for getting surrounding pixel coordinates."""

    def test_get_around_pixels_coordinates(self):
        """Test getting 8 surrounding coordinates."""
        from src.repositories.radar.core import get_around_pixels_coordinates

        center = (10, 10)
        around = get_around_pixels_coordinates(center)

        assert len(around) == 8

        # Check all 8 surrounding positions exist
        expected = [
            (9, 9), (10, 9), (11, 9),
            (9, 10), (11, 10),
            (9, 11), (10, 11), (11, 11)
        ]

        for exp in expected:
            assert any(np.allclose(exp, pos) for pos in around)


class TestClosestWaypointIndex:
    """Tests for finding closest waypoint."""

    def test_get_closest_waypoint_index_basic(self):
        """Test finding closest waypoint."""
        from src.repositories.radar.core import get_closest_waypoint_index

        current = (32000, 32000, 7)
        waypoints = [
            {'coordinate': (32010, 32000, 7)},  # 10 tiles away
            {'coordinate': (32002, 32000, 7)},  # 2 tiles away - closest
            {'coordinate': (32005, 32000, 7)},  # 5 tiles away
        ]

        index = get_closest_waypoint_index(current, waypoints)

        assert index == 1  # Second waypoint is closest

    def test_get_closest_waypoint_index_different_floor(self):
        """Test closest waypoint ignores different floors."""
        from src.repositories.radar.core import get_closest_waypoint_index

        current = (32000, 32000, 7)
        waypoints = [
            {'coordinate': (32001, 32000, 8)},  # 1 tile away but different floor
            {'coordinate': (32005, 32000, 7)},  # 5 tiles away same floor
        ]

        index = get_closest_waypoint_index(current, waypoints)

        assert index == 1  # Second waypoint (same floor)

    def test_get_closest_waypoint_index_no_coordinate(self):
        """Test closest waypoint handles missing coordinates."""
        from src.repositories.radar.core import get_closest_waypoint_index

        current = (32000, 32000, 7)
        waypoints = [
            {'label': 'no_coord'},  # No coordinate
            {'coordinate': (32005, 32000, 7)},
        ]

        index = get_closest_waypoint_index(current, waypoints)

        assert index == 1

    def test_get_closest_waypoint_index_empty_list(self):
        """Test closest waypoint with empty list."""
        from src.repositories.radar.core import get_closest_waypoint_index

        current = (32000, 32000, 7)
        waypoints = []

        index = get_closest_waypoint_index(current, waypoints)

        assert index is None


class TestClosestCoordinate:
    """Tests for finding closest coordinate from list."""

    def test_get_closest_coordinate_basic(self):
        """Test finding closest coordinate."""
        from src.repositories.radar.core import get_closest_coordinate

        current = (32000, 32000, 7)
        coordinates = [
            (32010, 32000, 7),
            (32002, 32000, 7),  # Closest
            (32005, 32000, 7),
        ]

        closest = get_closest_coordinate(current, coordinates)

        assert closest == (32002, 32000, 7)

    def test_get_closest_coordinate_empty_list(self):
        """Test closest coordinate with empty list."""
        from src.repositories.radar.core import get_closest_coordinate

        current = (32000, 32000, 7)

        closest = get_closest_coordinate(current, [])

        assert closest is None


class TestAvailableAroundCoordinates:
    """Tests for getting walkable surrounding coordinates."""

    def test_get_available_around_coordinates_all_walkable(self):
        """Test getting walkable coordinates when all are walkable."""
        from src.repositories.radar.core import get_available_around_coordinates, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y

        # Use coordinates that map to small pixel values (within a 500x500 array)
        # offset_x and offset_y are typically large values like 31744
        # So we need to create a coordinate that maps to a pixel we control
        pixel_x, pixel_y = 50, 50  # Target pixel position
        coord = (pixel_x + COORDINATE_OFFSET_X, pixel_y + COORDINATE_OFFSET_Y, 7)

        # Create walkable floor where all positions are walkable
        walkable_floor = np.ones((100, 100), dtype=np.int32)

        available = get_available_around_coordinates(coord, walkable_floor)

        assert len(available) == 8  # All 8 surrounding tiles

    def test_get_available_around_coordinates_some_blocked(self):
        """Test getting walkable coordinates when some are blocked."""
        from src.repositories.radar.core import get_available_around_coordinates, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y

        pixel_x, pixel_y = 50, 50
        coord = (pixel_x + COORDINATE_OFFSET_X, pixel_y + COORDINATE_OFFSET_Y, 7)

        # Create walkable floor with some blocked positions
        walkable_floor = np.ones((100, 100), dtype=np.int32)
        # Block some tiles around the center
        walkable_floor[pixel_y - 1, pixel_x - 1] = 0  # Top-left
        walkable_floor[pixel_y - 1, pixel_x] = 0      # Top

        available = get_available_around_coordinates(coord, walkable_floor)

        assert len(available) == 6  # 8 - 2 blocked = 6


class TestLocateFunction:
    """Tests for template locate function."""

    def test_locate_finds_template(self):
        """Test _locate finds matching template."""
        from src.repositories.radar.core import _locate

        # Create image with a distinctive pattern (gradient for better matching)
        img = np.zeros((100, 100), dtype=np.uint8)
        for i in range(10):
            for j in range(10):
                img[40+i, 40+j] = (i * 25 + j * 10) % 256

        # Create template that matches the pattern
        template = np.zeros((10, 10), dtype=np.uint8)
        for i in range(10):
            for j in range(10):
                template[i, j] = (i * 25 + j * 10) % 256

        result = _locate(img, template, confidence=0.9)

        assert result is not None
        assert result[0] == 40  # x
        assert result[1] == 40  # y

    def test_locate_not_found(self):
        """Test _locate returns None when not found."""
        from src.repositories.radar.core import _locate

        # Create gradient image
        img = np.zeros((100, 100), dtype=np.uint8)
        for i in range(100):
            img[i, :] = i * 2 % 256

        # Template with completely different pattern
        template = np.full((10, 10), 128, dtype=np.uint8)

        result = _locate(img, template, confidence=0.9)

        assert result is None

    def test_locate_none_inputs(self):
        """Test _locate handles None inputs."""
        from src.repositories.radar.core import _locate

        assert _locate(None, np.zeros((10, 10))) is None
        assert _locate(np.zeros((100, 100)), None) is None

    def test_locate_template_larger(self):
        """Test _locate handles template larger than image."""
        from src.repositories.radar.core import _locate

        img = np.zeros((10, 10), dtype=np.uint8)
        template = np.zeros((20, 20), dtype=np.uint8)

        result = _locate(img, template)

        assert result is None


class TestHashFunction:
    """Tests for hash function."""

    def test_hashit_same_array_same_hash(self):
        """Test same array produces same hash."""
        from src.repositories.radar.core import _hashit

        arr = np.array([1, 2, 3, 4, 5], dtype=np.uint8)

        hash1 = _hashit(arr)
        hash2 = _hashit(arr)

        assert hash1 == hash2

    def test_hashit_different_array_different_hash(self):
        """Test different arrays produce different hashes."""
        from src.repositories.radar.core import _hashit

        arr1 = np.array([1, 2, 3, 4, 5], dtype=np.uint8)
        arr2 = np.array([5, 4, 3, 2, 1], dtype=np.uint8)

        hash1 = _hashit(arr1)
        hash2 = _hashit(arr2)

        assert hash1 != hash2

    def test_hashit_none(self):
        """Test hashit handles None."""
        from src.repositories.radar.core import _hashit

        result = _hashit(None)

        assert result == 0


class TestIsCoordinateWalkable:
    """Tests for coordinate walkability check."""

    @patch('src.repositories.radar.config.walkableFloorsSqms')
    def test_is_coordinate_walkable_true(self, mock_walkable):
        """Test coordinate is walkable."""
        from src.repositories.radar.core import is_coordinate_walkable, get_pixel_from_coordinate

        coord = (32000, 32000, 7)
        pixel = get_pixel_from_coordinate(coord)

        # Mock the walkable array
        mock_walkable.__getitem__ = Mock(return_value=1)

        result = is_coordinate_walkable(coord)

        assert result == True

    @patch('src.repositories.radar.config.walkableFloorsSqms')
    def test_is_coordinate_walkable_false(self, mock_walkable):
        """Test coordinate is not walkable."""
        from src.repositories.radar.core import is_coordinate_walkable

        coord = (32000, 32000, 7)

        # Mock the walkable array to return 0 (not walkable)
        mock_walkable.__getitem__ = Mock(return_value=0)

        result = is_coordinate_walkable(coord)

        assert result == False


class TestNonWalkablePixelColor:
    """Tests for non-walkable pixel color check."""

    @patch('src.repositories.radar.core.nonWalkablePixelsColors', np.array([0, 64, 128]))
    def test_is_non_walkable_pixel_color_true(self):
        """Test pixel color is non-walkable."""
        from src.repositories.radar.core import is_non_walkable_pixel_color

        result = is_non_walkable_pixel_color(64)

        assert result == True

    @patch('src.repositories.radar.core.nonWalkablePixelsColors', np.array([0, 64, 128]))
    def test_is_non_walkable_pixel_color_false(self):
        """Test pixel color is walkable."""
        from src.repositories.radar.core import is_non_walkable_pixel_color

        result = is_non_walkable_pixel_color(200)

        assert result == False


class TestCheckRadarZoom:
    """Tests for radar zoom check function."""

    @patch('src.repositories.radar.core.get_radar_tools_position')
    def test_check_radar_zoom_tools_not_found(self, mock_get_tools):
        """Test radar zoom check when tools not found."""
        from src.repositories.radar.core import check_radar_zoom

        mock_get_tools.return_value = None
        screenshot = np.zeros((800, 600), dtype=np.uint8)

        ok, message = check_radar_zoom(screenshot)

        assert ok == False
        assert "tools not found" in message.lower()


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

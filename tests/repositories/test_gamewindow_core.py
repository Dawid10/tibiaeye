"""
Tests for the refactored gamewindow modules.

Covers every public function in:
- creatures.py  (bar detection, identification, pathfinding, filtering, new features)
- core.py       (locate, slot utilities, capture)
- config.py     (constants, loaders)
- wiki/misalignment.py
- gameloop direction tracking
"""
import numpy as np
import pytest
from collections import Counter
from dataclasses import dataclass
from typing import Tuple

from src.repositories.gamewindow.creatures import (
    GameWindowCreature,
    get_creatures_bars,
    has_matrix_inside_other,
    identify_creature,
    make_creature,
    get_creatures,
    bfs_flood_fill,
    get_closest_creature,
    has_target_to_creature,
    get_target_creature,
    get_creatures_by_type,
    get_monsters,
    get_players,
    get_different_creatures_by_slots,
    get_nearest_creatures_count,
)
from src.repositories.gamewindow.core import (
    locate,
    capture_game_window,
    get_slot_from_coordinate,
    get_slot_screen_position,
    find_left_arrow,
    find_right_arrow,
    get_game_window_position,
)
from src.repositories.gamewindow.config import (
    GAME_WINDOW_SIZES,
    RESOLUTIONS,
    GRID_WIDTH,
    GRID_HEIGHT,
    PLAYER_SLOT_X,
    PLAYER_SLOT_Y,
    BAR_WIDTH,
    BAR_HEIGHT,
    BLACK_THRESHOLD,
    UNDER_ROOF_PIXEL_VALUE,
    IGNORED_PIXEL_VALUES,
    load_gray_image,
    load_arrow_images,
    load_monster_templates,
)
from src.wiki.misalignment import get_misalignment, MISALIGNMENT, DEFAULT_MISALIGNMENT
from src.core.constants import UNIDENTIFIED_CREATURE_NAME


# ---------------------------------------------------------------------------
# helpers
# ---------------------------------------------------------------------------

def _make_hp_bar(x: int, y: int, fill: int = 20) -> tuple:
    """Return (bar_array, x, y) for placing into an image."""
    bar = np.zeros((4, 27), dtype=np.uint8)
    bar[1, 1:1 + fill] = 113
    bar[2, 1:1 + fill] = 113
    return bar


def _image_with_bars(positions, width=400, height=300):
    img = np.ones((height, width), dtype=np.uint8) * 128
    for x, y in positions:
        bar = _make_hp_bar(x, y)
        img[y:y + 4, x:x + 27] = bar
    return img


def _creature(name, slot, creature_type='monster', attacked=False,
              coord_base=(32000, 32000, 7)):
    sx, sy = slot
    return GameWindowCreature(
        name=name,
        creature_type=creature_type,
        slot=slot,
        coordinate=(coord_base[0] - 7 + sx, coord_base[1] - 5 + sy, coord_base[2]),
        window_coordinate=(100 + sx * 64, 100 + sy * 64),
        game_window_coordinate=(sx * 64, sy * 64),
        is_being_attacked=attacked,
    )


# ===================================================================
# config.py
# ===================================================================

class TestConfig:

    def test_game_window_sizes_has_both_resolutions(self):
        assert 720 in GAME_WINDOW_SIZES
        assert 1080 in GAME_WINDOW_SIZES
        assert GAME_WINDOW_SIZES[1080] == (960, 704)

    def test_resolutions_slot_widths(self):
        assert RESOLUTIONS[720]['slotWidth'] == 32
        assert RESOLUTIONS[1080]['slotWidth'] == 64

    def test_grid_constants(self):
        assert GRID_WIDTH == 15
        assert GRID_HEIGHT == 11
        assert PLAYER_SLOT_X == 7
        assert PLAYER_SLOT_Y == 5

    def test_bar_constants(self):
        assert BAR_WIDTH == 27
        assert BAR_HEIGHT == 4
        assert BLACK_THRESHOLD == 5

    def test_ignored_pixel_values_contains_expected(self):
        for v in (0, 113, 29, 57, 91, 152, 170, 192):
            assert v in IGNORED_PIXEL_VALUES

    def test_load_gray_image_nonexistent_returns_none(self):
        assert load_gray_image("/nonexistent/image.png") is None

    def test_load_arrow_images_returns_dict(self):
        arrows = load_arrow_images()
        assert isinstance(arrows, dict)

    def test_load_monster_templates_nonexistent_folder(self):
        templates = load_monster_templates("/nonexistent/folder")
        assert templates == {}

    def test_load_monster_templates_real_folder(self):
        templates = load_monster_templates()
        assert len(templates) > 0
        assert isinstance(list(templates.values())[0], np.ndarray)


# ===================================================================
# wiki/misalignment.py
# ===================================================================

class TestMisalignment:

    def test_known_creature_returns_data(self):
        m = get_misalignment('Rotworm')
        assert m == {'x': 16, 'y': 16}

    def test_unknown_creature_returns_default(self):
        m = get_misalignment('NonExistentMonster')
        assert m == DEFAULT_MISALIGNMENT
        assert m == {'x': 0, 'y': 0}

    def test_zero_misalignment_creatures(self):
        for name in ('Dragon', 'Cyclops', 'Demon'):
            assert get_misalignment(name) == {'x': 0, 'y': 0}

    def test_nonzero_misalignment_creatures(self):
        for name in ('Rat', 'Larva', 'Bug', 'Wasp', 'Snake', 'Spider'):
            m = get_misalignment(name)
            assert m['x'] == 16 and m['y'] == 16, f"{name} should have 16,16"

    def test_misalignment_dict_not_empty(self):
        assert len(MISALIGNMENT) > 0


# ===================================================================
# creatures.py — bar detection
# ===================================================================

class TestBarDetection:

    def test_single_bar(self):
        img = _image_with_bars([(50, 30)])
        bars = get_creatures_bars(img)
        assert len(bars) == 1
        assert bars[0] == (50, 30)

    def test_multiple_bars(self):
        positions = [(50, 30), (100, 60), (150, 90)]
        img = _image_with_bars(positions)
        bars = get_creatures_bars(img)
        assert len(bars) == 3
        for pos in positions:
            assert pos in bars

    def test_no_bars_in_plain_image(self):
        img = np.ones((100, 200), dtype=np.uint8) * 128
        bars = get_creatures_bars(img)
        assert len(bars) == 0

    def test_image_too_small_returns_empty(self):
        img = np.zeros((2, 10), dtype=np.uint8)
        bars = get_creatures_bars(img)
        assert bars == []

    def test_random_black_lines_not_detected(self):
        img = np.ones((100, 200), dtype=np.uint8) * 128
        img[20, 30:60] = 0
        img[40:45, 80] = 0
        bars = get_creatures_bars(img)
        assert len(bars) == 0

    def test_overlapping_bars_deduplicated(self):
        img = np.ones((100, 200), dtype=np.uint8) * 128
        bar = _make_hp_bar(50, 30)
        img[30:34, 50:77] = bar
        img[30:34, 55:82] = bar  # overlaps with first
        bars = get_creatures_bars(img)
        assert len(bars) == 1


# ===================================================================
# creatures.py — has_matrix_inside_other
# ===================================================================

class TestHasMatrixInsideOther:

    def test_identical_matrices_match(self):
        template = np.zeros((5, 10), dtype=np.uint8)
        region = np.zeros((5, 10), dtype=np.uint8)
        assert has_matrix_inside_other(region, template) is True

    def test_mismatch_detected(self):
        template = np.zeros((5, 10), dtype=np.uint8)
        region = np.full((5, 10), 50, dtype=np.uint8)
        assert has_matrix_inside_other(region, template) is False

    def test_ignored_pixel_values_pass(self):
        template = np.zeros((3, 3), dtype=np.uint8)
        for val in IGNORED_PIXEL_VALUES:
            region = np.full((3, 3), val, dtype=np.uint8)
            assert has_matrix_inside_other(region, template) is True, \
                f"pixel value {val} should be ignored"

    def test_non_ignored_pixel_fails(self):
        template = np.zeros((3, 3), dtype=np.uint8)
        region = np.full((3, 3), 100, dtype=np.uint8)
        assert has_matrix_inside_other(region, template) is False

    def test_nonzero_template_pixels_ignored(self):
        template = np.full((3, 3), 200, dtype=np.uint8)
        region = np.full((3, 3), 100, dtype=np.uint8)
        # template != 0 → condition skipped → should return True
        assert has_matrix_inside_other(region, template) is True

    def test_mixed_content(self):
        template = np.array([[0, 200], [0, 0]], dtype=np.uint8)
        region = np.array([[113, 50], [192, 0]], dtype=np.uint8)
        # (0,0): template=0, region=113 → ignored pixel → OK
        # (0,1): template=200 → skip
        # (1,0): template=0, region=192 → ignored pixel → OK
        # (1,1): template=0, region=0 → ignored pixel → OK
        assert has_matrix_inside_other(region, template) is True


# ===================================================================
# creatures.py — identify_creature
# ===================================================================

class TestIdentifyCreature:

    def _make_image(self, h=100, w=200):
        return np.ones((h, w), dtype=np.uint8) * 128

    def test_trust_battlelist_single_type(self):
        img = self._make_image()
        available = Counter({'Rotworm': 2})
        matched = Counter()
        name, ctype, method = identify_creature(
            img, 50, 30, ['Rotworm', 'Rotworm'], available, matched,
            total_bars=2, monster_templates={}, logged_warnings=set()
        )
        assert name == 'Rotworm'
        assert ctype == 'monster'
        assert method == 'BL'

    def test_fallback_to_player_when_no_names(self):
        img = self._make_image()
        available = Counter()
        matched = Counter()
        name, ctype, method = identify_creature(
            img, 50, 30, [], available, matched,
            total_bars=1, monster_templates={}, logged_warnings=set()
        )
        assert name == UNIDENTIFIED_CREATURE_NAME
        assert ctype == 'player'

    def test_more_bars_than_names_marks_player(self):
        img = self._make_image()
        available = Counter({'Rotworm': 1})
        matched = Counter({'Rotworm': 1})  # already matched
        name, ctype, method = identify_creature(
            img, 50, 30, ['Rotworm'], available, matched,
            total_bars=3, monster_templates={}, logged_warnings=set()
        )
        assert name == UNIDENTIFIED_CREATURE_NAME
        assert ctype == 'player'

    def test_fallback_bl_when_bars_leq_names(self):
        """When TM fails but bars <= monster names → BL fallback."""
        img = self._make_image()
        available = Counter({'Rotworm': 1, 'Larva': 1})
        matched = Counter()
        name, ctype, method = identify_creature(
            img, 50, 30, ['Rotworm', 'Larva'], available, matched,
            total_bars=2, monster_templates={}, logged_warnings=set()
        )
        # Multiple unique types → tries TM → fails → fallback BL
        assert ctype == 'monster'
        assert method == 'BL'

    def test_single_type_with_extra_bars_trusts_battlelist(self):
        """Bug fix: 2 bars + 1 monster name → first bar = monster (not player)."""
        img = self._make_image()
        available = Counter({'Swamp Troll': 1})
        matched = Counter()
        name, ctype, method = identify_creature(
            img, 50, 30, ['Swamp Troll'], available, matched,
            total_bars=2, monster_templates={}, logged_warnings=set()
        )
        assert name == 'Swamp Troll'
        assert ctype == 'monster'
        assert method == 'BL'

    def test_extra_bars_exhaust_names_then_player(self):
        """After all monster names assigned, remaining bars become player."""
        img = self._make_image()
        available = Counter({'Swamp Troll': 1})
        matched = Counter({'Swamp Troll': 1})  # already assigned
        name, ctype, method = identify_creature(
            img, 50, 30, ['Swamp Troll'], available, matched,
            total_bars=2, monster_templates={}, logged_warnings=set()
        )
        assert name == UNIDENTIFIED_CREATURE_NAME
        assert ctype == 'player'

    def test_multi_type_skips_strategy1(self):
        """Multiple unique types → Strategy 1 should NOT apply."""
        img = self._make_image()
        available = Counter({'Rotworm': 1, 'Larva': 1})
        matched = Counter()
        name, ctype, method = identify_creature(
            img, 50, 30, ['Rotworm', 'Larva'], available, matched,
            total_bars=3, monster_templates={}, logged_warnings=set()
        )
        # Strategy 1 fails (2 unique types), TM fails (no templates),
        # Strategy 3 fails (3 > 2), falls through to player
        assert ctype == 'player'

    def test_logs_warning_for_missing_template(self):
        img = self._make_image()
        available = Counter({'Rotworm': 1, 'Larva': 1})
        matched = Counter()
        warnings = set()
        identify_creature(
            img, 50, 30, ['Rotworm', 'Larva'], available, matched,
            total_bars=3, monster_templates={}, logged_warnings=warnings
        )
        assert 'Rotworm' in warnings
        assert 'Larva' in warnings


# ===================================================================
# creatures.py — make_creature
# ===================================================================

class TestMakeCreature:

    def _make_image(self, h=704, w=960):
        return np.ones((h, w), dtype=np.uint8) * 128

    def test_basic_creature_creation(self):
        img = self._make_image()
        c = make_creature(
            'Dragon', 'monster', 'TM', 200, 100,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704)
        )
        assert c.name == 'Dragon'
        assert c.creature_type == 'monster'
        assert c.id_method == 'TM'
        assert c.is_being_attacked is False
        assert isinstance(c.slot, tuple)
        assert len(c.slot) == 2
        assert isinstance(c.coordinate, tuple)
        assert len(c.coordinate) == 3
        assert c.coordinate[2] == 7

    def test_misalignment_affects_slot(self):
        """Rotworm has misalignment (16,16), should shift slot."""
        img = self._make_image()
        c_dragon = make_creature(
            'Dragon', 'monster', 'TM', 200, 100,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704)
        )
        c_rotworm = make_creature(
            'Rotworm', 'monster', 'TM', 200, 100,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704)
        )
        # Rotworm has +16 pixel offset, Dragon has 0
        # They may end up in different slots depending on bar position
        assert c_rotworm.slot[0] >= c_dragon.slot[0]

    def test_world_coordinate_derived_from_slot(self):
        img = self._make_image()
        player_coord = (32007, 32005, 7)
        c = make_creature(
            'Dragon', 'monster', 'TM', 200, 100,
            img, player_coord, 64, (0, 0, 960, 704)
        )
        sx, sy = c.slot
        assert c.coordinate == (player_coord[0] - 7 + sx,
                                player_coord[1] - 5 + sy,
                                player_coord[2])

    def test_is_under_roof_pixel_check(self):
        img = self._make_image()
        # Place UNDER_ROOF_PIXEL_VALUE at the check position
        slot_width = 64
        bar_x, bar_y = 200, 100
        check_x = max(0, bar_x - 19) + slot_width // 2
        check_y = bar_y + 5 + slot_width // 2
        img[check_y, check_x] = UNDER_ROOF_PIXEL_VALUE

        c = make_creature(
            'Dragon', 'monster', 'TM', bar_x, bar_y,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704)
        )
        assert c.is_under_roof

    def test_not_under_roof_by_default(self):
        img = self._make_image()
        c = make_creature(
            'Dragon', 'monster', 'TM', 200, 100,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704)
        )
        assert not c.is_under_roof

    def test_attack_border_detected(self):
        img = self._make_image()
        slot_width = 64
        bar_x, bar_y = 200, 100
        border_x = bar_x - 19
        border_y = bar_y + 5
        border_gap = 4

        # Fill top/bottom/left/right borders with attack color (76)
        region = img[border_y:border_y + slot_width, border_x:border_x + slot_width]
        region[0:border_gap, :] = 76
        region[-border_gap:, :] = 76
        region[border_gap:-border_gap, 0:border_gap] = 76
        region[border_gap:-border_gap, -border_gap:] = 76

        c = make_creature(
            'Dragon', 'monster', 'TM', bar_x, bar_y,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704)
        )
        assert c.is_being_attacked is True

    def test_direction_and_walked_pixels_accepted(self):
        """make_creature should accept direction and walked_pixels without error."""
        img = self._make_image()
        c = make_creature(
            'Dragon', 'monster', 'TM', 200, 100,
            img, (32007, 32005, 7), 64, (0, 0, 960, 704),
            direction='north', walked_pixels=10
        )
        assert c.name == 'Dragon'

    def test_bar_at_edge_doesnt_crash(self):
        img = self._make_image(h=120, w=100)
        c = make_creature(
            'Rat', 'monster', 'BL', 5, 5,
            img, (32007, 32005, 7), 64, (0, 0, 100, 120)
        )
        assert c.name == 'Rat'

    def test_resolution_720_slot_width_32(self):
        img = self._make_image(h=352, w=480)
        c = make_creature(
            'Dragon', 'monster', 'TM', 100, 50,
            img, (32007, 32005, 7), 32, (0, 0, 480, 352)
        )
        assert c.name == 'Dragon'
        assert isinstance(c.slot, tuple)


# ===================================================================
# creatures.py — get_creatures pipeline
# ===================================================================

class TestGetCreaturesPipeline:

    def test_returns_empty_when_no_bars(self):
        img = np.ones((704, 960), dtype=np.uint8) * 128
        result = get_creatures(
            ['Rotworm'], (32007, 32005, 7), img,
            (0, 0, 960, 704), 64, {}, set()
        )
        assert result == []

    def test_detects_creatures_from_bars(self):
        img = _image_with_bars([(50, 30), (150, 80)], width=960, height=704)
        result = get_creatures(
            ['Rotworm', 'Rotworm'], (32007, 32005, 7), img,
            (0, 0, 960, 704), 64, {}, set()
        )
        assert len(result) == 2
        assert all(c.name == 'Rotworm' for c in result)
        assert all(c.id_method == 'BL' for c in result)

    def test_extra_bars_first_monster_rest_player(self):
        img = _image_with_bars([(50, 30), (150, 80), (250, 130)],
                               width=960, height=704)
        result = get_creatures(
            ['Rotworm'], (32007, 32005, 7), img,
            (0, 0, 960, 704), 64, {}, set()
        )
        # First bar gets the single monster name, rest become player
        monsters = [c for c in result if c.creature_type == 'monster']
        players = [c for c in result if c.creature_type == 'player']
        assert len(result) == 3
        assert len(monsters) == 1
        assert monsters[0].name == 'Rotworm'
        assert len(players) == 2

    def test_direction_parameter_passed(self):
        img = _image_with_bars([(50, 30)], width=960, height=704)
        result = get_creatures(
            ['Rotworm'], (32007, 32005, 7), img,
            (0, 0, 960, 704), 64, {}, set(),
            direction='north', walked_pixels=10
        )
        assert len(result) == 1


# ===================================================================
# creatures.py — BFS pathfinding
# ===================================================================

class TestBFSFloodFill:

    def test_open_grid_all_reachable(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        distances = bfs_flood_fill(walkable, 5, 7, set())
        assert len(distances) == 11 * 15
        assert distances[(5, 7)] == 0

    def test_adjacent_distance_one(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        distances = bfs_flood_fill(walkable, 5, 7, set())
        assert distances[(5, 8)] == 1
        assert distances[(5, 6)] == 1
        assert distances[(4, 7)] == 1
        assert distances[(6, 7)] == 1

    def test_wall_blocks_path(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        walkable[5, 8] = 0
        distances = bfs_flood_fill(walkable, 5, 7, set())
        assert (5, 8) not in distances

    def test_full_wall_splits_grid(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        walkable[3, :] = 0  # wall at row 3, away from player
        distances = bfs_flood_fill(walkable, 5, 7, set())
        # player can't reach rows above the wall
        assert (2, 7) not in distances
        assert (0, 7) not in distances
        # player can reach rows below the wall
        assert (6, 7) in distances

    def test_creature_blocks_continuation(self):
        walkable = np.ones((5, 5), dtype=np.int32)
        blocked = {(3, 2)}  # creature at col 3, row 2 (x, y)
        distances = bfs_flood_fill(walkable, 2, 2, blocked)
        # creature tile IS reachable (can attack)
        assert (2, 3) in distances
        # tiles beyond are still reachable (going around)
        assert (2, 4) in distances

    def test_manhattan_distances_in_open_grid(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        distances = bfs_flood_fill(walkable, 5, 7, set())
        assert distances[(0, 0)] == 12
        assert distances[(10, 14)] == 12


# ===================================================================
# creatures.py — get_closest_creature
# ===================================================================

class TestGetClosestCreature:

    def _walkable_func(self, walkable_matrix):
        return lambda coord: walkable_matrix

    def test_empty_list_returns_none(self):
        result = get_closest_creature([], (32007, 32005, 7),
                                      self._walkable_func(None))
        assert result is None

    def test_single_reachable_creature(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        c = _creature('Rotworm', (9, 5))
        result = get_closest_creature(
            [c], (32007, 32005, 7), self._walkable_func(walkable)
        )
        assert result is not None
        assert result.name == 'Rotworm'

    def test_closest_selected_among_multiple(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        close = _creature('Rat', (8, 5))
        far = _creature('Dragon', (12, 5))
        result = get_closest_creature(
            [far, close], (32007, 32005, 7), self._walkable_func(walkable)
        )
        assert result.name == 'Rat'

    def test_creature_behind_wall_filtered(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        for row in range(11):
            walkable[row, 9] = 0
        behind_wall = _creature('Dragon', (10, 5))
        result = get_closest_creature(
            [behind_wall], (32007, 32005, 7), self._walkable_func(walkable)
        )
        assert result is None

    def test_reachable_preferred_over_unreachable(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        for row in range(11):
            walkable[row, 9] = 0
        unreachable = _creature('Dragon', (10, 5))
        reachable = _creature('Rat', (5, 5))
        result = get_closest_creature(
            [unreachable, reachable], (32007, 32005, 7),
            self._walkable_func(walkable)
        )
        assert result.name == 'Rat'

    def test_creature_at_player_slot_skipped(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        at_player = _creature('Ghost', (7, 5))
        nearby = _creature('Rat', (8, 5))
        result = get_closest_creature(
            [at_player, nearby], (32007, 32005, 7),
            self._walkable_func(walkable)
        )
        assert result.name == 'Rat'

    def test_no_walkable_returns_none(self):
        close = _creature('Rat', (8, 5))
        far = _creature('Dragon', (12, 5))
        result = get_closest_creature(
            [far, close], (32007, 32005, 7), lambda c: None
        )
        assert result is None

    def test_out_of_bounds_creature_ignored(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        oob = _creature('Ghost', (20, 20))
        valid = _creature('Rat', (8, 5))
        result = get_closest_creature(
            [oob, valid], (32007, 32005, 7), self._walkable_func(walkable)
        )
        assert result.name == 'Rat'


# ===================================================================
# creatures.py — has_target_to_creature
# ===================================================================

class TestHasTargetToCreature:

    def _walkable_func(self, walkable_matrix):
        return lambda coord: walkable_matrix

    def test_reachable_target_returns_true(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        target = _creature('Rotworm', (9, 5))
        result = has_target_to_creature(
            [target], target, (32007, 32005, 7),
            self._walkable_func(walkable)
        )
        assert result == True

    def test_target_behind_wall_returns_false(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        for row in range(11):
            walkable[row, 9] = 0
        target = _creature('Dragon', (10, 5))
        result = has_target_to_creature(
            [target], target, (32007, 32005, 7),
            self._walkable_func(walkable)
        )
        assert result == False

    def test_none_target_returns_false(self):
        walkable = np.ones((11, 15), dtype=np.int32)
        result = has_target_to_creature(
            [], None, (32007, 32005, 7),
            self._walkable_func(walkable)
        )
        assert result == False

    def test_no_walkable_returns_false(self):
        target = _creature('Rotworm', (9, 5))
        result = has_target_to_creature(
            [target], target, (32007, 32005, 7),
            lambda c: None
        )
        assert result == False


# ===================================================================
# creatures.py — filtering helpers
# ===================================================================

class TestFilteringHelpers:

    def test_get_target_creature_finds_attacked(self):
        c1 = _creature('Rotworm', (8, 5))
        c2 = _creature('Larva', (9, 5), attacked=True)
        assert get_target_creature([c1, c2]).name == 'Larva'

    def test_get_target_creature_none_when_no_attack(self):
        c1 = _creature('Rotworm', (8, 5))
        assert get_target_creature([c1]) is None

    def test_get_target_creature_empty_list(self):
        assert get_target_creature([]) is None

    def test_get_creatures_by_type(self):
        c1 = _creature('Rotworm', (8, 5), creature_type='monster')
        c2 = _creature('Player1', (9, 5), creature_type='player')
        c3 = _creature('Larva', (10, 5), creature_type='monster')
        assert len(get_creatures_by_type([c1, c2, c3], 'monster')) == 2
        assert len(get_creatures_by_type([c1, c2, c3], 'player')) == 1
        assert len(get_creatures_by_type([c1, c2, c3], 'npc')) == 0

    def test_get_monsters(self):
        creatures = [
            _creature('Rotworm', (8, 5), creature_type='monster'),
            _creature('Player1', (9, 5), creature_type='player'),
        ]
        monsters = get_monsters(creatures)
        assert len(monsters) == 1
        assert monsters[0].name == 'Rotworm'

    def test_get_players(self):
        creatures = [
            _creature('Rotworm', (8, 5), creature_type='monster'),
            _creature('Player1', (9, 5), creature_type='player'),
        ]
        players = get_players(creatures)
        assert len(players) == 1
        assert players[0].name == 'Player1'


# ===================================================================
# creatures.py — new feature: loot detection
# ===================================================================

class TestLootDetection:

    def test_detect_killed_creature(self):
        prev = [
            _creature('Rotworm', (8, 5)),
            _creature('Larva', (10, 5)),
        ]
        curr = [_creature('Rotworm', (8, 5))]

        killed = get_different_creatures_by_slots(prev, curr)
        assert len(killed) == 1
        assert killed[0].name == 'Larva'

    def test_no_kills(self):
        prev = [_creature('Rotworm', (8, 5))]
        curr = [_creature('Rotworm', (8, 5))]
        killed = get_different_creatures_by_slots(prev, curr)
        assert killed == []

    def test_all_killed(self):
        prev = [
            _creature('Rotworm', (8, 5)),
            _creature('Larva', (10, 5)),
        ]
        killed = get_different_creatures_by_slots(prev, [])
        assert len(killed) == 2

    def test_empty_previous(self):
        curr = [_creature('Rotworm', (8, 5))]
        killed = get_different_creatures_by_slots([], curr)
        assert killed == []

    def test_both_empty(self):
        assert get_different_creatures_by_slots([], []) == []

    def test_filter_by_slots(self):
        prev = [
            _creature('Rotworm', (8, 5)),
            _creature('Larva', (10, 5)),
        ]
        curr = []
        # Only check slot (8, 5)
        killed = get_different_creatures_by_slots(prev, curr, slots=[(8, 5)])
        assert len(killed) == 1
        assert killed[0].name == 'Rotworm'

    def test_new_creature_not_in_killed(self):
        prev = [_creature('Rotworm', (8, 5))]
        curr = [_creature('Larva', (10, 5))]  # new creature at different slot
        killed = get_different_creatures_by_slots(prev, curr)
        assert len(killed) == 1
        assert killed[0].name == 'Rotworm'


# ===================================================================
# creatures.py — new feature: nearest creatures count
# ===================================================================

class TestNearestCreaturesCount:

    def test_no_creatures(self):
        assert get_nearest_creatures_count([]) == 0

    def test_creature_adjacent(self):
        creatures = [_creature('Rotworm', (8, 5))]
        assert get_nearest_creatures_count(creatures) == 1

    def test_creature_at_player_not_counted(self):
        creatures = [_creature('Ghost', (7, 5))]
        assert get_nearest_creatures_count(creatures) == 0

    def test_diagonal_adjacent_counted(self):
        creatures = [_creature('Rotworm', (8, 6))]  # diagonal
        assert get_nearest_creatures_count(creatures) == 1

    def test_far_creature_not_counted(self):
        creatures = [_creature('Dragon', (12, 5))]
        assert get_nearest_creatures_count(creatures) == 0

    def test_all_8_surrounding(self):
        creatures = [
            _creature('R1', (6, 4)), _creature('R2', (7, 4)), _creature('R3', (8, 4)),
            _creature('R4', (6, 5)),                           _creature('R5', (8, 5)),
            _creature('R6', (6, 6)), _creature('R7', (7, 6)), _creature('R8', (8, 6)),
        ]
        assert get_nearest_creatures_count(creatures) == 8

    def test_mix_near_and_far(self):
        creatures = [
            _creature('Rat', (8, 5)),      # near
            _creature('Dragon', (12, 5)),  # far
            _creature('Larva', (6, 4)),    # near (diagonal)
        ]
        assert get_nearest_creatures_count(creatures) == 2


# ===================================================================
# core.py — locate
# ===================================================================

class TestLocate:

    def test_finds_exact_match(self):
        rng = np.random.RandomState(42)
        template = rng.randint(50, 200, (10, 10), dtype=np.uint8)
        img = np.zeros((100, 100), dtype=np.uint8)
        img[20:30, 30:40] = template
        result = locate(img, template, confidence=0.9)
        assert result is not None
        assert result[0] == 30
        assert result[1] == 20

    def test_returns_none_for_no_match(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        template = np.full((10, 10), 200, dtype=np.uint8)
        result = locate(img, template, confidence=0.99)
        assert result is None

    def test_none_inputs(self):
        assert locate(None, np.zeros((5, 5), dtype=np.uint8)) is None
        assert locate(np.zeros((50, 50), dtype=np.uint8), None) is None

    def test_template_larger_than_image(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        template = np.zeros((20, 20), dtype=np.uint8)
        assert locate(img, template) is None


# ===================================================================
# core.py — slot utilities
# ===================================================================

class TestSlotUtilities:

    def test_get_slot_from_coordinate_center(self):
        player = (32007, 32005, 7)
        target = (32007, 32005, 7)
        assert get_slot_from_coordinate(player, target) == (7, 5)

    def test_get_slot_from_coordinate_offset(self):
        player = (32007, 32005, 7)
        target = (32009, 32003, 7)
        assert get_slot_from_coordinate(player, target) == (9, 3)

    def test_get_slot_from_coordinate_out_of_range(self):
        player = (32007, 32005, 7)
        target = (32020, 32005, 7)  # too far
        assert get_slot_from_coordinate(player, target) is None

    def test_get_slot_from_coordinate_edge(self):
        player = (32007, 32005, 7)
        target = (32014, 32010, 7)  # diff_x=7, diff_y=5 (max allowed)
        assert get_slot_from_coordinate(player, target) == (14, 10)

    def test_get_slot_from_coordinate_negative_edge(self):
        player = (32007, 32005, 7)
        target = (32000, 32000, 7)  # diff_x=-7, diff_y=-5
        assert get_slot_from_coordinate(player, target) == (0, 0)

    def test_get_slot_screen_position(self):
        gw_pos = (100, 50, 960, 704)
        pos = get_slot_screen_position((7, 5), gw_pos)
        assert pos is not None
        slot_w = 960 // 15
        slot_h = 704 // 11
        expected_x = 100 + 7 * slot_w + slot_w // 2
        expected_y = 50 + 5 * slot_h + slot_h // 2
        assert pos == (expected_x, expected_y)

    def test_get_slot_screen_position_none_gw(self):
        assert get_slot_screen_position((7, 5), None) is None

    def test_get_slot_screen_position_corner(self):
        gw_pos = (0, 0, 960, 704)
        pos = get_slot_screen_position((0, 0), gw_pos)
        assert pos is not None
        assert pos[0] > 0
        assert pos[1] > 0


# ===================================================================
# core.py — capture_game_window
# ===================================================================

class TestCaptureGameWindow:

    def test_captures_region(self):
        screenshot = np.ones((1080, 1920), dtype=np.uint8) * 128
        gw_pos = (100, 50, 960, 704)
        result = capture_game_window(screenshot, gw_pos)
        assert result is not None
        assert result.shape == (704, 960)

    def test_none_position_returns_none(self):
        screenshot = np.ones((1080, 1920), dtype=np.uint8)
        assert capture_game_window(screenshot, None) is None


# ===================================================================
# core.py — arrow detection
# ===================================================================

class TestArrowDetection:

    def test_find_left_arrow_cache_hit(self):
        cache = {'position': (10, 20, 5, 5), 'arrow': 'test'}
        screenshot = np.ones((100, 100), dtype=np.uint8)
        result = find_left_arrow(screenshot, {}, cache)
        assert result == (10, 20, 5, 5)

    def test_find_left_arrow_cache_invalidated_by_bounds(self):
        cache = {'position': (10, 95, 5, 10), 'arrow': 'test'}
        screenshot = np.ones((100, 100), dtype=np.uint8)
        result = find_left_arrow(screenshot, {}, cache)
        assert cache['position'] is None

    def test_find_right_arrow_cache_hit(self):
        cache = {'position': (50, 20, 5, 5), 'arrow': 'test'}
        screenshot = np.ones((100, 100), dtype=np.uint8)
        result = find_right_arrow(screenshot, {}, cache)
        assert result == (50, 20, 5, 5)

    def test_get_game_window_position_no_arrows(self):
        screenshot = np.ones((100, 100), dtype=np.uint8)
        result = get_game_window_position(
            screenshot, {}, {'position': None}, {'position': None}
        )
        assert result is None


# ===================================================================
# gameloop — direction tracking
# ===================================================================

class TestDirectionTracking:

    def test_direction_from_delta_cardinal(self):
        from src.gameplay.gameloop import GameLoop
        assert GameLoop._direction_from_delta(0, -1) == 'north'
        assert GameLoop._direction_from_delta(0, 1) == 'south'
        assert GameLoop._direction_from_delta(1, 0) == 'east'
        assert GameLoop._direction_from_delta(-1, 0) == 'west'

    def test_direction_from_delta_diagonal(self):
        from src.gameplay.gameloop import GameLoop
        assert GameLoop._direction_from_delta(1, -1) == 'northeast'
        assert GameLoop._direction_from_delta(-1, -1) == 'northwest'
        assert GameLoop._direction_from_delta(1, 1) == 'southeast'
        assert GameLoop._direction_from_delta(-1, 1) == 'southwest'

    def test_direction_from_delta_no_movement(self):
        from src.gameplay.gameloop import GameLoop
        assert GameLoop._direction_from_delta(0, 0) is None

    def test_direction_from_delta_large_values_clamped(self):
        from src.gameplay.gameloop import GameLoop
        assert GameLoop._direction_from_delta(5, -3) == 'northeast'
        assert GameLoop._direction_from_delta(-10, 10) == 'southwest'

    def test_gameloop_has_direction_state(self):
        from src.gameplay.gameloop import GameLoop
        loop = GameLoop()
        assert loop._coming_from_direction is None
        assert loop._walked_pixels_in_sqm == 0
        assert loop._previous_monsters == []


# ===================================================================
# facade — backward compatibility
# ===================================================================

class TestFacadeBackwardCompat:

    def test_bfs_flood_fill_via_facade(self):
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()
        walkable = np.ones((11, 15), dtype=np.int32)
        distances = repo._bfs_flood_fill(walkable, 5, 7, set())
        assert distances[(5, 7)] == 0
        assert len(distances) == 165

    def test_get_creatures_bars_vectorized_alias(self):
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()
        img = _image_with_bars([(50, 30)])
        bars = repo._get_creatures_bars_vectorized(img)
        assert len(bars) == 1

    def test_get_monsters_via_facade(self):
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()
        creatures = [
            _creature('Rotworm', (8, 5), creature_type='monster'),
            _creature('Player1', (9, 5), creature_type='player'),
        ]
        assert len(repo.get_monsters(creatures)) == 1
        assert len(repo.get_players(creatures)) == 1

    def test_get_target_creature_via_facade(self):
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()
        c = _creature('Larva', (9, 5), attacked=True)
        assert repo.get_target_creature([c]).name == 'Larva'

    def test_slot_from_coordinate_via_facade(self):
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()
        result = repo.get_slot_from_coordinate(
            (32007, 32005, 7), (32009, 32003, 7)
        )
        assert result == (9, 3)

    def test_new_features_accessible_via_facade(self):
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()

        creatures = [_creature('Rat', (8, 5))]
        assert repo.get_nearest_creatures_count(creatures) == 1

        killed = repo.get_different_creatures_by_slots(creatures, [])
        assert len(killed) == 1

    def test_get_creatures_accepts_direction(self):
        """Facade get_creatures accepts new direction/walked_pixels params."""
        from src.repositories.gamewindow import GameWindowRepository
        repo = GameWindowRepository()
        # Just verify signature doesn't blow up; screenshot=None will
        # internally fail to capture, returning empty.
        result = repo.get_creatures(
            ['Rotworm'], (32007, 32005, 7),
            direction='north', walked_pixels=10
        )
        assert isinstance(result, list)

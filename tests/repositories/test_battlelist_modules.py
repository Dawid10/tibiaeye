"""
Tests for refactored BattleList modules.

Covers pure functions and new features across:
- config.py: constants, image loading, hash table building
- locators.py: locate(), get_icon_position(), get_bottom_bar_position()
- extractors.py: get_content(), get_creatures_names_images()
- core.py: pure functions + new features (skull, JIT attack, generator)
"""
import json
import pathlib
import tempfile

import cv2
import numpy as np
import pytest
from dataclasses import dataclass
from unittest.mock import patch

from src.repositories.battlelist.typings import GrayImage, BBox


# ============================================
# Helpers
# ============================================

@dataclass
class MockCreature:
    name: str
    is_being_attacked: bool = False


def _make_content(slots: int = 3, attacked_slot: int = -1) -> np.ndarray:
    """Build a fake battlelist content image with N filled slots."""
    content = np.zeros((220, 156), dtype=np.uint8)
    for i in range(slots):
        content[22 * i + 11, 23] = 192  # text pixel
    if attacked_slot >= 0:
        y = attacked_slot * 22
        for cy, cx in [(y, 0), (y, 19), (y + 19, 0), (y + 19, 19)]:
            content[cy, cx] = 76
    return content


def _gradient_block(size: int = 10) -> np.ndarray:
    """Deterministic gradient block for template-matching tests."""
    block = np.zeros((size, size), dtype=np.uint8)
    for i in range(size):
        for j in range(size):
            block[i, j] = (i * 25 + j * 10) % 256
    return block


# ============================================
# config.py tests
# ============================================

class TestConfigConstants:

    def test_slot_layout_constants_values(self):
        from src.repositories.battlelist.config import (
            SLOT_HEIGHT, CONTENT_WIDTH, SLOT_START_Y, NAME_START_X, NAME_WIDTH,
        )
        assert SLOT_HEIGHT == 22
        assert CONTENT_WIDTH == 156
        assert SLOT_START_Y == 11
        assert NAME_START_X == 23
        assert NAME_WIDTH == 115

    def test_pixel_values_constants(self):
        from src.repositories.battlelist.config import TEXT_PIXEL_VALUES, ATTACK_PIXEL_VALUES
        assert TEXT_PIXEL_VALUES == (192, 247)
        assert ATTACK_PIXEL_VALUES == (76, 166)

    def test_paths_are_pathlib(self):
        from src.repositories.battlelist.config import IMAGES_PATH, SKULLS_PATH, LEARNED_HASHES_PATH
        assert isinstance(IMAGES_PATH, pathlib.Path)
        assert isinstance(SKULLS_PATH, pathlib.Path)
        assert isinstance(LEARNED_HASHES_PATH, pathlib.Path)


class TestConfigLoadGrayImage:

    def test_load_existing_image(self):
        from src.repositories.battlelist.config import load_gray_image, IMAGES_PATH
        icon_path = IMAGES_PATH / "icons" / "battleList.png"
        img = load_gray_image(icon_path)
        assert img is not None
        assert len(img.shape) == 2  # grayscale

    def test_load_nonexistent_image_returns_none(self):
        from src.repositories.battlelist.config import load_gray_image
        img = load_gray_image(pathlib.Path("/nonexistent/path.png"))
        assert img is None


class TestConfigLoadSkullImages:

    def test_loads_all_six_skulls(self):
        from src.repositories.battlelist.config import load_skull_images
        skulls = load_skull_images()
        expected = {'black', 'green', 'orange', 'red', 'white', 'yellow'}
        assert set(skulls.keys()) == expected

    def test_skull_images_are_grayscale(self):
        from src.repositories.battlelist.config import load_skull_images
        skulls = load_skull_images()
        for name, img in skulls.items():
            assert len(img.shape) == 2, f"Skull '{name}' should be grayscale"

    def test_skull_images_dimensions(self):
        from src.repositories.battlelist.config import load_skull_images
        skulls = load_skull_images()
        for name, img in skulls.items():
            assert img.shape == (11, 11), f"Skull '{name}' expected 11x11"


class TestConfigExtractNameRow:

    def test_extracts_row_8(self):
        from src.repositories.battlelist.config import extract_name_row_from_image, NAME_WIDTH
        img = np.zeros((22, 120), dtype=np.uint8)
        img[8, 5] = 192  # text pixel
        row = extract_name_row_from_image(img)
        assert row is not None
        assert len(row) == NAME_WIDTH

    def test_returns_none_for_small_image(self):
        from src.repositories.battlelist.config import extract_name_row_from_image
        img = np.zeros((5, 50), dtype=np.uint8)
        assert extract_name_row_from_image(img) is None


class TestConfigBuildNameHashTable:

    def test_returns_empty_for_nonexistent_folder(self):
        from src.repositories.battlelist.config import build_name_hash_table
        result, collisions = build_name_hash_table("/nonexistent/folder")
        assert result == {}
        assert collisions == set()

    def test_builds_from_real_monsters_folder(self):
        from src.repositories.battlelist.config import build_name_hash_table, MONSTERS_PATH
        result, collisions = build_name_hash_table(MONSTERS_PATH)
        assert len(result) > 0
        assert all(isinstance(k, int) for k in result.keys())
        assert all(isinstance(v, str) for v in result.values())
        assert isinstance(collisions, set)


class TestConfigLearnedHashes:

    def test_load_learned_hashes_merges_into_dict(self):
        from src.repositories.battlelist.config import load_learned_hashes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"12345": "TestCreature"}, f)
            tmp_path = pathlib.Path(f.name)

        name_hashes = {}
        load_learned_hashes(name_hashes, tmp_path)
        assert name_hashes[12345] == "TestCreature"
        tmp_path.unlink()

    def test_load_learned_hashes_skips_existing(self):
        from src.repositories.battlelist.config import load_learned_hashes
        with tempfile.NamedTemporaryFile(mode='w', suffix='.json', delete=False) as f:
            json.dump({"12345": "NewName"}, f)
            tmp_path = pathlib.Path(f.name)

        name_hashes = {12345: "OriginalName"}
        load_learned_hashes(name_hashes, tmp_path)
        assert name_hashes[12345] == "OriginalName"
        tmp_path.unlink()

    def test_load_learned_hashes_nonexistent_file(self):
        from src.repositories.battlelist.config import load_learned_hashes
        name_hashes = {}
        load_learned_hashes(name_hashes, pathlib.Path("/nonexistent.json"))
        assert name_hashes == {}

    def test_save_learned_hash_creates_file(self):
        from src.repositories.battlelist.config import save_learned_hash
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir) / "learned.json"
            save_learned_hash(99999, "Dragon", tmp_path)
            assert tmp_path.exists()
            data = json.loads(tmp_path.read_text())
            assert data["99999"] == "Dragon"

    def test_save_learned_hash_skips_duplicate(self):
        from src.repositories.battlelist.config import save_learned_hash
        with tempfile.TemporaryDirectory() as tmpdir:
            tmp_path = pathlib.Path(tmpdir) / "learned.json"
            tmp_path.write_text(json.dumps({"99999": "Dragon"}))
            save_learned_hash(99999, "Dragon V2", tmp_path)
            data = json.loads(tmp_path.read_text())
            assert data["99999"] == "Dragon"  # NOT overwritten


class TestConfigLoadTemplates:

    def test_returns_empty_for_nonexistent_folder(self):
        from src.repositories.battlelist.config import load_templates
        assert load_templates("/nonexistent/folder") == []

    def test_loads_from_real_monsters_folder(self):
        from src.repositories.battlelist.config import load_templates, MONSTERS_PATH
        templates = load_templates(MONSTERS_PATH)
        assert len(templates) > 0
        assert 'name' in templates[0]
        assert 'image' in templates[0]


# ============================================
# locators.py tests
# ============================================

class TestLocatePureFunction:

    def test_locate_finds_template(self):
        from src.repositories.battlelist.locators import locate
        screenshot = np.zeros((100, 100), dtype=np.uint8)
        block = _gradient_block()
        screenshot[40:50, 40:50] = block
        result = locate(screenshot, block, confidence=0.9)
        assert result is not None
        assert result[:2] == (40, 40)

    def test_locate_returns_none_no_match(self):
        from src.repositories.battlelist.locators import locate
        screenshot = np.zeros((100, 100), dtype=np.uint8)
        for i in range(100):
            screenshot[i, :] = i * 2 % 256
        template = np.full((10, 10), 128, dtype=np.uint8)
        assert locate(screenshot, template, confidence=0.9) is None

    def test_locate_none_inputs(self):
        from src.repositories.battlelist.locators import locate
        assert locate(None, np.zeros((10, 10), dtype=np.uint8)) is None
        assert locate(np.zeros((100, 100), dtype=np.uint8), None) is None

    def test_locate_template_larger_than_screenshot(self):
        from src.repositories.battlelist.locators import locate
        assert locate(
            np.zeros((10, 10), dtype=np.uint8),
            np.zeros((20, 20), dtype=np.uint8),
        ) is None

    def test_locate_returns_bbox_with_template_dimensions(self):
        from src.repositories.battlelist.locators import locate
        screenshot = np.zeros((100, 100), dtype=np.uint8)
        block = _gradient_block(15)
        screenshot[30:45, 30:45] = block
        result = locate(screenshot, block, confidence=0.9)
        assert result is not None
        assert result[2] == 15  # width
        assert result[3] == 15  # height


class TestGetIconPosition:

    def test_returns_none_when_no_icon_image(self):
        from src.repositories.battlelist.locators import get_icon_position
        screenshot = np.zeros((200, 200), dtype=np.uint8)
        cache = {}
        assert get_icon_position(screenshot, None, cache) is None

    def test_uses_cached_position(self):
        from src.repositories.battlelist.locators import get_icon_position
        icon = np.zeros((20, 20), dtype=np.uint8)
        cache = {'icon_pos': (50, 30, 20, 20)}
        screenshot = np.zeros((200, 200), dtype=np.uint8)
        pos = get_icon_position(screenshot, icon, cache)
        assert pos == (50, 30, 20, 20)

    def test_clears_cache_on_bounds_fail(self):
        from src.repositories.battlelist.locators import get_icon_position
        # Icon with unique gradient that won't match a different gradient screenshot
        icon = _gradient_block(20)
        cache = {'icon_pos': (500, 500, 20, 20)}  # out of bounds
        # Screenshot with inverse pattern so icon won't be found
        screenshot = np.full((100, 100), 50, dtype=np.uint8)
        for i in range(100):
            screenshot[i, :] = (255 - i * 2) % 256
        pos = get_icon_position(screenshot, icon, cache, confidence=0.95)
        assert pos is None
        assert cache.get('icon_pos') is None

    def test_caches_found_position(self):
        from src.repositories.battlelist.locators import get_icon_position, locate
        icon = _gradient_block(15)
        screenshot = np.zeros((200, 200), dtype=np.uint8)
        screenshot[60:75, 60:75] = icon
        cache = {}
        pos = get_icon_position(screenshot, icon, cache, confidence=0.9)
        assert pos is not None
        assert cache['icon_pos'] == pos


class TestGetBottomBarPosition:

    def test_returns_none_when_no_image(self):
        from src.repositories.battlelist.locators import get_bottom_bar_position
        content = np.zeros((220, 156), dtype=np.uint8)
        assert get_bottom_bar_position(content, None) is None

    def test_finds_bottom_bar(self):
        from src.repositories.battlelist.locators import get_bottom_bar_position
        content = np.zeros((220, 156), dtype=np.uint8)
        bar = _gradient_block(8)
        content[180:188, 10:18] = bar
        pos = get_bottom_bar_position(content, bar, confidence=0.9)
        assert pos is not None
        assert pos[1] == 180  # y position


# ============================================
# extractors.py tests
# ============================================

class TestGetCreaturesNamesImages:

    def test_extracts_correct_rows(self):
        from src.repositories.battlelist.extractors import get_creatures_names_images
        content = np.zeros((220, 156), dtype=np.uint8)
        # Put known values at name row positions
        content[11, 23] = 100  # slot 0, row 11, col 23
        content[33, 23] = 200  # slot 1, row 33, col 23

        result = get_creatures_names_images(content, 2, 22, 23, 115)
        assert result.shape == (2, 115)
        assert result[0, 0] == 100
        assert result[1, 0] == 200

    def test_zero_slots_returns_empty(self):
        from src.repositories.battlelist.extractors import get_creatures_names_images
        content = np.zeros((220, 156), dtype=np.uint8)
        result = get_creatures_names_images(content, 0, 22, 23, 115)
        assert result.shape == (0, 115)

    def test_out_of_bounds_stops_gracefully(self):
        from src.repositories.battlelist.extractors import get_creatures_names_images
        content = np.zeros((30, 156), dtype=np.uint8)  # only room for ~1 slot
        result = get_creatures_names_images(content, 5, 22, 23, 115)
        assert result.shape == (5, 115)
        # Slots beyond content should be zeros
        assert np.all(result[2:] == 0)


class TestGetContent:

    def test_returns_none_when_no_icon(self):
        from src.repositories.battlelist.extractors import get_content
        screenshot = np.zeros((500, 500), dtype=np.uint8)
        result = get_content(screenshot, None, None, {}, 0.85)
        assert result is None

    def test_extracts_content_with_cached_icon(self):
        from src.repositories.battlelist.extractors import get_content
        screenshot = np.zeros((500, 500), dtype=np.uint8)
        cache = {'icon_pos': (100, 50, 20, 20)}
        # icon at (100, 50, 20, 20) -> content starts at y=71, x=99
        icon_img = np.zeros((20, 20), dtype=np.uint8)  # dummy
        result = get_content(screenshot, icon_img, None, cache, 0.85)
        assert result is not None
        assert result.shape[1] == 156  # CONTENT_WIDTH

    def test_returns_none_when_content_out_of_bounds(self):
        from src.repositories.battlelist.extractors import get_content
        screenshot = np.zeros((60, 500), dtype=np.uint8)
        cache = {'icon_pos': (100, 50, 20, 20)}  # content_y = 71 > 60
        icon_img = np.zeros((20, 20), dtype=np.uint8)
        result = get_content(screenshot, icon_img, None, cache, 0.85)
        assert result is None


# ============================================
# core.py - Pure functions tests
# ============================================

class TestGetFilledSlotsCountPure:

    def test_empty_content(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        content = np.zeros((220, 156), dtype=np.uint8)
        assert get_filled_slots_count(content) == 0

    def test_none_content(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        assert get_filled_slots_count(None) == 0

    def test_one_slot(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        content = _make_content(1)
        assert get_filled_slots_count(content) == 1

    def test_multiple_slots(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        content = _make_content(5)
        assert get_filled_slots_count(content) == 5

    def test_gap_stops_counting(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        content = np.zeros((220, 156), dtype=np.uint8)
        content[11, 23] = 192  # slot 0
        # slot 1 empty
        content[55, 23] = 192  # slot 2
        assert get_filled_slots_count(content) == 1

    def test_second_text_pixel_value(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        content = np.zeros((220, 156), dtype=np.uint8)
        content[11, 23] = 247  # second valid text value
        assert get_filled_slots_count(content) == 1

    def test_custom_parameters(self):
        from src.repositories.battlelist.core import get_filled_slots_count
        content = np.zeros((100, 50), dtype=np.uint8)
        content[5, 10] = 100
        count = get_filled_slots_count(
            content, slot_height=10, slot_start_y=5,
            name_start_x=10, text_pixel_values=(100, 200)
        )
        assert count == 1


class TestIsSlotBeingAttackedPure:

    def test_attacked_slot(self):
        from src.repositories.battlelist.core import is_slot_being_attacked
        content = _make_content(1, attacked_slot=0)
        assert is_slot_being_attacked(content, 0) is True

    def test_not_attacked(self):
        from src.repositories.battlelist.core import is_slot_being_attacked
        content = _make_content(1)
        assert is_slot_being_attacked(content, 0) is False

    def test_partial_corners(self):
        from src.repositories.battlelist.core import is_slot_being_attacked
        content = np.zeros((220, 156), dtype=np.uint8)
        content[0, 0] = 76
        content[0, 19] = 76
        # missing bottom corners
        assert is_slot_being_attacked(content, 0) is False

    def test_second_slot_attacked(self):
        from src.repositories.battlelist.core import is_slot_being_attacked
        content = _make_content(3, attacked_slot=1)
        assert is_slot_being_attacked(content, 0) is False
        assert is_slot_being_attacked(content, 1) is True
        assert is_slot_being_attacked(content, 2) is False

    def test_out_of_bounds_returns_false(self):
        from src.repositories.battlelist.core import is_slot_being_attacked
        content = np.zeros((10, 10), dtype=np.uint8)
        assert is_slot_being_attacked(content, 0) is False

    def test_second_attack_pixel_value(self):
        from src.repositories.battlelist.core import is_slot_being_attacked
        content = np.zeros((220, 156), dtype=np.uint8)
        for cy, cx in [(0, 0), (0, 19), (19, 0), (19, 19)]:
            content[cy, cx] = 166
        assert is_slot_being_attacked(content, 0) is True


class TestGetCreatureNameByHashPure:

    def test_returns_name_when_hash_matches(self):
        from src.repositories.battlelist.core import get_creature_name_by_hash
        from src.repositories.utils.hash import hashit, normalize_text_pixels

        content = np.zeros((220, 156), dtype=np.uint8)
        content[11, 23:30] = 192  # some text pixels

        row = content[11, 23:138]
        normalized = normalize_text_pixels(row, 115)
        expected_hash = hashit(normalized)

        name_hashes = {expected_hash: 'Rotworm'}
        result = get_creature_name_by_hash(content, 0, name_hashes)
        assert result == 'Rotworm'

    def test_returns_none_when_no_match(self):
        from src.repositories.battlelist.core import get_creature_name_by_hash
        content = np.zeros((220, 156), dtype=np.uint8)
        assert get_creature_name_by_hash(content, 0, {}) is None

    def test_returns_none_out_of_bounds(self):
        from src.repositories.battlelist.core import get_creature_name_by_hash
        content = np.zeros((5, 156), dtype=np.uint8)
        assert get_creature_name_by_hash(content, 0, {}) is None

    def test_returns_none_narrow_content(self):
        from src.repositories.battlelist.core import get_creature_name_by_hash
        content = np.zeros((220, 10), dtype=np.uint8)  # too narrow
        assert get_creature_name_by_hash(content, 0, {}) is None


class TestGetCreatureNameByTemplatePure:

    def test_returns_unknown_with_empty_templates(self):
        from src.repositories.battlelist.core import get_creature_name_by_template
        content = np.zeros((220, 156), dtype=np.uint8)
        assert get_creature_name_by_template(content, 0, []) == 'Unknown'

    def test_returns_unknown_when_slot_out_of_bounds(self):
        from src.repositories.battlelist.core import get_creature_name_by_template
        content = np.zeros((10, 156), dtype=np.uint8)
        templates = [{'name': 'Rotworm', 'image': np.zeros((5, 5), dtype=np.uint8)}]
        assert get_creature_name_by_template(content, 0, templates) == 'Unknown'

    def test_matches_exact_template(self):
        from src.repositories.battlelist.core import get_creature_name_by_template

        content = np.zeros((44, 156), dtype=np.uint8)
        pattern = _gradient_block(10)
        content[5:15, 25:35] = pattern

        templates = [{'name': 'Rotworm', 'image': pattern}]
        result = get_creature_name_by_template(content, 0, templates)
        assert result == 'Rotworm'

    def test_filters_by_target_names(self):
        from src.repositories.battlelist.core import get_creature_name_by_template

        content = np.zeros((44, 156), dtype=np.uint8)
        pattern = _gradient_block(10)
        content[5:15, 25:35] = pattern

        templates = [
            {'name': 'Rotworm', 'image': pattern},
            {'name': 'Dragon', 'image': pattern},
        ]
        # Only allow 'cave rat' -> neither Rotworm nor Dragon will be checked
        result = get_creature_name_by_template(
            content, 0, templates, target_names=['cave rat']
        )
        assert result == 'Unknown'

    def test_skips_oversized_template(self):
        from src.repositories.battlelist.core import get_creature_name_by_template
        content = np.zeros((44, 156), dtype=np.uint8)
        big_template = np.zeros((50, 50), dtype=np.uint8)
        templates = [{'name': 'Big', 'image': big_template}]
        assert get_creature_name_by_template(content, 0, templates) == 'Unknown'


# ============================================
# core.py - New features tests
# ============================================

class TestHasSkull:

    def test_returns_none_with_empty_skull_images(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((220, 156), dtype=np.uint8)
        assert has_skull(content, 0, {}) is None

    def test_returns_none_when_slot_out_of_bounds(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((10, 156), dtype=np.uint8)
        skulls = {'red': np.zeros((5, 5), dtype=np.uint8)}
        assert has_skull(content, 0, skulls) is None

    def test_detects_skull_in_slot(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((44, 156), dtype=np.uint8)
        skull_pattern = _gradient_block(8)
        content[5:13, 3:11] = skull_pattern

        skulls = {'red': skull_pattern}
        result = has_skull(content, 0, skulls, confidence=0.9)
        assert result == 'red'

    def test_no_skull_detected(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((44, 156), dtype=np.uint8)
        skull_pattern = _gradient_block(8)
        skulls = {'red': skull_pattern}
        result = has_skull(content, 0, skulls, confidence=0.9)
        assert result is None

    def test_detects_correct_skull_color(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((44, 156), dtype=np.uint8)
        orange_pattern = _gradient_block(8)
        content[5:13, 3:11] = orange_pattern

        # Red pattern: inverse gradient, won't match the content area
        red_pattern = np.zeros((8, 8), dtype=np.uint8)
        for i in range(8):
            for j in range(8):
                red_pattern[i, j] = (255 - i * 25 - j * 10) % 256

        skulls = {'red': red_pattern, 'orange': orange_pattern}
        result = has_skull(content, 0, skulls, confidence=0.9)
        assert result == 'orange'

    def test_skips_oversized_skull_image(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((44, 156), dtype=np.uint8)
        big_skull = np.zeros((30, 30), dtype=np.uint8)
        skulls = {'big': big_skull}
        assert has_skull(content, 0, skulls) is None

    def test_with_real_skull_images(self):
        from src.repositories.battlelist.core import has_skull
        from src.repositories.battlelist.config import load_skull_images
        skulls = load_skull_images()
        content = np.zeros((44, 156), dtype=np.uint8)
        # No skull placed -> should return None
        assert has_skull(content, 0, skulls) is None

    def test_second_slot_skull(self):
        from src.repositories.battlelist.core import has_skull
        content = np.zeros((66, 156), dtype=np.uint8)
        skull_pattern = _gradient_block(8)
        # Place in slot 1 (y=22..43)
        content[27:35, 3:11] = skull_pattern
        skulls = {'white': skull_pattern}
        assert has_skull(content, 0, skulls, confidence=0.9) is None
        assert has_skull(content, 1, skulls, confidence=0.9) == 'white'


class TestIsAttackingSomeCreature:

    def test_returns_true_when_attacking(self):
        from src.repositories.battlelist.core import is_attacking_some_creature
        creatures = [
            MockCreature('Rotworm', is_being_attacked=False),
            MockCreature('Dragon', is_being_attacked=True),
        ]
        assert is_attacking_some_creature(creatures) is True

    def test_returns_false_when_not_attacking(self):
        from src.repositories.battlelist.core import is_attacking_some_creature
        creatures = [
            MockCreature('Rotworm'),
            MockCreature('Dragon'),
        ]
        assert is_attacking_some_creature(creatures) is False

    def test_returns_false_for_empty_list(self):
        from src.repositories.battlelist.core import is_attacking_some_creature
        assert is_attacking_some_creature([]) is False

    def test_single_attacked_creature(self):
        from src.repositories.battlelist.core import is_attacking_some_creature
        creatures = [MockCreature('Rotworm', is_being_attacked=True)]
        assert is_attacking_some_creature(creatures) is True


class TestGetCreaturesNames:

    def test_yields_names_for_matching_hashes(self):
        from src.repositories.battlelist.core import get_creatures_names
        from src.repositories.utils.hash import hashit, normalize_text_pixels

        content = np.zeros((220, 156), dtype=np.uint8)
        content[11, 25] = 192  # some text in slot 0

        row = content[11, 23:138]
        normalized = normalize_text_pixels(row, 115)
        h = hashit(normalized)
        name_hashes = {h: 'Rotworm'}

        names = list(get_creatures_names(content, 1, name_hashes))
        assert len(names) == 1
        assert names[0] == 'Rotworm'

    def test_yields_none_for_unknown_hashes(self):
        from src.repositories.battlelist.core import get_creatures_names
        content = np.zeros((220, 156), dtype=np.uint8)
        names = list(get_creatures_names(content, 3, {}))
        assert len(names) == 3
        assert all(n is None for n in names)

    def test_zero_slots_yields_nothing(self):
        from src.repositories.battlelist.core import get_creatures_names
        content = np.zeros((220, 156), dtype=np.uint8)
        names = list(get_creatures_names(content, 0, {}))
        assert names == []

    def test_is_generator(self):
        from src.repositories.battlelist.core import get_creatures_names
        import types
        content = np.zeros((220, 156), dtype=np.uint8)
        result = get_creatures_names(content, 1, {})
        assert isinstance(result, types.GeneratorType)


class TestGetBeingAttackedCreaturesJit:

    @pytest.fixture
    def jit_available(self):
        from src.repositories.battlelist.core import NUMBA_BATTLELIST_AVAILABLE
        if not NUMBA_BATTLELIST_AVAILABLE:
            pytest.skip("Numba not available")

    def test_no_creature_attacked(self, jit_available):
        from src.repositories.battlelist.core import get_being_attacked_creatures_jit
        content = _make_content(3)
        result = get_being_attacked_creatures_jit(content, 3, 22, 76, 166)
        assert result.shape == (3,)
        assert not any(result)

    def test_first_slot_attacked(self, jit_available):
        from src.repositories.battlelist.core import get_being_attacked_creatures_jit
        content = _make_content(3, attacked_slot=0)
        result = get_being_attacked_creatures_jit(content, 3, 22, 76, 166)
        assert result[0] is np.True_
        # Early exit: slots after first attacked are not checked
        assert not result[1]
        assert not result[2]

    def test_second_slot_attacked(self, jit_available):
        from src.repositories.battlelist.core import get_being_attacked_creatures_jit
        content = _make_content(3, attacked_slot=1)
        result = get_being_attacked_creatures_jit(content, 3, 22, 76, 166)
        assert not result[0]
        assert result[1] is np.True_

    def test_single_slot(self, jit_available):
        from src.repositories.battlelist.core import get_being_attacked_creatures_jit
        content = _make_content(1, attacked_slot=0)
        result = get_being_attacked_creatures_jit(content, 1, 22, 76, 166)
        assert result.shape == (1,)
        assert result[0] is np.True_

    def test_second_attack_pixel_value(self, jit_available):
        from src.repositories.battlelist.core import get_being_attacked_creatures_jit
        content = np.zeros((220, 156), dtype=np.uint8)
        for cy, cx in [(0, 0), (0, 19), (19, 0), (19, 19)]:
            content[cy, cx] = 166  # second attack value
        result = get_being_attacked_creatures_jit(content, 1, 22, 76, 166)
        assert result[0] is np.True_


# ============================================
# Facade wrapper consistency tests
# ============================================

class TestFacadeWrappersMatchPureFunctions:
    """Verify that facade thin wrappers produce the same results as pure functions."""

    def test_filled_slots_count_wrapper(self):
        from src.repositories.battlelist.core import (
            BattleListRepository, get_filled_slots_count,
        )
        content = _make_content(3)
        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.SLOT_START_Y = 11
        repo.NAME_START_X = 23
        repo.TEXT_PIXEL_VALUES = (192, 247)

        assert repo._get_filled_slots_count(content) == get_filled_slots_count(content)

    def test_is_slot_being_attacked_wrapper(self):
        from src.repositories.battlelist.core import (
            BattleListRepository, is_slot_being_attacked,
        )
        content = _make_content(2, attacked_slot=1)
        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.ATTACK_PIXEL_VALUES = (76, 166)

        for slot in range(2):
            assert repo._is_slot_being_attacked(content, slot) == \
                is_slot_being_attacked(content, slot)

    def test_locate_wrapper(self):
        from src.repositories.battlelist.core import BattleListRepository
        from src.repositories.battlelist.locators import locate
        repo = BattleListRepository.__new__(BattleListRepository)
        screenshot = np.zeros((100, 100), dtype=np.uint8)
        block = _gradient_block()
        screenshot[40:50, 40:50] = block
        assert repo._locate(screenshot, block, 0.9) == locate(screenshot, block, 0.9)

    def test_extract_name_row_wrapper(self):
        from src.repositories.battlelist.core import BattleListRepository
        from src.repositories.battlelist.config import extract_name_row_from_image
        repo = BattleListRepository.__new__(BattleListRepository)
        img = np.zeros((22, 120), dtype=np.uint8)
        img[8, 5] = 192
        result_wrapper = repo._extract_name_row_from_image(img)
        result_pure = extract_name_row_from_image(img)
        assert np.array_equal(result_wrapper, result_pure)


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

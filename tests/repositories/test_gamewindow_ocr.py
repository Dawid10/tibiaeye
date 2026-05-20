"""
Tests for gamewindow OCR module.

Ensures:
1. Binarization converts grayscale to binary correctly
2. Character segmentation identifies character boundaries
3. Name hashing produces stable, unique hashes
4. Learning populates atlas from known creatures
5. Fuzzy matching handles typos and case differences
6. Atlas persistence saves and loads correctly
"""
import json
import tempfile
import pathlib

import numpy as np
import pytest

from src.repositories.gamewindow.ocr import (
    binarize_name_region,
    auto_detect_threshold,
    normalize_name_image,
    hash_name_image,
    segment_characters,
    extract_glyph,
    read_name_by_ocr,
    fuzzy_match_name,
    learn_name_hash,
    learn_glyphs_from_name,
    load_char_atlas,
    save_char_atlas,
    _levenshtein,
    CharAtlasManager,
)
from src.repositories.gamewindow.config import (
    OCR_BINARIZE_THRESHOLD,
    OCR_CORE_ROWS,
    OCR_GLYPH_HEIGHT,
)


def _make_name_image(text_cols, height=13, width=80):
    """Create a synthetic name region with bright columns at specified positions."""
    img = np.zeros((height, width), dtype=np.uint8)
    for col in text_cols:
        if col < width:
            img[3:9, col] = 200
    return img


def _make_binary_image(text_cols, height=13, width=80):
    """Create a binary name image with 255 at text columns."""
    img = np.zeros((height, width), dtype=np.uint8)
    for col in text_cols:
        if col < width:
            img[3:9, col] = 255
    return img


class TestBinarization:
    """Tests for binarize_name_region."""

    def test_pixels_above_threshold_become_255(self):
        """Pixels above threshold should become 255."""
        img = np.array([[100, 150, 200]], dtype=np.uint8)
        result = binarize_name_region(img, threshold=120)
        assert result[0, 0] == 0
        assert result[0, 1] == 255
        assert result[0, 2] == 255

    def test_pixels_below_threshold_become_0(self):
        """Pixels below threshold should become 0."""
        img = np.array([[10, 50, 119]], dtype=np.uint8)
        result = binarize_name_region(img, threshold=120)
        np.testing.assert_array_equal(result, np.zeros_like(img))

    def test_empty_input(self):
        """Empty input should return empty array."""
        result = binarize_name_region(np.array([], dtype=np.uint8))
        assert result.size == 0

    def test_none_input(self):
        """None input should return empty array."""
        result = binarize_name_region(None)
        assert result.size == 0

    def test_default_threshold(self):
        """Should use default OCR_BINARIZE_THRESHOLD."""
        img = np.array([[OCR_BINARIZE_THRESHOLD]], dtype=np.uint8)
        result = binarize_name_region(img)
        assert result[0, 0] == 255


class TestAutoDetectThreshold:
    """Tests for auto_detect_threshold."""

    def test_returns_int(self):
        """Should return an integer threshold."""
        img = np.random.randint(0, 256, (10, 20), dtype=np.uint8)
        result = auto_detect_threshold(img)
        assert isinstance(result, int)

    def test_empty_returns_default(self):
        """Empty input should return default threshold."""
        result = auto_detect_threshold(np.array([], dtype=np.uint8))
        assert result == OCR_BINARIZE_THRESHOLD


class TestNormalizeNameImage:
    """Tests for normalize_name_image."""

    def test_crops_to_text_bbox(self):
        """Should crop to tight bounding box of text pixels."""
        binary = np.zeros((13, 80), dtype=np.uint8)
        binary[3:7, 10:20] = 255
        result = normalize_name_image(binary)
        assert result.shape[1] == 10
        assert result.shape[0] == OCR_GLYPH_HEIGHT

    def test_pads_to_fixed_height(self):
        """Should pad to OCR_GLYPH_HEIGHT if shorter."""
        binary = np.zeros((5, 20), dtype=np.uint8)
        binary[1:3, 5:10] = 255
        result = normalize_name_image(binary)
        assert result.shape[0] == OCR_GLYPH_HEIGHT

    def test_all_zeros_returns_empty(self):
        """All-zero image should return empty result."""
        binary = np.zeros((10, 20), dtype=np.uint8)
        result = normalize_name_image(binary)
        assert result.shape[1] == 0

    def test_none_returns_empty(self):
        """None input should return empty result."""
        result = normalize_name_image(None)
        assert result.shape[1] == 0


class TestHashNameImage:
    """Tests for hash_name_image."""

    def test_same_image_same_hash(self):
        """Same image should produce same hash."""
        img = np.random.randint(0, 2, (6, 20), dtype=np.uint8) * 255
        h1 = hash_name_image(img)
        h2 = hash_name_image(img.copy())
        assert h1 == h2

    def test_different_images_different_hash(self):
        """Different images should produce different hashes."""
        img1 = np.zeros((6, 20), dtype=np.uint8)
        img1[0:3, 0:10] = 255
        img2 = np.zeros((6, 20), dtype=np.uint8)
        img2[3:6, 10:20] = 255
        assert hash_name_image(img1) != hash_name_image(img2)

    def test_empty_returns_zero(self):
        """Empty input should return 0."""
        assert hash_name_image(np.array([], dtype=np.uint8)) == 0
        assert hash_name_image(None) == 0


class TestSegmentCharacters:
    """Tests for segment_characters."""

    def test_single_character(self):
        """Should find single character segment."""
        binary = np.zeros((6, 20), dtype=np.uint8)
        binary[:, 5:10] = 255
        segments = segment_characters(binary)
        assert len(segments) == 1
        assert segments[0] == (5, 10)

    def test_two_characters_with_gap(self):
        """Should find two characters separated by gap."""
        binary = np.zeros((6, 30), dtype=np.uint8)
        binary[:, 2:5] = 255
        binary[:, 8:12] = 255
        segments = segment_characters(binary)
        assert len(segments) == 2

    def test_merge_close_segments(self):
        """Should merge segments within merge_gap."""
        binary = np.zeros((6, 20), dtype=np.uint8)
        binary[:, 2:4] = 255
        binary[:, 5:8] = 255  # gap of 1 (merge_gap=1)
        segments = segment_characters(binary, merge_gap=1)
        assert len(segments) == 1
        assert segments[0] == (2, 8)

    def test_space_detection(self):
        """Should insert space marker for large gaps."""
        binary = np.zeros((6, 30), dtype=np.uint8)
        binary[:, 2:5] = 255
        binary[:, 12:16] = 255  # gap of 7 (>= space_gap=4)
        segments = segment_characters(binary, space_gap=4)
        assert (-1, -1) in segments

    def test_filter_noise(self):
        """Should filter segments narrower than min_width."""
        binary = np.zeros((6, 20), dtype=np.uint8)
        binary[:, 5:6] = 255  # width=1 < min_width=2
        segments = segment_characters(binary, min_width=2)
        assert len(segments) == 0

    def test_empty_image(self):
        """Empty image should return no segments."""
        binary = np.zeros((6, 20), dtype=np.uint8)
        assert segment_characters(binary) == []

    def test_none_input(self):
        """None input should return empty list."""
        assert segment_characters(None) == []


class TestExtractGlyph:
    """Tests for extract_glyph."""

    def test_extracts_correct_region(self):
        """Should extract glyph from correct rows and columns."""
        binary = np.zeros((13, 20), dtype=np.uint8)
        binary[3:9, 5:10] = 255
        glyph = extract_glyph(binary, 5, 10, core_rows=(3, 9))
        assert glyph.shape == (OCR_GLYPH_HEIGHT, 5)
        assert np.all(glyph == 255)

    def test_pads_short_glyph(self):
        """Should pad glyph shorter than target height."""
        binary = np.zeros((6, 10), dtype=np.uint8)
        binary[0:4, 2:5] = 255
        glyph = extract_glyph(binary, 2, 5, core_rows=(0, 4))
        assert glyph.shape[0] == OCR_GLYPH_HEIGHT


class TestReadNameByOcr:
    """Tests for read_name_by_ocr."""

    def test_reads_known_glyphs(self):
        """Should read name when all glyphs are in atlas."""
        binary = np.zeros((13, 40), dtype=np.uint8)
        # First glyph: 3 cols wide
        binary[3:9, 2:5] = 255
        # Second glyph: 4 cols wide (distinct from first)
        binary[3:9, 8:12] = 255

        g1 = extract_glyph(binary, 2, 5, core_rows=(3, 9))
        g2 = extract_glyph(binary, 8, 12, core_rows=(3, 9))

        from src.utils.hash import hashit
        atlas = {
            str(hashit(g1)): 'A',
            str(hashit(g2)): 'B',
        }

        result = read_name_by_ocr(binary, atlas, core_rows=(3, 9))
        assert result == 'AB'

    def test_returns_none_for_unknown_glyph(self):
        """Should return None when a glyph is not in atlas."""
        binary = np.zeros((13, 20), dtype=np.uint8)
        binary[3:9, 2:5] = 255
        result = read_name_by_ocr(binary, {}, core_rows=(3, 9))
        assert result is None

    def test_empty_binary(self):
        """Should return None for empty binary image."""
        binary = np.zeros((13, 20), dtype=np.uint8)
        result = read_name_by_ocr(binary, {}, core_rows=(3, 9))
        assert result is None


class TestFuzzyMatchName:
    """Tests for fuzzy_match_name."""

    def test_exact_match(self):
        """Should find exact match."""
        assert fuzzy_match_name('Rotworm', ['Rotworm', 'Wasp']) == 'Rotworm'

    def test_case_insensitive(self):
        """Should match case-insensitively."""
        assert fuzzy_match_name('rotworm', ['Rotworm', 'Wasp']) == 'Rotworm'

    def test_edit_distance_1(self):
        """Should match within edit distance 1."""
        assert fuzzy_match_name('Rotworn', ['Rotworm', 'Wasp'], max_distance=1) == 'Rotworm'

    def test_too_far_returns_none(self):
        """Should return None when name is too different."""
        assert fuzzy_match_name('Xyz', ['Rotworm', 'Wasp'], max_distance=2) is None

    def test_empty_input(self):
        """Should return None for empty inputs."""
        assert fuzzy_match_name('', ['Rotworm']) is None
        assert fuzzy_match_name('Rotworm', []) is None
        assert fuzzy_match_name(None, ['Rotworm']) is None


class TestLevenshtein:
    """Tests for _levenshtein edit distance."""

    def test_identical(self):
        """Identical strings have distance 0."""
        assert _levenshtein('abc', 'abc') == 0

    def test_insertion(self):
        """Single insertion has distance 1."""
        assert _levenshtein('abc', 'abcd') == 1

    def test_deletion(self):
        """Single deletion has distance 1."""
        assert _levenshtein('abcd', 'abc') == 1

    def test_substitution(self):
        """Single substitution has distance 1."""
        assert _levenshtein('abc', 'axc') == 1

    def test_empty(self):
        """Distance to empty is string length."""
        assert _levenshtein('abc', '') == 3
        assert _levenshtein('', 'abc') == 3


class TestLearnNameHash:
    """Tests for learn_name_hash."""

    def test_learns_new_hash(self):
        """Should add new hash to dict."""
        binary = _make_binary_image([10, 11, 12, 13, 14])
        hashes = {}
        result = learn_name_hash(binary, 'Rotworm', hashes)
        assert result is True
        assert len(hashes) == 1
        assert 'Rotworm' in hashes.values()

    def test_skips_existing_hash(self):
        """Should not overwrite existing hash."""
        binary = _make_binary_image([10, 11, 12, 13, 14])
        hashes = {}
        learn_name_hash(binary, 'Rotworm', hashes)
        result = learn_name_hash(binary, 'Rotworm', hashes)
        assert result is False

    def test_empty_binary(self):
        """Should return False for empty binary."""
        hashes = {}
        result = learn_name_hash(np.zeros((10, 20), dtype=np.uint8), 'Test', hashes)
        assert result is False


class TestLearnGlyphsFromName:
    """Tests for learn_glyphs_from_name."""

    def test_learns_glyphs_when_count_matches(self):
        """Should learn glyphs when segment count equals name length."""
        binary = np.zeros((13, 40), dtype=np.uint8)
        # Two distinct glyphs (different widths)
        binary[3:9, 2:5] = 255
        binary[3:9, 8:12] = 255
        atlas = {}
        count = learn_glyphs_from_name(binary, 'AB', atlas, core_rows=(3, 9))
        assert count == 2
        assert len(atlas) == 2

    def test_skips_when_count_mismatch(self):
        """Should skip learning when segment count != name length."""
        binary = np.zeros((13, 40), dtype=np.uint8)
        binary[3:9, 2:5] = 255
        binary[3:9, 8:12] = 255
        atlas = {}
        count = learn_glyphs_from_name(binary, 'ABC', atlas, core_rows=(3, 9))
        assert count == 0

    def test_skips_already_known_glyphs(self):
        """Should not count already known glyphs."""
        binary = np.zeros((13, 40), dtype=np.uint8)
        binary[3:9, 2:5] = 255
        binary[3:9, 8:12] = 255
        atlas = {}
        learn_glyphs_from_name(binary, 'AB', atlas, core_rows=(3, 9))
        count = learn_glyphs_from_name(binary, 'AB', atlas, core_rows=(3, 9))
        assert count == 0


class TestAtlasPersistence:
    """Tests for load_char_atlas and save_char_atlas."""

    def test_save_and_load(self):
        """Should persist and reload atlas correctly."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            atlas = {
                'metadata': {'platform': 'test', 'threshold': 120, 'core_rows': [3, 9], 'version': 1},
                'glyphs': {'123': 'A', '456': 'B'},
                'name_hashes': {'789': 'Rotworm'},
            }
            save_char_atlas(atlas, tmppath)
            loaded = load_char_atlas(tmppath)
            assert loaded['glyphs'] == atlas['glyphs']
            assert loaded['name_hashes'] == atlas['name_hashes']

    def test_load_missing_file(self):
        """Should return default atlas when file doesn't exist."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            loaded = load_char_atlas(tmppath)
            assert loaded['glyphs'] == {}
            assert loaded['name_hashes'] == {}
            assert 'metadata' in loaded


class TestCharAtlasManager:
    """Tests for CharAtlasManager integration."""

    def test_identify_via_name_hash(self):
        """Should identify creature via learned name hash."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            manager = CharAtlasManager(tmppath)

            name_region = _make_name_image([10, 11, 12, 13, 14])
            manager.learn_from_creature(name_region, 'Rotworm')

            result = manager.identify_name(name_region, ['Rotworm', 'Wasp'])
            assert result == 'Rotworm'

    def test_returns_none_for_unknown(self):
        """Should return None when name is not in atlas or available list."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            manager = CharAtlasManager(tmppath)

            name_region = _make_name_image([10, 11, 12])
            result = manager.identify_name(name_region, ['Rotworm'])
            assert result is None

    def test_ignores_player_learning(self):
        """Should not learn from 'Player' names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            manager = CharAtlasManager(tmppath)

            name_region = _make_name_image([10, 11, 12])
            manager.learn_from_creature(name_region, 'Player')
            assert len(manager.name_hashes) == 0

    def test_only_matches_available_names(self):
        """Should not return a name that's not in available_names."""
        with tempfile.TemporaryDirectory() as tmpdir:
            tmppath = pathlib.Path(tmpdir)
            manager = CharAtlasManager(tmppath)

            name_region = _make_name_image([10, 11, 12, 13, 14])
            manager.learn_from_creature(name_region, 'Rotworm')

            result = manager.identify_name(name_region, ['Wasp'])
            assert result is None

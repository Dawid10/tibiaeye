"""
Tests for StatusBar Repository.

Ensures:
1. HP/MP percentage calculation is accurate
2. Template matching locates icons correctly
3. Bar color detection works with all HP colors
4. Caching behavior is correct
5. Edge cases are handled
"""
import numpy as np
import pytest
from unittest.mock import Mock, patch, MagicMock

from src.repositories.statusbar import StatusBarRepository
from src.repositories.statusbar.config import BAR_SIZE, HP_BAR_COLORS, MANA_BAR_COLORS
from src.repositories.statusbar.core import get_filled_percentage
from src.repositories.statusbar.locators import locate
from src.repositories.statusbar.extractors import get_hp_bar, get_mana_bar


class TestGetFilledPercentage:
    """Tests for get_filled_percentage function."""

    def test_empty_bar_returns_zero(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        assert percentage == 0

    def test_full_bar_returns_hundred(self):
        bar = np.full(BAR_SIZE, HP_BAR_COLORS[0], dtype=np.uint8)

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        assert percentage == 100

    def test_half_filled_bar(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)
        half_size = BAR_SIZE // 2
        bar[:half_size] = HP_BAR_COLORS[0]

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        assert 49 <= percentage <= 51

    def test_quarter_filled_bar(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)
        quarter_size = BAR_SIZE // 4
        bar[:quarter_size] = HP_BAR_COLORS[0]

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        assert 23 <= percentage <= 26

    def test_accepts_multiple_hp_colors(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)
        bar[0:20] = HP_BAR_COLORS[0]
        bar[20:40] = HP_BAR_COLORS[1]
        bar[40:60] = HP_BAR_COLORS[2]

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        expected = (60 * 100) // BAR_SIZE
        assert percentage == expected

    def test_mana_colors_work(self):
        bar = np.full(BAR_SIZE, MANA_BAR_COLORS[0], dtype=np.uint8)

        percentage = get_filled_percentage(bar, MANA_BAR_COLORS)

        assert percentage == 100

    def test_wrong_colors_not_counted(self):
        bar = np.full(BAR_SIZE, HP_BAR_COLORS[0], dtype=np.uint8)

        percentage = get_filled_percentage(bar, MANA_BAR_COLORS)

        assert percentage == 0

    def test_single_pixel_filled(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)
        bar[0] = HP_BAR_COLORS[0]

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        assert percentage == 1

    def test_bar_size_constant(self):
        assert BAR_SIZE == 94


class TestLocate:
    """Tests for locate template matching function."""

    def test_locate_finds_exact_match(self):
        template = np.array([
            [50,  100, 150, 100, 50],
            [100, 150, 200, 150, 100],
            [150, 200, 255, 200, 150],
            [100, 150, 200, 150, 100],
            [50,  100, 150, 100, 50]
        ], dtype=np.uint8)

        img = np.zeros((100, 100), dtype=np.uint8)
        img[20:25, 30:35] = template

        result = locate(img, template, confidence=0.95)

        assert result is not None
        x, y, w, h = result
        assert x == 30
        assert y == 20
        assert w == 5
        assert h == 5

    def test_locate_returns_none_when_not_found(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        template = np.array([
            [255, 0, 255],
            [0, 255, 0],
            [255, 0, 255]
        ], dtype=np.uint8)

        result = locate(img, template, confidence=0.9)

        assert result is None

    def test_locate_returns_none_for_none_inputs(self):
        img = np.zeros((100, 100), dtype=np.uint8)
        template = np.ones((5, 5), dtype=np.uint8)

        assert locate(None, template) is None
        assert locate(img, None) is None
        assert locate(None, None) is None

    def test_locate_template_larger_than_image(self):
        img = np.zeros((10, 10), dtype=np.uint8)
        template = np.ones((20, 20), dtype=np.uint8)

        result = locate(img, template)

        assert result is None

    def test_locate_respects_confidence_threshold(self):
        template = np.array([
            [50,  100, 150, 100, 50],
            [100, 150, 200, 150, 100],
            [150, 200, 255, 200, 150],
            [100, 150, 200, 150, 100],
            [50,  100, 150, 100, 50]
        ], dtype=np.uint8)

        img = np.zeros((100, 100), dtype=np.uint8)
        img[20:25, 30:35] = template

        result_mod = locate(img, template, confidence=0.9)
        assert result_mod is not None

        result_low = locate(img, template, confidence=0.5)
        assert result_low is not None


class TestBarExtraction:
    """Tests for bar pixel extraction functions."""

    def test_extract_hp_bar_correct_position(self):
        screenshot = np.zeros((200, 300), dtype=np.uint8)
        icon_pos = (50, 100, 10, 10)

        screenshot[105, 63:63 + BAR_SIZE] = HP_BAR_COLORS[0]

        bar = get_hp_bar(screenshot, icon_pos)

        assert len(bar) == BAR_SIZE
        assert np.all(bar == HP_BAR_COLORS[0])

    def test_extract_mana_bar_correct_position(self):
        screenshot = np.zeros((200, 300), dtype=np.uint8)
        icon_pos = (50, 100, 10, 10)

        screenshot[105, 64:64 + BAR_SIZE] = MANA_BAR_COLORS[0]

        bar = get_mana_bar(screenshot, icon_pos)

        assert len(bar) == BAR_SIZE
        assert np.all(bar == MANA_BAR_COLORS[0])


class TestStatusBarRepository:
    """Tests for StatusBarRepository class."""

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_is_hp_below_threshold(self, mock_screen, mock_mana, mock_hp):
        mock_screen.return_value = Mock()
        mock_hp.return_value = None

        repo = StatusBarRepository()
        repo._last_hp = 65.0

        assert repo.is_hp_below(70.0) == True
        assert repo.is_hp_below(60.0) == False

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_is_mp_below_threshold(self, mock_screen, mock_mana, mock_hp):
        mock_screen.return_value = Mock()
        mock_mana.return_value = None

        repo = StatusBarRepository()
        repo._last_mp = 45.0

        assert repo.is_mp_below(50.0) == True
        assert repo.is_mp_below(40.0) == False

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_is_critical(self, mock_screen, mock_mana, mock_hp):
        mock_screen.return_value = Mock()
        mock_hp.return_value = None

        repo = StatusBarRepository()
        repo._last_hp = 25.0

        assert repo.is_critical(30.0) == True
        assert repo.is_critical(20.0) == False

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_needs_heal(self, mock_screen, mock_mana, mock_hp):
        mock_screen.return_value = Mock()
        mock_hp.return_value = None

        repo = StatusBarRepository()
        repo._last_hp = 65.0

        assert repo.needs_heal(70.0) == True
        assert repo.needs_heal(60.0) == False

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_needs_mana(self, mock_screen, mock_mana, mock_hp):
        mock_screen.return_value = Mock()
        mock_mana.return_value = None

        repo = StatusBarRepository()
        repo._last_mp = 45.0

        assert repo.needs_mana(50.0) == True
        assert repo.needs_mana(40.0) == False

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_get_status_returns_player_status(self, mock_screen, mock_mana, mock_hp):
        from src.core.types import PlayerStatus

        mock_screen_instance = Mock()
        mock_screen_instance.capture.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_screen.return_value = mock_screen_instance
        mock_hp.return_value = None
        mock_mana.return_value = None

        repo = StatusBarRepository()
        repo._last_hp = 75.0
        repo._last_mp = 50.0

        status = repo.get_status()

        assert isinstance(status, PlayerStatus)
        assert status.hp_percent == 75.0
        assert status.mp_percent == 50.0

    @patch('src.repositories.statusbar.core.get_hp_percentage')
    @patch('src.repositories.statusbar.core.get_mana_percentage')
    @patch('src.repositories.statusbar.core.get_screen_capture')
    def test_get_both_percentages(self, mock_screen, mock_mana, mock_hp):
        mock_screen_instance = Mock()
        mock_screen_instance.capture.return_value = np.zeros((100, 100), dtype=np.uint8)
        mock_screen.return_value = mock_screen_instance
        mock_hp.return_value = None
        mock_mana.return_value = None

        repo = StatusBarRepository()
        repo._last_hp = 80.0
        repo._last_mp = 60.0

        hp, mp = repo.get_both_percentages()

        assert hp == 80.0
        assert mp == 60.0


class TestEdgeCases:
    """Edge case tests."""

    def test_percentage_calculation_with_all_colors(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)

        section_size = BAR_SIZE // len(HP_BAR_COLORS)
        for i, color in enumerate(HP_BAR_COLORS):
            start = i * section_size
            end = start + section_size
            bar[start:end] = color

        percentage = get_filled_percentage(bar, HP_BAR_COLORS)

        expected = (section_size * len(HP_BAR_COLORS) * 100) // BAR_SIZE
        assert abs(percentage - expected) <= 1

    def test_percentage_boundary_values(self):
        bar = np.zeros(BAR_SIZE, dtype=np.uint8)
        assert get_filled_percentage(bar, HP_BAR_COLORS) == 0

        bar = np.full(BAR_SIZE, HP_BAR_COLORS[0], dtype=np.uint8)
        assert get_filled_percentage(bar, HP_BAR_COLORS) == 100

        bar = np.zeros(BAR_SIZE, dtype=np.uint8)
        bar[0] = HP_BAR_COLORS[0]
        assert get_filled_percentage(bar, HP_BAR_COLORS) == 1

        bar = np.full(BAR_SIZE, HP_BAR_COLORS[0], dtype=np.uint8)
        bar[-1] = 0
        percentage = get_filled_percentage(bar, HP_BAR_COLORS)
        assert percentage == 98

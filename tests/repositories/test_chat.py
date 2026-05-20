"""
Tests for Chat Repository - loot message parsing and detection.

Ensures:
1. Loot messages are parsed correctly (single, multiple, nothing, boss)
2. Item quantities are extracted properly
3. New line detection via hash comparison works (legacy)
4. Text-based deduplication via _message_key works
5. ChatRepository deduplicates by parsed text content
"""
import numpy as np
from unittest.mock import patch, MagicMock, Mock

from src.repositories.chat.core import (
    parse_loot_message,
    detect_new_loot_lines,
    normalize_gray_pixels,
    extract_timestamp,
    _message_key,
    ChatRepository,
)


class TestParseLootMessage:
    """Tests for parse_loot_message pure function."""

    def test_single_item(self):
        """Should parse a single item loot message."""
        result = parse_loot_message("Loot of a demon: a demon horn.")

        assert result is not None
        assert result['creature'] == 'demon'
        assert len(result['items']) == 1
        assert result['items'][0]['name'] == 'demon horn'
        assert result['items'][0]['quantity'] == 1

    def test_multiple_items(self):
        """Should parse multiple items separated by commas."""
        result = parse_loot_message(
            "Loot of a demon: a demon horn, 2 platinum coins."
        )

        assert result is not None
        assert result['creature'] == 'demon'
        assert len(result['items']) == 2
        assert result['items'][0]['name'] == 'demon horn'
        assert result['items'][0]['quantity'] == 1
        assert result['items'][1]['name'] == 'platinum coins'
        assert result['items'][1]['quantity'] == 2

    def test_nothing(self):
        """Should return empty items for 'nothing' loot."""
        result = parse_loot_message("Loot of a rat: nothing")

        assert result is not None
        assert result['creature'] == 'rat'
        assert result['items'] == []

    def test_nothing_with_period(self):
        """Should handle 'nothing.' with trailing period."""
        result = parse_loot_message("Loot of a rat: nothing.")

        assert result is not None
        assert result['creature'] == 'rat'
        assert result['items'] == []

    def test_boss_no_article(self):
        """Should parse boss names without article."""
        result = parse_loot_message("Loot of Hellgorak: a boots of haste.")

        assert result is not None
        assert result['creature'] == 'Hellgorak'
        assert len(result['items']) == 1
        assert result['items'][0]['name'] == 'boots of haste'

    def test_quantity_greater_than_one(self):
        """Should extract numeric quantities."""
        result = parse_loot_message(
            "Loot of a dragon: 100 gold coins, 3 dragon ham."
        )

        assert result is not None
        assert result['creature'] == 'dragon'
        assert len(result['items']) == 2
        assert result['items'][0]['name'] == 'gold coins'
        assert result['items'][0]['quantity'] == 100
        assert result['items'][1]['name'] == 'dragon ham'
        assert result['items'][1]['quantity'] == 3

    def test_article_an(self):
        """Should handle 'an' article."""
        result = parse_loot_message("Loot of an orc: an orcish axe.")

        assert result is not None
        assert result['creature'] == 'orc'
        assert len(result['items']) == 1
        assert result['items'][0]['name'] == 'orcish axe'
        assert result['items'][0]['quantity'] == 1

    def test_empty_string(self):
        """Should return None for empty input."""
        assert parse_loot_message("") is None

    def test_none_input(self):
        """Should return None for None input."""
        assert parse_loot_message(None) is None

    def test_non_loot_text(self):
        """Should return None for non-loot text."""
        assert parse_loot_message("Player says hello") is None

    def test_lowercase_loot(self):
        """Should handle lowercase 'loot of'."""
        result = parse_loot_message("loot of a demon: a demon horn.")

        assert result is not None
        assert result['creature'] == 'demon'

    def test_many_items(self):
        """Should parse loot with many items."""
        text = (
            "Loot of a demon: a demon horn, 2 small rubies, "
            "a fire mushroom, 100 gold coins, a demonic essence."
        )
        result = parse_loot_message(text)

        assert result is not None
        assert len(result['items']) == 5


class TestExtractTimestamp:
    """Tests for extract_timestamp function."""

    def test_hh_mm_ss(self):
        """Should extract HH:MM:SS timestamp."""
        assert extract_timestamp("13:04:56 Loot of a rotworm: 10 gold coins.") == '13:04:56'

    def test_hh_mm(self):
        """Should extract HH:MM timestamp."""
        assert extract_timestamp("13:04 Loot of a rotworm: 10 gold coins.") == '13:04'

    def test_no_timestamp(self):
        """Should return empty string when no timestamp."""
        assert extract_timestamp("Loot of a rotworm: 10 gold coins.") == ''

    def test_empty_string(self):
        """Should return empty string for empty input."""
        assert extract_timestamp('') == ''

    def test_none_input(self):
        """Should return empty string for None."""
        assert extract_timestamp(None) == ''


class TestMessageKey:
    """Tests for _message_key dedup function."""

    def test_same_message_same_key(self):
        """Should produce identical keys for identical messages."""
        msg = {'creature': 'rotworm', 'items': [{'name': 'gold coins', 'quantity': 10}]}
        assert _message_key(msg, '13:04:56') == _message_key(msg, '13:04:56')

    def test_different_items_different_key(self):
        """Should produce different keys for different items."""
        msg_a = {'creature': 'rotworm', 'items': [{'name': 'gold coins', 'quantity': 10}]}
        msg_b = {'creature': 'rotworm', 'items': [{'name': 'gold coins', 'quantity': 6}]}
        assert _message_key(msg_a, '13:04:56') != _message_key(msg_b, '13:04:56')

    def test_different_creature_different_key(self):
        """Should produce different keys for different creatures."""
        msg_a = {'creature': 'rotworm', 'items': [{'name': 'gold coins', 'quantity': 10}]}
        msg_b = {'creature': 'swampling', 'items': [{'name': 'gold coins', 'quantity': 10}]}
        assert _message_key(msg_a, '13:04:56') != _message_key(msg_b, '13:04:56')

    def test_different_timestamp_different_key(self):
        """Should produce different keys for same loot at different times."""
        msg = {'creature': 'rotworm', 'items': [{'name': 'gold coins', 'quantity': 10}]}
        assert _message_key(msg, '13:04:56') != _message_key(msg, '13:05:12')

    def test_item_order_does_not_matter(self):
        """Should produce same key regardless of item order."""
        msg_a = {'creature': 'rotworm', 'items': [
            {'name': 'gold coins', 'quantity': 6},
            {'name': 'lump of dirt', 'quantity': 1},
        ]}
        msg_b = {'creature': 'rotworm', 'items': [
            {'name': 'lump of dirt', 'quantity': 1},
            {'name': 'gold coins', 'quantity': 6},
        ]}
        assert _message_key(msg_a, '13:04:56') == _message_key(msg_b, '13:04:56')


class TestChatRepositoryDedup:
    """Tests for ChatRepository text-based deduplication."""

    def _make_repo(self):
        """Create ChatRepository without loading templates."""
        repo = ChatRepository.__new__(ChatRepository)
        repo._loot_of_template = Mock()
        repo._nothing_template = None
        repo._tab_templates = [Mock()]
        repo._seen_text_keys = []
        repo._previous_hashes = []
        repo._enabled = True
        return repo

    @patch('src.repositories.chat.core.extract_all_loot_texts')
    @patch('src.repositories.chat.core.get_loot_lines')
    @patch('src.repositories.chat.core.get_chat_content_area')
    @patch('src.repositories.chat.core.get_loot_tab_position')
    def test_deduplicates_same_message(self, mock_tab, mock_area, mock_lines, mock_ocr):
        """Should not return same message on second call."""
        repo = self._make_repo()
        screenshot = np.zeros((100, 200), dtype=np.uint8)

        mock_tab.return_value = (100, 50, 80, 20)
        mock_area.return_value = (10, 60, 180, 30)
        mock_lines.return_value = [(np.zeros((14, 100), dtype=np.uint8), (0, 0, 100, 14))]
        mock_ocr.return_value = ["13:04:56 Loot of a rotworm: 10 gold coins."]

        # First call: should return the message
        result1 = repo.get_new_loot_messages(screenshot)
        assert len(result1) == 1
        assert result1[0]['creature'] == 'rotworm'

        # Second call (same line still visible, same timestamp): should be deduped
        result2 = repo.get_new_loot_messages(screenshot)
        assert len(result2) == 0

    @patch('src.repositories.chat.core.extract_all_loot_texts')
    @patch('src.repositories.chat.core.get_loot_lines')
    @patch('src.repositories.chat.core.get_chat_content_area')
    @patch('src.repositories.chat.core.get_loot_tab_position')
    def test_detects_new_message_alongside_old(self, mock_tab, mock_area, mock_lines, mock_ocr):
        """Should detect new message even when old one is still visible."""
        repo = self._make_repo()
        screenshot = np.zeros((100, 200), dtype=np.uint8)

        mock_tab.return_value = (100, 50, 80, 20)
        mock_area.return_value = (10, 60, 180, 30)

        # First call: one line
        mock_lines.return_value = [(np.zeros((14, 100), dtype=np.uint8), (0, 0, 100, 14))]
        mock_ocr.return_value = ["13:04:56 Loot of a rotworm: 10 gold coins."]
        result1 = repo.get_new_loot_messages(screenshot)
        assert len(result1) == 1

        # Second call: old line + new line (different timestamp)
        line_a = np.zeros((14, 100), dtype=np.uint8)
        line_b = np.full((14, 100), 200, dtype=np.uint8)
        mock_lines.return_value = [
            (line_a, (0, 0, 100, 14)),
            (line_b, (0, 14, 100, 14)),
        ]
        mock_ocr.return_value = [
            "13:05:03 Loot of a rotworm: 6 gold coins, a lump of dirt.",
        ]
        result2 = repo.get_new_loot_messages(screenshot)
        assert len(result2) == 1
        assert result2[0]['items'][0]['name'] == 'gold coins'
        assert result2[0]['items'][0]['quantity'] == 6

    @patch('src.repositories.chat.core.extract_all_loot_texts')
    @patch('src.repositories.chat.core.get_loot_lines')
    @patch('src.repositories.chat.core.get_chat_content_area')
    @patch('src.repositories.chat.core.get_loot_tab_position')
    def test_identical_loot_different_timestamp_both_tracked(self, mock_tab, mock_area, mock_lines, mock_ocr):
        """Two identical loots at different seconds should both be tracked."""
        repo = self._make_repo()
        screenshot = np.zeros((100, 200), dtype=np.uint8)

        mock_tab.return_value = (100, 50, 80, 20)
        mock_area.return_value = (10, 60, 180, 30)

        # Both lines visible at once, same loot but different timestamps
        # Use distinct images so hash-based dedup treats them as separate lines
        line_a = np.zeros((14, 100), dtype=np.uint8)
        line_b = np.full((14, 100), 200, dtype=np.uint8)
        mock_lines.return_value = [
            (line_a, (0, 0, 100, 14)),
            (line_b, (0, 14, 100, 14)),
        ]
        mock_ocr.return_value = [
            "13:04:56 Loot of a rotworm: 10 gold coins.",
            "13:05:03 Loot of a rotworm: 10 gold coins.",
        ]
        result = repo.get_new_loot_messages(screenshot)
        assert len(result) == 2


class TestDetectNewLootLines:
    """Tests for detect_new_loot_lines hash comparison (legacy, still exported)."""

    def test_all_new_when_no_previous(self):
        """Should detect all lines as new when no previous hashes."""
        hashes = [111, 222, 333]
        new_indices, updated = detect_new_loot_lines(hashes, [])

        assert new_indices == [0, 1, 2]
        assert updated == [111, 222, 333]

    def test_detects_only_new_lines(self):
        """Should only return indices of lines not in previous."""
        hashes = [111, 222, 333]
        previous = [111, 222]

        new_indices, updated = detect_new_loot_lines(hashes, previous)

        assert new_indices == [2]

    def test_no_new_when_all_seen(self):
        """Should return empty when all lines were already seen."""
        hashes = [111, 222]
        previous = [111, 222, 333]

        new_indices, updated = detect_new_loot_lines(hashes, previous)

        assert new_indices == []

    def test_updated_hashes_capped(self):
        """Should cap updated hashes to CHAT_MAX_LOOT_LINES."""
        from src.core.constants import CHAT_MAX_LOOT_LINES

        hashes = list(range(CHAT_MAX_LOOT_LINES + 5))
        _, updated = detect_new_loot_lines(hashes, [])

        assert len(updated) == CHAT_MAX_LOOT_LINES

    def test_empty_input(self):
        """Should handle empty line hashes."""
        new_indices, updated = detect_new_loot_lines([], [111])

        assert new_indices == []
        assert updated == []


class TestNormalizeGrayPixels:
    """Tests for normalize_gray_pixels binary threshold (legacy, still exported)."""

    def test_dark_pixels_become_black(self):
        """Should threshold pixels <= 100 to 0."""
        image = np.array([[0, 50, 75, 100]], dtype=np.uint8)

        result = normalize_gray_pixels(image)

        np.testing.assert_array_equal(result, np.array([[0, 0, 0, 0]], dtype=np.uint8))

    def test_light_pixels_become_white(self):
        """Should threshold pixels > 100 to 255."""
        image = np.array([[101, 150, 200, 255]], dtype=np.uint8)

        result = normalize_gray_pixels(image)

        np.testing.assert_array_equal(result, np.array([[255, 255, 255, 255]], dtype=np.uint8))

    def test_consistent_hash_across_slight_variations(self):
        """Same text with slightly different pixel values should hash the same."""
        from src.utils.hash import hashit

        # Simulate two screenshots of same line with slight pixel variation
        image_a = np.array([[0, 0, 180, 192, 0, 247, 0]], dtype=np.uint8)
        image_b = np.array([[2, 0, 182, 190, 1, 245, 0]], dtype=np.uint8)

        norm_a = normalize_gray_pixels(image_a)
        norm_b = normalize_gray_pixels(image_b)

        assert hashit(norm_a) == hashit(norm_b)

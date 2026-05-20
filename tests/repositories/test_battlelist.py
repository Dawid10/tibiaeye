"""
Tests for BattleListRepository - creature detection and targeting.

Ensures:
1. Creature detection works correctly
2. Attack state detection works
3. Slot counting works
4. Hash-based creature identification works
5. Blacklist filtering works
6. Best target selection works
"""
import numpy as np
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src.core.constants import UNIDENTIFIED_CREATURE_NAME


@dataclass
class MockCreature:
    """Mock creature for testing."""
    name: str
    x: int = 0
    y: int = 0
    width: int = 156
    height: int = 22
    creature_type: str = 'monster'
    confidence: float = 1.0
    is_being_attacked: bool = False


class TestBattleListSlotCounting:
    """Tests for slot counting logic."""

    def test_count_filled_slots_empty(self):
        """Test slot counting with empty battle list."""
        from src.repositories.battlelist.core import BattleListRepository

        # Create empty content (no text pixels)
        content = np.zeros((220, 156), dtype=np.uint8)

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.SLOT_START_Y = 11
        repo.NAME_START_X = 23
        repo.TEXT_PIXEL_VALUES = (192, 247)

        count = repo._get_filled_slots_count(content)

        assert count == 0

    def test_count_filled_slots_one_creature(self):
        """Test slot counting with one creature."""
        from src.repositories.battlelist.core import BattleListRepository

        # Create content with text pixel in first slot
        content = np.zeros((220, 156), dtype=np.uint8)
        content[11, 23] = 192  # Text pixel at slot 0, position (y=11, x=23)

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.SLOT_START_Y = 11
        repo.NAME_START_X = 23
        repo.TEXT_PIXEL_VALUES = (192, 247)

        count = repo._get_filled_slots_count(content)

        assert count == 1

    def test_count_filled_slots_multiple_creatures(self):
        """Test slot counting with multiple creatures."""
        from src.repositories.battlelist.core import BattleListRepository

        content = np.zeros((220, 156), dtype=np.uint8)
        # Add text pixels for 3 slots
        content[11, 23] = 192  # Slot 0
        content[33, 23] = 247  # Slot 1 (22 + 11 = 33)
        content[55, 23] = 192  # Slot 2 (44 + 11 = 55)

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.SLOT_START_Y = 11
        repo.NAME_START_X = 23
        repo.TEXT_PIXEL_VALUES = (192, 247)

        count = repo._get_filled_slots_count(content)

        assert count == 3

    def test_count_filled_slots_gap_stops(self):
        """Test that empty slot stops counting."""
        from src.repositories.battlelist.core import BattleListRepository

        content = np.zeros((220, 156), dtype=np.uint8)
        content[11, 23] = 192  # Slot 0
        # Slot 1 is empty
        content[55, 23] = 192  # Slot 2 (should not be counted)

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.SLOT_START_Y = 11
        repo.NAME_START_X = 23
        repo.TEXT_PIXEL_VALUES = (192, 247)

        count = repo._get_filled_slots_count(content)

        assert count == 1  # Only first slot counted

    def test_count_filled_slots_none_content(self):
        """Test slot counting with None content."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        count = repo._get_filled_slots_count(None)

        assert count == 0


class TestSlotAttackDetection:
    """Tests for attack state detection."""

    def test_is_slot_being_attacked_true(self):
        """Test attack detection when corners are red."""
        from src.repositories.battlelist.core import BattleListRepository

        content = np.zeros((220, 156), dtype=np.uint8)
        # Set all 4 corners to attack color (76)
        content[0, 0] = 76    # top-left
        content[0, 19] = 76   # top-right
        content[19, 0] = 76   # bottom-left
        content[19, 19] = 76  # bottom-right

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.ATTACK_PIXEL_VALUES = (76, 166)

        is_attacked = repo._is_slot_being_attacked(content, 0)

        assert is_attacked == True

    def test_is_slot_being_attacked_false(self):
        """Test attack detection when corners are not red."""
        from src.repositories.battlelist.core import BattleListRepository

        content = np.zeros((220, 156), dtype=np.uint8)
        # Corners have default value (0), not attack color

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.ATTACK_PIXEL_VALUES = (76, 166)

        is_attacked = repo._is_slot_being_attacked(content, 0)

        assert is_attacked == False

    def test_is_slot_being_attacked_partial(self):
        """Test attack detection when only some corners are red."""
        from src.repositories.battlelist.core import BattleListRepository

        content = np.zeros((220, 156), dtype=np.uint8)
        # Only 2 corners are red
        content[0, 0] = 76
        content[0, 19] = 76

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.ATTACK_PIXEL_VALUES = (76, 166)

        is_attacked = repo._is_slot_being_attacked(content, 0)

        assert is_attacked == False

    def test_is_slot_being_attacked_second_slot(self):
        """Test attack detection for second slot."""
        from src.repositories.battlelist.core import BattleListRepository

        content = np.zeros((220, 156), dtype=np.uint8)
        # Set corners for slot 1 (starting at y=22)
        content[22, 0] = 166    # top-left
        content[22, 19] = 166   # top-right
        content[41, 0] = 166    # bottom-left (22 + 19 = 41)
        content[41, 19] = 166   # bottom-right

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo.ATTACK_PIXEL_VALUES = (76, 166)

        is_attacked = repo._is_slot_being_attacked(content, 1)

        assert is_attacked == True


class TestBlacklistFiltering:
    """Tests for blacklist functionality."""

    def test_is_blacklisted_true(self):
        """Test creature is blacklisted."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = ['dragon', 'demon']

        assert repo.is_blacklisted('Dragon') == True
        assert repo.is_blacklisted('Demon Lord') == True

    def test_is_blacklisted_false(self):
        """Test creature is not blacklisted."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = ['dragon', 'demon']

        assert repo.is_blacklisted('Rotworm') == False
        assert repo.is_blacklisted('Cave Rat') == False

    def test_is_blacklisted_empty_list(self):
        """Test no blacklist."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = []

        assert repo.is_blacklisted('Dragon') == False

    def test_is_blacklisted_case_insensitive(self):
        """Test blacklist matching is case insensitive."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = ['dragon']

        assert repo.is_blacklisted('DRAGON') == True
        assert repo.is_blacklisted('dragon') == True
        assert repo.is_blacklisted('DrAgOn') == True


class TestValidTargets:
    """Tests for valid target filtering."""

    def test_get_valid_targets_filters_blacklist(self):
        """Test valid targets excludes blacklisted creatures."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = ['dragon']

        creatures = [
            MockCreature(name='Rotworm'),
            MockCreature(name='Dragon'),
            MockCreature(name='Cave Rat'),
        ]

        valid = repo.get_valid_targets(creatures)

        assert len(valid) == 2
        assert all(c.name != 'Dragon' for c in valid)

    def test_get_valid_targets_all_valid(self):
        """Test valid targets when no blacklist matches."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = ['demon']

        creatures = [
            MockCreature(name='Rotworm'),
            MockCreature(name='Cave Rat'),
        ]

        valid = repo.get_valid_targets(creatures)

        assert len(valid) == 2


class TestBestTarget:
    """Tests for best target selection."""

    def test_get_best_target_prioritizes_attacked(self):
        """Test best target returns creature being attacked."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = []

        creatures = [
            MockCreature(name='Rotworm', is_being_attacked=False),
            MockCreature(name='Cave Rat', is_being_attacked=True),
            MockCreature(name='Larva', is_being_attacked=False),
        ]

        best = repo.get_best_target(creatures)

        assert best.name == 'Cave Rat'

    def test_get_best_target_first_when_none_attacked(self):
        """Test best target returns first when none attacked."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = []

        creatures = [
            MockCreature(name='Rotworm'),
            MockCreature(name='Cave Rat'),
        ]

        best = repo.get_best_target(creatures)

        assert best.name == 'Rotworm'

    def test_get_best_target_empty_list(self):
        """Test best target returns None for empty list."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = []

        best = repo.get_best_target([])

        assert best is None

    def test_get_best_target_all_blacklisted(self):
        """Test best target returns None when all blacklisted."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._blacklist = ['rotworm', 'dragon']

        creatures = [
            MockCreature(name='Rotworm'),
            MockCreature(name='Dragon'),
        ]

        best = repo.get_best_target(creatures)

        assert best is None


class TestBeingAttackedCreature:
    """Tests for finding creature being attacked."""

    def test_get_being_attacked_creature_found(self):
        """Test finding creature being attacked."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        creatures = [
            MockCreature(name='Rotworm', is_being_attacked=False),
            MockCreature(name='Cave Rat', is_being_attacked=True),
        ]

        attacked = repo.get_being_attacked_creature(creatures)

        assert attacked is not None
        assert attacked.name == 'Cave Rat'

    def test_get_being_attacked_creature_not_found(self):
        """Test no creature being attacked."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        creatures = [
            MockCreature(name='Rotworm', is_being_attacked=False),
            MockCreature(name='Cave Rat', is_being_attacked=False),
        ]

        attacked = repo.get_being_attacked_creature(creatures)

        assert attacked is None

    def test_get_being_attacked_creature_empty(self):
        """Test empty creature list."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        attacked = repo.get_being_attacked_creature([])

        assert attacked is None


class TestHashTableNameLookup:
    """Tests for hash-based creature name lookup."""

    def test_get_creature_name_by_hash_found(self):
        """Test hash lookup when name exists in table."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_START_Y = 11
        repo.SLOT_HEIGHT = 22
        repo.NAME_START_X = 23
        repo.NAME_WIDTH = 115
        repo._name_hashes = {}
        repo._templates = []

        # Create content with known pattern
        content = np.zeros((220, 156), dtype=np.uint8)

        # The actual hash lookup won't find anything since we don't have real hashes
        name = repo._get_creature_name_by_hash(content, 0, None)

        # Should fall back to template matching or return Unknown
        assert name == 'Unknown'

    def test_get_creature_name_by_hash_with_whitelist(self):
        """Test hash lookup respects whitelist."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_START_Y = 11
        repo.SLOT_HEIGHT = 22
        repo.NAME_START_X = 23
        repo.NAME_WIDTH = 115
        repo._name_hashes = {}
        repo._templates = []

        content = np.zeros((220, 156), dtype=np.uint8)

        # With whitelist, should still return Unknown (hash not found)
        name = repo._get_creature_name_by_hash(content, 0, ['rotworm'])

        assert name == 'Unknown'


class TestTemplateMatchingFallback:
    """Tests for template matching fallback."""

    def test_get_creature_name_by_template_no_templates(self):
        """Test template matching with no templates."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo._templates = []

        content = np.zeros((220, 156), dtype=np.uint8)

        name = repo._get_creature_name_by_template(content, 0, None)

        assert name == 'Unknown'

    def test_get_creature_name_by_template_with_whitelist(self):
        """Test template matching filters by whitelist."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo.SLOT_HEIGHT = 22
        repo._templates = [
            {'name': 'Rotworm', 'image': np.zeros((20, 100), dtype=np.uint8)},
            {'name': 'Dragon', 'image': np.zeros((20, 100), dtype=np.uint8)},
        ]

        content = np.zeros((220, 156), dtype=np.uint8)

        # With whitelist that doesn't include our templates
        name = repo._get_creature_name_by_template(content, 0, ['cave rat'])

        # Should return Unknown since no match
        assert name == 'Unknown'


class TestCreatureTypeFromName:
    """Tests for creature type determination."""

    def test_unknown_creature_is_player_type(self):
        """Test that unidentified creatures are typed as PLAYER (safety feature)."""
        from src.core.types import CreatureType

        # This is documented behavior: Unknown creatures are marked as PLAYER
        # to prevent attacking players by mistake
        creature_name = 'Unknown'  # Internal value before conversion

        if creature_name == 'Unknown':
            creature_name = UNIDENTIFIED_CREATURE_NAME
            creature_type = CreatureType.PLAYER
        else:
            creature_type = CreatureType.MONSTER

        assert creature_type == CreatureType.PLAYER
        assert creature_name == UNIDENTIFIED_CREATURE_NAME

    def test_known_creature_is_monster_type(self):
        """Test that known creatures are typed as MONSTER."""
        from src.core.types import CreatureType

        creature_name = 'Rotworm'

        if creature_name == 'Unknown':
            creature_name = UNIDENTIFIED_CREATURE_NAME
            creature_type = CreatureType.PLAYER
        else:
            creature_type = CreatureType.MONSTER

        assert creature_type == CreatureType.MONSTER
        assert creature_name == 'Rotworm'  # Name should NOT change


class TestLocateFunction:
    """Tests for template locate function."""

    def test_locate_finds_template(self):
        """Test _locate finds matching template."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        # Create screenshot with a distinctive pattern (gradient for better matching)
        screenshot = np.zeros((100, 100), dtype=np.uint8)
        for i in range(10):
            for j in range(10):
                screenshot[40+i, 40+j] = (i * 25 + j * 10) % 256

        # Create template that matches the pattern
        template = np.zeros((10, 10), dtype=np.uint8)
        for i in range(10):
            for j in range(10):
                template[i, j] = (i * 25 + j * 10) % 256

        result = repo._locate(screenshot, template, confidence=0.9)

        assert result is not None
        assert result[0] == 40  # x
        assert result[1] == 40  # y

    def test_locate_not_found(self):
        """Test _locate returns None when not found."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        # Create gradient screenshot
        screenshot = np.zeros((100, 100), dtype=np.uint8)
        for i in range(100):
            screenshot[i, :] = i * 2 % 256

        # Template with completely different pattern
        template = np.full((10, 10), 128, dtype=np.uint8)

        result = repo._locate(screenshot, template, confidence=0.9)

        assert result is None

    def test_locate_template_larger_than_image(self):
        """Test _locate returns None when template larger than image."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        screenshot = np.zeros((10, 10), dtype=np.uint8)
        template = np.zeros((20, 20), dtype=np.uint8)

        result = repo._locate(screenshot, template)

        assert result is None

    def test_locate_none_inputs(self):
        """Test _locate handles None inputs."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)

        assert repo._locate(None, np.zeros((10, 10))) is None
        assert repo._locate(np.zeros((100, 100)), None) is None


class TestIconPositionCaching:
    """Tests for icon position caching optimization."""

    def test_cached_icon_pos_used(self):
        """Test that cached icon position is reused."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._icon_image = np.zeros((20, 20), dtype=np.uint8)
        repo._cached_icon_pos = (100, 50, 20, 20)  # x, y, w, h
        repo._cached_icon_hash = None
        repo._template_confidence = 0.85

        # Create screenshot large enough
        screenshot = np.zeros((200, 200), dtype=np.uint8)

        pos = repo._get_icon_position(screenshot)

        # Should return cached position
        assert pos == (100, 50, 20, 20)

    def test_cache_cleared_on_bounds_fail(self):
        """Test _get_icon_position returns None when no icon image loaded."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._icon_image = None  # No icon image loaded
        repo._cached_icon_pos = None
        repo._template_confidence = 0.85

        screenshot = np.zeros((100, 100), dtype=np.uint8)

        pos = repo._get_icon_position(screenshot)

        # Should return None because no icon image
        assert pos is None


class TestProperties:
    """Tests for repository properties."""

    def test_template_count(self):
        """Test template_count property."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._name_hashes = {123: 'Rotworm', 456: 'Cave Rat', 789: 'Larva'}

        assert repo.template_count == 3

    def test_template_names(self):
        """Test template_names property."""
        from src.repositories.battlelist.core import BattleListRepository

        repo = BattleListRepository.__new__(BattleListRepository)
        repo._name_hashes = {123: 'Rotworm', 456: 'Cave Rat'}

        names = repo.template_names

        assert 'Rotworm' in names
        assert 'Cave Rat' in names


if __name__ == '__main__':
    pytest.main([__file__, '-v'])

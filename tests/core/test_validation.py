"""Tests for pre-flight validation checks."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from src.core.validation import check_healing_configured, check_route_file


class TestCheckHealingConfigured:
    def test_no_healing_configured(self):
        """Should fail when no healing is configured."""
        settings = {'healthPotion': {}, 'manaPotion': {}, 'spells': []}
        passed, msg = check_healing_configured(settings)
        assert not passed
        assert "Nenhuma" in msg

    def test_hp_potion_configured(self):
        """Should pass when HP potion is configured."""
        settings = {
            'healthPotion': {'enabled': True, 'hotkey': '1'},
            'manaPotion': {},
            'spells': [],
        }
        passed, msg = check_healing_configured(settings)
        assert passed

    def test_spell_configured(self):
        """Should pass when a spell is configured."""
        settings = {
            'healthPotion': {},
            'manaPotion': {},
            'spells': [{'enabled': True, 'hotkey': 'F1'}],
        }
        passed, msg = check_healing_configured(settings)
        assert passed

    def test_disabled_potion_not_counted(self):
        """Should not count disabled potions."""
        settings = {
            'healthPotion': {'enabled': False, 'hotkey': '1'},
            'manaPotion': {},
            'spells': [],
        }
        passed, msg = check_healing_configured(settings)
        assert not passed


class TestCheckRouteFile:
    def test_empty_route_file(self):
        """Should fail when route file is empty string."""
        passed, msg = check_route_file('')
        assert not passed
        assert "Nenhuma" in msg

    def test_nonexistent_route_file(self):
        """Should fail when route file does not exist."""
        passed, msg = check_route_file('/nonexistent/path/route.json')
        assert not passed
        assert "nao encontrado" in msg

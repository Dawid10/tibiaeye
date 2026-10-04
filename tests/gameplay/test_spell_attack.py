"""Tests for the spell attack system."""
import time
from dataclasses import dataclass
from unittest.mock import patch, MagicMock

import pytest

from src.gameplay.spell_attack import (
    handle_spell_attack,
    _should_skip,
    _match_condition,
    _find_matching_group,
    _select_spell,
    _can_cast,
    _has_enough_mana,
    _get_creature_count,
    _cast_spell,
    _cooldown_ready,
    _log_cast,
)


@dataclass
class MockCreature:
    name: str
    slot: tuple = (7, 5)


def create_spell(name='exori', hotkey='F4', mana_cost=30, cooldown=2.0,
                 spell_group='attack', enabled=True):
    return {
        'name': name,
        'hotkey': hotkey,
        'manaCost': mana_cost,
        'cooldown': cooldown,
        'spellGroup': spell_group,
        'enabled': enabled,
    }


def create_group(name='AoE', spells=None, compare='greaterThanOrEqual',
                 value=1, count_mode='nearest', enabled=True):
    return {
        'name': name,
        'spells': spells or [],
        'compare': compare,
        'value': value,
        'countMode': count_mode,
        'enabled': enabled,
    }


def create_mock_context(mana=500, mana_percent=80, is_attacking=True,
                        monsters=None, groups=None, enabled=True,
                        mana_reserve=30, gui_logger=None, cavebot_enabled=True):
    if monsters is None:
        monsters = [MockCreature('Rat', (7, 4))]
    if groups is None:
        groups = []
    return {
        'statusBar': {
            'mana': mana,
            'manaPercentage': mana_percent,
        },
        'cavebot': {
            'enabled': cavebot_enabled,
            'isAttackingSomeCreature': is_attacking,
        },
        'gameWindow': {
            'monsters': monsters,
        },
        'spellAttack': {
            'enabled': enabled,
            'manaReservePercent': mana_reserve,
            'groups': groups,
            'lastCastSpell': None,
            'lastCastTime': 0,
        },
        'gui_logger': gui_logger,
    }


class TestShouldSkip:
    """Test _should_skip conditions."""

    def test_skip_when_cavebot_off(self):
        """Healing-only runs (cavebot off) never press attack keys."""
        context = create_mock_context(cavebot_enabled=False)
        assert _should_skip(context) is True

    def test_skip_when_disabled(self):
        """Should skip when spell attack is disabled."""
        context = create_mock_context(enabled=False)
        assert _should_skip(context) is True

    def test_skip_before_the_bot_attacks(self):
        """A monster in sight but no attack yet: casting now would hide its health bar."""
        context = create_mock_context(is_attacking=False)
        assert _should_skip(context) is True

    def test_no_skip_during_attack_task_without_red_square(self):
        """The red attack square is often not seen mid-fight: the running attack task is enough."""
        context = create_mock_context(is_attacking=False)
        context['cavebot']['inAttackTask'] = True
        assert _should_skip(context) is False

    def test_skip_when_no_monsters(self):
        """Should skip when no monsters visible."""
        context = create_mock_context(monsters=[])
        assert _should_skip(context) is True

    def test_no_skip_when_valid(self):
        """Should not skip when enabled, attacking, and monsters visible."""
        context = create_mock_context()
        assert _should_skip(context) is False

    def test_skip_when_spell_attack_missing(self):
        """Should skip when spellAttack key is missing from context."""
        context = {'cavebot': {}, 'gameWindow': {}}
        assert _should_skip(context) is True


class TestMatchCondition:
    """Test _match_condition with various comparisons."""

    def test_less_than_true(self):
        assert _match_condition('lessThan', 3, 2) is True

    def test_less_than_false(self):
        assert _match_condition('lessThan', 3, 3) is False

    def test_less_than_or_equal_boundary(self):
        assert _match_condition('lessThanOrEqual', 3, 3) is True

    def test_less_than_or_equal_above(self):
        assert _match_condition('lessThanOrEqual', 3, 4) is False

    def test_greater_than_true(self):
        assert _match_condition('greaterThan', 3, 4) is True

    def test_greater_than_false(self):
        assert _match_condition('greaterThan', 3, 3) is False

    def test_greater_than_or_equal_boundary(self):
        assert _match_condition('greaterThanOrEqual', 3, 3) is True

    def test_greater_than_or_equal_below(self):
        assert _match_condition('greaterThanOrEqual', 3, 2) is False

    def test_unknown_condition(self):
        assert _match_condition('equals', 3, 3) is False


class TestGroupSelection:
    """Test _find_matching_group."""

    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_first_match_wins(self, mock_count):
        """Should return the first matching group."""
        groups = [
            create_group(name='G1', compare='greaterThanOrEqual', value=5),
            create_group(name='G2', compare='greaterThanOrEqual', value=3),
            create_group(name='G3', compare='greaterThanOrEqual', value=1),
        ]
        context = create_mock_context()
        result = _find_matching_group(groups, context)
        assert result['name'] == 'G2'

    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_disabled_group_skipped(self, mock_count):
        """Should skip disabled groups."""
        groups = [
            create_group(name='Disabled', compare='greaterThanOrEqual', value=1, enabled=False),
            create_group(name='Active', compare='greaterThanOrEqual', value=1),
        ]
        context = create_mock_context()
        result = _find_matching_group(groups, context)
        assert result['name'] == 'Active'

    @patch('src.gameplay.spell_attack._get_creature_count', return_value=1)
    def test_no_match_returns_none(self, mock_count):
        """Should return None when no group matches."""
        groups = [
            create_group(compare='greaterThanOrEqual', value=5),
        ]
        context = create_mock_context()
        assert _find_matching_group(groups, context) is None

    def test_empty_groups(self):
        """Should return None with empty groups list."""
        context = create_mock_context()
        assert _find_matching_group([], context) is None


class TestSpellSelection:
    """Test _select_spell."""

    def test_first_castable_spell(self):
        """Should select the first spell that can be cast."""
        cooldowns = {}
        spells = [
            create_spell('exori gran', cooldown=6.0),
            create_spell('exori', cooldown=2.0),
        ]
        result = _select_spell(spells, cooldowns)
        assert result['name'] == 'exori gran'

    def test_skip_on_cooldown(self):
        """Should skip spells on individual cooldown."""
        cooldowns = {'spell:exori gran': time.time()}
        spells = [
            create_spell('exori gran', cooldown=6.0),
            create_spell('exori', cooldown=2.0),
        ]
        result = _select_spell(spells, cooldowns)
        assert result['name'] == 'exori'

    def test_all_on_cooldown(self):
        """Should return None if all spells are on cooldown."""
        now = time.time()
        cooldowns = {
            'spell:exori gran': now,
            'spell:exori': now,
            'spell_attack:global': now,
        }
        spells = [
            create_spell('exori gran', cooldown=6.0),
            create_spell('exori', cooldown=2.0),
        ]
        assert _select_spell(spells, cooldowns) is None

    def test_skip_disabled_spell(self):
        """Should skip disabled spells."""
        cooldowns = {}
        spells = [
            create_spell('exori gran', enabled=False),
            create_spell('exori'),
        ]
        result = _select_spell(spells, cooldowns)
        assert result['name'] == 'exori'

    def test_empty_spells(self):
        """Should return None with empty spell list."""
        cooldowns = {}
        assert _select_spell([], cooldowns) is None


class TestCanCast:
    """Test _can_cast cooldown checks."""

    def test_can_cast_fresh(self):
        """Should be castable with no cooldowns active."""
        cooldowns = {}
        spell = create_spell()
        assert _can_cast(spell, cooldowns) is True

    def test_global_cooldown_blocks(self):
        """Global cooldown should block casting."""
        cooldowns = {'spell_attack:global': time.time()}
        spell = create_spell()
        assert _can_cast(spell, cooldowns) is False

    def test_individual_cooldown_blocks(self):
        """Individual spell cooldown should block casting."""
        cooldowns = {'spell:exori': time.time()}
        spell = create_spell('exori', cooldown=2.0)
        assert _can_cast(spell, cooldowns) is False

    def test_group_cooldown_blocks(self):
        """Group cooldown should block casting."""
        cooldowns = {'group:attack': time.time()}
        spell = create_spell(spell_group='attack')
        assert _can_cast(spell, cooldowns) is False

    def test_support_group_independent(self):
        """Attack group cooldown should not block support group spells."""
        cooldowns = {'group:attack': time.time()}
        spell = create_spell(spell_group='support')
        # Global is not on cooldown, individual is not on cooldown
        assert _can_cast(spell, cooldowns) is True


class TestCooldownReady:
    """Test _cooldown_ready helper."""

    def test_ready_when_no_entry(self):
        """Should be ready when key doesn't exist."""
        assert _cooldown_ready({}, 'test', 1.0, time.time()) is True

    def test_ready_when_expired(self):
        """Should be ready when cooldown has expired."""
        cooldowns = {'test': time.time() - 5.0}
        assert _cooldown_ready(cooldowns, 'test', 2.0, time.time()) is True

    def test_not_ready_when_active(self):
        """Should not be ready when cooldown is still active."""
        cooldowns = {'test': time.time()}
        assert _cooldown_ready(cooldowns, 'test', 2.0, time.time()) is False


class TestManaCheck:
    """Test _has_enough_mana (percentage-based only)."""

    def test_enough_mana(self):
        """Should return True when mana percentage is above reserve."""
        context = create_mock_context(mana_percent=80)
        spell = create_spell(mana_cost=30)
        assert _has_enough_mana(context, spell, 30) is True

    def test_below_mana_reserve(self):
        """Should return False when mana percentage is below reserve."""
        context = create_mock_context(mana_percent=20)
        spell = create_spell(mana_cost=30)
        assert _has_enough_mana(context, spell, 30) is False

    def test_zero_reserve(self):
        """Should allow casting with zero mana reserve."""
        context = create_mock_context(mana_percent=5)
        spell = create_spell(mana_cost=30)
        assert _has_enough_mana(context, spell, 0) is True

    def test_boundary_reserve(self):
        """Should allow casting when mana percent exactly equals reserve."""
        context = create_mock_context(mana_percent=30)
        spell = create_spell(mana_cost=30)
        assert _has_enough_mana(context, spell, 30) is True


class TestCooldowns:
    """Test cooldown recording in _cast_spell."""

    @patch('src.gameplay.spell_attack.pyautogui')
    def test_records_all_cooldowns(self, mock_pyautogui):
        """Should record global, individual, and group cooldowns."""
        cooldowns = {}
        spell = create_spell('exori', hotkey='F4', spell_group='attack')
        _cast_spell(spell, cooldowns)

        assert 'spell_attack:global' in cooldowns
        assert 'spell:exori' in cooldowns
        assert 'group:attack' in cooldowns

    @patch('src.gameplay.spell_attack.pyautogui')
    def test_presses_hotkey(self, mock_pyautogui):
        """Should press the spell hotkey."""
        cooldowns = {}
        spell = create_spell(hotkey='F5')
        _cast_spell(spell, cooldowns)
        mock_pyautogui.press.assert_called_once_with('F5')

    @patch('src.gameplay.spell_attack.pyautogui')
    def test_no_press_without_hotkey(self, mock_pyautogui):
        """Should not press anything if hotkey is empty."""
        cooldowns = {}
        spell = create_spell(hotkey='')
        _cast_spell(spell, cooldowns)
        mock_pyautogui.press.assert_not_called()

    @patch('src.gameplay.spell_attack.pyautogui')
    def test_independent_groups(self, mock_pyautogui):
        """Attack and support groups should have independent cooldowns."""
        cooldowns = {}

        spell_attack = create_spell('exori', spell_group='attack')
        _cast_spell(spell_attack, cooldowns)

        # Support group should still be available
        assert 'group:support' not in cooldowns
        # Attack group should be on cooldown
        assert 'group:attack' in cooldowns


class TestCreatureCount:
    """Test _get_creature_count."""

    def test_total_mode(self):
        """Total mode should return len(monsters)."""
        monsters = [MockCreature('Rat') for _ in range(5)]
        context = create_mock_context(monsters=monsters)
        assert _get_creature_count(context, 'total') == 5

    def test_total_mode_empty(self):
        """Total mode should return 0 for empty list."""
        context = create_mock_context(monsters=[])
        assert _get_creature_count(context, 'total') == 0

    @patch('src.repositories.gamewindow.get_nearest_creatures_count', return_value=3)
    def test_nearest_mode(self, mock_nearest):
        """Nearest mode should use get_nearest_creatures_count."""
        monsters = [MockCreature('Rat') for _ in range(5)]
        context = create_mock_context(monsters=monsters)
        result = _get_creature_count(context, 'nearest')
        assert result == 3
        mock_nearest.assert_called_once_with(monsters)

    @patch('src.repositories.gamewindow.get_nearest_creatures_count', return_value=0)
    def test_nearest_mode_empty(self, mock_nearest):
        """Nearest mode should return 0 for empty list."""
        context = create_mock_context(monsters=[])
        result = _get_creature_count(context, 'nearest')
        assert result == 0


class TestIntegration:
    """Integration tests for handle_spell_attack."""

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_full_flow_casts_spell(self, mock_count, mock_pyautogui):
        """Full flow: matching group + available spell -> cast."""
        spells = [create_spell('exori gran', 'F5', 340, 6.0)]
        groups = [create_group('AoE', spells, 'greaterThanOrEqual', 3)]
        context = create_mock_context(mana=500, mana_percent=80, groups=groups)
        cooldowns = {}

        result = handle_spell_attack(context, cooldowns)

        mock_pyautogui.press.assert_called_once_with('F5')
        assert result['spellAttack']['lastCastSpell'] == 'exori gran'
        assert result['spellAttack']['lastCastTime'] > 0

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_context_updated_after_cast(self, mock_count, mock_pyautogui):
        """Context should be updated with lastCastSpell and lastCastTime."""
        spells = [create_spell('exori')]
        groups = [create_group('G1', spells, 'greaterThanOrEqual', 1)]
        context = create_mock_context(groups=groups)
        cooldowns = {}

        before = time.time()
        result = handle_spell_attack(context, cooldowns)
        after = time.time()

        assert result['spellAttack']['lastCastSpell'] == 'exori'
        assert before <= result['spellAttack']['lastCastTime'] <= after

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count')
    def test_switches_group_on_count_change(self, mock_count, mock_pyautogui):
        """Should switch to a different group when creature count changes."""
        spell_aoe = create_spell('exori gran', 'F5', 340, 6.0)
        spell_single = create_spell('exori', 'F4', 30, 2.0)

        groups = [
            create_group('AoE', [spell_aoe], 'greaterThanOrEqual', 3),
            create_group('Single', [spell_single], 'greaterThanOrEqual', 1),
        ]
        context = create_mock_context(groups=groups)
        cooldowns = {}

        # First: 3 creatures -> AoE group
        mock_count.return_value = 3
        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_called_with('F5')

        # Reset cooldowns for next cast
        cooldowns.clear()

        # Second: 1 creature -> Single group
        mock_count.return_value = 1
        context['spellAttack']['lastCastSpell'] = None
        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_called_with('F4')

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_fallback_on_cooldown(self, mock_count, mock_pyautogui):
        """Should fallback to lower priority spell when higher is on cooldown."""
        spells = [
            create_spell('exori gran', 'F5', 340, 6.0),
            create_spell('exori', 'F4', 30, 2.0),
        ]
        groups = [create_group('G1', spells, 'greaterThanOrEqual', 1)]
        context = create_mock_context(groups=groups)
        cooldowns = {}

        # Cast first spell
        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_called_with('F5')

        # Reset global and group but keep individual cooldowns
        del cooldowns['spell_attack:global']
        del cooldowns['group:attack']

        # Second cast should fallback to exori
        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_called_with('F4')

    @patch('src.gameplay.spell_attack.pyautogui')
    def test_skip_when_disabled(self, mock_pyautogui):
        """Should not cast when spell attack is disabled."""
        spells = [create_spell()]
        groups = [create_group('G1', spells)]
        context = create_mock_context(enabled=False, groups=groups)
        cooldowns = {}

        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_not_called()

    @patch('src.gameplay.spell_attack.pyautogui')
    def test_skip_when_no_monster_anywhere(self, mock_pyautogui):
        """No monster in the battle list or on screen: nothing to cast at."""
        spells = [create_spell()]
        groups = [create_group('G1', spells)]
        context = create_mock_context(is_attacking=False, groups=groups, monsters=[])
        cooldowns = {}

        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_not_called()

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_skip_when_mana_below_reserve(self, mock_count, mock_pyautogui):
        """Should not cast when mana percentage is below reserve."""
        spells = [create_spell('exori', mana_cost=30)]
        groups = [create_group('G1', spells, 'greaterThanOrEqual', 1)]
        context = create_mock_context(mana_percent=20,
                                      groups=groups, mana_reserve=30)
        cooldowns = {}

        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_not_called()

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=1)
    def test_no_matching_group(self, mock_count, mock_pyautogui):
        """Should not cast when no group condition matches."""
        spells = [create_spell()]
        groups = [create_group('G1', spells, 'greaterThanOrEqual', 5)]
        context = create_mock_context(groups=groups)
        cooldowns = {}

        handle_spell_attack(context, cooldowns)
        mock_pyautogui.press.assert_not_called()


class TestLogging:
    """Test logging behavior."""

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    def test_gui_logger_called(self, mock_count, mock_pyautogui):
        """Should call gui_logger when available."""
        mock_logger = MagicMock()
        spells = [create_spell('exori')]
        groups = [create_group('G1', spells, 'greaterThanOrEqual', 1)]
        context = create_mock_context(groups=groups, gui_logger=mock_logger)
        cooldowns = {}

        handle_spell_attack(context, cooldowns)

        mock_logger.assert_called_once()
        call_args = mock_logger.call_args
        assert 'exori' in call_args[0][0]
        assert call_args[0][1] == 'info'

    @patch('src.gameplay.spell_attack.pyautogui')
    @patch('src.gameplay.spell_attack._get_creature_count', return_value=3)
    @patch('builtins.print')
    def test_fallback_to_print(self, mock_print, mock_count, mock_pyautogui):
        """Should fallback to print when gui_logger is not available."""
        spells = [create_spell('exori')]
        groups = [create_group('G1', spells, 'greaterThanOrEqual', 1)]
        context = create_mock_context(groups=groups, gui_logger=None)
        cooldowns = {}

        handle_spell_attack(context, cooldowns)

        mock_print.assert_called_once()
        assert 'exori' in mock_print.call_args[0][0]

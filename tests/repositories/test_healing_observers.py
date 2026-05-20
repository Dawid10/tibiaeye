"""
Tests for Healing Observers system.

Ensures:
1. Observers trigger at correct HP/MP thresholds
2. Cooldowns are respected
3. Mana checks work for spell observers
4. HealingSystem manages priority correctly
5. Enable/disable functionality works
"""
import pytest
from unittest.mock import Mock, patch, MagicMock
from dataclasses import dataclass

from src.core.types import PlayerStatus, GameContext
from src.healing.cooldown import CooldownManager
from src.healing.observers import (
    HealAction,
    HealingObserver,
    HealSpellObserver,
    StrongHealObserver,
    HealthPotionObserver,
    ManaPotionObserver,
    EmergencyHealObserver,
    HealingSystem
)


def create_context(hp: float = 100.0, mp: float = 100.0) -> GameContext:
    """Create a GameContext with specified HP/MP for testing."""
    return GameContext(
        player=PlayerStatus(
            hp_percent=hp,
            mp_percent=mp
        )
    )


class TestHealSpellObserver:
    """Tests for HealSpellObserver."""

    @patch('src.healing.observers.pyautogui')
    def test_triggers_when_hp_below_threshold(self, mock_pyautogui):
        """Test that observer triggers when HP is below threshold."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        context = create_context(hp=65.0, mp=100.0)

        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_does_not_trigger_when_hp_above_threshold(self, mock_pyautogui):
        """Test that observer does not trigger when HP is above threshold."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        context = create_context(hp=75.0, mp=100.0)

        assert observer.should_trigger(context) == False

    @patch('src.healing.observers.pyautogui')
    def test_does_not_trigger_when_low_mana(self, mock_pyautogui):
        """Test that observer does not trigger when mana is very low."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        # HP is low but mana is critically low (below 10%)
        context = create_context(hp=50.0, mp=5.0)

        assert observer.should_trigger(context) == False

    @patch('src.healing.observers.pyautogui')
    def test_does_not_trigger_during_cooldown(self, mock_pyautogui):
        """Test that observer respects cooldown."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1",
            cooldown=1.0
        )

        context = create_context(hp=50.0, mp=100.0)

        # First trigger should work
        assert observer.should_trigger(context) == True

        # Execute to start cooldown
        observer.execute(context)

        # Should not trigger during cooldown
        assert observer.should_trigger(context) == False

    @patch('src.healing.observers.pyautogui')
    def test_execute_presses_hotkey(self, mock_pyautogui):
        """Test that execute() presses the configured hotkey."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        context = create_context(hp=50.0, mp=100.0)
        result = observer.execute(context)

        mock_pyautogui.press.assert_called_with("f1")
        assert result.success == True
        assert "exura" in result.action_name

    @patch('src.healing.observers.pyautogui')
    def test_execute_without_hotkey_types_spell(self, mock_pyautogui):
        """Test that execute() types spell when no hotkey configured."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            spell="exura vita",
            threshold=70.0,
            hotkey=None
        )

        context = create_context(hp=50.0, mp=100.0)
        observer.execute(context)

        # Should press enter, type spell, press enter
        mock_pyautogui.press.assert_any_call('enter')
        mock_pyautogui.typewrite.assert_called_once()


class TestStrongHealObserver:
    """Tests for StrongHealObserver."""

    @patch('src.healing.observers.pyautogui')
    def test_triggers_at_critical_hp(self, mock_pyautogui):
        """Test that strong heal triggers at critical HP."""
        cooldowns = CooldownManager()
        observer = StrongHealObserver(
            cooldowns=cooldowns,
            threshold=40.0,
            hotkey="f5"
        )

        context = create_context(hp=35.0, mp=100.0)

        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_does_not_trigger_above_threshold(self, mock_pyautogui):
        """Test that strong heal does not trigger above threshold."""
        cooldowns = CooldownManager()
        observer = StrongHealObserver(
            cooldowns=cooldowns,
            threshold=40.0,
            hotkey="f5"
        )

        context = create_context(hp=45.0, mp=100.0)

        assert observer.should_trigger(context) == False

    @patch('src.healing.observers.pyautogui')
    def test_does_not_trigger_low_mana(self, mock_pyautogui):
        """Test that strong heal respects mana check."""
        cooldowns = CooldownManager()
        observer = StrongHealObserver(
            cooldowns=cooldowns,
            threshold=40.0,
            hotkey="f5"
        )

        context = create_context(hp=30.0, mp=5.0)

        assert observer.should_trigger(context) == False


class TestHealthPotionObserver:
    """Tests for HealthPotionObserver."""

    @patch('src.healing.observers.pyautogui')
    def test_triggers_at_threshold(self, mock_pyautogui):
        """Test health potion triggers at threshold."""
        cooldowns = CooldownManager()
        observer = HealthPotionObserver(
            cooldowns=cooldowns,
            threshold=30.0,
            hotkey="f4"
        )

        context = create_context(hp=25.0, mp=50.0)

        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_does_not_check_mana(self, mock_pyautogui):
        """Test health potion does not require mana."""
        cooldowns = CooldownManager()
        observer = HealthPotionObserver(
            cooldowns=cooldowns,
            threshold=30.0,
            hotkey="f4"
        )

        # HP low, mana also low - should still trigger
        context = create_context(hp=25.0, mp=0.0)

        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_execute_returns_failure_without_hotkey(self, mock_pyautogui):
        """Test that execute fails gracefully without hotkey."""
        cooldowns = CooldownManager()
        observer = HealthPotionObserver(
            cooldowns=cooldowns,
            threshold=30.0,
            hotkey=None  # No hotkey!
        )

        context = create_context(hp=25.0)
        result = observer.execute(context)

        assert result.success == False


class TestManaPotionObserver:
    """Tests for ManaPotionObserver."""

    @patch('src.healing.observers.pyautogui')
    def test_triggers_when_mp_low(self, mock_pyautogui):
        """Test mana potion triggers when MP is low."""
        cooldowns = CooldownManager()
        observer = ManaPotionObserver(
            cooldowns=cooldowns,
            threshold=50.0,
            hotkey="f2"
        )

        context = create_context(hp=100.0, mp=40.0)

        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_does_not_trigger_above_threshold(self, mock_pyautogui):
        """Test mana potion does not trigger above threshold."""
        cooldowns = CooldownManager()
        observer = ManaPotionObserver(
            cooldowns=cooldowns,
            threshold=50.0,
            hotkey="f2"
        )

        context = create_context(hp=100.0, mp=60.0)

        assert observer.should_trigger(context) == False


class TestEmergencyHealObserver:
    """Tests for EmergencyHealObserver."""

    @patch('src.healing.observers.pyautogui')
    def test_triggers_at_emergency_level(self, mock_pyautogui):
        """Test emergency heal triggers at very low HP."""
        cooldowns = CooldownManager()
        observer = EmergencyHealObserver(
            cooldowns=cooldowns,
            threshold=20.0,
            hotkey="f6"
        )

        context = create_context(hp=15.0, mp=50.0)

        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_shorter_default_cooldown(self, mock_pyautogui):
        """Test emergency heal has shorter cooldown by default."""
        cooldowns = CooldownManager()
        observer = EmergencyHealObserver(
            cooldowns=cooldowns,
            threshold=20.0,
            hotkey="f6"
            # default cooldown is 0.5
        )

        assert observer._cooldown == 0.5


class TestHealingObserverBase:
    """Tests for HealingObserver base class behavior."""

    @patch('src.healing.observers.pyautogui')
    def test_observe_returns_none_when_disabled(self, mock_pyautogui):
        """Test that observe() returns None when observer is disabled."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        # Disable the observer
        observer.enabled = False

        context = create_context(hp=50.0, mp=100.0)  # Would trigger if enabled

        result = observer.observe(context)
        assert result is None

    @patch('src.healing.observers.pyautogui')
    def test_observe_increments_action_count(self, mock_pyautogui):
        """Test that successful actions increment action_count."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1",
            cooldown=0.0  # No cooldown for rapid testing
        )

        context = create_context(hp=50.0, mp=100.0)

        assert observer.action_count == 0

        observer.observe(context)
        assert observer.action_count == 1

        observer.observe(context)
        assert observer.action_count == 2

    @patch('src.healing.observers.pyautogui')
    def test_enabled_property(self, mock_pyautogui):
        """Test enable/disable functionality."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        assert observer.enabled == True

        observer.enabled = False
        assert observer.enabled == False

        observer.enabled = True
        assert observer.enabled == True


class TestHealingSystem:
    """Tests for HealingSystem manager."""

    @patch('src.healing.observers.pyautogui')
    def test_add_observer(self, mock_pyautogui):
        """Test adding observers to the system."""
        system = HealingSystem()

        observer1 = HealSpellObserver(system.cooldowns, threshold=70.0)
        observer2 = ManaPotionObserver(system.cooldowns, threshold=50.0)

        system.add_observer(observer1)
        system.add_observer(observer2)

        assert system.observer_count == 2

    @patch('src.healing.observers.pyautogui')
    def test_add_observer_chaining(self, mock_pyautogui):
        """Test that add_observer supports method chaining."""
        system = HealingSystem()

        result = system.add_observer(
            HealSpellObserver(system.cooldowns, threshold=70.0)
        ).add_observer(
            ManaPotionObserver(system.cooldowns, threshold=50.0)
        )

        assert result is system
        assert system.observer_count == 2

    @patch('src.healing.observers.pyautogui')
    def test_tick_processes_observers(self, mock_pyautogui):
        """Test that tick() processes all observers."""
        system = HealingSystem()

        # Add heal spell observer (triggers at 70% HP)
        system.add_observer(HealSpellObserver(
            system.cooldowns,
            threshold=70.0,
            hotkey="f1"
        ))

        # Context with low HP
        context = create_context(hp=60.0, mp=100.0)

        actions = system.tick(context)

        assert len(actions) == 1
        assert actions[0].success == True

    @patch('src.healing.observers.pyautogui')
    def test_tick_returns_empty_when_no_triggers(self, mock_pyautogui):
        """Test that tick() returns empty list when nothing triggers."""
        system = HealingSystem()

        system.add_observer(HealSpellObserver(
            system.cooldowns,
            threshold=70.0,
            hotkey="f1"
        ))

        # Context with full HP
        context = create_context(hp=100.0, mp=100.0)

        actions = system.tick(context)

        assert len(actions) == 0

    @patch('src.healing.observers.pyautogui')
    def test_enable_all(self, mock_pyautogui):
        """Test enable_all() enables all observers."""
        system = HealingSystem()

        observer1 = HealSpellObserver(system.cooldowns, threshold=70.0)
        observer2 = ManaPotionObserver(system.cooldowns, threshold=50.0)

        observer1.enabled = False
        observer2.enabled = False

        system.add_observer(observer1)
        system.add_observer(observer2)

        system.enable_all()

        assert observer1.enabled == True
        assert observer2.enabled == True

    @patch('src.healing.observers.pyautogui')
    def test_disable_all(self, mock_pyautogui):
        """Test disable_all() disables all observers."""
        system = HealingSystem()

        observer1 = HealSpellObserver(system.cooldowns, threshold=70.0)
        observer2 = ManaPotionObserver(system.cooldowns, threshold=50.0)

        system.add_observer(observer1)
        system.add_observer(observer2)

        system.disable_all()

        assert observer1.enabled == False
        assert observer2.enabled == False

    @patch('src.healing.observers.pyautogui')
    def test_get_observer_by_name(self, mock_pyautogui):
        """Test get_observer() finds observer by name."""
        system = HealingSystem()

        heal_observer = HealSpellObserver(system.cooldowns, threshold=70.0)
        mana_observer = ManaPotionObserver(system.cooldowns, threshold=50.0)

        system.add_observer(heal_observer)
        system.add_observer(mana_observer)

        found = system.get_observer("HealSpell")
        assert found is heal_observer

        found = system.get_observer("ManaPotion")
        assert found is mana_observer

    @patch('src.healing.observers.pyautogui')
    def test_get_observer_not_found(self, mock_pyautogui):
        """Test get_observer() returns None when not found."""
        system = HealingSystem()

        found = system.get_observer("NonExistent")
        assert found is None

    @patch('src.healing.observers.pyautogui')
    def test_total_actions_tracking(self, mock_pyautogui):
        """Test that total_actions tracks all successful actions."""
        system = HealingSystem()

        system.add_observer(HealSpellObserver(
            system.cooldowns,
            threshold=70.0,
            hotkey="f1",
            cooldown=0.0
        ))

        context = create_context(hp=60.0, mp=100.0)

        assert system.total_actions == 0

        system.tick(context)
        assert system.total_actions == 1

        system.tick(context)
        assert system.total_actions == 2

    @patch('src.healing.observers.pyautogui')
    def test_cooldowns_property(self, mock_pyautogui):
        """Test that cooldowns property returns the manager."""
        system = HealingSystem()

        assert system.cooldowns is not None
        assert isinstance(system.cooldowns, CooldownManager)


class TestHealAction:
    """Tests for HealAction dataclass."""

    def test_heal_action_creation(self):
        """Test HealAction creation."""
        action = HealAction(
            action_name="Test Heal",
            success=True,
            hp_before=50.0,
            mp_before=75.0
        )

        assert action.action_name == "Test Heal"
        assert action.success == True
        assert action.hp_before == 50.0
        assert action.mp_before == 75.0

    def test_heal_action_defaults(self):
        """Test HealAction default values."""
        action = HealAction(
            action_name="Test",
            success=False
        )

        assert action.hp_before == 0.0
        assert action.mp_before == 0.0


class TestObserverPriority:
    """Tests for observer priority ordering."""

    @patch('src.healing.observers.pyautogui')
    def test_multiple_observers_can_trigger(self, mock_pyautogui):
        """Test that multiple observers can trigger in same tick."""
        system = HealingSystem()

        # Emergency heal at 20%
        system.add_observer(EmergencyHealObserver(
            system.cooldowns,
            threshold=20.0,
            hotkey="f6",
            cooldown=0.0
        ))

        # Health potion at 30%
        system.add_observer(HealthPotionObserver(
            system.cooldowns,
            threshold=30.0,
            hotkey="f4",
            cooldown=0.0
        ))

        # HP at 15% should trigger both
        context = create_context(hp=15.0, mp=100.0)

        actions = system.tick(context)

        # Both should trigger
        assert len(actions) == 2

    @patch('src.healing.observers.pyautogui')
    def test_observers_processed_in_order(self, mock_pyautogui):
        """Test that observers are processed in add order."""
        system = HealingSystem()
        call_order = []

        class TrackedObserver(HealSpellObserver):
            def execute(self, context):
                call_order.append(self.name)
                return super().execute(context)

        obs1 = TrackedObserver(system.cooldowns, threshold=70.0, hotkey="f1")
        obs1._name = "First"
        obs2 = TrackedObserver(system.cooldowns, threshold=70.0, hotkey="f2")
        obs2._name = "Second"

        system.add_observer(obs1)
        system.add_observer(obs2)

        context = create_context(hp=50.0, mp=100.0)
        system.tick(context)

        # Should be processed in order added
        assert call_order[0] == "HealSpell"  # Both have same name


class TestEdgeCases:
    """Edge case tests for healing system."""

    @patch('src.healing.observers.pyautogui')
    def test_exact_threshold(self, mock_pyautogui):
        """Test behavior when HP equals exactly the threshold."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        # HP exactly at threshold (should NOT trigger - needs to be below)
        context = create_context(hp=70.0, mp=100.0)
        assert observer.should_trigger(context) == False

        # HP just below threshold
        context = create_context(hp=69.9, mp=100.0)
        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_mana_threshold_boundary(self, mock_pyautogui):
        """Test mana threshold at exactly 10%."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        # MP at exactly 10% (should NOT trigger - needs to be 10+)
        context = create_context(hp=50.0, mp=10.0)
        assert observer.should_trigger(context) == True  # 10% is acceptable

        # MP below 10%
        context = create_context(hp=50.0, mp=9.9)
        assert observer.should_trigger(context) == False

    @patch('src.healing.observers.pyautogui')
    def test_zero_hp(self, mock_pyautogui):
        """Test with 0% HP (dead state)."""
        cooldowns = CooldownManager()
        observer = EmergencyHealObserver(
            cooldowns=cooldowns,
            threshold=20.0,
            hotkey="f6"
        )

        context = create_context(hp=0.0, mp=100.0)
        assert observer.should_trigger(context) == True

    @patch('src.healing.observers.pyautogui')
    def test_zero_mp(self, mock_pyautogui):
        """Test spell observer with 0% MP."""
        cooldowns = CooldownManager()
        observer = HealSpellObserver(
            cooldowns=cooldowns,
            threshold=70.0,
            hotkey="f1"
        )

        context = create_context(hp=50.0, mp=0.0)
        # Should not trigger due to low mana
        assert observer.should_trigger(context) == False

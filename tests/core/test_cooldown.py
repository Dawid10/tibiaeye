"""
Tests for CooldownManager.

Ensures:
1. Actions are properly tracked
2. Cooldown timing is accurate
3. Reset functionality works
4. Use count is properly maintained
"""
import time
import pytest

from src.healing.cooldown import CooldownManager


class TestCooldownManager:
    """Tests for CooldownManager class."""

    def test_can_use_first_time(self):
        """Test that action can be used if never used before."""
        manager = CooldownManager()

        assert manager.can_use("heal", cooldown=1.0) == True
        assert manager.can_use("attack", cooldown=0.5) == True

    def test_cannot_use_during_cooldown(self):
        """Test that action cannot be used during cooldown period."""
        manager = CooldownManager()

        # Use the action
        manager.use("heal")

        # Should not be able to use immediately with 1 second cooldown
        assert manager.can_use("heal", cooldown=1.0) == False

    def test_can_use_after_cooldown(self):
        """Test that action can be used after cooldown expires."""
        manager = CooldownManager()

        # Use the action
        manager.use("heal")

        # Wait slightly longer than cooldown
        time.sleep(0.15)

        # Should be able to use again with 0.1 second cooldown
        assert manager.can_use("heal", cooldown=0.1) == True

    def test_different_actions_independent(self):
        """Test that different actions have independent cooldowns."""
        manager = CooldownManager()

        # Use heal
        manager.use("heal")

        # Attack should still be available
        assert manager.can_use("attack", cooldown=1.0) == True
        # Heal should not be
        assert manager.can_use("heal", cooldown=1.0) == False

    def test_use_increments_count(self):
        """Test that use() increments action count."""
        manager = CooldownManager()

        assert manager.get_use_count("heal") == 0

        manager.use("heal")
        assert manager.get_use_count("heal") == 1

        manager.use("heal")
        assert manager.get_use_count("heal") == 2

    def test_get_remaining_not_used(self):
        """Test get_remaining returns 0 for unused actions."""
        manager = CooldownManager()

        assert manager.get_remaining("heal", cooldown=1.0) == 0.0

    def test_get_remaining_during_cooldown(self):
        """Test get_remaining returns positive value during cooldown."""
        manager = CooldownManager()

        manager.use("heal")

        # Remaining should be close to 1.0 for 1 second cooldown
        remaining = manager.get_remaining("heal", cooldown=1.0)
        assert remaining > 0.9
        assert remaining <= 1.0

    def test_get_remaining_after_cooldown(self):
        """Test get_remaining returns 0 after cooldown expires."""
        manager = CooldownManager()

        manager.use("heal")
        time.sleep(0.15)

        remaining = manager.get_remaining("heal", cooldown=0.1)
        assert remaining == 0.0

    def test_reset_specific_action(self):
        """Test resetting a specific action cooldown."""
        manager = CooldownManager()

        manager.use("heal")
        manager.use("attack")

        # Reset only heal
        manager.reset("heal")

        # Heal should be available now
        assert manager.can_use("heal", cooldown=1.0) == True
        # Attack should still be on cooldown
        assert manager.can_use("attack", cooldown=1.0) == False

    def test_reset_all_actions(self):
        """Test resetting all action cooldowns."""
        manager = CooldownManager()

        manager.use("heal")
        manager.use("attack")
        manager.use("potion")

        # Reset all
        manager.reset()

        # All should be available
        assert manager.can_use("heal", cooldown=1.0) == True
        assert manager.can_use("attack", cooldown=1.0) == True
        assert manager.can_use("potion", cooldown=1.0) == True

    def test_get_last_use_time_not_used(self):
        """Test get_last_use_time returns None for unused action."""
        manager = CooldownManager()

        assert manager.get_last_use_time("heal") is None

    def test_get_last_use_time_after_use(self):
        """Test get_last_use_time returns timestamp after use."""
        manager = CooldownManager()

        before = time.time()
        manager.use("heal")
        after = time.time()

        last_use = manager.get_last_use_time("heal")

        assert last_use is not None
        assert before <= last_use <= after

    def test_actions_property(self):
        """Test actions property returns tracked action names."""
        manager = CooldownManager()

        assert manager.actions == []

        manager.use("heal")
        manager.use("attack")

        actions = manager.actions
        assert "heal" in actions
        assert "attack" in actions
        assert len(actions) == 2

    def test_zero_cooldown(self):
        """Test that zero cooldown allows immediate reuse."""
        manager = CooldownManager()

        manager.use("instant")

        # With 0 cooldown, should be usable immediately
        assert manager.can_use("instant", cooldown=0.0) == True

    def test_very_short_cooldown(self):
        """Test behavior with very short cooldown."""
        manager = CooldownManager()

        manager.use("quick")

        # Immediately should not be able to use
        assert manager.can_use("quick", cooldown=0.001) == False

        # After tiny wait
        time.sleep(0.005)
        assert manager.can_use("quick", cooldown=0.001) == True

    def test_multiple_uses_updates_timestamp(self):
        """Test that multiple uses update the timestamp."""
        manager = CooldownManager()

        manager.use("heal")
        first_use = manager.get_last_use_time("heal")

        time.sleep(0.05)

        manager.use("heal")
        second_use = manager.get_last_use_time("heal")

        assert second_use > first_use

    def test_use_count_independent_of_cooldown(self):
        """Test that use count tracks all uses regardless of cooldown."""
        manager = CooldownManager()

        # Rapid uses (ignoring cooldown)
        for _ in range(5):
            manager.use("spam")

        assert manager.get_use_count("spam") == 5

    def test_get_use_count_untracked_action(self):
        """Test get_use_count returns 0 for untracked action."""
        manager = CooldownManager()

        assert manager.get_use_count("never_used") == 0


class TestCooldownEdgeCases:
    """Edge case tests for CooldownManager."""

    def test_reset_nonexistent_action(self):
        """Test resetting an action that was never used."""
        manager = CooldownManager()

        # Should not raise an error
        manager.reset("nonexistent")

        # Should still be able to use
        assert manager.can_use("nonexistent", cooldown=1.0) == True

    def test_negative_cooldown(self):
        """Test behavior with negative cooldown value."""
        manager = CooldownManager()

        manager.use("action")

        # Negative cooldown should always allow use
        assert manager.can_use("action", cooldown=-1.0) == True

    def test_large_cooldown(self):
        """Test behavior with very large cooldown value."""
        manager = CooldownManager()

        manager.use("action")

        # Should not be able to use with huge cooldown
        assert manager.can_use("action", cooldown=999999.0) == False

        # Remaining should be large
        remaining = manager.get_remaining("action", cooldown=999999.0)
        assert remaining > 999998.0

    def test_special_characters_in_action_name(self):
        """Test that action names with special characters work."""
        manager = CooldownManager()

        manager.use("heal-spell-1")
        manager.use("attack_combo_2")
        manager.use("potion.ultra")

        assert manager.get_use_count("heal-spell-1") == 1
        assert manager.get_use_count("attack_combo_2") == 1
        assert manager.get_use_count("potion.ultra") == 1

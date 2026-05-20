"""Healing Observers - reactive healing system."""
from abc import ABC, abstractmethod
from dataclasses import dataclass
from typing import List, Optional

import pyautogui

from ..core import GameContext, HealingConfig
from .cooldown import CooldownManager


@dataclass
class HealAction:
    """Result of a healing action."""
    action_name: str
    success: bool
    hp_before: float = 0.0
    mp_before: float = 0.0


def cast_spell_or_hotkey(hotkey: Optional[str], spell: str) -> None:
    """Cast spell using hotkey or by typing."""
    if hotkey:
        pyautogui.press(hotkey)
        return

    pyautogui.press('enter')
    pyautogui.typewrite(spell, interval=0.02)
    pyautogui.press('enter')


class HealingObserver(ABC):
    """Base class for healing observers."""

    def __init__(self, name: str, cooldowns: CooldownManager):
        self.name = name
        self._cooldowns = cooldowns
        self._enabled = True
        self._action_count = 0

    @abstractmethod
    def should_trigger(self, context: GameContext) -> bool:
        """Check if healing should be triggered."""
        pass

    @abstractmethod
    def execute(self, context: GameContext) -> HealAction:
        """Execute the healing action."""
        pass

    def observe(self, context: GameContext) -> Optional[HealAction]:
        """Observe and heal if needed."""
        if not self._enabled:
            return None

        if not self.should_trigger(context):
            return None

        result = self.execute(context)
        if result.success:
            self._action_count += 1
        return result

    @property
    def enabled(self) -> bool:
        """Check if observer is enabled."""
        return self._enabled

    @enabled.setter
    def enabled(self, value: bool) -> None:
        """Enable or disable observer."""
        self._enabled = value

    @property
    def action_count(self) -> int:
        """Get number of actions performed."""
        return self._action_count


class SpellHealingObserver(HealingObserver):
    """Observer that casts healing spells when HP is low."""

    def __init__(self, cooldowns: CooldownManager,
                 name: str = "HealSpell",
                 spell: str = "exura",
                 threshold: float = 70.0,
                 hotkey: Optional[str] = "f1",
                 cooldown: float = 1.0,
                 mana_cost: int = 20,
                 min_mana_percent: float = 10.0):
        super().__init__(name, cooldowns)
        self._spell = spell
        self._threshold = threshold
        self._hotkey = hotkey
        self._cooldown = cooldown
        self._mana_cost = mana_cost
        self._min_mana_percent = min_mana_percent

    def should_trigger(self, context: GameContext) -> bool:
        """Check if HP is below threshold and cooldown ready."""
        if context.player.hp_percent >= self._threshold:
            return False

        if context.player.mp_percent < self._min_mana_percent:
            return False

        return self._cooldowns.can_use(self.name, self._cooldown)

    def execute(self, context: GameContext) -> HealAction:
        """Cast healing spell."""
        cast_spell_or_hotkey(self._hotkey, self._spell)
        self._cooldowns.use(self.name)

        return HealAction(
            action_name=f"Heal ({self._spell})",
            success=True,
            hp_before=context.player.hp_percent,
            mp_before=context.player.mp_percent
        )


class HealSpellObserver(SpellHealingObserver):
    """Observer that casts healing spells when HP is low."""

    def __init__(self, cooldowns: CooldownManager,
                 spell: str = "exura",
                 threshold: float = 70.0,
                 hotkey: Optional[str] = "f1",
                 cooldown: float = 1.0,
                 mana_cost: int = 20):
        super().__init__(
            cooldowns,
            name="HealSpell",
            spell=spell,
            threshold=threshold,
            hotkey=hotkey,
            cooldown=cooldown,
            mana_cost=mana_cost
        )


class StrongHealObserver(SpellHealingObserver):
    """Observer that casts strong healing when HP is critically low."""

    def __init__(self, cooldowns: CooldownManager,
                 spell: str = "exura gran",
                 threshold: float = 40.0,
                 hotkey: Optional[str] = "f5",
                 cooldown: float = 1.0,
                 mana_cost: int = 70):
        super().__init__(
            cooldowns,
            name="StrongHeal",
            spell=spell,
            threshold=threshold,
            hotkey=hotkey,
            cooldown=cooldown,
            mana_cost=mana_cost
        )

    def execute(self, context: GameContext) -> HealAction:
        """Cast strong healing spell."""
        cast_spell_or_hotkey(self._hotkey, self._spell)
        self._cooldowns.use(self.name)

        return HealAction(
            action_name=f"Strong Heal ({self._spell})",
            success=True,
            hp_before=context.player.hp_percent,
            mp_before=context.player.mp_percent
        )


class PotionObserver(HealingObserver):
    """Base observer for potion usage."""

    def __init__(self, cooldowns: CooldownManager,
                 name: str,
                 action_name: str,
                 threshold: float,
                 hotkey: str,
                 cooldown: float = 1.0,
                 check_hp: bool = True):
        super().__init__(name, cooldowns)
        self._action_name = action_name
        self._threshold = threshold
        self._hotkey = hotkey
        self._cooldown = cooldown
        self._check_hp = check_hp

    def should_trigger(self, context: GameContext) -> bool:
        """Check if stat is below threshold and cooldown ready."""
        stat_percent = context.player.hp_percent if self._check_hp else context.player.mp_percent

        if stat_percent >= self._threshold:
            return False

        return self._cooldowns.can_use(self.name, self._cooldown)

    def execute(self, context: GameContext) -> HealAction:
        """Use potion."""
        if not self._hotkey:
            return HealAction(action_name=self._action_name, success=False)

        pyautogui.press(self._hotkey)
        self._cooldowns.use(self.name)

        return HealAction(
            action_name=self._action_name,
            success=True,
            hp_before=context.player.hp_percent,
            mp_before=context.player.mp_percent
        )


class HealthPotionObserver(PotionObserver):
    """Observer that uses health potions in emergencies."""

    def __init__(self, cooldowns: CooldownManager,
                 threshold: float = 30.0,
                 hotkey: str = "f4",
                 cooldown: float = 1.0):
        super().__init__(
            cooldowns,
            name="HealthPotion",
            action_name="Health Potion",
            threshold=threshold,
            hotkey=hotkey,
            cooldown=cooldown,
            check_hp=True
        )


class ManaPotionObserver(PotionObserver):
    """Observer that uses mana potions when MP is low."""

    def __init__(self, cooldowns: CooldownManager,
                 threshold: float = 50.0,
                 hotkey: str = "f2",
                 cooldown: float = 1.0):
        super().__init__(
            cooldowns,
            name="ManaPotion",
            action_name="Mana Potion",
            threshold=threshold,
            hotkey=hotkey,
            cooldown=cooldown,
            check_hp=False
        )


class EmergencyHealObserver(PotionObserver):
    """Observer for emergency healing at critical HP levels."""

    def __init__(self, cooldowns: CooldownManager,
                 threshold: float = 20.0,
                 hotkey: str = "f6",
                 cooldown: float = 0.5):
        super().__init__(
            cooldowns,
            name="EmergencyHeal",
            action_name="EMERGENCY HEAL",
            threshold=threshold,
            hotkey=hotkey,
            cooldown=cooldown,
            check_hp=True
        )


class HealingSystem:
    """Manages multiple healing observers with priority."""

    def __init__(self):
        self._observers: List[HealingObserver] = []
        self._cooldowns = CooldownManager()
        self._actions_taken: List[HealAction] = []

    def add_observer(self, observer: HealingObserver) -> 'HealingSystem':
        """Add healing observer."""
        self._observers.append(observer)
        return self

    def setup_default_observers(self, config: HealingConfig) -> 'HealingSystem':
        """Setup default healing observers from config."""
        self._observers.clear()

        if config.emergency_hotkey:
            self.add_observer(EmergencyHealObserver(
                self._cooldowns,
                threshold=config.emergency_percent,
                hotkey=config.emergency_hotkey,
                cooldown=config.emergency_cooldown
            ))

        if config.health_pot_hotkey:
            self.add_observer(HealthPotionObserver(
                self._cooldowns,
                threshold=config.health_pot_percent,
                hotkey=config.health_pot_hotkey,
                cooldown=config.health_pot_cooldown
            ))

        if config.strong_heal_hotkey:
            self.add_observer(StrongHealObserver(
                self._cooldowns,
                spell=config.strong_heal_spell,
                threshold=config.strong_heal_percent,
                hotkey=config.strong_heal_hotkey,
                cooldown=config.strong_heal_cooldown
            ))

        if config.heal_spell_hotkey:
            self.add_observer(HealSpellObserver(
                self._cooldowns,
                spell=config.heal_spell,
                threshold=config.heal_spell_percent,
                hotkey=config.heal_spell_hotkey,
                cooldown=config.heal_spell_cooldown
            ))

        if config.mana_pot_hotkey:
            self.add_observer(ManaPotionObserver(
                self._cooldowns,
                threshold=config.mana_pot_percent,
                hotkey=config.mana_pot_hotkey,
                cooldown=config.mana_pot_cooldown
            ))

        return self

    def tick(self, context: GameContext) -> List[HealAction]:
        """Process all observers and apply healing."""
        actions = []

        for observer in self._observers:
            action = observer.observe(context)
            if action and action.success:
                actions.append(action)
                self._actions_taken.append(action)

        return actions

    def enable_all(self) -> None:
        """Enable all observers."""
        for observer in self._observers:
            observer.enabled = True

    def disable_all(self) -> None:
        """Disable all observers."""
        for observer in self._observers:
            observer.enabled = False

    def get_observer(self, name: str) -> Optional[HealingObserver]:
        """Get observer by name."""
        for observer in self._observers:
            if observer.name == name:
                return observer
        return None

    @property
    def cooldowns(self) -> CooldownManager:
        """Get the cooldown manager."""
        return self._cooldowns

    @property
    def total_actions(self) -> int:
        """Get total number of healing actions taken."""
        return len(self._actions_taken)

    @property
    def observer_count(self) -> int:
        """Get number of observers."""
        return len(self._observers)

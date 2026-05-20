"""
Healing module - automatic healing system.
"""
from .cooldown import CooldownManager

from .observers import (
    HealAction,
    HealingObserver,
    HealSpellObserver,
    StrongHealObserver,
    HealthPotionObserver,
    ManaPotionObserver,
    EmergencyHealObserver,
    HealingSystem
)

__all__ = [
    'CooldownManager',
    'HealAction',
    'HealingObserver',
    'HealSpellObserver',
    'StrongHealObserver',
    'HealthPotionObserver',
    'ManaPotionObserver',
    'EmergencyHealObserver',
    'HealingSystem',
]

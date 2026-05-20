"""
Wiki module - game knowledge database.
"""
from .spells import (
    SpellType,
    Vocation,
    Spell,
    HEALING_SPELLS,
    ATTACK_SPELLS,
    get_spell,
    get_healing_spells,
    get_attack_spells
)

from .potions import (
    PotionType,
    Potion,
    HEALTH_POTIONS,
    MANA_POTIONS,
    SPIRIT_POTIONS,
    get_potion,
    get_health_potions,
    get_mana_potions,
    get_best_health_potion,
    get_best_mana_potion
)

from .creatures import (
    CreatureClass,
    Element,
    Creature,
    CREATURES,
    get_creature,
    get_creatures_by_class,
    get_creatures_weak_to,
    get_creatures_by_exp_range
)

__all__ = [
    # Spells
    'SpellType',
    'Vocation',
    'Spell',
    'HEALING_SPELLS',
    'ATTACK_SPELLS',
    'get_spell',
    'get_healing_spells',
    'get_attack_spells',

    # Potions
    'PotionType',
    'Potion',
    'HEALTH_POTIONS',
    'MANA_POTIONS',
    'SPIRIT_POTIONS',
    'get_potion',
    'get_health_potions',
    'get_mana_potions',
    'get_best_health_potion',
    'get_best_mana_potion',

    # Creatures
    'CreatureClass',
    'Element',
    'Creature',
    'CREATURES',
    'get_creature',
    'get_creatures_by_class',
    'get_creatures_weak_to',
    'get_creatures_by_exp_range',
]

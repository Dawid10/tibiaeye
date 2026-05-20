"""
Spell database - information about Tibia spells.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, Optional, List


class SpellType(Enum):
    """Types of spells."""
    HEALING = auto()
    ATTACK = auto()
    SUPPORT = auto()
    SUMMON = auto()


class Vocation(Enum):
    """Character vocations."""
    KNIGHT = auto()
    PALADIN = auto()
    SORCERER = auto()
    DRUID = auto()
    ALL = auto()


@dataclass
class Spell:
    """Spell information."""
    name: str
    incantation: str
    mana_cost: int
    cooldown: float  # seconds
    spell_type: SpellType
    vocations: List[Vocation]
    level_required: int = 1
    soul_points: int = 0
    is_premium: bool = False
    description: str = ""

    @property
    def is_healing(self) -> bool:
        return self.spell_type == SpellType.HEALING

    @property
    def is_attack(self) -> bool:
        return self.spell_type == SpellType.ATTACK


# Healing Spells Database
HEALING_SPELLS: Dict[str, Spell] = {
    # Light Healing
    "exura": Spell(
        name="Light Healing",
        incantation="exura",
        mana_cost=20,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.DRUID, Vocation.SORCERER, Vocation.PALADIN, Vocation.KNIGHT],
        level_required=9,
        description="Heals a small amount of health."
    ),

    # Intense Healing
    "exura gran": Spell(
        name="Intense Healing",
        incantation="exura gran",
        mana_cost=70,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.DRUID, Vocation.SORCERER, Vocation.PALADIN],
        level_required=11,
        description="Heals a medium amount of health."
    ),

    # Ultimate Healing
    "exura vita": Spell(
        name="Ultimate Healing",
        incantation="exura vita",
        mana_cost=160,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.DRUID, Vocation.SORCERER],
        level_required=30,
        description="Heals a large amount of health."
    ),

    # Wound Cleansing (Knight)
    "exura ico": Spell(
        name="Wound Cleansing",
        incantation="exura ico",
        mana_cost=40,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.KNIGHT],
        level_required=10,
        description="Knight healing spell."
    ),

    # Intense Wound Cleansing (Knight)
    "exura gran ico": Spell(
        name="Intense Wound Cleansing",
        incantation="exura gran ico",
        mana_cost=200,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.KNIGHT],
        level_required=300,
        description="Strong knight healing spell."
    ),

    # Divine Healing (Paladin)
    "exura san": Spell(
        name="Divine Healing",
        incantation="exura san",
        mana_cost=160,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.PALADIN],
        level_required=35,
        description="Paladin healing spell."
    ),

    # Recovery (Utura)
    "utura": Spell(
        name="Recovery",
        incantation="utura",
        mana_cost=75,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.KNIGHT, Vocation.PALADIN],
        level_required=25,
        description="Regeneration spell that heals over time."
    ),

    # Intense Recovery
    "utura gran": Spell(
        name="Intense Recovery",
        incantation="utura gran",
        mana_cost=165,
        cooldown=1.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.KNIGHT, Vocation.PALADIN],
        level_required=50,
        description="Strong regeneration spell."
    ),

    # Mass Healing
    "exura gran mas res": Spell(
        name="Mass Healing",
        incantation="exura gran mas res",
        mana_cost=150,
        cooldown=2.0,
        spell_type=SpellType.HEALING,
        vocations=[Vocation.DRUID],
        level_required=36,
        description="Heals all party members in range."
    ),
}

# Attack Spells Database
ATTACK_SPELLS: Dict[str, Spell] = {
    # Exori
    "exori": Spell(
        name="Brutal Strike",
        incantation="exori",
        mana_cost=30,
        cooldown=2.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.KNIGHT],
        level_required=16,
        description="Physical attack spell."
    ),

    # Exori Gran
    "exori gran": Spell(
        name="Fierce Berserk",
        incantation="exori gran",
        mana_cost=340,
        cooldown=6.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.KNIGHT],
        level_required=90,
        description="Strong area physical attack."
    ),

    # Exori Mas
    "exori mas": Spell(
        name="Groundshaker",
        incantation="exori mas",
        mana_cost=160,
        cooldown=8.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.KNIGHT],
        level_required=33,
        description="Area physical attack."
    ),

    # Exori Hur
    "exori hur": Spell(
        name="Front Sweep",
        incantation="exori hur",
        mana_cost=60,
        cooldown=6.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.KNIGHT],
        level_required=110,
        description="Frontal sweep attack."
    ),

    # Exori Min
    "exori min": Spell(
        name="Whirlwind Throw",
        incantation="exori min",
        mana_cost=25,
        cooldown=6.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.KNIGHT],
        level_required=28,
        description="Ranged physical attack."
    ),

    # Exevo Gran Mas Flam
    "exevo gran mas flam": Spell(
        name="Rage of the Skies",
        incantation="exevo gran mas flam",
        mana_cost=650,
        cooldown=40.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.SORCERER],
        level_required=55,
        description="Massive fire attack."
    ),

    # Exevo Vis Hur
    "exevo vis hur": Spell(
        name="Lightning Beam",
        incantation="exevo vis hur",
        mana_cost=110,
        cooldown=4.0,
        spell_type=SpellType.ATTACK,
        vocations=[Vocation.SORCERER],
        level_required=23,
        description="Energy beam attack."
    ),
}


def get_spell(incantation: str) -> Optional[Spell]:
    """
    Get spell by incantation.

    Args:
        incantation: Spell incantation (e.g., "exura").

    Returns:
        Spell object or None.
    """
    incantation = incantation.lower().strip()

    if incantation in HEALING_SPELLS:
        return HEALING_SPELLS[incantation]
    if incantation in ATTACK_SPELLS:
        return ATTACK_SPELLS[incantation]

    return None


def get_healing_spells(vocation: Vocation = None) -> List[Spell]:
    """
    Get all healing spells, optionally filtered by vocation.

    Args:
        vocation: Filter by vocation.

    Returns:
        List of healing spells.
    """
    spells = list(HEALING_SPELLS.values())

    if vocation:
        spells = [s for s in spells if vocation in s.vocations or Vocation.ALL in s.vocations]

    return spells


# Spell area coordinates (slot positions relative to 15x11 grid, player at 7,5)
# Used to determine which creatures are in range of area spells
SPELL_AREAS = {
    'exori': [
        (6, 4), (7, 4), (8, 4),
        (6, 5),         (8, 5),
        (6, 6), (7, 6), (8, 6),
    ],
    'exori gran': [
        (6, 4), (7, 4), (8, 4),
        (6, 5),         (8, 5),
        (6, 6), (7, 6), (8, 6),
    ],
    'exori mas': [
                (5, 2), (6, 2), (7, 2), (8, 2), (9, 2),
        (4, 3), (5, 3), (6, 3), (7, 3), (8, 3), (9, 3), (10, 3),
        (3, 4), (4, 4), (5, 4), (6, 4), (7, 4), (8, 4), (9, 4), (10, 4), (11, 4),
        (3, 5), (4, 5), (5, 5), (6, 5),         (8, 5), (9, 5), (10, 5), (11, 5),
        (3, 6), (4, 6), (5, 6), (6, 6), (7, 6), (8, 6), (9, 6), (10, 6), (11, 6),
        (4, 7), (5, 7), (6, 7), (7, 7), (8, 7), (9, 7), (10, 7),
                (5, 8), (6, 8), (7, 8), (8, 8), (9, 8),
    ],
    'exori hur': [
        (6, 3), (7, 3), (8, 3),
        (6, 4), (7, 4), (8, 4),
    ],
    'exori min': [
        (7, 5),
    ],
}


def get_attack_spells(vocation: Vocation = None) -> List[Spell]:
    """
    Get all attack spells, optionally filtered by vocation.

    Args:
        vocation: Filter by vocation.

    Returns:
        List of attack spells.
    """
    spells = list(ATTACK_SPELLS.values())

    if vocation:
        spells = [s for s in spells if vocation in s.vocations or Vocation.ALL in s.vocations]

    return spells

"""
Creature database - information about Tibia creatures.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict, List, Optional


class CreatureClass(Enum):
    """Classification of creatures."""
    AMPHIBIC = auto()
    AQUATIC = auto()
    BIO_ELEMENTAL = auto()
    BIRD = auto()
    CONSTRUCT = auto()
    DEMON = auto()
    DRAGON = auto()
    ELEMENTAL = auto()
    EXTRA_DIMENSIONAL = auto()
    FEY = auto()
    GIANT = auto()
    HUMAN = auto()
    HUMANOID = auto()
    LYCANTHROPE = auto()
    MAGICAL = auto()
    MAMMAL = auto()
    PLANT = auto()
    REPTILE = auto()
    SLIME = auto()
    UNDEAD = auto()
    VERMIN = auto()


class Element(Enum):
    """Damage/resistance elements."""
    PHYSICAL = auto()
    HOLY = auto()
    DEATH = auto()
    FIRE = auto()
    ENERGY = auto()
    ICE = auto()
    EARTH = auto()


@dataclass
class Creature:
    """Creature information."""
    name: str
    hp: int
    exp: int
    creature_class: CreatureClass
    armor: int = 0
    speed: int = 100
    summon_cost: int = 0
    convince_cost: int = 0
    is_boss: bool = False
    is_pushable: bool = True
    pushes_objects: bool = False
    sees_invisible: bool = False
    paralyzable: bool = True

    # Resistances/Weaknesses (percentage: 100 = normal, >100 = weak, <100 = resistant, 0 = immune)
    physical_modifier: int = 100
    holy_modifier: int = 100
    death_modifier: int = 100
    fire_modifier: int = 100
    energy_modifier: int = 100
    ice_modifier: int = 100
    earth_modifier: int = 100

    # Loot categories
    common_loot: List[str] = field(default_factory=list)
    uncommon_loot: List[str] = field(default_factory=list)
    rare_loot: List[str] = field(default_factory=list)

    description: str = ""

    def is_weak_to(self, element: Element) -> bool:
        """Check if creature is weak to an element."""
        modifier = self._get_modifier(element)
        return modifier > 100

    def is_resistant_to(self, element: Element) -> bool:
        """Check if creature is resistant to an element."""
        modifier = self._get_modifier(element)
        return modifier < 100

    def is_immune_to(self, element: Element) -> bool:
        """Check if creature is immune to an element."""
        modifier = self._get_modifier(element)
        return modifier == 0

    def _get_modifier(self, element: Element) -> int:
        """Get damage modifier for element."""
        modifiers = {
            Element.PHYSICAL: self.physical_modifier,
            Element.HOLY: self.holy_modifier,
            Element.DEATH: self.death_modifier,
            Element.FIRE: self.fire_modifier,
            Element.ENERGY: self.energy_modifier,
            Element.ICE: self.ice_modifier,
            Element.EARTH: self.earth_modifier,
        }
        return modifiers.get(element, 100)


# Common Creatures Database
CREATURES: Dict[str, Creature] = {
    # Rotworms
    "rotworm": Creature(
        name="Rotworm",
        hp=65,
        exp=40,
        creature_class=CreatureClass.VERMIN,
        armor=4,
        speed=60,
        physical_modifier=100,
        fire_modifier=110,  # Weak to fire
        earth_modifier=0,   # Immune to earth
        common_loot=["Gold Coin", "Meat", "Ham"],
        uncommon_loot=["Sword", "Mace"],
        rare_loot=["Copper Shield", "Legion Helmet"],
        description="A common underground vermin."
    ),

    "carrion_worm": Creature(
        name="Carrion Worm",
        hp=145,
        exp=70,
        creature_class=CreatureClass.VERMIN,
        armor=11,
        speed=60,
        physical_modifier=100,
        fire_modifier=110,
        earth_modifier=0,
        common_loot=["Gold Coin", "Meat"],
        uncommon_loot=["Bag", "Sword"],
        description="A larger, more dangerous worm."
    ),

    # Swamp creatures
    "swampling": Creature(
        name="Swampling",
        hp=90,
        exp=35,
        creature_class=CreatureClass.PLANT,
        armor=7,
        speed=60,
        fire_modifier=110,  # Weak to fire
        ice_modifier=80,    # Resistant to ice
        earth_modifier=0,   # Immune to earth
        common_loot=["Gold Coin", "Swampling Moss"],
        description="A small swamp creature."
    ),

    # Basic monsters
    "rat": Creature(
        name="Rat",
        hp=20,
        exp=5,
        creature_class=CreatureClass.MAMMAL,
        armor=1,
        speed=68,
        common_loot=["Gold Coin", "Cheese"],
        description="A common vermin found everywhere."
    ),

    "cave_rat": Creature(
        name="Cave Rat",
        hp=30,
        exp=10,
        creature_class=CreatureClass.MAMMAL,
        armor=2,
        speed=70,
        common_loot=["Gold Coin", "Cheese", "Worm"],
        description="A rat adapted to cave life."
    ),

    "troll": Creature(
        name="Troll",
        hp=50,
        exp=20,
        creature_class=CreatureClass.HUMANOID,
        armor=7,
        speed=60,
        fire_modifier=110,
        earth_modifier=80,
        common_loot=["Gold Coin", "Meat", "Leather Legs"],
        uncommon_loot=["Hand Axe", "Spear"],
        rare_loot=["Brass Armor", "Brass Helmet"],
        description="A brutish humanoid creature."
    ),

    "goblin": Creature(
        name="Goblin",
        hp=50,
        exp=25,
        creature_class=CreatureClass.HUMANOID,
        armor=4,
        speed=70,
        earth_modifier=80,
        common_loot=["Gold Coin", "Short Sword"],
        uncommon_loot=["Bone", "Fish"],
        description="A small and sneaky humanoid."
    ),

    "orc": Creature(
        name="Orc",
        hp=70,
        exp=25,
        creature_class=CreatureClass.HUMANOID,
        armor=6,
        speed=70,
        holy_modifier=110,
        common_loot=["Gold Coin", "Meat", "Sabre"],
        uncommon_loot=["Studded Armor", "Orc Leather"],
        description="A common orc warrior."
    ),

    "orc_spearman": Creature(
        name="Orc Spearman",
        hp=105,
        exp=38,
        creature_class=CreatureClass.HUMANOID,
        armor=8,
        speed=70,
        holy_modifier=110,
        common_loot=["Gold Coin", "Meat", "Spear"],
        uncommon_loot=["Throwing Spear", "Orc Tooth"],
        description="An orc specialized in ranged combat."
    ),

    # Skeletons
    "skeleton": Creature(
        name="Skeleton",
        hp=50,
        exp=35,
        creature_class=CreatureClass.UNDEAD,
        armor=8,
        speed=70,
        holy_modifier=125,  # Very weak to holy
        death_modifier=0,   # Immune to death
        ice_modifier=100,
        earth_modifier=100,
        common_loot=["Gold Coin", "Bone", "Torch"],
        uncommon_loot=["Mace", "Viking Helmet", "Brass Shield"],
        description="An animated skeleton warrior."
    ),

    "ghoul": Creature(
        name="Ghoul",
        hp=100,
        exp=85,
        creature_class=CreatureClass.UNDEAD,
        armor=10,
        speed=80,
        holy_modifier=125,
        death_modifier=0,
        fire_modifier=100,
        earth_modifier=75,
        common_loot=["Gold Coin", "Rotten Meat"],
        uncommon_loot=["Skull", "Brown Bread", "Torch"],
        rare_loot=["Ghoul Snack", "Life Ring"],
        description="A hungry undead creature."
    ),

    # Dragons
    "dragon": Creature(
        name="Dragon",
        hp=1000,
        exp=700,
        creature_class=CreatureClass.DRAGON,
        armor=25,
        speed=86,
        is_pushable=False,
        pushes_objects=True,
        fire_modifier=0,    # Immune to fire
        ice_modifier=110,   # Weak to ice
        energy_modifier=80,
        earth_modifier=80,
        common_loot=["Gold Coin", "Dragon Ham", "Burst Arrow"],
        uncommon_loot=["Dragon Shield", "Steel Helmet"],
        rare_loot=["Dragon Claw", "Dragon Scale Mail", "Life Crystal"],
        description="A powerful fire-breathing dragon."
    ),

    "dragon_lord": Creature(
        name="Dragon Lord",
        hp=1900,
        exp=2100,
        creature_class=CreatureClass.DRAGON,
        armor=32,
        speed=90,
        is_boss=False,
        is_pushable=False,
        pushes_objects=True,
        sees_invisible=True,
        fire_modifier=0,
        ice_modifier=110,
        energy_modifier=80,
        earth_modifier=60,
        common_loot=["Gold Coin", "Dragon Ham"],
        uncommon_loot=["Royal Helmet", "Tower Shield"],
        rare_loot=["Dragon Lord Trophy", "Dragon Scale Legs"],
        description="A king among dragons."
    ),
}


def get_creature(name: str) -> Optional[Creature]:
    """
    Get creature by name.

    Args:
        name: Creature name (case-insensitive).

    Returns:
        Creature object or None.
    """
    name_lower = name.lower().replace(" ", "_")
    return CREATURES.get(name_lower)


def get_creatures_by_class(creature_class: CreatureClass) -> List[Creature]:
    """
    Get all creatures of a specific class.

    Args:
        creature_class: Class to filter by.

    Returns:
        List of creatures.
    """
    return [c for c in CREATURES.values() if c.creature_class == creature_class]


def get_creatures_weak_to(element: Element) -> List[Creature]:
    """
    Get creatures weak to an element.

    Args:
        element: Element to check.

    Returns:
        List of weak creatures.
    """
    return [c for c in CREATURES.values() if c.is_weak_to(element)]


def get_creatures_by_exp_range(min_exp: int, max_exp: int) -> List[Creature]:
    """
    Get creatures within an exp range.

    Args:
        min_exp: Minimum exp.
        max_exp: Maximum exp.

    Returns:
        List of creatures.
    """
    return [c for c in CREATURES.values() if min_exp <= c.exp <= max_exp]

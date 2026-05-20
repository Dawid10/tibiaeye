"""
Potion database - information about Tibia potions.
"""
from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict, List, Optional, Tuple


class PotionType(Enum):
    """Types of potions."""
    HEALTH = auto()
    MANA = auto()
    SPIRIT = auto()  # Heals both HP and MP


@dataclass
class Potion:
    """Potion information."""
    name: str
    potion_type: PotionType
    heal_range: Tuple[int, int]  # (min, max) healing
    level_required: int = 1
    vocation_required: List[str] = None
    weight: float = 1.0
    price_npc: int = 0
    is_premium: bool = False
    description: str = ""

    @property
    def average_heal(self) -> float:
        """Get average healing amount."""
        return (self.heal_range[0] + self.heal_range[1]) / 2

    @property
    def is_health(self) -> bool:
        return self.potion_type == PotionType.HEALTH

    @property
    def is_mana(self) -> bool:
        return self.potion_type == PotionType.MANA


# Health Potions Database
HEALTH_POTIONS: Dict[str, Potion] = {
    "small_health_potion": Potion(
        name="Small Health Potion",
        potion_type=PotionType.HEALTH,
        heal_range=(50, 100),
        level_required=1,
        price_npc=20,
        description="Basic healing potion."
    ),

    "health_potion": Potion(
        name="Health Potion",
        potion_type=PotionType.HEALTH,
        heal_range=(100, 200),
        level_required=50,
        price_npc=45,
        description="Standard healing potion."
    ),

    "strong_health_potion": Potion(
        name="Strong Health Potion",
        potion_type=PotionType.HEALTH,
        heal_range=(200, 400),
        level_required=80,
        vocation_required=["Knight", "Paladin"],
        price_npc=100,
        description="Strong healing potion for warriors."
    ),

    "great_health_potion": Potion(
        name="Great Health Potion",
        potion_type=PotionType.HEALTH,
        heal_range=(400, 600),
        level_required=130,
        vocation_required=["Knight"],
        price_npc=190,
        description="Powerful healing potion for knights."
    ),

    "ultimate_health_potion": Potion(
        name="Ultimate Health Potion",
        potion_type=PotionType.HEALTH,
        heal_range=(600, 800),
        level_required=200,
        vocation_required=["Knight"],
        price_npc=310,
        description="Ultimate healing potion for high-level knights."
    ),

    "supreme_health_potion": Potion(
        name="Supreme Health Potion",
        potion_type=PotionType.HEALTH,
        heal_range=(800, 1000),
        level_required=300,
        vocation_required=["Knight"],
        price_npc=500,
        description="Supreme healing potion."
    ),
}

# Mana Potions Database
MANA_POTIONS: Dict[str, Potion] = {
    "small_mana_potion": Potion(
        name="Small Mana Potion",
        potion_type=PotionType.MANA,
        heal_range=(35, 75),
        level_required=1,
        price_npc=35,
        description="Basic mana potion."
    ),

    "mana_potion": Potion(
        name="Mana Potion",
        potion_type=PotionType.MANA,
        heal_range=(75, 125),
        level_required=50,
        price_npc=50,
        description="Standard mana potion."
    ),

    "strong_mana_potion": Potion(
        name="Strong Mana Potion",
        potion_type=PotionType.MANA,
        heal_range=(110, 190),
        level_required=80,
        vocation_required=["Sorcerer", "Druid", "Paladin"],
        price_npc=80,
        description="Strong mana potion for magic users."
    ),

    "great_mana_potion": Potion(
        name="Great Mana Potion",
        potion_type=PotionType.MANA,
        heal_range=(150, 250),
        level_required=130,
        vocation_required=["Sorcerer", "Druid"],
        price_npc=120,
        description="Powerful mana potion."
    ),

    "ultimate_mana_potion": Potion(
        name="Ultimate Mana Potion",
        potion_type=PotionType.MANA,
        heal_range=(200, 350),
        level_required=200,
        vocation_required=["Sorcerer", "Druid"],
        price_npc=175,
        description="Ultimate mana potion."
    ),
}

# Spirit Potions Database (heal both)
SPIRIT_POTIONS: Dict[str, Potion] = {
    "great_spirit_potion": Potion(
        name="Great Spirit Potion",
        potion_type=PotionType.SPIRIT,
        heal_range=(150, 250),  # for both HP and MP
        level_required=130,
        vocation_required=["Paladin"],
        price_npc=190,
        description="Heals both health and mana for paladins."
    ),

    "ultimate_spirit_potion": Potion(
        name="Ultimate Spirit Potion",
        potion_type=PotionType.SPIRIT,
        heal_range=(200, 400),
        level_required=200,
        vocation_required=["Paladin"],
        price_npc=350,
        description="Ultimate potion for paladins."
    ),

    "supreme_spirit_potion": Potion(
        name="Supreme Spirit Potion",
        potion_type=PotionType.SPIRIT,
        heal_range=(250, 500),
        level_required=300,
        vocation_required=["Paladin"],
        price_npc=500,
        description="Supreme spirit potion."
    ),
}


def get_potion(name: str) -> Optional[Potion]:
    """
    Get potion by name.

    Args:
        name: Potion name or key.

    Returns:
        Potion object or None.
    """
    name_lower = name.lower().replace(" ", "_")

    if name_lower in HEALTH_POTIONS:
        return HEALTH_POTIONS[name_lower]
    if name_lower in MANA_POTIONS:
        return MANA_POTIONS[name_lower]
    if name_lower in SPIRIT_POTIONS:
        return SPIRIT_POTIONS[name_lower]

    return None


def get_health_potions() -> List[Potion]:
    """Get all health potions."""
    return list(HEALTH_POTIONS.values())


def get_mana_potions() -> List[Potion]:
    """Get all mana potions."""
    return list(MANA_POTIONS.values())


def get_best_health_potion(level: int, vocation: str = None) -> Optional[Potion]:
    """
    Get the best health potion available for level/vocation.

    Args:
        level: Character level.
        vocation: Character vocation.

    Returns:
        Best available potion or None.
    """
    suitable = []

    for potion in HEALTH_POTIONS.values():
        if potion.level_required > level:
            continue

        if potion.vocation_required:
            if vocation and vocation not in potion.vocation_required:
                continue

        suitable.append(potion)

    if not suitable:
        return None

    # Return the one with highest average heal
    return max(suitable, key=lambda p: p.average_heal)


def get_best_mana_potion(level: int, vocation: str = None) -> Optional[Potion]:
    """
    Get the best mana potion available for level/vocation.

    Args:
        level: Character level.
        vocation: Character vocation.

    Returns:
        Best available potion or None.
    """
    suitable = []

    for potion in MANA_POTIONS.values():
        if potion.level_required > level:
            continue

        if potion.vocation_required:
            if vocation and vocation not in potion.vocation_required:
                continue

        suitable.append(potion)

    if not suitable:
        return None

    return max(suitable, key=lambda p: p.average_heal)


# Potion prices lookup (for quick access without loading full Potion objects)
POTION_PRICES: Dict[str, int] = {
    # Health potions
    'health potion': 45,
    'strong health potion': 100,
    'great health potion': 190,
    'ultimate health potion': 310,
    'supreme health potion': 500,
    # Mana potions
    'mana potion': 50,
    'strong mana potion': 80,
    'great mana potion': 120,
    'ultimate mana potion': 175,
    # Spirit potions
    'great spirit potion': 190,
    'ultimate spirit potion': 350,
}


def get_potion_price(potion_name: str) -> int:
    """
    Get the NPC buy price for a potion.

    Args:
        potion_name: Name of the potion (case-insensitive).

    Returns:
        Price in gold, or 0 if not found.
    """
    normalized = potion_name.lower().strip()

    # Try direct lookup
    if normalized in POTION_PRICES:
        return POTION_PRICES[normalized]

    # Try without "potion" suffix
    if 'potion' not in normalized:
        with_potion = f"{normalized} potion"
        if with_potion in POTION_PRICES:
            return POTION_PRICES[with_potion]

    # Try from Potion object
    potion = get_potion(potion_name)
    if potion is not None:
        return potion.price_npc

    return 0


def calculate_refill_cost(
    health_potion: str,
    health_qty: int,
    mana_potion: str,
    mana_qty: int
) -> int:
    """
    Calculate the total cost of a refill.

    Args:
        health_potion: Name of health potion to buy.
        health_qty: Quantity of health potions.
        mana_potion: Name of mana potion to buy.
        mana_qty: Quantity of mana potions.

    Returns:
        Total cost in gold.
    """
    hp_price = get_potion_price(health_potion)
    mp_price = get_potion_price(mana_potion)

    hp_cost = hp_price * health_qty
    mp_cost = mp_price * mana_qty

    return hp_cost + mp_cost

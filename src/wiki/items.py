"""
Item price database - NPC sell prices for common loot items.

Prices are what NPCs pay for items (sell to NPC).
Used by telemetry to calculate loot value.
Source: TibiaWiki NPC Trade data.
"""
from typing import Optional


# NPC sell prices (gold coins) - what NPCs pay for items
# Items not listed here have value 0 (no NPC buys them)
ITEM_NPC_PRICES = {
    # Currency
    'gold coin': 1,
    'gold coins': 1,
    'platinum coin': 100,
    'platinum coins': 100,
    'crystal coin': 10000,
    'crystal coins': 10000,

    # Common drops (food, basic)
    'meat': 2,
    'ham': 4,
    'egg': 2,
    'cheese': 3,
    'bread': 3,
    'fish': 2,
    'worm': 1,

    # Animal products
    'wool': 15,
    'spider silk': 100,
    'bat wing': 50,
    'bear paw': 100,
    'minotaur horn': 75,
    'minotaur leather': 80,
    'red dragon scale': 200,
    'green dragon scale': 100,
    'dragon ham': 25,
    'dragon claw': 100,

    # Creature products (common)
    'bone': 3,
    'skull': 12,
    'flask of demonic blood': 120,
    'demonic essence': 1000,
    'demon horn': 1000,
    'devil helmet': 1000,
    'demonbone amulet': 32000,
    'fire axe': 8000,
    'giant sword': 17000,
    'golden armor': 20000,
    'magic plate armor': 90000,
    'platinum amulet': 2500,
    'golden legs': 30000,
    'lump of dirt': 5,

    # Gems
    'small ruby': 250,
    'small emerald': 250,
    'small sapphire': 250,
    'small amethyst': 200,
    'small diamond': 300,
    'small topaz': 200,
    'ruby necklace': 2000,
    'emerald bangle': 800,
    'sapphire hammer': 7000,
    'gold ring': 8000,
    'white pearl': 160,
    'black pearl': 280,
    'talon': 320,

    # Rotworm drops
    'mace': 30,
    'sword': 25,
    'gold coin': 1,
    'ham': 4,
    'meat': 2,
    'lump of dirt': 5,
    'copper shield': 50,
    'legion helmet': 22,
    'katana': 35,

    # Orc drops
    'broken helmet': 4,
    'leather armor': 12,
    'sabre': 12,
    'studded club': 10,
    'studded shield': 16,
    'studded armor': 25,
    'studded helmet': 20,
    'axe': 7,
    'orc leather': 30,
    'orc tooth': 150,
    'war hammer': 470,

    # Skeleton/Undead drops
    'bone club': 5,
    'pelvis bone': 3,
    'brass shield': 16,
    'hatchet': 25,
    'viking helmet': 66,
    'dark armor': 400,
    'dark helmet': 250,

    # Dragon drops
    'dragon scale mail': 40000,
    'dragon shield': 4000,
    'serpent sword': 900,
    'steel helmet': 293,
    'crossbow': 120,
    'strong health potion': 100,
    'green dragon leather': 100,

    # Giant spider drops
    'spider silk': 100,
    'plate armor': 400,
    'plate legs': 115,
    'knight armor': 5000,
    'knight legs': 5000,
    'steel helmet': 293,
    'time ring': 2000,

    # Cyclops drops
    'cyclops toe': 40,
    'battle shield': 95,
    'club ring': 100,
    'short sword': 10,

    # Dwarf drops
    'white mushroom': 10,
    'leather legs': 9,
    'pick': 15,
    'iron ore': 30,

    # Amazon drops
    'brown bread': 3,
    'dagger': 2,
    'small ruby': 250,
    'crystal necklace': 400,
    'protective charm': 60,

    # Common equipment
    'morning star': 100,
    'two handed sword': 450,
    'steel shield': 80,
    'scale armor': 75,
    'chain armor': 70,
    'chain helmet': 17,
    'chain legs': 25,
    'doublet': 3,
    'leather helmet': 4,
    'sandals': 2,
    'torch': 2,

    # Potions & Runes (NPC value)
    'health potion': 45,
    'mana potion': 50,
    'great health potion': 190,
    'great mana potion': 120,
    'ultimate health potion': 310,

    # Valuables
    'gold ingot': 5000,
    'holy orchid': 110,
    'scarab coin': 100,
    'ancient coin': 350,

    # Misc common loot
    'rope': 15,
    'torch': 2,
    'candelabrum': 100,
    'bag': 5,
}


def get_item_value(item_name: str) -> int:
    """Get NPC sell value for an item.

    Args:
        item_name: Item name (case-insensitive).

    Returns:
        Value in gold coins, or 0 if unknown.
    """
    return ITEM_NPC_PRICES.get(item_name.lower(), 0)

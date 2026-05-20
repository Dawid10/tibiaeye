"""
Creature misalignment data - pixel offsets for name-to-slot correction.

Some creatures have names that don't align perfectly with their sprite center.
This data maps creature names to their pixel offset (x, y) for slot correction.

Source: PyTibia wiki + empirical testing.
"""

DEFAULT_MISALIGNMENT = {'x': 0, 'y': 0}

MISALIGNMENT = {
    'Rotworm': {'x': 16, 'y': 16},
    'Carrion Worm': {'x': 0, 'y': 0},
    'Cyclops': {'x': 0, 'y': 0},
    'Dragon': {'x': 0, 'y': 0},
    'Dragon Lord': {'x': 0, 'y': 0},
    'Rat': {'x': 16, 'y': 16},
    'Cave Rat': {'x': 16, 'y': 16},
    'Orc': {'x': 0, 'y': 0},
    'Orc Spearman': {'x': 0, 'y': 0},
    'Skeleton': {'x': 0, 'y': 0},
    'Ghoul': {'x': 0, 'y': 0},
    'Troll': {'x': 0, 'y': 0},
    'Amazon': {'x': 0, 'y': 0},
    'Larva': {'x': 16, 'y': 16},
    'Scarab': {'x': 0, 'y': 0},
    'Ancient Scarab': {'x': 0, 'y': 0},
    'Bug': {'x': 16, 'y': 16},
    'Wasp': {'x': 16, 'y': 16},
    'Snake': {'x': 16, 'y': 16},
    'Spider': {'x': 16, 'y': 16},
    'Giant Spider': {'x': 0, 'y': 0},
    'Tarantula': {'x': 0, 'y': 0},
    'Dwarf': {'x': 0, 'y': 0},
    'Dwarf Guard': {'x': 0, 'y': 0},
    'Dwarf Soldier': {'x': 0, 'y': 0},
    'Minotaur': {'x': 0, 'y': 0},
    'Minotaur Guard': {'x': 0, 'y': 0},
    'Minotaur Mage': {'x': 0, 'y': 0},
    'Demon': {'x': 0, 'y': 0},
    'Demon Skeleton': {'x': 0, 'y': 0},
    'Bonebeast': {'x': 0, 'y': 0},
    'Necromancer': {'x': 0, 'y': 0},
    'Lich': {'x': 0, 'y': 0},
    'Vampire': {'x': 0, 'y': 0},
    'Witch': {'x': 0, 'y': 0},
    'Warlock': {'x': 0, 'y': 0},
    'Hero': {'x': 0, 'y': 0},
    'Hydra': {'x': 0, 'y': 0},
    'Serpent Spawn': {'x': 0, 'y': 0},
    'Behemoth': {'x': 0, 'y': 0},
}


def get_misalignment(name: str) -> dict:
    return MISALIGNMENT.get(name, DEFAULT_MISALIGNMENT)

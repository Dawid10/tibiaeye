"""
Cities Wiki - Depot coordinates and NPC locations for major Tibian cities.

Based on PyTibia's cities data structure.

Coordinates are in Tibia's native format: [x, y, z]
where z=7 is ground level, z<7 is above ground, z>7 is below ground.
"""
from typing import Dict, List, Tuple, Any


# Type aliases
Coordinate = Tuple[int, int, int]


cities: Dict[str, Dict[str, Any]] = {
    'Darashia': {
        'depotCoordinates': [
            (33213, 32454, 7),
            (33214, 32454, 7),
            (33215, 32454, 7),
            (33216, 32454, 7),
        ],
        'depotGoalCoordinates': {
            (33213, 32454, 7): (33213, 32455, 7),
            (33214, 32454, 7): (33214, 32455, 7),
            (33215, 32454, 7): (33215, 32455, 7),
            (33216, 32454, 7): (33216, 32455, 7),
        },
        'npcs': {
            'bank': (33212, 32456, 7),
            'potions': (33192, 32432, 7),  # Alesar
        },
    },
    'Thais': {
        'depotCoordinates': [
            (32369, 32241, 7),
            (32370, 32241, 7),
            (32371, 32241, 7),
            (32372, 32241, 7),
        ],
        'depotGoalCoordinates': {
            (32369, 32241, 7): (32369, 32242, 7),
            (32370, 32241, 7): (32370, 32242, 7),
            (32371, 32241, 7): (32371, 32242, 7),
            (32372, 32241, 7): (32372, 32242, 7),
        },
        'npcs': {
            'bank': (32368, 32242, 7),
            'potions': (32385, 32210, 7),  # Xodet
        },
    },
    'Carlin': {
        'depotCoordinates': [
            (32589, 31844, 7),
            (32590, 31844, 7),
            (32591, 31844, 7),
            (32592, 31844, 7),
        ],
        'depotGoalCoordinates': {
            (32589, 31844, 7): (32589, 31845, 7),
            (32590, 31844, 7): (32590, 31845, 7),
            (32591, 31844, 7): (32591, 31845, 7),
            (32592, 31844, 7): (32592, 31845, 7),
        },
        'npcs': {
            'bank': (32588, 31842, 7),
            'potions': (32595, 31879, 7),  # Alexander
        },
    },
    'Venore': {
        'depotGoalCoordinates': {
            # Depot principal (Norte)
            (32930, 32072, 7): (32930, 32071, 7),
            (32928, 32072, 7): (32928, 32071, 7),
            (32926, 32072, 7): (32926, 32071, 7),
            (32924, 32072, 7): (32924, 32071, 7),
            (32922, 32069, 7): (32922, 32068, 7),
            (32920, 32069, 7): (32920, 32068, 7),
            (32917, 32069, 7): (32917, 32068, 7),
            (32915, 32069, 7): (32915, 32068, 7),
            (32913, 32072, 7): (32913, 32071, 7),
            (32911, 32072, 7): (32911, 32071, 7),


            # Depot principal (Sul)
            # TODO

            # Depot oeste - player fica 1 tile ao sul do locker
            (32930, 32071, 7): (32930, 32072, 7),
            (32928, 32071, 7): (32928, 32072, 7),
            (32926, 32071, 7): (32926, 32072, 7),
            (32924, 32071, 7): (32924, 32072, 7),
        },
        'npcs': {
            'bank': (32955, 32078, 7),
            'potions': (32969, 32060, 7),  # Asrak
        },
    },
    'Edron': {
        'depotCoordinates': [
            (33175, 31764, 8),
            (33176, 31764, 8),
            (33177, 31764, 8),
            (33178, 31764, 8),
        ],
        'depotGoalCoordinates': {
            (33175, 31764, 8): (33175, 31765, 8),
            (33176, 31764, 8): (33176, 31765, 8),
            (33177, 31764, 8): (33177, 31765, 8),
            (33178, 31764, 8): (33178, 31765, 8),
        },
        'npcs': {
            'bank': (33174, 31762, 8),
            'potions': (33172, 31802, 8),  # Rudolph
        },
    },
    'Kazordoon': {
        'depotCoordinates': [
            (32632, 31904, 8),
            (32633, 31904, 8),
            (32634, 31904, 8),
            (32635, 31904, 8),
        ],
        'depotGoalCoordinates': {
            (32632, 31904, 8): (32632, 31905, 8),
            (32633, 31904, 8): (32633, 31905, 8),
            (32634, 31904, 8): (32634, 31905, 8),
            (32635, 31904, 8): (32635, 31905, 8),
        },
        'npcs': {
            'bank': (32631, 31902, 8),
            'potions': (32648, 31916, 8),
        },
    },
    'Ab\'Dendriel': {
        'depotCoordinates': [
            (32590, 31676, 7),
            (32591, 31676, 7),
            (32592, 31676, 7),
            (32593, 31676, 7),
        ],
        'depotGoalCoordinates': {
            (32590, 31676, 7): (32590, 31677, 7),
            (32591, 31676, 7): (32591, 31677, 7),
            (32592, 31676, 7): (32592, 31677, 7),
            (32593, 31676, 7): (32593, 31677, 7),
        },
        'npcs': {
            'bank': (32589, 31674, 7),
            'potions': (32605, 31704, 7),
        },
    },
    'Svargrond': {
        'depotCoordinates': [
            (32254, 31071, 7),
            (32255, 31071, 7),
            (32256, 31071, 7),
            (32257, 31071, 7),
        ],
        'depotGoalCoordinates': {
            (32254, 31071, 7): (32254, 31072, 7),
            (32255, 31071, 7): (32255, 31072, 7),
            (32256, 31071, 7): (32256, 31072, 7),
            (32257, 31071, 7): (32257, 31072, 7),
        },
        'npcs': {
            'bank': (32253, 31073, 7),
            'potions': (32272, 31089, 7),
        },
    },
    'Liberty Bay': {
        'depotCoordinates': [
            (32317, 32835, 7),
            (32318, 32835, 7),
            (32319, 32835, 7),
            (32320, 32835, 7),
        ],
        'depotGoalCoordinates': {
            (32317, 32835, 7): (32317, 32836, 7),
            (32318, 32835, 7): (32318, 32836, 7),
            (32319, 32835, 7): (32319, 32836, 7),
            (32320, 32835, 7): (32320, 32836, 7),
        },
        'npcs': {
            'bank': (32316, 32837, 7),
            'potions': (32301, 32839, 7),
        },
    },
    'Port Hope': {
        'depotCoordinates': [
            (32629, 32749, 7),
            (32630, 32749, 7),
            (32631, 32749, 7),
            (32632, 32749, 7),
        ],
        'depotGoalCoordinates': {
            (32629, 32749, 7): (32629, 32750, 7),
            (32630, 32749, 7): (32630, 32750, 7),
            (32631, 32749, 7): (32631, 32750, 7),
            (32632, 32749, 7): (32632, 32750, 7),
        },
        'npcs': {
            'bank': (32628, 32747, 7),
            'potions': (32594, 32739, 7),
        },
    },
    'Yalahar': {
        'depotCoordinates': [
            (32785, 31276, 7),
            (32786, 31276, 7),
            (32787, 31276, 7),
            (32788, 31276, 7),
        ],
        'depotGoalCoordinates': {
            (32785, 31276, 7): (32785, 31277, 7),
            (32786, 31276, 7): (32786, 31277, 7),
            (32787, 31276, 7): (32787, 31277, 7),
            (32788, 31276, 7): (32788, 31277, 7),
        },
        'npcs': {
            'bank': (32784, 31278, 7),
            'potions': (32813, 31271, 7),
        },
    },
}


def get_depot_coordinates(city: str) -> List[Coordinate]:
    """Get list of depot locker coordinates for a city."""
    city_data = cities.get(city)
    if city_data is None:
        return []

    # Prefer depotCoordinates if exists, otherwise use keys from depotGoalCoordinates
    if 'depotCoordinates' in city_data:
        return city_data['depotCoordinates']

    # Fallback: get locker coords from depotGoalCoordinates keys
    return list(city_data.get('depotGoalCoordinates', {}).keys())


def get_depot_goal_coordinate(city: str, depot_coord: Coordinate) -> Coordinate:
    """Get the goal coordinate (where to stand) for a specific depot locker."""
    city_data = cities.get(city)
    if city_data is None:
        return depot_coord
    goals = city_data.get('depotGoalCoordinates', {})
    return goals.get(depot_coord, depot_coord)


def get_npc_coordinate(city: str, npc_type: str) -> Coordinate:
    """
    Get NPC coordinate by type.

    Args:
        city: City name
        npc_type: One of 'bank', 'potions', etc.

    Returns:
        Coordinate tuple or None if not found
    """
    city_data = cities.get(city)
    if city_data is None:
        return None
    npcs = city_data.get('npcs', {})
    return npcs.get(npc_type)


def get_all_city_names() -> List[str]:
    """Get list of all known city names."""
    return list(cities.keys())

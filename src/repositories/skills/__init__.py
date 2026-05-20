"""
Skills Repository - Reads skills window values like PyTibia.

Detects:
- Food timer (minutes)
- HP/Mana values
- Capacity
- Speed
- Stamina
"""
from .core import get_food, get_hp, get_mana, get_capacity, get_speed, get_stamina, get_experience

__all__ = [
    'get_food',
    'get_hp',
    'get_mana',
    'get_capacity',
    'get_speed',
    'get_stamina',
    'get_experience',
]

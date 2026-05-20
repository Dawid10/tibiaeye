"""
Inventory Repository - Container and backpack management.
"""
from .core import (
    get_container_position,
    is_container_open,
    open_container,
    close_container,
    get_slot_position,
    drag_item,
    is_depot_open,
    open_depot_slot,
    open_depot_chest,
)

__all__ = [
    'get_container_position',
    'is_container_open',
    'open_container',
    'close_container',
    'get_slot_position',
    'drag_item',
    'is_depot_open',
    'open_depot_slot',
    'open_depot_chest',
]

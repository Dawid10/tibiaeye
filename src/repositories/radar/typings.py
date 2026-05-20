"""
Radar typings - Type definitions for radar/navigation.
"""
from typing import Tuple, List, Dict, Any, TypedDict
import numpy as np


# Coordinate is (x, y, z) tuple
Coordinate = Tuple[int, int, int]

# List of coordinates
CoordinateList = List[Coordinate]

# XY coordinate (without floor)
XYCoordinate = Tuple[int, int]

# Floor level (0-15)
FloorLevel = int

# Tile friction value (affects movement speed)
TileFriction = int

# Waypoint structure
class Waypoint(TypedDict, total=False):
    label: str
    type: str
    coordinate: Coordinate
    options: Dict[str, Any]

# List of waypoints
WaypointList = List[Waypoint]

# Checkpoint for navigation
class Checkpoint(TypedDict):
    goalCoordinate: Coordinate
    checkInCoordinate: Coordinate

# Waypoint distance (for sorting)
class WaypointDistance(TypedDict):
    index: int
    distance: float

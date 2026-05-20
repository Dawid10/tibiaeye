"""
Shared types and data classes for the tibia bot.
"""
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Any, Tuple


class Direction(Enum):
    """Cardinal and intercardinal directions."""
    NORTH = auto()
    SOUTH = auto()
    EAST = auto()
    WEST = auto()
    NORTHEAST = auto()
    NORTHWEST = auto()
    SOUTHEAST = auto()
    SOUTHWEST = auto()
    CENTER = auto()

    @classmethod
    def from_relative_position(cls, rel_x: int, rel_y: int, threshold: int = 5) -> 'Direction':
        """Determine direction from relative coordinates."""
        d = ""
        if rel_y < -threshold:
            d += "N"
        if rel_y > threshold:
            d += "S"
        if rel_x < -threshold:
            d += "W"
        if rel_x > threshold:
            d += "E"

        direction_map = {
            "N": cls.NORTH,
            "S": cls.SOUTH,
            "E": cls.EAST,
            "W": cls.WEST,
            "NE": cls.NORTHEAST,
            "NW": cls.NORTHWEST,
            "SE": cls.SOUTHEAST,
            "SW": cls.SOUTHWEST,
            "": cls.CENTER
        }
        return direction_map.get(d, cls.CENTER)

    @property
    def opposite(self) -> 'Direction':
        """Get the opposite direction."""
        opposites = {
            Direction.NORTH: Direction.SOUTH,
            Direction.SOUTH: Direction.NORTH,
            Direction.EAST: Direction.WEST,
            Direction.WEST: Direction.EAST,
            Direction.NORTHEAST: Direction.SOUTHWEST,
            Direction.SOUTHWEST: Direction.NORTHEAST,
            Direction.NORTHWEST: Direction.SOUTHEAST,
            Direction.SOUTHEAST: Direction.NORTHWEST,
            Direction.CENTER: Direction.CENTER
        }
        return opposites[self]

    @property
    def short_name(self) -> str:
        """Get short direction name (N, S, E, W, NE, etc)."""
        names = {
            Direction.NORTH: "N",
            Direction.SOUTH: "S",
            Direction.EAST: "E",
            Direction.WEST: "W",
            Direction.NORTHEAST: "NE",
            Direction.NORTHWEST: "NW",
            Direction.SOUTHEAST: "SE",
            Direction.SOUTHWEST: "SW",
            Direction.CENTER: "."
        }
        return names[self]


class CreatureType(Enum):
    """Types of creatures in the game."""
    MONSTER = auto()
    NPC = auto()
    PLAYER = auto()
    UNKNOWN = auto()


class HPColor(Enum):
    """HP bar color indicating health status."""
    GREEN = auto()   # High HP
    YELLOW = auto()  # Medium HP
    RED = auto()     # Low HP
    UNKNOWN = auto()

    @property
    def priority(self) -> int:
        """Lower number = higher attack priority."""
        priorities = {
            HPColor.RED: 1,
            HPColor.YELLOW: 2,
            HPColor.GREEN: 3,
            HPColor.UNKNOWN: 4
        }
        return priorities[self]


class TaskStatus(Enum):
    """Status of a bot task."""
    NOT_STARTED = auto()
    AWAITING_DELAY = auto()
    RUNNING = auto()
    COMPLETED = auto()
    FAILED = auto()
    TIMEOUT = auto()


class BotMode(Enum):
    """Current operating mode of the bot."""
    IDLE = auto()
    EXPLORING = auto()
    COMBAT = auto()
    HEALING = auto()
    LOOTING = auto()
    WALKING = auto()


@dataclass
class Coordinate:
    """Game world coordinate."""
    x: int
    y: int
    z: int = 7  # Default floor level

    def distance_to(self, other: 'Coordinate') -> float:
        """Calculate distance to another coordinate."""
        import math
        return math.sqrt(
            (self.x - other.x) ** 2 +
            (self.y - other.y) ** 2
        )

    def to_tuple(self) -> Tuple[int, int, int]:
        """Convert to tuple."""
        return (self.x, self.y, self.z)


@dataclass
class Creature:
    """Represents a creature in the battle list."""
    name: str
    x: int
    y: int
    width: int
    height: int
    hp_color: HPColor = HPColor.UNKNOWN
    creature_type: CreatureType = CreatureType.UNKNOWN
    confidence: float = 0.0
    is_being_attacked: bool = False

    @property
    def center(self) -> Tuple[int, int]:
        """Get center position."""
        return (self.x + self.width // 2, self.y + self.height // 2)

    @property
    def attack_priority(self) -> Tuple[int, int]:
        """Sort key for attack priority (HP color, then Y position)."""
        return (self.hp_color.priority, self.y)


@dataclass
class Marker:
    """Represents a minimap marker."""
    x: int
    y: int
    rel_x: int
    rel_y: int
    distance: float
    confidence: float
    screen_x: int
    screen_y: int
    direction: Direction = Direction.CENTER

    @classmethod
    def from_detection(cls, x: int, y: int, center_x: int, center_y: int,
                       region_x: int, region_y: int, confidence: float) -> 'Marker':
        """Create marker from detection result."""
        import math
        rel_x = x - center_x
        rel_y = y - center_y
        distance = math.sqrt(rel_x ** 2 + rel_y ** 2)
        direction = Direction.from_relative_position(rel_x, rel_y)

        return cls(
            x=x,
            y=y,
            rel_x=rel_x,
            rel_y=rel_y,
            distance=distance,
            confidence=confidence,
            screen_x=region_x + x,
            screen_y=region_y + y,
            direction=direction
        )


@dataclass
class PlayerStatus:
    """Current player status."""
    hp_percent: float = 100.0
    mp_percent: float = 100.0
    is_attacking: bool = False
    current_target: Optional[Creature] = None


@dataclass
class GameContext:
    """
    Shared context passed through middleware pipeline.

    Contains all game state extracted from screen.
    """
    # Screenshot data
    screenshot: Optional[Any] = None
    minimap_img: Optional[Any] = None
    battlelist_img: Optional[Any] = None

    # Player status
    player: PlayerStatus = field(default_factory=PlayerStatus)

    # Battle list
    creatures: List[Creature] = field(default_factory=list)
    creature_count: int = 0

    # Minimap
    markers: List[Marker] = field(default_factory=list)
    player_position: Optional[Coordinate] = None

    # Bot state
    mode: BotMode = BotMode.IDLE
    current_task: Optional[Any] = None

    # Timing
    timestamp: float = 0.0
    frame_count: int = 0

    # Configuration
    config: Dict[str, Any] = field(default_factory=dict)

    def get_valid_targets(self, blacklist: List[str] = None) -> List[Creature]:
        """Get creatures that can be attacked."""
        blacklist = blacklist or []
        blacklist_lower = [b.lower() for b in blacklist]

        return [
            c for c in self.creatures
            if c.creature_type == CreatureType.MONSTER
            and c.name.lower() not in blacklist_lower
        ]

    def get_best_target(self, blacklist: List[str] = None) -> Optional[Creature]:
        """Get highest priority attack target."""
        targets = self.get_valid_targets(blacklist)
        if not targets:
            return None

        # Sort by attack priority (HP color, then Y position)
        targets.sort(key=lambda c: c.attack_priority)
        return targets[0]

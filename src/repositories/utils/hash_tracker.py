"""
Hash Learning Tracker - Tracks recently learned hashes for GUI display.

Singleton pattern to share state between BattleList and GameWindow repositories.
"""
from collections import deque
from typing import List, Tuple
from dataclasses import dataclass
from datetime import datetime


@dataclass
class LearnedHash:
    """Represents a learned hash entry."""
    name: str
    source: str  # 'BL' or 'GW'
    timestamp: datetime


class HashLearningTracker:
    """Singleton tracker for hash learning events."""

    _instance = None
    MAX_RECENT = 5

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._recent: deque = deque(maxlen=cls.MAX_RECENT)
            cls._instance._bl_count = 0
            cls._instance._gw_count = 0
        return cls._instance

    def record_learn(self, name: str, source: str) -> None:
        """
        Record a hash learning event.

        Args:
            name: Creature name that was learned
            source: 'BL' for BattleList, 'GW' for GameWindow
        """
        entry = LearnedHash(name=name, source=source, timestamp=datetime.now())
        self._recent.appendleft(entry)

        if source == 'BL':
            self._bl_count += 1
        elif source == 'GW':
            self._gw_count += 1

    def get_recent(self) -> List[LearnedHash]:
        """Get list of recently learned hashes (newest first)."""
        return list(self._recent)

    def get_counts(self) -> Tuple[int, int]:
        """Get (battlelist_count, gamewindow_count) of learned hashes this session."""
        return (self._bl_count, self._gw_count)

    def set_initial_counts(self, bl_count: int, gw_count: int) -> None:
        """Set initial counts from loaded hash files."""
        self._bl_count = bl_count
        self._gw_count = gw_count

    def reset(self) -> None:
        """Reset all tracking (for testing)."""
        self._recent.clear()
        self._bl_count = 0
        self._gw_count = 0


# Global instance
_tracker = HashLearningTracker()


def record_hash_learned(name: str, source: str) -> None:
    """Record a hash learning event."""
    _tracker.record_learn(name, source)


def get_recent_learned() -> List[LearnedHash]:
    """Get list of recently learned hashes."""
    return _tracker.get_recent()


def get_hash_counts() -> Tuple[int, int]:
    """Get (battlelist_count, gamewindow_count)."""
    return _tracker.get_counts()


def set_initial_hash_counts(bl_count: int, gw_count: int) -> None:
    """Set initial counts from loaded hash files."""
    _tracker.set_initial_counts(bl_count, gw_count)

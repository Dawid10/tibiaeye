"""Targeting Filter - filters monsters based on targeting settings."""
from typing import Any, Dict, List, Optional, Set


class TargetingFilter:
    """Filters monsters based on whitelist/blacklist targeting settings."""

    def __init__(self):
        self._tick_count = 0

    def set_tick_count(self, tick_count: int) -> None:
        """Update tick count for logging purposes."""
        self._tick_count = tick_count

    def get_target_names(self, context: Dict[str, Any]) -> Optional[List[str]]:
        """
        Get list of creature names to detect based on targeting settings.

        Returns lowercase names when using whitelist mode, None otherwise.
        """
        targeting = context.get('targeting', {})

        if not targeting.get('enabled', True):
            return None

        mode = targeting.get('mode', 'all')

        if mode != 'whitelist':
            return None

        whitelist = targeting.get('whitelist', [])
        if not whitelist:
            return None

        return [name.lower() for name in whitelist if isinstance(name, str)]

    def filter(self, monsters: list, context: Dict[str, Any]) -> list:
        """
        Filter monsters based on targeting settings.

        Args:
            monsters: List of monsters from game window
            context: Game context with targeting configuration

        Returns:
            Filtered list of monsters that should be attacked
        """
        targeting = context.get('targeting', {})

        if not targeting.get('enabled', True):
            return []

        mode = targeting.get('mode', 'all')

        if mode == 'all':
            return monsters

        if mode == 'whitelist':
            return self._filter_whitelist(monsters, targeting)

        if mode == 'blacklist':
            return self._filter_blacklist(monsters, targeting)

        return monsters

    def _filter_whitelist(self, monsters: list, targeting: Dict) -> list:
        """Filter monsters to only include those in whitelist."""
        whitelist = self._normalize_names(targeting.get('whitelist', []))

        if not whitelist:
            return monsters

        filtered = []
        for monster in monsters:
            name = getattr(monster, 'name', '').lower()
            if name in whitelist:
                filtered.append(monster)

        self._log_whitelist_filtering(monsters, filtered, whitelist)
        return filtered

    def _filter_blacklist(self, monsters: list, targeting: Dict) -> list:
        """Filter monsters to exclude those in blacklist."""
        blacklist = self._normalize_names(targeting.get('blacklist', []))

        if not blacklist:
            return monsters

        filtered = []
        for monster in monsters:
            name = getattr(monster, 'name', '').lower()
            if name not in blacklist:
                filtered.append(monster)

        self._log_blacklist_filtering(monsters, filtered)
        return filtered

    def _normalize_names(self, names) -> Set[str]:
        """Convert name list/set to lowercase set."""
        if not names:
            return set()
        return set(n.lower() if isinstance(n, str) else n for n in names)

    def _log_whitelist_filtering(self, monsters: list, filtered: list,
                                  whitelist: Set[str]) -> None:
        """Log whitelist filtering results periodically."""
        if not monsters:
            return
        if self._tick_count % 100 != 0:
            return

        original_names = [getattr(m, 'name', 'Unknown') for m in monsters]
        filtered_names = [getattr(m, 'name', 'Unknown') for m in filtered]
        rejected = [n for n in original_names if n.lower() not in whitelist]

        if not rejected:
            return

        print(f"[Targeting] Whitelist: {list(whitelist)}")
        print(f"[Targeting] Rejected (not in whitelist): {rejected}")
        print(f"[Targeting] Accepted: {filtered_names}")

    def _log_blacklist_filtering(self, monsters: list, filtered: list) -> None:
        """Log blacklist filtering results periodically."""
        if filtered == monsters:
            return
        if self._tick_count % 100 != 0:
            return

        original_names = [getattr(m, 'name', 'Unknown') for m in monsters]
        filtered_names = [getattr(m, 'name', 'Unknown') for m in filtered]
        print(f"[Targeting] Blacklist filter: {original_names} -> {filtered_names}")

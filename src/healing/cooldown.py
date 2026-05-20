"""
Cooldown Manager - tracks action cooldowns.
"""
import time
from typing import Dict, Optional


class CooldownManager:
    """
    Manages cooldowns for various actions.

    Prevents action spam by tracking last use times.
    """

    def __init__(self):
        """Initialize cooldown manager."""
        self._last_use: Dict[str, float] = {}
        self._use_count: Dict[str, int] = {}

    def can_use(self, action: str, cooldown: float) -> bool:
        """
        Check if action can be used (cooldown expired).

        Args:
            action: Action identifier.
            cooldown: Cooldown duration in seconds.

        Returns:
            True if action can be used.
        """
        if action not in self._last_use:
            return True

        elapsed = time.time() - self._last_use[action]
        return elapsed >= cooldown

    def use(self, action: str) -> None:
        """
        Mark action as used.

        Args:
            action: Action identifier.
        """
        self._last_use[action] = time.time()
        self._use_count[action] = self._use_count.get(action, 0) + 1

    def get_remaining(self, action: str, cooldown: float) -> float:
        """
        Get remaining cooldown time.

        Args:
            action: Action identifier.
            cooldown: Total cooldown duration.

        Returns:
            Remaining time in seconds (0 if ready).
        """
        if action not in self._last_use:
            return 0.0

        elapsed = time.time() - self._last_use[action]
        remaining = cooldown - elapsed
        return max(0.0, remaining)

    def reset(self, action: str = None) -> None:
        """
        Reset cooldown(s).

        Args:
            action: Specific action to reset. If None, resets all.
        """
        if action:
            self._last_use.pop(action, None)
        else:
            self._last_use.clear()

    def get_use_count(self, action: str) -> int:
        """
        Get number of times action was used.

        Args:
            action: Action identifier.

        Returns:
            Use count.
        """
        return self._use_count.get(action, 0)

    def get_last_use_time(self, action: str) -> Optional[float]:
        """
        Get timestamp of last use.

        Args:
            action: Action identifier.

        Returns:
            Last use timestamp or None.
        """
        return self._last_use.get(action)

    @property
    def actions(self) -> list:
        """Get list of tracked actions."""
        return list(self._last_use.keys())

"""Bot Health tracker - monitors middleware health and triggers safe mode.

Tracks consecutive failures per middleware. When critical middlewares fail
too many times, the bot pauses automatically instead of continuing blind.
"""
import time
from collections import deque
from typing import Dict, List, Optional, Tuple

from ..core.constants import (
    MAX_CRITICAL_FAILURES,
    MAX_IMPORTANT_FAILURES,
    SAFE_MODE_RECOVERY_INTERVAL,
    SAFE_MODE_RECOVERY_TIMEOUT,
)

MAX_RECENT_ERRORS = 10

CRITICAL_MIDDLEWARES = frozenset({'screenshot', 'statusbar'})
IMPORTANT_MIDDLEWARES = frozenset({'battlelist', 'gamewindow', 'radar'})
NON_CRITICAL_MIDDLEWARES = frozenset({'skills', 'chat'})

ALL_MIDDLEWARES = CRITICAL_MIDDLEWARES | IMPORTANT_MIDDLEWARES | NON_CRITICAL_MIDDLEWARES

# Gameplay subsystems (not middlewares, but tracked for health)
GAMEPLAY_SUBSYSTEMS = frozenset({'cavebot', 'orchestrator', 'healing', 'spell_attack'})


class BotHealth:
    """Tracks middleware health and decides when to enter safe mode."""

    def __init__(self):
        self._failure_counts: Dict[str, int] = {}
        self._last_errors: Dict[str, str] = {}
        self._last_failure_times: Dict[str, float] = {}
        self._recent_errors: deque = deque(maxlen=MAX_RECENT_ERRORS)

    def report_success(self, name: str) -> None:
        """Reset failure counter for a middleware after successful execution."""
        self._failure_counts[name] = 0

    def report_failure(self, name: str, error: Exception) -> None:
        """Increment failure counter and log the error."""
        self._failure_counts[name] = self._failure_counts.get(name, 0) + 1
        error_str = str(error)
        self._last_errors[name] = error_str
        now = time.time()
        self._last_failure_times[name] = now

        # Add to recent errors ring buffer
        from src.utils.error_messages import friendly_error
        friendly_msg, suggestion = friendly_error(error_str)
        self._recent_errors.append({
            'time': now,
            'subsystem': name,
            'technical': error_str,
            'friendly': friendly_msg,
            'suggestion': suggestion,
        })

        count = self._failure_counts[name]
        is_critical = name in CRITICAL_MIDDLEWARES

        if is_critical:
            print(f"[BotHealth] CRITICAL failure #{count} in '{name}': {error}")
        elif count == 1 or count % 5 == 0:
            print(f"[BotHealth] Failure #{count} in '{name}': {error}")

    def should_pause(self) -> bool:
        """Return True if any critical middleware exceeded its failure threshold."""
        for name in CRITICAL_MIDDLEWARES:
            if self._failure_counts.get(name, 0) >= MAX_CRITICAL_FAILURES:
                return True
        return False

    def should_warn(self) -> bool:
        """Return True if any important middleware is degraded."""
        for name in IMPORTANT_MIDDLEWARES:
            if self._failure_counts.get(name, 0) >= MAX_IMPORTANT_FAILURES:
                return True
        return False

    def get_failing_critical(self) -> list:
        """Return names of critical middlewares that exceeded threshold."""
        return [
            name for name in CRITICAL_MIDDLEWARES
            if self._failure_counts.get(name, 0) >= MAX_CRITICAL_FAILURES
        ]

    def get_status(self) -> Dict[str, dict]:
        """Return health status for all tracked middlewares."""
        status = {}
        for name in ALL_MIDDLEWARES | GAMEPLAY_SUBSYSTEMS:
            count = self._failure_counts.get(name, 0)
            status[name] = {
                'failures': count,
                'last_error': self._last_errors.get(name),
                'last_failure_time': self._last_failure_times.get(name),
                'healthy': count == 0,
            }
        return status

    def get_recent_errors(self) -> List[dict]:
        """Return list of recent errors (newest first)."""
        return list(reversed(self._recent_errors))

    def reset(self) -> None:
        """Reset all counters (called after successful recovery)."""
        self._failure_counts.clear()
        self._last_errors.clear()
        self._last_failure_times.clear()

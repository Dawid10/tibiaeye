"""
Timing utilities - timers and rate limiters.
"""
import time
from functools import wraps
from typing import Callable, Optional


class Timer:
    """
    Simple timer for measuring execution time.

    Usage:
        with Timer() as t:
            # code to measure
        print(f"Took {t.elapsed:.3f}s")

    Or:
        timer = Timer()
        timer.start()
        # code
        timer.stop()
        print(f"Took {timer.elapsed:.3f}s")
    """

    def __init__(self):
        """Initialize timer."""
        self._start: float = 0.0
        self._end: float = 0.0
        self._running = False

    def start(self) -> 'Timer':
        """Start the timer."""
        self._start = time.perf_counter()
        self._running = True
        return self

    def stop(self) -> float:
        """Stop the timer and return elapsed time."""
        self._end = time.perf_counter()
        self._running = False
        return self.elapsed

    def reset(self) -> None:
        """Reset the timer."""
        self._start = 0.0
        self._end = 0.0
        self._running = False

    @property
    def elapsed(self) -> float:
        """Get elapsed time in seconds."""
        if self._running:
            return time.perf_counter() - self._start
        return self._end - self._start

    @property
    def elapsed_ms(self) -> float:
        """Get elapsed time in milliseconds."""
        return self.elapsed * 1000

    def __enter__(self) -> 'Timer':
        """Context manager entry."""
        self.start()
        return self

    def __exit__(self, *args) -> None:
        """Context manager exit."""
        self.stop()


class RateLimiter:
    """
    Rate limiter to control action frequency.

    Usage:
        limiter = RateLimiter(min_interval=0.5)

        while True:
            if limiter.can_proceed():
                # do action
                limiter.mark()
    """

    def __init__(self, min_interval: float = 1.0):
        """
        Initialize rate limiter.

        Args:
            min_interval: Minimum time between actions in seconds.
        """
        self._min_interval = min_interval
        self._last_action: float = 0.0
        self._action_count: int = 0

    def can_proceed(self) -> bool:
        """Check if enough time has passed."""
        return time.time() - self._last_action >= self._min_interval

    def mark(self) -> None:
        """Mark an action as performed."""
        self._last_action = time.time()
        self._action_count += 1

    def wait_if_needed(self) -> None:
        """Wait until action can proceed."""
        remaining = self._min_interval - (time.time() - self._last_action)
        if remaining > 0:
            time.sleep(remaining)

    def time_until_ready(self) -> float:
        """Get time until next action can proceed."""
        remaining = self._min_interval - (time.time() - self._last_action)
        return max(0.0, remaining)

    def reset(self) -> None:
        """Reset the limiter."""
        self._last_action = 0.0

    @property
    def action_count(self) -> int:
        """Get number of actions performed."""
        return self._action_count


def rate_limiter(min_interval: float = 1.0):
    """
    Decorator that rate-limits function calls.

    Args:
        min_interval: Minimum time between calls in seconds.

    Usage:
        @rate_limiter(0.5)
        def my_function():
            pass
    """
    def decorator(func: Callable) -> Callable:
        limiter = RateLimiter(min_interval)

        @wraps(func)
        def wrapper(*args, **kwargs):
            limiter.wait_if_needed()
            result = func(*args, **kwargs)
            limiter.mark()
            return result

        wrapper.limiter = limiter
        return wrapper

    return decorator


def timed(func: Callable) -> Callable:
    """
    Decorator that measures function execution time.

    Usage:
        @timed
        def my_function():
            pass

        my_function()  # Prints execution time
    """
    @wraps(func)
    def wrapper(*args, **kwargs):
        with Timer() as t:
            result = func(*args, **kwargs)
        print(f"{func.__name__} took {t.elapsed_ms:.2f}ms")
        return result

    return wrapper

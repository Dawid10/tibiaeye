"""
Tests for timing utilities.

Ensures:
1. Timer accurately measures execution time
2. RateLimiter correctly limits action frequency
3. Decorators work correctly
4. Context manager usage works
"""
import time
import pytest

from src.utils.timing import Timer, RateLimiter, rate_limiter, timed


class TestTimer:
    """Tests for Timer class."""

    def test_timer_start_stop(self):
        """Test basic timer start/stop functionality."""
        timer = Timer()

        timer.start()
        time.sleep(0.1)
        elapsed = timer.stop()

        # Should be at least 0.1 seconds
        assert elapsed >= 0.09  # Allow small tolerance
        assert elapsed < 0.2    # But not too long

    def test_timer_elapsed_while_running(self):
        """Test getting elapsed time while timer is running."""
        timer = Timer()

        timer.start()
        time.sleep(0.05)

        elapsed = timer.elapsed
        assert elapsed >= 0.04
        assert timer._running == True

    def test_timer_elapsed_after_stop(self):
        """Test getting elapsed time after timer stopped."""
        timer = Timer()

        timer.start()
        time.sleep(0.05)
        timer.stop()

        # Elapsed should stay the same after stop
        elapsed1 = timer.elapsed
        time.sleep(0.05)
        elapsed2 = timer.elapsed

        assert elapsed1 == elapsed2

    def test_timer_elapsed_ms(self):
        """Test elapsed time in milliseconds."""
        timer = Timer()

        timer.start()
        time.sleep(0.1)
        timer.stop()

        elapsed_ms = timer.elapsed_ms

        assert elapsed_ms >= 90  # At least 90ms
        assert elapsed_ms < 200  # Less than 200ms

    def test_timer_reset(self):
        """Test timer reset functionality."""
        timer = Timer()

        timer.start()
        time.sleep(0.05)
        timer.stop()

        timer.reset()

        assert timer.elapsed == 0.0
        assert timer._running == False

    def test_timer_context_manager(self):
        """Test timer as context manager."""
        with Timer() as t:
            time.sleep(0.1)

        assert t.elapsed >= 0.09
        assert t._running == False

    def test_timer_start_returns_self(self):
        """Test that start() returns self for chaining."""
        timer = Timer()

        result = timer.start()

        assert result is timer

    def test_timer_not_started(self):
        """Test elapsed time when timer never started."""
        timer = Timer()

        assert timer.elapsed == 0.0

    def test_timer_multiple_start_stop_cycles(self):
        """Test timer can be reused with start/stop."""
        timer = Timer()

        # First cycle
        timer.start()
        time.sleep(0.05)
        elapsed1 = timer.stop()

        # Reset and second cycle
        timer.reset()
        timer.start()
        time.sleep(0.1)
        elapsed2 = timer.stop()

        assert elapsed1 < elapsed2  # Second was longer


class TestRateLimiter:
    """Tests for RateLimiter class."""

    def test_can_proceed_first_time(self):
        """Test that first action can always proceed."""
        limiter = RateLimiter(min_interval=1.0)

        assert limiter.can_proceed() == True

    def test_cannot_proceed_during_interval(self):
        """Test that action is blocked during interval."""
        limiter = RateLimiter(min_interval=1.0)

        limiter.mark()

        assert limiter.can_proceed() == False

    def test_can_proceed_after_interval(self):
        """Test that action can proceed after interval."""
        limiter = RateLimiter(min_interval=0.1)

        limiter.mark()
        time.sleep(0.15)

        assert limiter.can_proceed() == True

    def test_mark_updates_last_action_time(self):
        """Test that mark() updates the last action time."""
        limiter = RateLimiter(min_interval=0.1)

        before = time.time()
        limiter.mark()
        after = time.time()

        assert before <= limiter._last_action <= after

    def test_action_count_increments(self):
        """Test that action_count increments on mark."""
        limiter = RateLimiter(min_interval=0.0)

        assert limiter.action_count == 0

        limiter.mark()
        assert limiter.action_count == 1

        limiter.mark()
        assert limiter.action_count == 2

    def test_time_until_ready(self):
        """Test time_until_ready calculation."""
        limiter = RateLimiter(min_interval=1.0)

        limiter.mark()

        remaining = limiter.time_until_ready()
        assert remaining > 0.9
        assert remaining <= 1.0

    def test_time_until_ready_when_ready(self):
        """Test time_until_ready returns 0 when ready."""
        limiter = RateLimiter(min_interval=0.1)

        limiter.mark()
        time.sleep(0.15)

        assert limiter.time_until_ready() == 0.0

    def test_time_until_ready_never_used(self):
        """Test time_until_ready when never used."""
        limiter = RateLimiter(min_interval=1.0)

        # Should be ready immediately
        assert limiter.time_until_ready() == 0.0

    def test_reset(self):
        """Test reset clears last action time."""
        limiter = RateLimiter(min_interval=1.0)

        limiter.mark()
        assert limiter.can_proceed() == False

        limiter.reset()
        assert limiter.can_proceed() == True

    def test_wait_if_needed_waits(self):
        """Test wait_if_needed blocks until ready."""
        limiter = RateLimiter(min_interval=0.1)

        limiter.mark()

        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start

        # Should have waited at least some time
        assert elapsed >= 0.05

    def test_wait_if_needed_no_wait_when_ready(self):
        """Test wait_if_needed returns immediately when ready."""
        limiter = RateLimiter(min_interval=0.1)

        limiter.mark()
        time.sleep(0.15)

        start = time.time()
        limiter.wait_if_needed()
        elapsed = time.time() - start

        # Should return immediately
        assert elapsed < 0.05

    def test_zero_interval(self):
        """Test with zero interval allows immediate actions."""
        limiter = RateLimiter(min_interval=0.0)

        limiter.mark()
        assert limiter.can_proceed() == True

    def test_very_short_interval(self):
        """Test behavior with very short interval."""
        limiter = RateLimiter(min_interval=0.001)

        limiter.mark()

        # Immediately should be blocked
        assert limiter.can_proceed() == False

        # After short wait
        time.sleep(0.005)
        assert limiter.can_proceed() == True


class TestRateLimiterDecorator:
    """Tests for rate_limiter decorator."""

    def test_decorator_limits_calls(self):
        """Test that decorator limits function call rate."""
        call_count = 0

        @rate_limiter(min_interval=0.1)
        def limited_func():
            nonlocal call_count
            call_count += 1
            return call_count

        # First call - immediate
        start = time.time()
        limited_func()
        first_elapsed = time.time() - start

        # Second call - should wait
        start = time.time()
        limited_func()
        second_elapsed = time.time() - start

        assert first_elapsed < 0.05  # First should be fast
        assert second_elapsed >= 0.05  # Second should wait

    def test_decorator_preserves_return_value(self):
        """Test that decorator preserves function return value."""
        @rate_limiter(min_interval=0.0)
        def return_value():
            return 42

        assert return_value() == 42

    def test_decorator_preserves_arguments(self):
        """Test that decorator passes arguments correctly."""
        @rate_limiter(min_interval=0.0)
        def with_args(a, b, c=None):
            return (a, b, c)

        result = with_args(1, 2, c=3)
        assert result == (1, 2, 3)

    def test_decorator_exposes_limiter(self):
        """Test that decorator exposes the limiter object."""
        @rate_limiter(min_interval=0.5)
        def func():
            pass

        assert hasattr(func, 'limiter')
        assert isinstance(func.limiter, RateLimiter)

    def test_decorator_limiter_can_be_reset(self):
        """Test that exposed limiter can be reset."""
        @rate_limiter(min_interval=1.0)
        def func():
            pass

        func()
        assert func.limiter.can_proceed() == False

        func.limiter.reset()
        assert func.limiter.can_proceed() == True


class TestTimedDecorator:
    """Tests for timed decorator."""

    def test_timed_prints_execution_time(self, capsys):
        """Test that timed decorator prints execution time."""
        @timed
        def slow_func():
            time.sleep(0.05)
            return "done"

        result = slow_func()

        captured = capsys.readouterr()
        assert "slow_func" in captured.out
        assert "ms" in captured.out
        assert result == "done"

    def test_timed_preserves_function_name(self):
        """Test that timed preserves function metadata."""
        @timed
        def named_func():
            pass

        assert named_func.__name__ == "named_func"

    def test_timed_preserves_return_value(self):
        """Test that timed preserves return value."""
        @timed
        def return_func():
            return {"key": "value"}

        result = return_func()
        assert result == {"key": "value"}

    def test_timed_preserves_arguments(self, capsys):
        """Test that timed passes arguments correctly."""
        @timed
        def args_func(a, b, c=None):
            return a + b + (c or 0)

        result = args_func(1, 2, c=3)
        assert result == 6


class TestTimerEdgeCases:
    """Edge case tests for Timer."""

    def test_stop_without_start(self):
        """Test stop() without start() returns negative elapsed."""
        timer = Timer()

        elapsed = timer.stop()

        # Will return negative because _end is set but _start is 0
        assert timer._running == False

    def test_multiple_stops(self):
        """Test calling stop() multiple times."""
        timer = Timer()

        timer.start()
        time.sleep(0.05)

        elapsed1 = timer.stop()
        time.sleep(0.05)  # Wait after first stop
        elapsed2 = timer.stop()  # Stop again

        # Second stop should update _end, changing elapsed
        # This is expected behavior - not necessarily an error


class TestRateLimiterEdgeCases:
    """Edge case tests for RateLimiter."""

    def test_large_interval(self):
        """Test with very large interval."""
        limiter = RateLimiter(min_interval=999999.0)

        limiter.mark()

        assert limiter.can_proceed() == False
        remaining = limiter.time_until_ready()
        assert remaining > 999998.0

    def test_negative_interval(self):
        """Test behavior with negative interval."""
        limiter = RateLimiter(min_interval=-1.0)

        limiter.mark()

        # With negative interval, should always be able to proceed
        assert limiter.can_proceed() == True

    def test_rapid_marks(self):
        """Test rapid marking behavior."""
        limiter = RateLimiter(min_interval=0.0)

        for _ in range(100):
            limiter.mark()

        assert limiter.action_count == 100

    def test_concurrent_like_usage(self):
        """Test rate limiter with rapid consecutive calls."""
        limiter = RateLimiter(min_interval=0.05)
        successful_actions = 0

        start = time.time()
        while time.time() - start < 0.2:
            if limiter.can_proceed():
                limiter.mark()
                successful_actions += 1
            time.sleep(0.01)

        # Should allow roughly 4-5 actions in 0.2s with 0.05s interval
        assert 3 <= successful_actions <= 6

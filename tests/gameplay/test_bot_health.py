"""
Tests for BotHealth - middleware health tracker and safe mode trigger.

Ensures:
1. Success resets failure counters
2. Failure increments counters and logs
3. should_pause triggers on critical middleware failures
4. should_warn triggers on important middleware degradation
5. Non-critical failures don't trigger pause
6. reset clears all state
7. get_status returns complete health info
"""
from src.gameplay.bot_health import BotHealth
from src.core.constants import MAX_CRITICAL_FAILURES, MAX_IMPORTANT_FAILURES


class TestReportSuccess:
    """Tests for report_success behavior."""

    def test_resets_failure_count(self):
        """Should reset failure counter after a successful execution."""
        health = BotHealth()
        health.report_failure('screenshot', RuntimeError("fail"))
        health.report_failure('screenshot', RuntimeError("fail"))
        health.report_success('screenshot')

        assert health._failure_counts.get('screenshot', 0) == 0

    def test_success_on_fresh_middleware(self):
        """Should work even if middleware never failed before."""
        health = BotHealth()
        health.report_success('radar')

        assert health._failure_counts.get('radar', 0) == 0


class TestReportFailure:
    """Tests for report_failure behavior."""

    def test_increments_count(self):
        """Should increment failure counter on each failure."""
        health = BotHealth()
        health.report_failure('statusbar', RuntimeError("fail 1"))
        health.report_failure('statusbar', RuntimeError("fail 2"))

        assert health._failure_counts['statusbar'] == 2

    def test_stores_last_error(self):
        """Should store the most recent error message."""
        health = BotHealth()
        health.report_failure('radar', ValueError("bad coord"))

        assert health._last_errors['radar'] == "bad coord"

    def test_stores_failure_time(self):
        """Should record the time of the last failure."""
        health = BotHealth()
        health.report_failure('battlelist', RuntimeError("fail"))

        assert health._last_failure_times['battlelist'] > 0


class TestShouldPause:
    """Tests for should_pause (critical middleware threshold)."""

    def test_pauses_when_critical_exceeds_threshold(self):
        """Should return True when screenshot failures exceed MAX_CRITICAL_FAILURES."""
        health = BotHealth()
        for i in range(MAX_CRITICAL_FAILURES):
            health.report_failure('screenshot', RuntimeError(f"fail {i}"))

        assert health.should_pause() is True

    def test_pauses_when_statusbar_exceeds_threshold(self):
        """Should return True when statusbar failures exceed threshold."""
        health = BotHealth()
        for i in range(MAX_CRITICAL_FAILURES):
            health.report_failure('statusbar', RuntimeError(f"fail {i}"))

        assert health.should_pause() is True

    def test_no_pause_below_threshold(self):
        """Should not pause if failures haven't reached threshold."""
        health = BotHealth()
        for i in range(MAX_CRITICAL_FAILURES - 1):
            health.report_failure('screenshot', RuntimeError(f"fail {i}"))

        assert health.should_pause() is False

    def test_no_pause_when_non_critical_fails(self):
        """Should not pause when only non-critical middlewares fail."""
        health = BotHealth()
        for i in range(50):
            health.report_failure('skills', RuntimeError(f"fail {i}"))

        assert health.should_pause() is False

    def test_no_pause_when_important_fails(self):
        """Should not pause when only important (non-critical) middlewares fail."""
        health = BotHealth()
        for i in range(50):
            health.report_failure('battlelist', RuntimeError(f"fail {i}"))
            health.report_failure('gamewindow', RuntimeError(f"fail {i}"))
            health.report_failure('radar', RuntimeError(f"fail {i}"))

        assert health.should_pause() is False

    def test_pause_resets_after_success(self):
        """Should stop pausing after critical middleware succeeds."""
        health = BotHealth()
        for i in range(MAX_CRITICAL_FAILURES):
            health.report_failure('screenshot', RuntimeError(f"fail {i}"))

        assert health.should_pause() is True

        health.report_success('screenshot')
        assert health.should_pause() is False


class TestShouldWarn:
    """Tests for should_warn (important middleware degradation)."""

    def test_warns_when_important_exceeds_threshold(self):
        """Should return True when important middleware failures exceed threshold."""
        health = BotHealth()
        for i in range(MAX_IMPORTANT_FAILURES):
            health.report_failure('battlelist', RuntimeError(f"fail {i}"))

        assert health.should_warn() is True

    def test_no_warn_below_threshold(self):
        """Should not warn if failures haven't reached threshold."""
        health = BotHealth()
        for i in range(MAX_IMPORTANT_FAILURES - 1):
            health.report_failure('radar', RuntimeError(f"fail {i}"))

        assert health.should_warn() is False

    def test_no_warn_for_non_critical(self):
        """Should not warn for non-critical middleware failures."""
        health = BotHealth()
        for i in range(50):
            health.report_failure('skills', RuntimeError(f"fail {i}"))

        assert health.should_warn() is False


class TestGetFailingCritical:
    """Tests for get_failing_critical."""

    def test_returns_failing_middlewares(self):
        """Should return names of critical middlewares that exceeded threshold."""
        health = BotHealth()
        for i in range(MAX_CRITICAL_FAILURES):
            health.report_failure('screenshot', RuntimeError(f"fail {i}"))

        failing = health.get_failing_critical()
        assert 'screenshot' in failing
        assert 'statusbar' not in failing

    def test_returns_empty_when_healthy(self):
        """Should return empty list when no critical middleware is failing."""
        health = BotHealth()
        failing = health.get_failing_critical()
        assert failing == []


class TestReset:
    """Tests for reset (clears all counters)."""

    def test_clears_all_counters(self):
        """Should clear all failure counts, errors, and times."""
        health = BotHealth()
        health.report_failure('screenshot', RuntimeError("fail"))
        health.report_failure('statusbar', RuntimeError("fail"))
        health.report_failure('radar', RuntimeError("fail"))

        health.reset()

        assert health._failure_counts == {}
        assert health._last_errors == {}
        assert health._last_failure_times == {}

    def test_should_pause_false_after_reset(self):
        """Should not pause after reset even if thresholds were exceeded before."""
        health = BotHealth()
        for i in range(MAX_CRITICAL_FAILURES):
            health.report_failure('screenshot', RuntimeError(f"fail {i}"))

        assert health.should_pause() is True

        health.reset()
        assert health.should_pause() is False


class TestGetStatus:
    """Tests for get_status (full health status)."""

    def test_returns_all_middleware_states(self):
        """Should return status for all tracked middlewares."""
        health = BotHealth()
        status = health.get_status()

        assert 'screenshot' in status
        assert 'statusbar' in status
        assert 'battlelist' in status
        assert 'gamewindow' in status
        assert 'radar' in status
        assert 'skills' in status
        assert 'chat' in status

    def test_healthy_by_default(self):
        """Should report all middlewares as healthy by default."""
        health = BotHealth()
        status = health.get_status()

        for name, info in status.items():
            assert info['healthy'] is True
            assert info['failures'] == 0

    def test_reflects_failures(self):
        """Should reflect failure state correctly."""
        health = BotHealth()
        health.report_failure('radar', ValueError("bad"))

        status = health.get_status()
        assert status['radar']['failures'] == 1
        assert status['radar']['healthy'] is False
        assert status['radar']['last_error'] == "bad"

    def test_includes_gameplay_subsystems(self):
        """Should also track gameplay subsystems like cavebot and healing."""
        health = BotHealth()
        status = health.get_status()

        assert 'cavebot' in status
        assert 'orchestrator' in status
        assert 'healing' in status
        assert 'spell_attack' in status

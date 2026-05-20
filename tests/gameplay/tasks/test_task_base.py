"""
Tests for BaseTask - the fundamental task class.

Ensures:
1. Task lifecycle works correctly (NOT_STARTED -> RUNNING -> COMPLETED)
2. Delays work (before start, after complete)
3. Timeouts are detected
4. Restart mechanism works
5. Hooks are called at the right times
"""
import time
import pytest
from unittest.mock import Mock, patch

from src.gameplay.core.tasks.base import BaseTask, TaskState


class TestTaskState:
    """Tests for TaskState enum."""

    def test_all_states_exist(self):
        """Test that all task states are defined."""
        assert TaskState.NOT_STARTED is not None
        assert TaskState.AWAITING_DELAY_BEFORE_START is not None
        assert TaskState.RUNNING is not None
        assert TaskState.AWAITING_DELAY_TO_COMPLETE is not None
        assert TaskState.COMPLETED is not None
        assert TaskState.TIMED_OUT is not None


class TestBaseTaskCreation:
    """Tests for BaseTask initialization."""

    def test_default_creation(self):
        """Test task creation with defaults."""
        task = BaseTask()

        assert task.name == "BaseTask"
        assert task.state == TaskState.NOT_STARTED
        assert task.delay_before_start == 0
        assert task.delay_after_complete == 0
        assert task.delay_of_timeout == 0
        assert task.parent is None

    def test_custom_name(self):
        """Test task creation with custom name."""
        task = BaseTask(name="MyTask")

        assert task.name == "MyTask"

    def test_initial_timing(self):
        """Test initial timing values."""
        task = BaseTask()

        assert task.started_at == 0
        assert task.finished_at == 0
        assert task.retry_count == 0


class TestTaskLifecycle:
    """Tests for task lifecycle transitions."""

    def test_start_transitions_to_running(self):
        """Test that start() transitions to RUNNING when no delay."""
        task = BaseTask()
        context = {}

        task.start(context)

        assert task.state == TaskState.RUNNING
        assert task.started_at > 0

    def test_start_with_delay_transitions_to_awaiting(self):
        """Test that start() with delay transitions to AWAITING_DELAY_BEFORE_START."""
        task = BaseTask()
        task.delay_before_start = 1.0
        context = {}

        task.start(context)

        assert task.state == TaskState.AWAITING_DELAY_BEFORE_START

    def test_complete_transitions_to_completed(self):
        """Test that complete() transitions to COMPLETED."""
        task = BaseTask()
        context = {}

        task.start(context)
        task.complete(context)

        assert task.state == TaskState.COMPLETED
        assert task.finished_at > 0

    def test_timeout_transitions_to_timed_out(self):
        """Test that timeout() transitions to TIMED_OUT."""
        task = BaseTask()
        context = {}

        task.start(context)
        task.timeout(context)

        assert task.state == TaskState.TIMED_OUT
        assert task.finished_at > 0

    def test_restart_resets_state(self):
        """Test that restart() resets task state."""
        task = BaseTask()
        context = {}

        task.start(context)
        task.complete(context)

        # Restart
        task.restart(context)

        assert task.state == TaskState.NOT_STARTED
        assert task.started_at == 0
        assert task.finished_at == 0
        assert task.retry_count == 1  # Incremented


class TestTaskProperties:
    """Tests for task properties."""

    def test_is_completed(self):
        """Test is_completed property."""
        task = BaseTask()

        assert task.is_completed == False

        task.state = TaskState.COMPLETED
        assert task.is_completed == True

    def test_is_running(self):
        """Test is_running property."""
        task = BaseTask()

        assert task.is_running == False

        task.state = TaskState.RUNNING
        assert task.is_running == True

    def test_is_timed_out(self):
        """Test is_timed_out property."""
        task = BaseTask()

        assert task.is_timed_out == False

        task.state = TaskState.TIMED_OUT
        assert task.is_timed_out == True

    def test_elapsed_time_not_started(self):
        """Test elapsed_time when not started."""
        task = BaseTask()

        assert task.elapsed_time == 0

    def test_elapsed_time_running(self):
        """Test elapsed_time while running."""
        task = BaseTask()
        task.start({})

        time.sleep(0.05)

        assert task.elapsed_time >= 0.04


class TestTaskHooks:
    """Tests for task lifecycle hooks."""

    def test_on_before_start_called(self):
        """Test that on_before_start is called during start()."""
        task = BaseTask()
        task.on_before_start = Mock(return_value={})
        context = {}

        task.start(context)

        task.on_before_start.assert_called_once_with(context)

    def test_on_complete_called(self):
        """Test that on_complete is called during complete()."""
        task = BaseTask()
        task.on_complete = Mock(return_value={})
        context = {}

        task.start(context)
        task.complete(context)

        task.on_complete.assert_called_once_with(context)

    def test_on_timeout_called(self):
        """Test that on_timeout is called during timeout()."""
        task = BaseTask()
        task.on_timeout = Mock(return_value={})
        context = {}

        task.start(context)
        task.timeout(context)

        task.on_timeout.assert_called_once_with(context)

    def test_on_before_restart_called(self):
        """Test that on_before_restart is called during restart()."""
        task = BaseTask()
        task.on_before_restart = Mock(return_value={})
        context = {}

        task.start(context)
        task.restart(context)

        task.on_before_restart.assert_called_once_with(context)


class TestTaskMethods:
    """Tests for task core methods."""

    def test_do_returns_context(self):
        """Test that do() returns context."""
        task = BaseTask()
        context = {'test': 'value'}

        result = task.do(context)

        assert result == context

    def test_did_returns_true_by_default(self):
        """Test that did() returns True by default."""
        task = BaseTask()

        assert task.did({}) == True

    def test_ping_returns_context(self):
        """Test that ping() returns context."""
        task = BaseTask()
        context = {'test': 'value'}

        result = task.ping(context)

        assert result == context

    def test_should_ignore_returns_false_by_default(self):
        """Test that should_ignore returns False by default."""
        task = BaseTask()

        assert task.should_ignore({}) == False

    def test_should_restart_returns_false_by_default(self):
        """Test that should_restart returns False by default."""
        task = BaseTask()

        assert task.should_restart({}) == False


class TestTaskRetry:
    """Tests for task retry mechanism."""

    def test_retry_count_increments(self):
        """Test that retry_count increments on restart."""
        task = BaseTask()
        context = {}

        assert task.retry_count == 0

        task.restart(context)
        assert task.retry_count == 1

        task.restart(context)
        assert task.retry_count == 2

    def test_max_retries_default(self):
        """Test default max_retries value."""
        task = BaseTask()

        assert task.max_retries == 3


class TestCustomTask:
    """Tests for custom task implementations."""

    def test_custom_do(self):
        """Test custom do() implementation."""
        class CounterTask(BaseTask):
            def __init__(self):
                super().__init__("CounterTask")
                self.counter = 0

            def do(self, context):
                self.counter += 1
                context['counter'] = self.counter
                return context

        task = CounterTask()
        context = {}

        task.start(context)

        assert task.counter == 1
        assert context['counter'] == 1

    def test_custom_did(self):
        """Test custom did() implementation."""
        class WaitForValueTask(BaseTask):
            def __init__(self, target_value):
                super().__init__("WaitForValueTask")
                self.target_value = target_value

            def did(self, context):
                return context.get('value') == self.target_value

        task = WaitForValueTask(target_value=42)

        assert task.did({'value': 10}) == False
        assert task.did({'value': 42}) == True

    def test_custom_should_ignore(self):
        """Test custom should_ignore() implementation."""
        class ConditionalTask(BaseTask):
            def should_ignore(self, context):
                return context.get('skip', False)

        task = ConditionalTask()

        assert task.should_ignore({'skip': False}) == False
        assert task.should_ignore({'skip': True}) == True

    def test_custom_should_restart(self):
        """Test custom should_restart() implementation."""
        class RepeatTask(BaseTask):
            def __init__(self, repeat_count):
                super().__init__("RepeatTask")
                self.repeat_count = repeat_count
                self.executions = 0

            def do(self, context):
                self.executions += 1
                return context

            def should_restart(self, context):
                return self.executions < self.repeat_count

        task = RepeatTask(repeat_count=3)

        task.do({})
        assert task.should_restart({}) == True  # 1 < 3

        task.do({})
        assert task.should_restart({}) == True  # 2 < 3

        task.do({})
        assert task.should_restart({}) == False  # 3 < 3 = False


class TestTaskRepr:
    """Tests for task string representation."""

    def test_repr_default(self):
        """Test default repr."""
        task = BaseTask()

        assert "BaseTask" in repr(task)
        assert "NOT_STARTED" in repr(task)

    def test_repr_with_custom_name(self):
        """Test repr with custom name."""
        task = BaseTask(name="MyTask")

        assert "MyTask" in repr(task)

    def test_repr_running_state(self):
        """Test repr when running."""
        task = BaseTask()
        task.state = TaskState.RUNNING

        assert "RUNNING" in repr(task)


class TestDelayBehavior:
    """Tests for delay behavior."""

    def test_delay_before_start_prevents_immediate_do(self):
        """Test that delay_before_start prevents immediate do() call."""
        do_called = False

        class TrackedTask(BaseTask):
            def do(self, context):
                nonlocal do_called
                do_called = True
                return context

        task = TrackedTask()
        task.delay_before_start = 1.0

        task.start({})

        # do() should NOT have been called yet
        assert do_called == False
        assert task.state == TaskState.AWAITING_DELAY_BEFORE_START

    def test_zero_delay_calls_do_immediately(self):
        """Test that zero delay calls do() immediately."""
        do_called = False

        class TrackedTask(BaseTask):
            def do(self, context):
                nonlocal do_called
                do_called = True
                return context

        task = TrackedTask()
        task.delay_before_start = 0

        task.start({})

        # do() should have been called
        assert do_called == True
        assert task.state == TaskState.RUNNING


class TestTaskBehaviorFlags:
    """Tests for task behavior flags."""

    def test_should_timeout_tree_default(self):
        """Test default value for should_timeout_tree_when_timeout."""
        task = BaseTask()

        assert task.should_timeout_tree_when_timeout == True

    def test_manually_complete_default(self):
        """Test default value for manually_complete."""
        task = BaseTask()

        assert task.manually_complete == False

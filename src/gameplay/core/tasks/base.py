"""
Base Task - PyTibia style task system.

Tasks are the fundamental unit of action. They have:
- Lifecycle: notStarted -> running -> completed
- Timeouts and delays
- Hooks for customization
"""
import time
from enum import Enum, auto
from typing import Any, Dict, Optional, Callable


class TaskState(Enum):
    """Task lifecycle states."""
    NOT_STARTED = auto()
    AWAITING_DELAY_BEFORE_START = auto()
    RUNNING = auto()
    AWAITING_DELAY_TO_COMPLETE = auto()
    COMPLETED = auto()
    TIMED_OUT = auto()


Context = Dict[str, Any]


class BaseTask:
    """
    Base class for all tasks.

    Lifecycle:
    1. notStarted
    2. awaitingDelayBeforeStart (if delayBeforeStart > 0)
    3. running (do() is called)
    4. awaitingDelayToComplete (if delayAfterComplete > 0)
    5. completed

    Override these methods:
    - do(context): Execute the task action
    - did(context): Check if task completed successfully
    - shouldIgnore(context): Skip this task?
    - shouldRestart(context): Restart this task?
    """

    def __init__(self, name: str = "BaseTask"):
        self.name = name
        self.state = TaskState.NOT_STARTED

        # Timing
        self.started_at: float = 0
        self.finished_at: float = 0
        self._delay_complete_started_at: float = 0

        # Delays (in seconds)
        self.delay_before_start: float = 0
        self.delay_after_complete: float = 0
        self.delay_of_timeout: float = 0  # 0 = no timeout

        # Behavior flags
        self.should_timeout_tree_when_timeout: bool = True
        self.manually_complete: bool = False
        self.retry_count: int = 0
        self.max_retries: int = 3

        # Parent reference (set by VectorTask)
        self.parent: Optional['BaseTask'] = None

    # ========== Core Methods ==========

    def do(self, context: Context) -> Context:
        """
        Execute the task action.

        Override this to define what the task does.
        Called once when task enters RUNNING state.
        """
        return context

    def did(self, context: Context) -> bool:
        """
        Check if task completed successfully.

        Override this to define completion condition.
        Called every frame while task is RUNNING.
        """
        return True

    def ping(self, context: Context) -> Context:
        """
        Called every frame while task is running.

        Use for continuous actions or monitoring.
        """
        return context

    # ========== Condition Methods ==========

    def should_ignore(self, context: Context) -> bool:
        """
        Check if task should be skipped.

        Override to skip task under certain conditions.
        """
        return False

    def should_restart(self, context: Context) -> bool:
        """
        Check if task should restart after completion.

        Override for repeating tasks.
        """
        return False

    # ========== Lifecycle Hooks ==========

    def on_before_start(self, context: Context) -> Context:
        """Called before task starts."""
        return context

    def on_before_restart(self, context: Context) -> Context:
        """Called before task restarts."""
        return context

    def on_complete(self, context: Context) -> Context:
        """Called when task completes successfully."""
        return context

    def on_timeout(self, context: Context) -> Context:
        """Called when task times out."""
        return context

    def on_interrupt(self, context: Context) -> Context:
        """Called when task is interrupted."""
        return context

    # ========== State Management ==========

    def start(self, context: Context) -> Context:
        """Start the task."""
        self.started_at = time.time()
        context = self.on_before_start(context)

        if self.delay_before_start > 0:
            self.state = TaskState.AWAITING_DELAY_BEFORE_START
        else:
            self.state = TaskState.RUNNING
            context = self.do(context)

        return context

    def complete(self, context: Context) -> Context:
        """Mark task as completed."""
        self.finished_at = time.time()
        self.state = TaskState.COMPLETED
        return self.on_complete(context)

    def timeout(self, context: Context) -> Context:
        """Mark task as timed out."""
        self.finished_at = time.time()
        self.state = TaskState.TIMED_OUT
        return self.on_timeout(context)

    def restart(self, context: Context) -> Context:
        """Restart the task."""
        context = self.on_before_restart(context)
        self.state = TaskState.NOT_STARTED
        self.started_at = 0
        self.finished_at = 0
        self._delay_complete_started_at = 0
        self.retry_count += 1
        return context

    # ========== Properties ==========

    @property
    def is_completed(self) -> bool:
        return self.state == TaskState.COMPLETED

    @property
    def is_running(self) -> bool:
        return self.state == TaskState.RUNNING

    @property
    def is_timed_out(self) -> bool:
        return self.state == TaskState.TIMED_OUT

    @property
    def elapsed_time(self) -> float:
        if self.started_at == 0:
            return 0
        return time.time() - self.started_at

    def __repr__(self) -> str:
        return f"{self.name}({self.state.name})"

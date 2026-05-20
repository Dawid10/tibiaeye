"""
Task Orchestrator - PyTibia style task executor.

The orchestrator manages the task tree execution:
1. Handles task lifecycle (start, complete, timeout, restart)
2. Executes current task each frame
3. Manages parent-child task relationships
"""
import time
from typing import Any, Dict, Optional

from .base import BaseTask, TaskState, Context
from .vector import VectorTask
from ....utils.jitter import jitter


class TasksOrchestrator:
    """
    Manages hierarchical task execution.

    The orchestrator:
    1. Holds a root task (can be VectorTask with children)
    2. Each frame, processes the current task
    3. Handles state transitions (start, complete, timeout)
    4. Supports task interruption and restart
    """

    def __init__(self):
        self.root_task: Optional[BaseTask] = None
        self._last_context: Context = {}

    def set_root_task(self, task: BaseTask) -> None:
        """
        Set a new root task, interrupting any current task.
        """
        if self.root_task is not None:
            # Interrupt current task tree
            self._interrupt_task(self.root_task)

        self.root_task = task

    def clear(self) -> None:
        """Clear the current task."""
        if self.root_task is not None:
            self._interrupt_task(self.root_task)
        self.root_task = None

    def do(self, context: Context) -> Context:
        """
        Process one frame of task execution.

        Called every game loop iteration (~45ms).
        """
        self._last_context = context

        if self.root_task is None:
            return context

        # Get the deepest currently active task
        current_task = self._get_current_task(self.root_task)
        if current_task is None:
            # All tasks completed
            self.root_task = None
            return context

        # Process the current task
        context = self._process_task(current_task, context)

        return context

    def _get_current_task(self, task: BaseTask) -> Optional[BaseTask]:
        """
        Get the deepest currently active task in the tree.

        For VectorTask, descends into the current child.
        """
        if task.is_completed:
            return None

        # If task hasn't started yet, return it so it can be started
        if task.state == TaskState.NOT_STARTED:
            return task

        # If task is waiting for delay, return it
        if task.state == TaskState.AWAITING_DELAY_BEFORE_START:
            return task

        if isinstance(task, VectorTask):
            child = task.current_task
            if child is not None and not child.is_completed:
                return self._get_current_task(child)
            # All children done - return VectorTask so it can be processed
            # (did() will be called in _process_task with proper context)
            return task

        return task

    def _process_task(self, task: BaseTask, context: Context) -> Context:
        """
        Process a single task for one frame.
        """
        # Check if should ignore
        if task.should_ignore(context):
            context = task.complete(context)
            return self._on_task_completed(task, context)

        # Handle based on state
        if task.state == TaskState.NOT_STARTED:
            # Apply jitter to delay_before_start (NOT timeout — timeouts must be fixed)
            if task.delay_before_start > 0:
                task._jittered_delay_before_start = jitter(task.delay_before_start)
            context = task.start(context)

        elif task.state == TaskState.AWAITING_DELAY_BEFORE_START:
            # Check if jittered delay elapsed
            actual_delay = getattr(task, '_jittered_delay_before_start', task.delay_before_start)
            if task.elapsed_time >= actual_delay:
                task.state = TaskState.RUNNING
                context = task.do(context)

        elif task.state == TaskState.RUNNING:
            # Check timeout (NO jitter — timeouts must be fixed for safety)
            if task.delay_of_timeout > 0 and task.elapsed_time >= task.delay_of_timeout:
                context = task.timeout(context)
                return self._on_task_timeout(task, context)

            # Ping (continuous action)
            context = task.ping(context)

            # Check if done
            if task.did(context):
                if task.delay_after_complete > 0:
                    task.state = TaskState.AWAITING_DELAY_TO_COMPLETE
                    task._delay_complete_started_at = time.time()
                    task._jittered_delay_after_complete = jitter(task.delay_after_complete)
                else:
                    context = task.complete(context)
                    return self._on_task_completed(task, context)

        elif task.state == TaskState.AWAITING_DELAY_TO_COMPLETE:
            # Check if jittered delay elapsed
            actual_delay = getattr(task, '_jittered_delay_after_complete', task.delay_after_complete)
            if time.time() - task._delay_complete_started_at >= actual_delay:
                context = task.complete(context)
                return self._on_task_completed(task, context)

        return context

    def _on_task_completed(self, task: BaseTask, context: Context) -> Context:
        """Handle task completion."""
        # Check if should restart
        if task.should_restart(context) and task.retry_count < task.max_retries:
            context = task.restart(context)
            return context

        # If this is a child of VectorTask, advance parent
        if task.parent is not None and isinstance(task.parent, VectorTask):
            if not task.parent.advance_to_next_task():
                # No more children, complete parent
                if task.parent.did(context):
                    context = task.parent.complete(context)
                    return self._on_task_completed(task.parent, context)

        # If this was root task, clear it
        if task == self.root_task:
            self.root_task = None

        return context

    def _on_task_timeout(self, task: BaseTask, context: Context) -> Context:
        """Handle task timeout."""
        # If should timeout tree, propagate to parent
        if task.should_timeout_tree_when_timeout and task.parent is not None:
            context = task.parent.timeout(context)
            return self._on_task_timeout(task.parent, context)

        # If this was root task, clear it
        if task == self.root_task:
            self.root_task = None

        return context

    def _interrupt_task(self, task: BaseTask) -> None:
        """Interrupt a task and its children."""
        if isinstance(task, VectorTask):
            for child in task.tasks:
                self._interrupt_task(child)

        if task.state == TaskState.RUNNING:
            task.on_interrupt(self._last_context)

    @property
    def is_idle(self) -> bool:
        """Check if orchestrator has no active task."""
        return self.root_task is None

    @property
    def current_task_name(self) -> str:
        """Get name of current task for debugging."""
        if self.root_task is None:
            return "idle"
        current = self._get_current_task(self.root_task)
        if current is None:
            return "completing"
        return current.name

    def __repr__(self) -> str:
        return f"TasksOrchestrator(task={self.current_task_name})"

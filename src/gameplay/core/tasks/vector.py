"""
Vector Task - Composite task that executes children sequentially.

A VectorTask contains multiple child tasks and executes them one by one.
When all children complete, the VectorTask completes.
"""
from typing import Any, Dict, List, Optional

from .base import BaseTask, TaskState, Context


class VectorTask(BaseTask):
    """
    A task that contains and executes child tasks sequentially.

    Example:
        WalkToWaypointTask (VectorTask)
        ├── WalkTask (direction='up')
        ├── WalkTask (direction='left')
        └── SetNextWaypointTask

    When child 1 completes, moves to child 2, etc.
    When all children complete, VectorTask completes.
    """

    def __init__(self, name: str = "VectorTask", tasks: List[BaseTask] = None):
        super().__init__(name)
        self.tasks: List[BaseTask] = tasks or []
        self.current_task_index: int = 0

        # Set parent reference on all children
        for task in self.tasks:
            task.parent = self

    def add_task(self, task: BaseTask) -> None:
        """Add a child task."""
        task.parent = self
        self.tasks.append(task)

    def add_tasks(self, tasks: List[BaseTask]) -> None:
        """Add multiple child tasks."""
        for task in tasks:
            self.add_task(task)

    @property
    def current_task(self) -> Optional[BaseTask]:
        """Get the currently executing child task."""
        if 0 <= self.current_task_index < len(self.tasks):
            return self.tasks[self.current_task_index]
        return None

    def advance_to_next_task(self) -> bool:
        """
        Move to the next child task.

        Returns:
            True if there's a next task, False if all done.
        """
        self.current_task_index += 1
        return self.current_task_index < len(self.tasks)

    def did(self, context: Context) -> bool:
        """
        VectorTask is done when all children are done.
        """
        # No tasks = immediately done
        if not self.tasks:
            return True

        # All tasks completed?
        return self.current_task_index >= len(self.tasks)

    def reset_children(self) -> None:
        """Reset all child tasks to NOT_STARTED."""
        self.current_task_index = 0
        for task in self.tasks:
            task.state = TaskState.NOT_STARTED
            task.started_at = 0
            task.finished_at = 0
            if isinstance(task, VectorTask):
                task.reset_children()

    def on_before_restart(self, context: Context) -> Context:
        """Reset children when restarting."""
        self.reset_children()
        return super().on_before_restart(context)

    def __len__(self) -> int:
        return len(self.tasks)

    def __repr__(self) -> str:
        current = self.current_task.name if self.current_task else "none"
        return f"{self.name}({self.current_task_index}/{len(self.tasks)}, current={current})"

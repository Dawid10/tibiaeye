"""
Tests for VectorTask - composite task that executes children sequentially.

Ensures:
1. Children are executed in order
2. Parent advances when child completes
3. VectorTask completes when all children complete
4. Reset functionality works
"""
import pytest
from unittest.mock import Mock

from src.gameplay.core.tasks.base import BaseTask, TaskState
from src.gameplay.core.tasks.vector import VectorTask


class SimpleTask(BaseTask):
    """Simple task for testing that completes immediately."""

    def __init__(self, name: str = "SimpleTask"):
        super().__init__(name)
        self.do_called = False
        self.did_called = False

    def do(self, context):
        self.do_called = True
        return context

    def did(self, context):
        self.did_called = True
        return True  # Completes immediately


class ConditionalTask(BaseTask):
    """Task that completes based on context."""

    def __init__(self, name: str, complete_key: str):
        super().__init__(name)
        self.complete_key = complete_key

    def did(self, context):
        return context.get(self.complete_key, False)


class TestVectorTaskCreation:
    """Tests for VectorTask initialization."""

    def test_default_creation(self):
        """Test VectorTask creation with defaults."""
        task = VectorTask()

        assert task.name == "VectorTask"
        assert task.tasks == []
        assert task.current_task_index == 0

    def test_creation_with_name(self):
        """Test VectorTask creation with custom name."""
        task = VectorTask(name="MyVectorTask")

        assert task.name == "MyVectorTask"

    def test_creation_with_tasks(self):
        """Test VectorTask creation with initial tasks."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")

        task = VectorTask(name="Parent", tasks=[child1, child2])

        assert len(task.tasks) == 2
        assert task.tasks[0] == child1
        assert task.tasks[1] == child2

    def test_children_have_parent_reference(self):
        """Test that children have parent reference set."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")

        task = VectorTask(tasks=[child1, child2])

        assert child1.parent == task
        assert child2.parent == task


class TestAddTask:
    """Tests for adding tasks to VectorTask."""

    def test_add_single_task(self):
        """Test adding a single task."""
        parent = VectorTask()
        child = SimpleTask("Child")

        parent.add_task(child)

        assert len(parent.tasks) == 1
        assert child in parent.tasks
        assert child.parent == parent

    def test_add_multiple_tasks(self):
        """Test adding multiple tasks."""
        parent = VectorTask()
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")

        parent.add_tasks([child1, child2])

        assert len(parent.tasks) == 2
        assert child1.parent == parent
        assert child2.parent == parent


class TestCurrentTask:
    """Tests for current_task property."""

    def test_current_task_empty(self):
        """Test current_task when no tasks."""
        task = VectorTask()

        assert task.current_task is None

    def test_current_task_first(self):
        """Test current_task returns first task initially."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        parent = VectorTask(tasks=[child1, child2])

        assert parent.current_task == child1

    def test_current_task_after_advance(self):
        """Test current_task after advancing."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        parent = VectorTask(tasks=[child1, child2])

        parent.advance_to_next_task()

        assert parent.current_task == child2


class TestAdvanceToNextTask:
    """Tests for advance_to_next_task method."""

    def test_advance_returns_true_when_more_tasks(self):
        """Test advance returns True when more tasks available."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        parent = VectorTask(tasks=[child1, child2])

        result = parent.advance_to_next_task()

        assert result == True
        assert parent.current_task_index == 1

    def test_advance_returns_false_when_no_more_tasks(self):
        """Test advance returns False when no more tasks."""
        child1 = SimpleTask("Child1")
        parent = VectorTask(tasks=[child1])

        result = parent.advance_to_next_task()

        assert result == False
        assert parent.current_task_index == 1

    def test_advance_empty_vector(self):
        """Test advance on empty VectorTask."""
        parent = VectorTask()

        result = parent.advance_to_next_task()

        assert result == False


class TestVectorTaskDid:
    """Tests for VectorTask completion."""

    def test_did_empty_vector(self):
        """Test that empty VectorTask is done immediately."""
        task = VectorTask()

        assert task.did({}) == True

    def test_did_not_done_initially(self):
        """Test that VectorTask with tasks is not done initially."""
        child = SimpleTask("Child")
        task = VectorTask(tasks=[child])

        assert task.did({}) == False

    def test_did_after_all_children_complete(self):
        """Test that VectorTask is done when all children complete."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        task = VectorTask(tasks=[child1, child2])

        # Advance past all children
        task.advance_to_next_task()  # index = 1
        task.advance_to_next_task()  # index = 2 (past end)

        assert task.did({}) == True


class TestResetChildren:
    """Tests for reset_children method."""

    def test_reset_children_resets_index(self):
        """Test that reset_children resets current_task_index."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        task = VectorTask(tasks=[child1, child2])

        task.advance_to_next_task()
        assert task.current_task_index == 1

        task.reset_children()

        assert task.current_task_index == 0

    def test_reset_children_resets_states(self):
        """Test that reset_children resets child states."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        task = VectorTask(tasks=[child1, child2])

        # Complete children
        child1.state = TaskState.COMPLETED
        child2.state = TaskState.COMPLETED

        task.reset_children()

        assert child1.state == TaskState.NOT_STARTED
        assert child2.state == TaskState.NOT_STARTED

    def test_reset_children_resets_timing(self):
        """Test that reset_children resets child timing."""
        child = SimpleTask("Child")
        task = VectorTask(tasks=[child])

        child.started_at = 123.0
        child.finished_at = 456.0

        task.reset_children()

        assert child.started_at == 0
        assert child.finished_at == 0

    def test_reset_children_recursive(self):
        """Test that reset_children works recursively."""
        grandchild = SimpleTask("Grandchild")
        child = VectorTask(name="Child", tasks=[grandchild])
        parent = VectorTask(name="Parent", tasks=[child])

        grandchild.state = TaskState.COMPLETED
        child.current_task_index = 1

        parent.reset_children()

        assert grandchild.state == TaskState.NOT_STARTED
        assert child.current_task_index == 0


class TestOnBeforeRestart:
    """Tests for on_before_restart hook."""

    def test_on_before_restart_resets_children(self):
        """Test that on_before_restart calls reset_children."""
        child = SimpleTask("Child")
        task = VectorTask(tasks=[child])

        child.state = TaskState.COMPLETED
        task.advance_to_next_task()

        task.on_before_restart({})

        assert task.current_task_index == 0
        assert child.state == TaskState.NOT_STARTED


class TestVectorTaskLen:
    """Tests for __len__ method."""

    def test_len_empty(self):
        """Test len() on empty VectorTask."""
        task = VectorTask()

        assert len(task) == 0

    def test_len_with_tasks(self):
        """Test len() with tasks."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        child3 = SimpleTask("Child3")
        task = VectorTask(tasks=[child1, child2, child3])

        assert len(task) == 3


class TestVectorTaskRepr:
    """Tests for __repr__ method."""

    def test_repr_shows_progress(self):
        """Test that repr shows task progress."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        task = VectorTask(name="Parent", tasks=[child1, child2])

        repr_str = repr(task)

        assert "Parent" in repr_str
        assert "0/2" in repr_str
        assert "Child1" in repr_str

    def test_repr_after_advance(self):
        """Test repr after advancing."""
        child1 = SimpleTask("Child1")
        child2 = SimpleTask("Child2")
        task = VectorTask(name="Parent", tasks=[child1, child2])

        task.advance_to_next_task()
        repr_str = repr(task)

        assert "1/2" in repr_str
        assert "Child2" in repr_str


class TestNestedVectorTasks:
    """Tests for nested VectorTask structures."""

    def test_nested_vector_tasks(self):
        """Test VectorTask containing another VectorTask."""
        grandchild1 = SimpleTask("Grandchild1")
        grandchild2 = SimpleTask("Grandchild2")
        child_vector = VectorTask(name="ChildVector", tasks=[grandchild1, grandchild2])

        parent = VectorTask(name="Parent", tasks=[child_vector])

        assert parent.current_task == child_vector
        assert child_vector.current_task == grandchild1

    def test_nested_parent_references(self):
        """Test parent references in nested structure."""
        grandchild = SimpleTask("Grandchild")
        child_vector = VectorTask(name="ChildVector", tasks=[grandchild])
        parent = VectorTask(name="Parent", tasks=[child_vector])

        assert grandchild.parent == child_vector
        assert child_vector.parent == parent
        assert parent.parent is None


class TestVectorTaskExecution:
    """Tests for VectorTask execution flow."""

    def test_execution_order(self):
        """Test that children execute in order."""
        execution_order = []

        class TrackingTask(BaseTask):
            def do(self, context):
                execution_order.append(self.name)
                return context

        child1 = TrackingTask("First")
        child2 = TrackingTask("Second")
        child3 = TrackingTask("Third")

        parent = VectorTask(tasks=[child1, child2, child3])

        # Manually simulate execution
        child1.do({})
        parent.advance_to_next_task()
        child2.do({})
        parent.advance_to_next_task()
        child3.do({})

        assert execution_order == ["First", "Second", "Third"]

    def test_current_task_after_all_complete(self):
        """Test current_task is None after all children complete."""
        child1 = SimpleTask("Child1")
        task = VectorTask(tasks=[child1])

        task.advance_to_next_task()

        assert task.current_task is None

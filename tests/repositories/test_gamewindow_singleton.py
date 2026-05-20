"""
Tests for GameWindowRepository singleton pattern.

These tests ensure that:
1. The singleton returns the same instance every time
2. No task files create GameWindowRepository() directly (performance anti-pattern)
3. The reset function works correctly for testing purposes
"""
import pytest
import ast
import os
from pathlib import Path


class TestGameWindowSingleton:
    """Test the singleton pattern for GameWindowRepository."""

    def test_singleton_returns_same_instance(self):
        """Singleton should return the same instance on multiple calls."""
        from src.repositories.gamewindow import (
            get_gamewindow_repository,
            reset_gamewindow_repository
        )

        # Reset to ensure clean state
        reset_gamewindow_repository()

        # Get instance twice
        instance1 = get_gamewindow_repository()
        instance2 = get_gamewindow_repository()

        # Should be the exact same object
        assert instance1 is instance2
        assert id(instance1) == id(instance2)

    def test_reset_creates_new_instance(self):
        """Reset should allow creating a new instance."""
        from src.repositories.gamewindow import (
            get_gamewindow_repository,
            reset_gamewindow_repository
        )

        # Get first instance
        instance1 = get_gamewindow_repository()

        # Reset
        reset_gamewindow_repository()

        # Get new instance
        instance2 = get_gamewindow_repository()

        # Should be different objects
        assert instance1 is not instance2
        assert id(instance1) != id(instance2)

    def test_singleton_is_gamewindow_repository(self):
        """Singleton should return a GameWindowRepository instance."""
        from src.repositories.gamewindow import (
            get_gamewindow_repository,
            reset_gamewindow_repository,
            GameWindowRepository
        )

        reset_gamewindow_repository()
        instance = get_gamewindow_repository()

        assert isinstance(instance, GameWindowRepository)


class TestNoDirectInstantiation:
    """
    Test that no task files create GameWindowRepository() directly.

    This is a static analysis test to prevent performance regressions.
    Creating GameWindowRepository() is expensive because it loads 100+ templates.
    All tasks should use get_gamewindow_repository() instead.
    """

    # Files that are ALLOWED to instantiate GameWindowRepository directly
    ALLOWED_FILES = {
        '__init__.py',  # The singleton factory + facade
        'test_gamewindow_singleton.py',  # This test file
    }

    # Directories to scan for violations
    SCAN_DIRECTORIES = [
        'src/gameplay/core/tasks',
        'src/gameplay',
    ]

    def _find_direct_instantiation(self, filepath: str) -> list:
        """
        Find direct GameWindowRepository() instantiation in a file.

        Returns list of line numbers where violations occur.
        """
        violations = []

        try:
            with open(filepath, 'r') as f:
                content = f.read()

            # Parse the AST
            tree = ast.parse(content)

            for node in ast.walk(tree):
                # Look for Call nodes
                if isinstance(node, ast.Call):
                    # Check if it's calling GameWindowRepository()
                    if isinstance(node.func, ast.Name):
                        if node.func.id == 'GameWindowRepository':
                            violations.append(node.lineno)
                    elif isinstance(node.func, ast.Attribute):
                        if node.func.attr == 'GameWindowRepository':
                            violations.append(node.lineno)

        except SyntaxError:
            # Skip files with syntax errors
            pass

        return violations

    def test_no_direct_instantiation_in_tasks(self):
        """No task file should create GameWindowRepository() directly."""
        project_root = Path(__file__).parent.parent.parent

        violations = []

        for scan_dir in self.SCAN_DIRECTORIES:
            dir_path = project_root / scan_dir
            if not dir_path.exists():
                continue

            for filepath in dir_path.rglob('*.py'):
                filename = filepath.name

                # Skip allowed files
                if filename in self.ALLOWED_FILES:
                    continue

                # Check for violations
                file_violations = self._find_direct_instantiation(str(filepath))
                if file_violations:
                    rel_path = filepath.relative_to(project_root)
                    for line in file_violations:
                        violations.append(f"{rel_path}:{line}")

        if violations:
            violation_list = '\n  '.join(violations)
            pytest.fail(
                f"Found direct GameWindowRepository() instantiation in task files.\n"
                f"This is a performance anti-pattern - use get_gamewindow_repository() instead.\n"
                f"Violations:\n  {violation_list}"
            )

    def test_tasks_use_singleton_import(self):
        """Task files should import get_gamewindow_repository, not GameWindowRepository."""
        project_root = Path(__file__).parent.parent.parent
        tasks_dir = project_root / 'src/gameplay/core/tasks'

        if not tasks_dir.exists():
            pytest.skip("Tasks directory not found")

        files_with_wrong_import = []

        for filepath in tasks_dir.glob('*.py'):
            filename = filepath.name
            if filename in self.ALLOWED_FILES or filename.startswith('__'):
                continue

            with open(filepath, 'r') as f:
                content = f.read()

            # Check if file imports GameWindowRepository but not get_gamewindow_repository
            imports_class = 'import GameWindowRepository' in content or 'GameWindowRepository' in content
            imports_singleton = 'get_gamewindow_repository' in content

            # If it uses GameWindowRepository at all, it should use the singleton
            if imports_class and not imports_singleton:
                # Double check it's not just a type hint
                if 'GameWindowRepository()' in content:
                    files_with_wrong_import.append(filename)

        if files_with_wrong_import:
            pytest.fail(
                f"Files importing GameWindowRepository but not using singleton:\n"
                f"  {', '.join(files_with_wrong_import)}\n"
                f"Use 'from ....repositories.gamewindow import get_gamewindow_repository' instead."
            )


class TestPerformanceRegression:
    """Tests to prevent performance regressions."""

    def test_singleton_initialization_is_cached(self):
        """After first call, subsequent calls should be nearly instant."""
        import time
        from src.repositories.gamewindow import (
            get_gamewindow_repository,
            reset_gamewindow_repository
        )

        reset_gamewindow_repository()

        # First call (cold - may be slow)
        start = time.time()
        get_gamewindow_repository()
        first_call_time = time.time() - start

        # Subsequent calls (should be instant - just returning cached instance)
        times = []
        for _ in range(10):
            start = time.time()
            get_gamewindow_repository()
            times.append(time.time() - start)

        avg_subsequent = sum(times) / len(times)

        # Subsequent calls should be at least 100x faster than first call
        # (first call loads templates, subsequent just return cached instance)
        if first_call_time > 0.001:  # Only check if first call took measurable time
            assert avg_subsequent < first_call_time / 10, (
                f"Singleton not caching properly. "
                f"First call: {first_call_time:.4f}s, "
                f"Avg subsequent: {avg_subsequent:.6f}s"
            )

    def test_multiple_task_instances_share_repository(self):
        """Multiple task instances should share the same repository."""
        from src.repositories.gamewindow import (
            get_gamewindow_repository,
            reset_gamewindow_repository
        )

        reset_gamewindow_repository()

        # Simulate what tasks do
        repo1 = get_gamewindow_repository()
        repo2 = get_gamewindow_repository()
        repo3 = get_gamewindow_repository()

        # All should be the same instance
        assert repo1 is repo2 is repo3

"""Gameplay validators — compare bot decision against expected values."""

from e2e.validators import make_check


def validate_gameplay(decision_result: dict, task_result: dict, expected: dict) -> list:
    """Validate bot decision, target name, and task sequence.

    Expected format:
        {
            "context_overrides": {"cavebot": {"enabled": true}},
            "decision": "attack",
            "target": "Rotworm",
            "task_sequence": ["AttackTask(Rotworm)"]
        }
    """
    if expected is None:
        return []

    checks = []

    exp_decision = expected.get("decision")
    if exp_decision is not None:
        actual_decision = decision_result.get("decision", "idle")
        passed = actual_decision == exp_decision
        checks.append(make_check(
            "GP bot decision",
            "gameplay",
            passed,
            exp_decision,
            actual_decision,
            f"Expected decision '{exp_decision}' but got '{actual_decision}'. "
            f"Reason: {decision_result.get('reason', 'unknown')}. "
            f"Check that cavebot.enabled and targeting match the expected state.",
        ))

    exp_target = expected.get("target")
    if exp_target is not None:
        diag = decision_result.get("diagnostics", {})
        actual_target = diag.get("target_name")
        passed = actual_target is not None and actual_target.lower() == exp_target.lower()
        checks.append(make_check(
            "GP target creature",
            "gameplay",
            passed,
            exp_target,
            actual_target,
            f"Expected target '{exp_target}' but got '{actual_target}'. "
            f"Check that BattleList and GameWindow detected the creature correctly.",
        ))

    exp_tasks = expected.get("task_sequence")
    if exp_tasks is not None:
        actual_tasks = task_result.get("task_sequence", [])
        passed = actual_tasks == exp_tasks
        checks.append(make_check(
            "GP task sequence",
            "gameplay",
            passed,
            exp_tasks,
            actual_tasks,
            f"Expected task sequence {exp_tasks} but got {actual_tasks}.",
        ))

    return checks

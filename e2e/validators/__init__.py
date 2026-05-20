"""Shared validator utilities."""


def make_check(name, module, passed, expected_str, actual_str, rationale=""):
    """Create a check result dict.

    Used by all validator modules to ensure consistent format.
    """
    return {
        "name": name,
        "module": module,
        "passed": passed,
        "expected": str(expected_str),
        "actual": str(actual_str),
        "rationale": rationale if not passed else "",
    }

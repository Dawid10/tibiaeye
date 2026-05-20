"""Pathfinding validators — compare walkable grid and BFS path against expected values."""

from e2e.validators import make_check


def validate_pathfinding(pf_walkable: dict, pf_path: dict, expected: dict) -> list:
    """Validate walkable tile count range, path existence, and path max length.

    Expected format:
        {
            "walkable_tile_count_range": [20, 60],
            "path_to_target_exists": true,
            "path_max_length": 15
        }
    """
    if expected is None:
        return []

    checks = []

    count_range = expected.get("walkable_tile_count_range")
    if count_range is not None:
        walkable_count = pf_walkable["walkable_count"]
        low, high = count_range[0], count_range[1]
        passed = low <= walkable_count <= high
        checks.append(make_check(
            "PF walkable tile count",
            "pathfinding",
            passed,
            f"[{low}, {high}]",
            walkable_count,
            f"Expected walkable tiles in range [{low}, {high}] but got {walkable_count}. "
            f"Check that coordinate is valid and walkableFloorsSqms is loaded.",
        ))

    path_expected = expected.get("path_to_target_exists")
    if path_expected is not None:
        path_exists = pf_path["path_exists"]
        passed = path_exists == path_expected
        checks.append(make_check(
            "PF path to target exists",
            "pathfinding",
            passed,
            path_expected,
            path_exists,
            f"Expected path_to_target_exists={path_expected} but got {path_exists}. "
            f"BFS may have failed or target is unreachable.",
        ))

    max_length = expected.get("path_max_length")
    if max_length is not None and pf_path["path_exists"]:
        distance = pf_path["distance"] or 0
        passed = distance <= max_length
        checks.append(make_check(
            "PF path max length",
            "pathfinding",
            passed,
            f"<= {max_length}",
            distance,
            f"Expected BFS distance <= {max_length} but got {distance}. "
            f"Target creature may be farther than expected.",
        ))

    return checks

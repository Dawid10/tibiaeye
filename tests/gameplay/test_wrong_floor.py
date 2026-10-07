"""
jump_back_to_current_floor: retry a failed floor change, but never jump across the route.

Regression: start waypoint 0 (floor 6) with the character on floor 7 - the whole-route search
wrapped backwards and jumped to waypoint 44, the last floor-7 walk waypoint of the route.
"""
import json
import os


ROUTE = os.path.join(os.path.dirname(__file__), '..', '..', 'routes', 'elves-hoof-carlin.json')


def _context(waypoints, current_index, coordinate):
    return {
        'radar': {'coordinate': coordinate},
        'cavebot': {'waypoints': {'items': waypoints, 'currentIndex': current_index}},
    }


def _walk(x, y, z):
    return {'type': 'walk', 'coordinate': [x, y, z]}


def _ladder(x, y, z):
    return {'type': 'useLadder', 'coordinate': [x, y, z]}


def test_failed_ladder_rewinds_to_walk_before_it():
    from src.gameplay.core.waypoint import jump_back_to_current_floor
    waypoints = [_walk(100, 100, 7), _ladder(101, 100, 7), _walk(101, 100, 6)]
    context = _context(waypoints, 2, (101, 100, 7))

    assert jump_back_to_current_floor(context) is True
    # SetNextWaypoint adds 1 -> walk waypoint 0 again, then the ladder gets retried
    assert context['cavebot']['waypoints']['currentIndex'] == len(waypoints) - 1


def test_start_on_other_floor_holds_first_waypoint():
    from src.gameplay.core.waypoint import jump_back_to_current_floor
    with open(ROUTE) as route_file:
        waypoints = json.load(route_file)['waypoints']
    context = _context(waypoints, 0, (32438, 31730, 7))

    assert jump_back_to_current_floor(context) is False
    # SetNextWaypoint adds 1 -> back on waypoint 0, not 44
    assert context['cavebot']['waypoints']['currentIndex'] == len(waypoints) - 1


def test_far_away_floor_match_is_ignored():
    from src.gameplay.core.waypoint import jump_back_to_current_floor
    from src.core.constants import WRONG_FLOOR_LOOKBACK
    waypoints = [_walk(100, 100, 7)] + [_walk(100 + i, 100, 6) for i in range(1, WRONG_FLOOR_LOOKBACK + 3)]
    current_index = len(waypoints) - 1
    context = _context(waypoints, current_index, (100, 100, 7))

    assert jump_back_to_current_floor(context) is False
    assert context['cavebot']['waypoints']['currentIndex'] == current_index - 1


def test_warning_is_throttled(capsys):
    from src.gameplay.core.waypoint import jump_back_to_current_floor
    waypoints = [_walk(100, 100, 6), _walk(101, 100, 6)]
    context = _context(waypoints, 0, (100, 100, 7))

    jump_back_to_current_floor(context)
    context['cavebot']['waypoints']['currentIndex'] = 0
    jump_back_to_current_floor(context)

    assert capsys.readouterr().out.count('holding it') == 1

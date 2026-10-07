"""
Waypoint utilities - PyTibia style pathfinding and waypoint resolution.

This module handles:
1. A* pathfinding to generate walkpoints
2. Waypoint type resolution (walk, rope, shovel, etc.)
"""
from typing import List, Dict, Any, Optional, TypedDict
import time

import numpy as np

try:
    import tcod
    TCOD_AVAILABLE = True
except ImportError:
    TCOD_AVAILABLE = False

from ...core.constants import WRONG_FLOOR_LOOKBACK, WRONG_FLOOR_WARNING_INTERVAL, WAYPOINT_JUMP_MAX_FORWARD
from ...repositories.radar import config as _radar_cfg
from ...repositories.radar import (
    get_pixel_from_coordinate,
    get_coordinate_from_pixel,
    get_available_around_coordinates,
    get_closest_coordinate,
    Coordinate,
    CoordinateList,
)


class Checkpoint(TypedDict):
    """Checkpoint for navigation validation."""
    goalCoordinate: Coordinate
    checkInCoordinate: Coordinate


def generate_floor_walkpoints(
    coordinate: Coordinate,
    goal_coordinate: Coordinate,
    non_walkable_coordinates: CoordinateList = None
) -> CoordinateList:
    """
    Generate path from current to goal using A* pathfinding.

    Args:
        coordinate: Starting (x, y, z) coordinate
        goal_coordinate: Target (x, y, z) coordinate
        non_walkable_coordinates: Additional blocked coordinates (monsters, etc.)

    Returns:
        List of coordinates to walk through
    """
    if non_walkable_coordinates is None:
        non_walkable_coordinates = []

    # Different floors - can't pathfind
    if coordinate[2] != goal_coordinate[2]:
        return [goal_coordinate]

    # Convert to pixel coordinates
    pixel_coord = get_pixel_from_coordinate(coordinate)
    goal_pixel = get_pixel_from_coordinate(goal_coordinate)

    # Define radar window (106x109 around player)
    x_start = pixel_coord[0] - 53
    x_end = pixel_coord[0] + 53
    y_start = pixel_coord[1] - 54
    y_end = pixel_coord[1] + 55

    floor = coordinate[2]

    # Copy walkable matrix for this area
    _radar_cfg._ensure_loaded()
    try:
        walkable = _radar_cfg.walkableFloorsSqms[floor][y_start:y_end, x_start:x_end].copy()
    except IndexError:
        # Out of bounds - return direct path
        return [goal_coordinate]

    # Mark non-walkable coordinates (monsters, etc.)
    for nw_coord in non_walkable_coordinates:
        if nw_coord[2] == floor:
            nw_pixel = get_pixel_from_coordinate(nw_coord)
            local_x = nw_pixel[0] - x_start
            local_y = nw_pixel[1] - y_start
            if 0 <= local_x < 106 and 0 <= local_y < 109:
                walkable[local_y, local_x] = 0

    # Calculate goal in local coordinates
    goal_local_x = goal_pixel[0] - x_start
    goal_local_y = goal_pixel[1] - y_start

    # Player is at center of radar (53, 54 in local coords)
    start_local_x = 53
    start_local_y = 54

    # Check if goal is within radar range
    if not (0 <= goal_local_x < 106 and 0 <= goal_local_y < 109):
        # Goal outside radar - walk towards it
        return [goal_coordinate]

    if TCOD_AVAILABLE:
        # Use A* pathfinding
        try:
            astar = tcod.path.AStar(walkable, 0)  # 0 = diagonal cost
            path = astar.get_path(start_local_y, start_local_x, goal_local_y, goal_local_x)

            # Convert path back to world coordinates
            result = []
            for local_y, local_x in path:
                world_x = (x_start + local_x) + 31744
                world_y = (y_start + local_y) + 30976
                result.append((world_x, world_y, floor))

            return result if result else [goal_coordinate]

        except Exception as e:
            print(f"[Pathfinding] A* pathfinding failed: {e}")

    # Fallback: simple straight-line path
    return _generate_simple_path(coordinate, goal_coordinate)


def _generate_simple_path(start: Coordinate, goal: Coordinate) -> CoordinateList:
    """Generate simple straight-line path without obstacle avoidance."""
    path = []
    x, y, z = start
    gx, gy, gz = goal

    while x != gx or y != gy:
        if x < gx:
            x += 1
        elif x > gx:
            x -= 1

        if y < gy:
            y += 1
        elif y > gy:
            y -= 1

        path.append((x, y, z))

    return path if path else [goal]

def generate_global_walkpoints(
    coordinate: Coordinate,
    goal_coordinate: Coordinate,
    max_path_length: int = 50
) -> CoordinateList:
    """
    Generate path using the FULL floor walkable matrix (not just radar range).

    Use this when the goal is far away and outside the normal radar range.

    Args:
        coordinate: Starting (x, y, z) coordinate
        goal_coordinate: Target (x, y, z) coordinate
        max_path_length: Maximum steps to return (for performance)

    Returns:
        List of coordinates to walk through (limited to max_path_length)
    """
    if coordinate[2] != goal_coordinate[2]:
        return [goal_coordinate]

    if not TCOD_AVAILABLE:
        return _generate_simple_path(coordinate, goal_coordinate)

    floor = coordinate[2]

    start_pixel = get_pixel_from_coordinate(coordinate)
    goal_pixel = get_pixel_from_coordinate(goal_coordinate)

    try:
        _radar_cfg._ensure_loaded()
        floor_walkable = _radar_cfg.walkableFloorsSqms[floor]

        if floor_walkable is None:
            return _generate_simple_path(coordinate, goal_coordinate)

        start_y, start_x = start_pixel[1], start_pixel[0]
        goal_y, goal_x = goal_pixel[1], goal_pixel[0]

        if not (0 <= start_x < floor_walkable.shape[1] and 0 <= start_y < floor_walkable.shape[0]):
            return _generate_simple_path(coordinate, goal_coordinate)
        if not (0 <= goal_x < floor_walkable.shape[1] and 0 <= goal_y < floor_walkable.shape[0]):
            return _generate_simple_path(coordinate, goal_coordinate)

        astar = tcod.path.AStar(floor_walkable, diagonal=0)
        path = astar.get_path(start_y, start_x, goal_y, goal_x)

        if not path:
            print(f"[Pathfinding] A* failed, using greedy pathfinding...")

        if len(path) > max_path_length:
            path = path[:max_path_length]

        result = []
        for pixel_y, pixel_x in path:
            world_coord = get_coordinate_from_pixel((pixel_x, pixel_y), floor)
            result.append(world_coord)

        print(f"[Pathfinding] Global path: {len(result)} steps (total would be {len(path)})")
        return result

    except Exception as e:
        print(f"[Pathfinding] Global pathfinding error: {e}")
        return _generate_simple_path(coordinate, goal_coordinate)


def resolve_floor_coordinate(_, next_coordinate: Coordinate) -> Checkpoint:
    """Resolve standard walk waypoint."""
    return {
        'goalCoordinate': next_coordinate,
        'checkInCoordinate': next_coordinate,
    }


def resolve_move_down_coordinate(_, waypoint: Dict[str, Any]) -> Checkpoint:
    """Resolve moveDown waypoint (descend stairs/hole)."""
    coord = waypoint['coordinate']
    direction = waypoint.get('options', {}).get('direction', 'south')

    check_in = None
    if direction == 'north':
        check_in = (coord[0], coord[1] - 2, coord[2] + 1)
    elif direction == 'south':
        check_in = (coord[0], coord[1] + 2, coord[2] + 1)
    elif direction == 'east':
        check_in = (coord[0] + 2, coord[1], coord[2] + 1)
    else:  # west
        check_in = (coord[0] - 2, coord[1], coord[2] + 1)

    return {
        'goalCoordinate': tuple(coord),
        'checkInCoordinate': check_in,
    }


def resolve_move_up_coordinate(_, waypoint: Dict[str, Any]) -> Checkpoint:
    """Resolve moveUp waypoint (climb stairs/ladder)."""
    coord = waypoint['coordinate']
    direction = waypoint.get('options', {}).get('direction', 'south')

    check_in = None
    if direction == 'north':
        check_in = (coord[0], coord[1] - 2, coord[2] - 1)
    elif direction == 'south':
        check_in = (coord[0], coord[1] + 2, coord[2] - 1)
    elif direction == 'east':
        check_in = (coord[0] + 2, coord[1], coord[2] - 1)
    else:  # west
        check_in = (coord[0] - 2, coord[1], coord[2] - 1)

    return {
        'goalCoordinate': tuple(coord),
        'checkInCoordinate': check_in,
    }


def resolve_use_shovel_coordinate(coordinate: Coordinate, next_coordinate: Coordinate) -> Checkpoint:
    """Resolve useShovel waypoint."""
    # Find walkable position near the hole
    _radar_cfg._ensure_loaded()
    floor = next_coordinate[2]
    available = get_available_around_coordinates(next_coordinate, _radar_cfg.walkableFloorsSqms[floor])
    closest = get_closest_coordinate(coordinate, available)

    return {
        'goalCoordinate': closest if closest else next_coordinate,
        'checkInCoordinate': (next_coordinate[0], next_coordinate[1], next_coordinate[2] + 1),
    }


def resolve_use_rope_coordinate(_, next_coordinate: Coordinate) -> Checkpoint:
    """Resolve useRope waypoint."""
    return {
        'goalCoordinate': (next_coordinate[0], next_coordinate[1], next_coordinate[2]),
        'checkInCoordinate': (next_coordinate[0], next_coordinate[1] + 1, next_coordinate[2] - 1),
    }


def resolve_use_hole_coordinate(_, next_coordinate: Coordinate) -> Checkpoint:
    """Resolve useHole waypoint."""
    return {
        'goalCoordinate': next_coordinate,
        'checkInCoordinate': (next_coordinate[0], next_coordinate[1], next_coordinate[2] + 1),
    }


def resolve_use_teleport_coordinate(_, waypoint: Dict[str, Any]) -> Checkpoint:
    """Resolve useTeleport waypoint."""
    coord = tuple(waypoint['coordinate'])
    return {
        'goalCoordinate': coord,
        'checkInCoordinate': coord,
    }


def _get_closest_forward_waypoint_index(
    current_coord: tuple,
    waypoints: list,
    current_index: int,
    max_forward: int,
) -> Optional[int]:
    """
    Find the closest waypoint by distance, searching only FORWARD in sequence.

    Prevents jumping to return-path waypoints that share the same physical
    location (e.g., going to depot vs coming back from depot).
    """
    from scipy.spatial import distance

    closest_index = None
    closest_distance = float('inf')
    total = len(waypoints)

    for offset in range(1, min(max_forward, total)):
        candidate_index = (current_index + offset) % total
        wp_coord = waypoints[candidate_index].get('coordinate')
        if wp_coord is None:
            continue
        if wp_coord[2] != current_coord[2]:
            continue

        dist = distance.euclidean(
            (current_coord[0], current_coord[1]),
            (wp_coord[0], wp_coord[1]),
        )
        if dist < closest_distance:
            closest_distance = dist
            closest_index = candidate_index

    return closest_index


def jump_to_closest_waypoint(context: Dict[str, Any], force: bool = False) -> bool:
    """
    Jump to the closest reachable waypoint, searching only forward in sequence.

    Only searches the next WAYPOINT_JUMP_MAX_FORWARD waypoints (at most a third of the route) to
    avoid jumping to return-path waypoints that share the same physical location, or past a
    ladder/stairs into a part of the route on another floor.

    Args:
        context: Game context dict
        force: If True, skip creature/attack checks (used by stuck recovery)

    Returns:
        True if jumped to a different waypoint
    """
    if not force:
        is_attacking = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        if is_attacking:
            return False

        creatures = context.get('battleList', {}).get('creatures', [])
        if len(creatures) > 0:
            return False

    current_coord = context.get('radar', {}).get('coordinate')
    if current_coord is None:
        return False

    waypoints_data = context.get('cavebot', {}).get('waypoints', {})
    waypoints = waypoints_data.get('items', [])
    if not waypoints:
        return False

    current_index = waypoints_data.get('currentIndex', 0)
    # A third of the route was 31 waypoints on a 94-waypoint route - far past ladders and stairs.
    # +1: the search range end is exclusive
    max_forward = min(max(1, len(waypoints) // 3), WAYPOINT_JUMP_MAX_FORWARD + 1)

    closest_index = _get_closest_forward_waypoint_index(
        current_coord, waypoints, current_index, max_forward,
    )

    if closest_index is None:
        return False

    if closest_index == current_index:
        return False

    context['cavebot']['waypoints']['currentIndex'] = closest_index
    print(f"[Walk] UNSTUCK: Jumped from waypoint {current_index} to forward waypoint {closest_index}")
    return True


def jump_back_to_current_floor(context: Dict[str, Any]) -> bool:
    """
    After a failed floor change, rewind to the last walk waypoint on our floor
    so the floor-change waypoint that follows it gets retried.

    Looks back only WRONG_FLOOR_LOOKBACK waypoints: a failed ladder is right behind us. Searching the
    whole route jumped a character that simply started on another floor to wherever the route last
    visits that floor (waypoint 0 on floor 6, player on 7 -> waypoint 44). Nothing close by means
    the player isn't on the route: hold the current waypoint and say so.
    """
    current_coord = context.get('radar', {}).get('coordinate')
    if current_coord is None:
        return False

    waypoints_data = context.get('cavebot', {}).get('waypoints', {})
    waypoints = waypoints_data.get('items', [])
    current_index = waypoints_data.get('currentIndex', 0)
    total = len(waypoints)

    for offset in range(1, min(WRONG_FLOOR_LOOKBACK + 1, total)):
        candidate_index = (current_index - offset) % total
        waypoint = waypoints[candidate_index]
        wp_coord = waypoint.get('coordinate')
        if wp_coord is None or wp_coord[2] != current_coord[2]:
            continue
        if waypoint.get('type', 'walk') != 'walk':
            continue
        # SetNextWaypoint runs after this and adds 1
        waypoints_data['currentIndex'] = (candidate_index - 1) % total
        print(f"[Walk] Wrong floor {current_coord[2]} for waypoint {current_index} - "
              f"going back to waypoint {candidate_index} to retry the floor change")
        return True

    _hold_waypoint_on_wrong_floor(waypoints_data, waypoints[current_index], current_coord)
    return False


def _hold_waypoint_on_wrong_floor(waypoints_data: Dict[str, Any], waypoint: Dict[str, Any], current_coord) -> None:
    current_index = waypoints_data.get('currentIndex', 0)
    # SetNextWaypoint runs after this and adds 1 - land back on the same waypoint
    waypoints_data['currentIndex'] = (current_index - 1) % len(waypoints_data.get('items', [waypoint]))
    now = time.time()
    if now - waypoints_data.get('_wrongFloorWarnedAt', 0) < WRONG_FLOOR_WARNING_INTERVAL:
        return
    waypoints_data['_wrongFloorWarnedAt'] = now
    print(f"[Walk] On floor {current_coord[2]}, but waypoint {current_index} is on floor "
          f"{waypoint.get('coordinate', [0, 0, '?'])[2]} - holding it. Move the character to that floor "
          f"(or pick another start waypoint)")


def resolve_goal_coordinate(coordinate: Coordinate, waypoint: Dict[str, Any]) -> Checkpoint:
    """
    Resolve goal and check-in coordinates for a waypoint.

    Args:
        coordinate: Current player coordinate
        waypoint: Waypoint dict with type, coordinate, options

    Returns:
        Checkpoint with goalCoordinate and checkInCoordinate
    """
    wp_type = waypoint.get('type', 'walk')
    wp_coord = tuple(waypoint.get('coordinate', coordinate))

    if wp_type == 'useRope':
        return resolve_use_rope_coordinate(coordinate, wp_coord)
    elif wp_type == 'useShovel':
        return resolve_use_shovel_coordinate(coordinate, wp_coord)
    elif wp_type == 'moveDown':
        return resolve_move_down_coordinate(coordinate, waypoint)
    elif wp_type == 'moveUp':
        return resolve_move_up_coordinate(coordinate, waypoint)
    elif wp_type == 'useHole':
        return resolve_use_hole_coordinate(coordinate, wp_coord)
    elif wp_type == 'useTeleport':
        return resolve_use_teleport_coordinate(coordinate, waypoint)
    else:
        return resolve_floor_coordinate(coordinate, wp_coord)

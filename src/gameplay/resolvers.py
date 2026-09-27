"""
Waypoint Resolvers - Convert waypoints to tasks.

PyTibia style: each waypoint type maps to a specific task or task tree.
"""
from typing import Any, Dict, Optional

from ..core.constants import WALK_MAP_CLICK_ARRIVE_DISTANCE

from .core.tasks import (
    BaseTask,
    VectorTask,
    WalkToWaypointTask,
    WalkToCoordinateTask,
    UseRopeTask,
    UseShovelTask,
    UseLadderTask,
    UseHoleTask,
    UseHotkeyTask,
    SetNextWaypointTask,
    AttackClosestCreatureTask,
    LootCorpseTask,
    RefillCheckerTask,
    DepositGoldTask,
    RefillTask,
    RefillPotionsTask,
    DepositItemsTask,
    DropFlasksTask,
)


def _arrive_distance_for_walk(context: Dict[str, Any]) -> int:
    """Pass through walk waypoints loosely; floor changes etc. need the exact tile."""
    waypoints = context.get('cavebot', {}).get('waypoints', {})
    items = waypoints.get('items', [])
    if not items:
        return 0
    next_waypoint = items[(waypoints.get('currentIndex', 0) + 1) % len(items)]
    if next_waypoint.get('type', 'walk') != 'walk':
        return 0
    return WALK_MAP_CLICK_ARRIVE_DISTANCE


def resolve_tasks_by_waypoint(waypoint: Dict[str, Any], context: Dict[str, Any]) -> Optional[BaseTask]:
    """
    Convert a waypoint to the appropriate task.

    Waypoint format:
    {
        'type': 'walk',
        'coordinate': (x, y, z),
        'label': 'optional_name',
        'options': {
            'direction': 'north',  # For moveUp/moveDown
            ...
        }
    }
    """
    waypoint_type = waypoint.get('type', 'walk')
    coordinate = waypoint.get('coordinate')
    options = waypoint.get('options', {})

    if waypoint_type == 'walk':
        if coordinate:
            return WalkToWaypointTask(tuple(coordinate), _arrive_distance_for_walk(context))
        return None

    elif waypoint_type == 'moveUp':
        # Climb stairs
        direction = options.get('direction', 'up')
        task = VectorTask("MoveUp")
        task.add_task(UseLadderTask(direction))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'moveDown':
        # Descend hole/stairs
        direction = options.get('direction', 'down')
        task = VectorTask("MoveDown")
        task.add_task(UseLadderTask(direction))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'useRope':
        hotkey = options.get('hotkey', 'o')
        task = VectorTask("UseRopeWaypoint")
        # First walk to the rope spot
        if coordinate:
            task.add_task(WalkToCoordinateTask(tuple(coordinate)))
        # Then use the rope (press hotkey + click on current tile)
        task.add_task(UseRopeTask(hotkey, tuple(coordinate) if coordinate else None))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'useShovel':
        hotkey = options.get('hotkey', 'p')
        direction = options.get('direction')  # 'north', 'south', 'east', 'west'
        task = VectorTask("UseShovelWaypoint")
        # First walk to the shovel spot (where player stands)
        if coordinate:
            task.add_task(WalkToCoordinateTask(tuple(coordinate)))
        # Then use the shovel in the specified direction
        task.add_task(UseShovelTask(hotkey, direction=direction))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'useHole':
        # Right-click on ladder/hole to descend
        task = VectorTask("UseHoleWaypoint")
        # First walk to the hole
        if coordinate:
            task.add_task(WalkToCoordinateTask(tuple(coordinate)))
        # Then right-click to use the ladder/hole
        task.add_task(UseHoleTask(tuple(coordinate) if coordinate else None))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'useLadder':
        # Right-click on ladder to climb (same as useHole)
        task = VectorTask("UseLadderWaypoint")
        # First walk to the ladder
        if coordinate:
            task.add_task(WalkToCoordinateTask(tuple(coordinate)))
        # Then right-click to use the ladder
        task.add_task(UseHoleTask(tuple(coordinate) if coordinate else None))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'useTeleport':
        # Walk into teleport
        if coordinate:
            return WalkToWaypointTask(tuple(coordinate))
        return None

    elif waypoint_type == 'label':
        # Just a marker, skip
        task = SetNextWaypointTask()
        return task

    elif waypoint_type == 'stand':
        # Just advance to next
        task = SetNextWaypointTask()
        return task

    elif waypoint_type == 'useHotkey':
        hotkey = options.get('hotkey', 'space')
        task = VectorTask("UseHotkeyWaypoint")
        task.add_task(UseHotkeyTask(hotkey))
        task.add_task(SetNextWaypointTask())
        return task

    elif waypoint_type == 'refillChecker':
        # Check if refill is needed (potions + cap)
        return RefillCheckerTask(waypoint)

    elif waypoint_type == 'depositGold':
        # Deposit gold at banker
        return DepositGoldTask(waypoint)

    elif waypoint_type == 'refill':
        # Buy potions from NPC (old chat-based method)
        return RefillTask(waypoint)

    elif waypoint_type == 'refillPotions':
        # Buy potions from NPC (new GUI-based method with search box)
        try:
            task = RefillPotionsTask(waypoint)
            print(f"[Resolver] Created RefillPotionsTask: {task}")
            return task
        except Exception as e:
            print(f"[Resolver] ERROR creating RefillPotionsTask: {e}")
            import traceback
            traceback.print_exc()
            return None

    elif waypoint_type == 'depositItems':
        # Deposit items at depot
        return DepositItemsTask(waypoint)

    elif waypoint_type == 'dropFlasks':
        # Drop empty flasks
        hotkey = options.get('hotkey', 'f')
        task = VectorTask("DropFlasksWaypoint")
        task.add_task(DropFlasksTask(hotkey))
        task.add_task(SetNextWaypointTask())
        return task

    else:
        # Unknown type, skip
        print(f"Unknown waypoint type: {waypoint_type}")
        return SetNextWaypointTask()


def resolve_cavebot_tasks(context: Dict[str, Any]) -> Optional[BaseTask]:
    """
    Resolve cavebot task when monsters are present.

    Returns AttackClosestCreatureTask when there are creatures to attack.
    """
    # Check all sources for creatures
    if has_creatures_to_attack(context):
        return AttackClosestCreatureTask()

    return None


def get_current_waypoint(context: Dict[str, Any]) -> Optional[Dict[str, Any]]:
    """Get the current waypoint from context."""
    waypoints = context.get('cavebot', {}).get('waypoints', {})
    items = waypoints.get('items', [])
    current_index = waypoints.get('currentIndex', 0)

    if 0 <= current_index < len(items):
        return items[current_index]

    return None


def has_creatures_to_attack(context: Dict[str, Any]) -> bool:
    """
    Check if there are REACHABLE creatures to attack.

    This is the single source of truth for deciding if we should enter combat.
    Uses closestCreature from pathfinding - if it's None, no creature is reachable.
    """
    battle_list = context.get('battleList', {}).get('creatures', [])

    # No creatures at all = nothing to attack
    if len(battle_list) == 0:
        return False

    # Creatures exist - but are any reachable?
    # closestCreature is calculated by pathfinding in gamewindow_middleware
    closest_creature = context.get('cavebot', {}).get('closestCreature')

    # Only return True if we have a reachable creature
    return closest_creature is not None

"""
Cavebot - PyTibia style cavebot logic.

Handles the decision making:
1. If monsters present -> attack
2. Else -> follow waypoints
"""
from typing import Any, Dict, Optional

from ..core.tasks import BaseTask, TasksOrchestrator
from ..resolvers import (
    resolve_tasks_by_waypoint,
    resolve_cavebot_tasks,
    get_current_waypoint,
    has_creatures_to_attack,
)


def handle_cavebot(context: Dict[str, Any], orchestrator: TasksOrchestrator) -> Dict[str, Any]:
    """
    Main cavebot handler - called every game loop.

    Decision flow:
    1. If there are creatures to attack -> enter combat
    2. Else if following waypoints -> navigate
    3. Handle loot if needed
    """
    # Skip if cavebot disabled
    cavebot_enabled = context.get('cavebot', {}).get('enabled', False)
    if not cavebot_enabled:
        return context

    # Check current state
    creatures = context.get('battleList', {}).get('creatures', [])
    is_idle = orchestrator.is_idle
    current_task = orchestrator.current_task_name

    # If orchestrator is busy with an attack task, let it continue
    if not is_idle:
        # But if task is not attack-related and creatures to attack appeared, interrupt!
        # Click attack: only with closestCreature (pathfinding confirmed reachability).
        # Space attack: any targetable monster in the battle list - so it fights while walking.
        uninterruptible = {
            'AttackClosestCreature', 'ClickInClosestCreature', 'WalkToTargetCreature', 'SpaceAttack',
            'AttackTrappedCreature',
            'UseHole', 'UseRope', 'UseShovel', 'SetNextWaypoint',
            'idle', 'completing',
        }
        is_uninterruptible = current_task in uninterruptible or current_task.startswith('UseLadder')
        if has_creatures_to_attack(context) and not is_uninterruptible:
            print(f"[Cavebot] Interrupting {current_task} to attack {len(creatures)} reachable creatures!")
            task = resolve_cavebot_tasks(context)
            if task is not None:
                orchestrator.set_root_task(task)
        return context

    # Priority 1: Loot corpses
    corpses = context.get('loot', {}).get('corpsesToLoot', [])
    if corpses and context.get('loot', {}).get('enabled', False):
        from ..core.tasks import LootCorpseTask
        hotkey = context.get('loot', {}).get('hotkey', 'g')
        orchestrator.set_root_task(LootCorpseTask(hotkey))
        context['loot']['corpsesToLoot'] = corpses[1:]  # Remove first
        return context

    # Priority 2: Attack REACHABLE creatures (PyTibia style)
    # has_creatures_to_attack now only returns True if closestCreature exists
    if has_creatures_to_attack(context):
        task = resolve_cavebot_tasks(context)
        if task is not None:
            closest = context.get('cavebot', {}).get('closestCreature')
            print(f"[Cavebot] Starting attack! {len(creatures)} in battle list, attacking: {closest.name if closest else 'unknown'}")
            orchestrator.set_root_task(task)
            return context

    # Priority 3: Follow waypoints
    waypoint = get_current_waypoint(context)
    if waypoint:
        wp_type = waypoint.get('type', 'unknown')
        wp_coord = waypoint.get('coordinate')
        wp_idx = context.get('cavebot', {}).get('waypoints', {}).get('currentIndex', -1)
        print(f"[Cavebot] Processing waypoint {wp_idx}: type={wp_type}, coord={wp_coord}")

        try:
            task = resolve_tasks_by_waypoint(waypoint, context)
            if task is not None:
                print(f"[Cavebot] Created task: {task.name}")
                orchestrator.set_root_task(task)
            else:
                print(f"[Cavebot] WARNING: resolve_tasks_by_waypoint returned None for waypoint {wp_idx}")
        except Exception as e:
            print(f"[Cavebot] ERROR resolving waypoint {wp_idx}: {e}")
            import traceback
            traceback.print_exc()
    else:
        waypoints_info = context.get('cavebot', {}).get('waypoints', {})
        print(f"[Cavebot] No current waypoint! items={len(waypoints_info.get('items', []))}, currentIndex={waypoints_info.get('currentIndex')}")

    return context


def load_waypoints_from_file(filepath: str) -> list:
    """
    Load waypoints from a JSON file.

    File format:
    {
        "waypoints": [
            {"type": "walk", "coordinate": [32000, 32000, 7]},
            {"type": "useRope", "options": {"hotkey": "t"}},
            ...
        ]
    }
    """
    import json
    import os

    if not os.path.exists(filepath):
        print(f"Waypoints file not found: {filepath}")
        return []

    try:
        with open(filepath, 'r') as f:
            data = json.load(f)

        waypoints = data.get('waypoints', [])
        print(f"Loaded {len(waypoints)} waypoints from {filepath}")
        return waypoints

    except Exception as e:
        print(f"Error loading waypoints: {e}")
        return []



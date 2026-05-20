"""Gameplay detectors — simulate bot decision-making from detection results."""
import time
from typing import Any, Dict, List, Optional


def build_context(
    bl_result: dict,
    radar_result: dict,
    gw_result: dict,
    sb_result: dict,
    context_overrides: Optional[Dict[str, Any]] = None,
) -> dict:
    """Build a minimal context dict from detection results + optional overrides.

    Mirrors the structure populated by GameLoop middlewares so that gameplay
    logic (handle_cavebot, TargetingFilter) can run against e2e data.
    """
    context = {
        "screenshot": None,
        "radar": {
            "coordinate": radar_result.get("coordinate"),
            "previousCoordinate": None,
            "lastCoordinateVisited": None,
        },
        "battleList": {
            "creatures": bl_result.get("creatures", []),
            "beingAttackedCreatureCategory": None,
        },
        "gameWindow": {
            "coordinate": gw_result.get("game_window_position"),
            "image": gw_result.get("game_window_image"),
            "monsters": gw_result.get("monsters", []),
            "players": gw_result.get("players", []),
            "creatures": gw_result.get("creatures", []),
            "previousMonsters": [],
            "monstersBars": gw_result.get("bars", []),
        },
        "statusBar": {
            "hp": 0,
            "hpPercentage": sb_result.get("hp_percent") or 100,
            "mana": 0,
            "manaPercentage": sb_result.get("mana_percent") or 100,
        },
        "cavebot": {
            "enabled": False,
            "waypoints": {"items": [], "currentIndex": 0, "indexBeforeCombat": None},
            "targetCreature": None,
            "closestCreature": gw_result.get("closest"),
            "isAttackingSomeCreature": False,
            "holesOrStairs": [],
            "nonWalkableCoordinates": [],
            "stuckAlert": {"enabled": False, "timeoutSeconds": 120},
        },
        "targeting": {
            "enabled": True,
            "mode": "all",
            "whitelist": [],
            "blacklist": [],
            "creatures": {},
        },
        "healing": {"enabled": False, "spells": [], "potions": []},
        "loot": {"enabled": False, "hotkey": "g", "corpsesToLoot": []},
        "pause": False,
        "tasksOrchestrator": None,
        "playerSpeed": 110,
    }

    if context_overrides:
        _deep_merge(context, context_overrides)

    return context


def _deep_merge(base: dict, overrides: dict) -> None:
    """Merge overrides into base dict recursively in place."""
    for key, value in overrides.items():
        if key in base and isinstance(base[key], dict) and isinstance(value, dict):
            _deep_merge(base[key], value)
        else:
            base[key] = value


def detect_targeting(creatures: list, context_overrides: Optional[Dict] = None) -> dict:
    """Filter creatures by whitelist/blacklist from context_overrides.

    Returns dict with:
        filtered        — list of creature objects after targeting filter
        mode            — str ('all', 'whitelist', 'blacklist')
        timing_ms       — float
        diagnostics     — dict
    """
    from src.gameplay.targeting import TargetingFilter

    t0 = time.perf_counter()

    targeting_config = {}
    if context_overrides:
        targeting_config = context_overrides.get("targeting", {})

    mock_context = {
        "targeting": {
            "enabled": True,
            "mode": "all",
            "whitelist": [],
            "blacklist": [],
            **targeting_config,
        }
    }

    targeting_filter = TargetingFilter()
    filtered = targeting_filter.filter(creatures, mock_context)
    mode = mock_context["targeting"].get("mode", "all")

    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "total_input": len(creatures),
        "total_filtered": len(filtered),
        "mode": mode,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "filtered": filtered,
        "mode": mode,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_decision(context: dict) -> dict:
    """Determine what the bot would do given the current context.

    Returns dict with:
        decision        — str: 'attack', 'loot', 'walk', 'idle'
        reason          — str
        timing_ms       — float
        diagnostics     — dict
    """
    t0 = time.perf_counter()

    decision = "idle"
    reason = "no action"

    cavebot = context.get("cavebot", {})
    targeting = context.get("targeting", {})

    if not cavebot.get("enabled", False):
        decision = "idle"
        reason = "cavebot disabled"
        timing_ms = (time.perf_counter() - t0) * 1000
        return {
            "decision": decision,
            "reason": reason,
            "timing_ms": timing_ms,
            "diagnostics": {"reason": reason, "time_ms": round(timing_ms, 2)},
        }

    # Check loot
    loot_config = context.get("loot", {})
    corpsesToLoot = cavebot.get("corpsesToLoot", []) or context.get("loot", {}).get("corpsesToLoot", [])
    if corpsesToLoot and loot_config.get("enabled", False):
        decision = "loot"
        reason = f"{len(corpsesToLoot)} corpse(s) to loot"
        timing_ms = (time.perf_counter() - t0) * 1000
        return {
            "decision": decision,
            "reason": reason,
            "timing_ms": timing_ms,
            "diagnostics": {"reason": reason, "time_ms": round(timing_ms, 2)},
        }

    # Check monsters to attack
    monsters = context.get("gameWindow", {}).get("monsters", [])
    if monsters and targeting.get("enabled", True):
        from src.gameplay.targeting import TargetingFilter
        targeting_filter = TargetingFilter()
        filtered = targeting_filter.filter(monsters, context)
        if filtered:
            closest = cavebot.get("closestCreature") or (filtered[0] if filtered else None)
            decision = "attack"
            reason = f"target: {getattr(closest, 'name', 'unknown')}"
            timing_ms = (time.perf_counter() - t0) * 1000
            return {
                "decision": decision,
                "reason": reason,
                "timing_ms": timing_ms,
                "diagnostics": {
                    "reason": reason,
                    "target_name": getattr(closest, "name", None),
                    "time_ms": round(timing_ms, 2),
                },
            }

    # Check waypoints
    waypoints = cavebot.get("waypoints", {})
    if waypoints.get("items"):
        decision = "walk"
        reason = f"{len(waypoints['items'])} waypoint(s)"
    else:
        decision = "idle"
        reason = "no waypoints, no targets"

    timing_ms = (time.perf_counter() - t0) * 1000
    return {
        "decision": decision,
        "reason": reason,
        "timing_ms": timing_ms,
        "diagnostics": {"reason": reason, "time_ms": round(timing_ms, 2)},
    }


def detect_task_sequence(context: dict, decision_result: dict, target) -> dict:
    """Determine what task sequence the bot would create.

    Returns dict with:
        task_sequence   — list of str task descriptions
        timing_ms       — float
        diagnostics     — dict
    """
    t0 = time.perf_counter()

    decision = decision_result.get("decision", "idle")
    task_sequence = []

    if decision == "attack" and target is not None:
        name = getattr(target, "name", "unknown")
        task_sequence = [f"AttackTask({name})"]

    elif decision == "loot":
        task_sequence = ["LootTask"]

    elif decision == "walk":
        waypoints = context.get("cavebot", {}).get("waypoints", {})
        items = waypoints.get("items", [])
        if items:
            idx = waypoints.get("currentIndex", 0)
            wp = items[idx] if idx < len(items) else items[0]
            label = wp.get("label", wp.get("coordinate", "?")) if isinstance(wp, dict) else str(wp)
            task_sequence = [f"WalkTask({label})"]
        else:
            task_sequence = ["WalkTask"]

    timing_ms = (time.perf_counter() - t0) * 1000

    return {
        "task_sequence": task_sequence,
        "timing_ms": timing_ms,
        "diagnostics": {
            "decision": decision,
            "task_count": len(task_sequence),
            "time_ms": round(timing_ms, 2),
        },
    }

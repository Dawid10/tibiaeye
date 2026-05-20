"""
Default configuration - single source of truth for all config values.

- GUI config (gui_config.json) defaults live here.
- Bot context defaults (stuck alert, cavebot, etc.) use the same values.
- constants.py keeps only non-configurable technical constants (grid, radar, delays).
"""

from typing import Any, Dict


def _get_by_path(data: Dict, path: str) -> Any:
    """Get value by dot-notation key (e.g. 'general.stuckAlertTimeout')."""
    keys = path.split(".")
    value = data
    for k in keys:
        if isinstance(value, dict) and k in value:
            value = value[k]
        else:
            return None
    return value


# -----------------------------------------------------------------------------
# Default config: used by ConfigManager (GUI) and as fallback in bot code.
# All user-configurable and bot-behavior defaults in one place.
# -----------------------------------------------------------------------------
DEFAULT_CONFIG: Dict[str, Any] = {
    "healing": {
        "healthPotion": {
            "enabled": True,
            "threshold": 30,
            "hotkey": "1",
            "cooldown": 1.0,
        },
        "manaPotion": {
            "enabled": True,
            "threshold": 50,
            "hotkey": "2",
            "cooldown": 1.0,
        },
        "spells": [
            {"name": "Emergency Heal", "enabled": True, "threshold": 20, "spell": "exura vita", "hotkey": "F1", "minMana": 10},
            {"name": "Strong Heal", "enabled": True, "threshold": 40, "spell": "exura gran", "hotkey": "F2", "minMana": 10},
            {"name": "Light Heal", "enabled": True, "threshold": 70, "spell": "exura", "hotkey": "F3", "minMana": 10},
        ],
        "food": {
            "enabled": True,
            "threshold": 5,
            "hotkey": "f",
            "cooldown": 2.0,
        },
    },
    "cavebot": {
        "routeFile": "",
        "startWaypoint": 0,
        "loop": True,
    },
    "refill": {
        "city": "Darashia",
        "hpPotionMin": 50,
        "mpPotionMin": 100,
        "capMin": 200,
        "checkCapacity": True,
        "hpPotionTarget": 200,
        "mpPotionTarget": 400,
        "depositGold": True,
        "depositLoot": True,
        "dropFlasks": True,
        "lootBackpack": "Beach Backpack",
        "mainBackpack": "Golden Backpack",
        "stashBackpack": "Beach Backpack",
        "depotChest": 1,
        "returnLabel": "caveStart",
    },
    "general": {
        "tickRate": 0.100,
        "enableHealing": True,
        "enableCavebot": True,
        "enableLoot": True,
        "lootHotkey": "g",
        "stuckAlertTimeout": 120,
        "enableStuckAlert": True,
        "enableLogging": False,
        "window": "",
    },
    "targeting": {
        "enabled": True,
        "mode": "all",
        "whitelist": [],
        "blacklist": [],
    },
    "recorder": {
        "outputFile": "",
        "ropeHotkey": "t",
        "shovelHotkey": "r",
        "direction": "south",
    },
    "reconnect": {
        "enabled": False,
        "email": "",
        "password": "",
        "maxRetries": 10,
        "delayBetweenRetries": 5.0,
    },
    "spellAttack": {
        "enabled": False,
        "manaReservePercent": 30,
        "groups": [],
    },
    "hardware": {
        "mode": "software",
        "arduinoPort": "",
        "captureDevice": 0,
    },
    "serverSave": {
        "enabled": True,
        "time": "10:00",
        "windowMinutes": 5,
        "waitAfterKickSeconds": 90,
    },
}


def get_default(key: str) -> Any:
    """Return default value for a dot-notation key (e.g. 'general.stuckAlertTimeout')."""
    return _get_by_path(DEFAULT_CONFIG, key)

"""
Repository detectors — thin wrappers over src/repositories/ for e2e validation.

Each detector runs actual detection against a screenshot and returns a dict with:
- Actual data (creatures, coordinate, etc.)
- timing_ms — execution time in milliseconds
- diagnostics — dict with debug info for JSON report
"""
import time
from typing import List, Optional, Tuple

import cv2
import numpy as np


_current_platform = None


def set_platform(os_name):
    """Reload skills config with platform-specific digit templates.

    Temporarily switches PLATFORM for the reload, then restores it.
    Only skills needs platform-specific templates — other repositories
    work cross-platform with their existing templates.
    """
    global _current_platform
    import src.utils.image_resolver as resolver

    platform_map = {"macos": "darwin", "windows": "win32", "linux": "linux"}
    target = platform_map.get(os_name, os_name)

    if _current_platform == target:
        return

    _current_platform = target

    # Temporarily switch PLATFORM for skills config reload only
    original_platform = resolver.PLATFORM
    resolver.PLATFORM = target

    import importlib
    import sys

    # Reload skills config with new PLATFORM
    skills_cfg = sys.modules.get('src.repositories.skills.config')
    if skills_cfg is None:
        return

    # Get references BEFORE reload (these are what core.py uses)
    old_digits = skills_cfg.images['digits']
    old_numbers = skills_cfg.numbers_hashes
    old_minutes = skills_cfg.minutes_or_hours_hashes

    importlib.reload(skills_cfg)

    # Mutate the original dicts in-place so all module-level references update
    old_digits.clear()
    old_digits.update(skills_cfg.images['digits'])
    old_numbers.clear()
    old_numbers.update(skills_cfg.numbers_hashes)
    old_minutes.clear()
    old_minutes.update(skills_cfg.minutes_or_hours_hashes)

    # Also update the skills icon template
    old_icons = sys.modules.get('src.repositories.skills.config').images.get('icons', {})
    old_icons.clear()
    old_icons.update(skills_cfg.images.get('icons', {}))

    # Restore original PLATFORM so other repositories aren't affected
    resolver.PLATFORM = original_platform


def reset_caches():
    """Clear all repository caches between screenshots.

    Repositories cache UI element positions (radar tools, BL icon, GW arrows,
    statusbar icons). When running E2E on different screenshots, these positions
    change, so caches must be cleared between images.

    This only affects the E2E runner — the bot's game loop never calls this
    because it processes the same screen continuously.
    """
    from src.repositories.radar.locators import clear_cache as clear_radar_cache
    from src.repositories.gamewindow import reset_gamewindow_repository
    from src.repositories.statusbar.locators import (
        get_hp_icon_position, get_mana_icon_position)

    clear_radar_cache()
    reset_gamewindow_repository()
    get_hp_icon_position.clear_cache()
    get_mana_icon_position.clear_cache()

    # Clear skills caches (import AFTER set_platform may have reloaded the module)
    from src.repositories.skills import core as skills_core_mod
    from src.repositories.skills import locators as skills_locators
    skills_core_mod.clear_digit_cache()
    skills_locators._skills_icon_cache['position'] = None


def detect_battlelist(screenshot_gray: np.ndarray, screenshot_bgr: np.ndarray = None) -> dict:
    """Run BattleListRepository against a screenshot.

    Returns dict with:
        creatures       — List[Creature]
        content         — grayscale battlelist content region or None
        color_content   — BGR battlelist content region or None
        filled_slots    — int
        creature_count  — int
        timing_ms       — float
        diagnostics     — dict
    """
    from src.repositories.battlelist import BattleListRepository

    bl_repo = BattleListRepository()
    t0 = time.perf_counter()
    creatures = bl_repo.get_creatures(screenshot_gray, color_img=screenshot_bgr)
    content = bl_repo._get_content(screenshot_gray)
    timing_ms = (time.perf_counter() - t0) * 1000

    filled_slots = bl_repo._get_filled_slots_count(content) if content is not None else 0

    # Extract color content for diagnostics (mirrors BattleListRepository.get_creatures logic)
    color_content = None
    if screenshot_bgr is not None and content is not None:
        cached_icon_pos = bl_repo._cache.get('icon_pos')
        if cached_icon_pos:
            x, y, w, h = cached_icon_pos
            cx = x - 1
            cy = y + h + 1
            from src.repositories.battlelist.config import CONTENT_WIDTH
            if cy < screenshot_bgr.shape[0] and cx >= 0:
                color_content = screenshot_bgr[cy:cy + content.shape[0], cx:cx + CONTENT_WIDTH]

    diagnostics = {
        "creature_count": len(creatures),
        "filled_slots": filled_slots,
        "content_shape": list(content.shape) if content is not None else None,
        "time_ms": round(timing_ms, 2),
        "creatures": [
            {
                "name": c.name,
                "type": str(c.creature_type),
                "is_being_attacked": c.is_being_attacked,
            }
            for c in creatures
        ],
    }

    return {
        "creatures": creatures,
        "content": content,
        "color_content": color_content,
        "filled_slots": filled_slots,
        "creature_count": len(creatures),
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_radar(screenshot_gray: np.ndarray) -> dict:
    """Run get_coordinate() against a screenshot.

    Returns dict with:
        coordinate  — (x, y, z) tuple or None
        found       — bool
        timing_ms   — float
        diagnostics — dict
    """
    from src.repositories.radar.core import get_coordinate

    t0 = time.perf_counter()
    coordinate = get_coordinate(screenshot_gray)
    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "coordinate": list(coordinate) if coordinate is not None else None,
        "found": coordinate is not None,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "coordinate": coordinate,
        "found": coordinate is not None,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_gamewindow(
    screenshot_bgr: np.ndarray,
    coordinate: Optional[Tuple[int, int, int]],
    creature_names: List[str],
    attacked_name: Optional[str] = None,
) -> dict:
    """Run GameWindowRepository against a screenshot.

    Returns dict with:
        creatures           — List[GameWindowCreature] (all)
        monsters            — List[GameWindowCreature]
        players             — List[GameWindowCreature]
        closest             — GameWindowCreature or None
        bars                — List[Tuple[int, int]] raw bar positions
        game_window_image   — grayscale game window crop or None
        game_window_position— (x, y, w, h) or None
        timing_ms           — float
        diagnostics         — dict
    """
    from src.repositories.gamewindow import get_gamewindow_repository
    from src.repositories.gamewindow.creatures import get_creatures_bars

    gw_repo = get_gamewindow_repository()

    if coordinate is None:
        diagnostics = {"error": "No radar coordinate", "time_ms": 0.0}
        return {
            "creatures": [],
            "monsters": [],
            "players": [],
            "closest": None,
            "bars": [],
            "game_window_image": None,
            "game_window_position": None,
            "timing_ms": 0.0,
            "diagnostics": diagnostics,
        }

    screenshot_gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)

    t0 = time.perf_counter()

    if not creature_names:
        pass  # get_creatures handles empty names gracefully

    gw_creatures = gw_repo.get_creatures(creature_names, coordinate, screenshot_gray)
    gw_repo.mark_attacked(gw_creatures, attacked_name, screenshot_bgr)

    monsters = gw_repo.get_monsters(gw_creatures)
    players = gw_repo.get_players(gw_creatures)

    gw_image = gw_repo.capture(screenshot_gray)
    bars = []
    if gw_image is not None:
        bars = get_creatures_bars(gw_image)

    closest = None
    if monsters:
        closest = gw_repo.get_closest_creature(monsters, coordinate)

    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "total_creatures": len(gw_creatures),
        "monster_count": len(monsters),
        "player_count": len(players),
        "bar_count": len(bars),
        "time_ms": round(timing_ms, 2),
        "monsters": [
            {
                "name": m.name,
                "method": m.id_method,
                "slot": list(m.slot),
                "coordinate": list(m.coordinate),
                "window_coordinate": list(m.window_coordinate),
                "is_being_attacked": m.is_being_attacked,
            }
            for m in monsters
        ],
        "false_positives": [
            {
                "slot": list(p.slot),
                "window_coordinate": list(p.window_coordinate),
            }
            for p in players
        ],
        "bars": [{"x": int(b[0]), "y": int(b[1])} for b in bars],
        "closest": (
            {
                "name": closest.name,
                "slot": list(closest.slot),
                "window_coordinate": list(closest.window_coordinate),
            }
            if closest is not None
            else None
        ),
    }
    if gw_image is not None:
        diagnostics["gw_shape"] = list(gw_image.shape)
    if not creature_names:
        diagnostics["warning"] = "No BL creature names, cannot identify"

    return {
        "creatures": gw_creatures,
        "monsters": monsters,
        "players": players,
        "closest": closest,
        "bars": bars,
        "game_window_image": gw_image,
        "game_window_position": gw_repo._game_window_position,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_statusbar(screenshot_gray: np.ndarray) -> dict:
    """Run get_hp_percentage / get_mana_percentage against a screenshot.

    Returns dict with:
        hp_percent  — int or None
        mana_percent— int or None
        timing_ms   — float
        diagnostics — dict
    """
    from src.repositories.statusbar.core import get_hp_percentage, get_mana_percentage

    t0 = time.perf_counter()
    hp = get_hp_percentage(screenshot_gray)
    mana = get_mana_percentage(screenshot_gray)
    timing_ms = (time.perf_counter() - t0) * 1000

    hp_int = int(hp) if hp is not None else None
    mana_int = int(mana) if mana is not None else None

    diagnostics = {
        "hp_percent": hp_int,
        "mana_percent": mana_int,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "hp_percent": hp_int,
        "mana_percent": mana_int,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_skills(screenshot_gray: np.ndarray) -> dict:
    """Run skills detectors against a screenshot.

    Returns dict with:
        hp, mana, soul, capacity, speed, food, stamina — int or None
        icon_position — (x, y, w, h) or None
        timing_ms     — float
        diagnostics   — dict
    """
    from src.repositories.skills.core import (
        get_hp, get_mana, get_capacity, get_speed,
        get_food, get_stamina, get_skill_value,
    )
    from src.repositories.skills.locators import get_skills_icon_position

    t0 = time.perf_counter()
    icon_pos = get_skills_icon_position(screenshot_gray)
    level = get_skill_value(screenshot_gray, 'level')
    experience = get_skill_value(screenshot_gray, 'experience')
    hp = get_hp(screenshot_gray)
    mana = get_mana(screenshot_gray)
    capacity = get_capacity(screenshot_gray)
    speed = get_speed(screenshot_gray)
    food = get_food(screenshot_gray)
    stamina = get_stamina(screenshot_gray)
    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "icon_position": list(icon_pos) if icon_pos else None,
        "level": level,
        "experience": experience,
        "hp": hp,
        "mana": mana,
        "capacity": capacity,
        "speed": speed,
        "food": food,
        "stamina": stamina,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "level": level,
        "experience": experience,
        "hp": hp,
        "mana": mana,
        "capacity": capacity,
        "speed": speed,
        "food": food,
        "stamina": stamina,
        "icon_position": icon_pos,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_actionbar(screenshot_gray: np.ndarray) -> dict:
    """Run ActionBarRepository against a screenshot.

    Reads slot counts for slots 1 and 2 (health/mana potions by convention).

    Returns dict with:
        slot_counts — dict mapping slot number to count (or None if not detected)
        configured  — bool (True if arrow templates loaded)
        timing_ms   — float
        diagnostics — dict
    """
    from src.repositories.actionBar.core import ActionBarRepository

    repo = ActionBarRepository()
    t0 = time.perf_counter()

    slot_counts = {}
    for slot in range(1, 11):
        count = repo.get_slot_count(screenshot_gray, slot)
        if count is not None:
            slot_counts[slot] = count

    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "configured": repo.is_configured,
        "slot_counts": {str(k): v for k, v in slot_counts.items()},
        "detected_slots": len(slot_counts),
        "time_ms": round(timing_ms, 2),
    }

    return {
        "slot_counts": slot_counts,
        "configured": repo.is_configured,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_inventory(screenshot_gray: np.ndarray) -> dict:
    """Run inventory detectors against a screenshot.

    Returns dict with:
        depot_open  — bool
        timing_ms   — float
        diagnostics — dict
    """
    from src.repositories.inventory.core import is_depot_open

    t0 = time.perf_counter()
    depot_open = is_depot_open(screenshot_gray)
    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "depot_open": depot_open,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "depot_open": depot_open,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_depot_slots(screenshot_gray: np.ndarray) -> dict:
    """Detect depot-related slot icons (depot, stash, depot chests, locker).

    Uses template matching against slot images in inventory/images/slots/
    and the locker container template.

    Returns dict with:
        locker         — (x, y) or None
        depot          — (x, y) or None
        stash          — (x, y) or None
        depot_chest_1  — (x, y) or None
        depot_chest_2  — (x, y) or None
        depot_chest_3  — (x, y) or None
        depot_chest_4  — (x, y) or None
        timing_ms      — float
        diagnostics    — dict
    """
    import pathlib

    SLOTS_DIR = pathlib.Path("src/repositories/inventory/images/slots")
    CONTAINERS_DIR = pathlib.Path("src/repositories/inventory/images/containers")
    CONFIDENCE = 0.75

    templates = {
        "locker": CONTAINERS_DIR / "locker.png",
        "depot": SLOTS_DIR / "depot.png",
        "stash": SLOTS_DIR / "stash.png",
        "depot_chest_1": SLOTS_DIR / "depot chest 1.png",
        "depot_chest_2": SLOTS_DIR / "depot chest 2.png",
        "depot_chest_3": SLOTS_DIR / "depot chest 3.png",
        "depot_chest_4": SLOTS_DIR / "depot chest 4.png",
    }

    t0 = time.perf_counter()
    results = {}

    for name, path in templates.items():
        template = cv2.imread(str(path), cv2.IMREAD_GRAYSCALE)
        if template is None:
            results[name] = None
            continue

        match = cv2.matchTemplate(screenshot_gray, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(match)

        if max_val >= CONFIDENCE:
            results[name] = (int(max_loc[0]), int(max_loc[1]))
        else:
            results[name] = None

    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        k: list(v) if v else None for k, v in results.items()
    }
    diagnostics["time_ms"] = round(timing_ms, 2)

    return {
        **results,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }


def detect_connection(screenshot_gray: np.ndarray) -> dict:
    """Run connection/login screen detection.

    Returns dict with:
        is_login_screen    — bool
        is_character_list  — bool
        is_disconnected    — bool
        login_button       — (x, y) or None
        email_field        — (x, y) or None
        password_field     — (x, y) or None
        enter_game_button  — (x, y) or None
        timing_ms          — float
        diagnostics        — dict
    """
    from src.repositories.connection.core import (
        is_login_screen,
        is_character_list,
        is_disconnected,
        get_login_button_position,
        get_email_field_position,
        get_password_field_position,
        get_enter_game_button_position,
    )

    t0 = time.perf_counter()
    login_screen = is_login_screen(screenshot_gray)
    character_list = is_character_list(screenshot_gray)
    disconnected = is_disconnected(screenshot_gray)
    login_button = get_login_button_position(screenshot_gray)
    email_field = get_email_field_position(screenshot_gray)
    password_field = get_password_field_position(screenshot_gray)
    enter_game_button = get_enter_game_button_position(screenshot_gray)
    timing_ms = (time.perf_counter() - t0) * 1000

    diagnostics = {
        "is_login_screen": login_screen,
        "is_character_list": character_list,
        "is_disconnected": disconnected,
        "login_button": list(login_button) if login_button else None,
        "email_field": list(email_field) if email_field else None,
        "password_field": list(password_field) if password_field else None,
        "enter_game_button": list(enter_game_button) if enter_game_button else None,
        "time_ms": round(timing_ms, 2),
    }

    return {
        "is_login_screen": login_screen,
        "is_character_list": character_list,
        "is_disconnected": disconnected,
        "login_button": login_button,
        "email_field": email_field,
        "password_field": password_field,
        "enter_game_button": enter_game_button,
        "timing_ms": timing_ms,
        "diagnostics": diagnostics,
    }

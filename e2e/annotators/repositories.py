"""Repository annotators — draw green borders around detected elements.

Only draws annotations for modules that have non-null expectations.
Every annotation is a green border around the actual UI element position.
"""
import cv2

from e2e.config import (
    COLOR_ATTACKING,
    COLOR_BAR,
    COLOR_FALSE_POSITIVE,
    COLOR_MONSTER,
    COLOR_PASS,
    COLOR_FAIL,
    COLOR_TARGET,
    FONT,
    FONT_SCALE_LABEL,
    FONT_SCALE_STATUS,
)

COLOR_DETECTED = (0, 255, 0)  # Green for all detected elements


def annotate_gamewindow_creatures(image, gw_result, gw_expected):
    """Draw creature detection overlays on game window.

    Only draws if gamewindow expectations are non-null.
    """
    if gw_expected is None:
        return

    monsters = gw_result.get("monsters") or []
    players = gw_result.get("players") or []
    closest = gw_result.get("closest")

    for m in monsters:
        coord = getattr(m, "window_coordinate", None)
        if not coord:
            continue
        x, y = coord
        if m.is_being_attacked:
            cv2.circle(image, (x, y), 22, COLOR_ATTACKING, 3)
            cv2.line(image, (x - 28, y), (x + 28, y), COLOR_ATTACKING, 2)
            cv2.line(image, (x, y - 28), (x, y + 28), COLOR_ATTACKING, 2)
            cv2.putText(image, f"ATTACKING {m.name}", (x - 60, y - 30),
                        FONT, FONT_SCALE_LABEL + 0.2, COLOR_ATTACKING, 2)
        else:
            cv2.circle(image, (x, y), 12, COLOR_DETECTED, 2)
            label = f"{m.name} ({m.id_method})"
            cv2.putText(image, label, (x - 30, y - 18), FONT, FONT_SCALE_LABEL, COLOR_DETECTED, 1)

    for p in players:
        coord = getattr(p, "window_coordinate", None)
        if not coord:
            continue
        x, y = coord
        cv2.circle(image, (x, y), 8, COLOR_FALSE_POSITIVE, 1)
        cv2.putText(image, "FP", (x - 8, y - 12), FONT, FONT_SCALE_LABEL, COLOR_FALSE_POSITIVE, 1)

    if closest is None:
        return
    coord = getattr(closest, "window_coordinate", None)
    if not coord:
        return
    if closest.is_being_attacked:
        return
    x, y = coord
    cv2.circle(image, (x, y), 16, COLOR_TARGET, 3)
    cv2.putText(image, "TARGET", (x - 25, y - 22), FONT, 0.5, COLOR_TARGET, 2)


def annotate_hp_bars(image, gw_result, gw_expected):
    """Draw cyan rectangles around HP bars on the game window.

    Only draws if gamewindow expectations are non-null.
    """
    if gw_expected is None:
        return

    from src.repositories.gamewindow.config import BAR_WIDTH

    gw_position = gw_result.get("game_window_position")
    bars = gw_result.get("bars") or []

    if gw_position is None or not bars:
        return

    gw_x, gw_y = gw_position[0], gw_position[1]
    for bar_x, bar_y in bars:
        sx = gw_x + bar_x
        sy = gw_y + bar_y
        cv2.rectangle(image, (sx, sy - 1), (sx + BAR_WIDTH, sy + 3), COLOR_BAR, 1)


def annotate_battlelist(image, bl_result, bl_expected, screenshot_gray):
    """Draw green border around the actual BattleList position on screen.

    No zoom, no inset — just a green rectangle around the BL content area.
    Only draws if battlelist expectations are non-null.
    """
    if bl_expected is None:
        return

    from src.repositories.battlelist import BattleListRepository

    bl_repo = BattleListRepository()
    bl_repo.get_creatures(screenshot_gray)
    icon_pos = bl_repo._cache.get('icon_pos')
    content = bl_result.get("content")

    if icon_pos is None or content is None:
        return

    cx = icon_pos[0] - 1
    cy = icon_pos[1] + icon_pos[3] + 1
    ch, cw = content.shape[:2]

    # Green border around BL content area
    cv2.rectangle(image, (cx - 2, cy - 2), (cx + cw + 2, cy + ch + 2), COLOR_DETECTED, 2)

    # Label with creature count
    creatures = bl_result.get("creatures") or []
    count = len(creatures)
    names = sorted(set(c.name for c in creatures))
    label = f"BL: {count} [{', '.join(names)}]"
    cv2.rectangle(image, (cx - 2, cy - 20), (cx + len(label) * 8 + 10, cy - 4), (0, 0, 0), -1)
    cv2.putText(image, label, (cx, cy - 7), FONT, FONT_SCALE_LABEL, COLOR_DETECTED, 1)

    # Mark attacked creature slot
    from src.repositories.battlelist.config import SLOT_HEIGHT
    for idx, c in enumerate(creatures):
        if c.is_being_attacked:
            sy = cy + idx * SLOT_HEIGHT
            cv2.rectangle(image, (cx, sy), (cx + cw, sy + SLOT_HEIGHT - 1), COLOR_ATTACKING, 2)


def annotate_radar(image, radar_result, radar_expected, screenshot_gray):
    """Draw green border around the radar/minimap area.

    Only draws if radar expectations are non-null.
    """
    if radar_expected is None:
        return
    if not radar_result.get("found"):
        return

    from src.repositories.radar.locators import get_radar_tools_position

    tools_pos = get_radar_tools_position(screenshot_gray, use_cache=False)
    if tools_pos is None:
        return

    # Radar minimap is above the tools buttons
    # Tools are at bottom of minimap area
    tx, ty, tw, th = tools_pos
    radar_w = 106
    radar_h = 109
    radar_x = tx + tw // 2 - radar_w // 2
    radar_y = ty - radar_h - 2

    cv2.rectangle(image, (radar_x - 2, radar_y - 2),
                  (radar_x + radar_w + 2, radar_y + radar_h + 2), COLOR_DETECTED, 2)

    coord = radar_result.get("coordinate")
    if coord:
        label = f"Radar: {coord}"
        cv2.rectangle(image, (radar_x - 2, radar_y - 20),
                      (radar_x + len(label) * 7 + 10, radar_y - 4), (0, 0, 0), -1)
        cv2.putText(image, label, (radar_x, radar_y - 7), FONT, FONT_SCALE_LABEL, COLOR_DETECTED, 1)


def annotate_statusbar(image, sb_result, sb_expected, screenshot_gray):
    """Draw green borders around HP and Mana bars with percentages.

    Only draws if statusbar expectations are non-null.
    """
    if sb_expected is None:
        return

    from src.repositories.statusbar.locators import locate
    from src.repositories.statusbar.config import images, BAR_SIZE

    hp = sb_result.get("hp_percent")
    mana = sb_result.get("mana_percent")

    hp_pos = locate(screenshot_gray, images['icons']['hp'])
    if hp_pos is None:
        hp_pos = locate(screenshot_gray, images['icons']['hp_macos'])
    mana_pos = locate(screenshot_gray, images['icons']['mana'])

    if hp_pos is not None and hp is not None:
        bar_x = hp_pos[0] + 13
        bar_y = hp_pos[1] + 3
        cv2.rectangle(image, (bar_x - 3, bar_y - 3),
                      (bar_x + BAR_SIZE + 3, bar_y + 10), COLOR_DETECTED, 2)
        label = f"HP {hp}%"
        lx = bar_x + BAR_SIZE + 8
        cv2.rectangle(image, (lx - 2, bar_y - 3), (lx + 80, bar_y + 12), (0, 0, 0), -1)
        cv2.putText(image, label, (lx, bar_y + 9), FONT, 0.5, COLOR_DETECTED, 1)

    if mana_pos is not None and mana is not None:
        bar_x = mana_pos[0] + 13
        bar_y = mana_pos[1] + 3
        cv2.rectangle(image, (bar_x - 3, bar_y - 3),
                      (bar_x + BAR_SIZE + 3, bar_y + 10), COLOR_DETECTED, 2)
        label = f"Mana {mana}%"
        lx = bar_x + BAR_SIZE + 8
        cv2.rectangle(image, (lx - 2, bar_y - 3), (lx + 100, bar_y + 12), (0, 0, 0), -1)
        cv2.putText(image, label, (lx, bar_y + 9), FONT, 0.5, COLOR_DETECTED, 1)


def annotate_skills(image, skills_result, skills_expected):
    """Draw green border around skills panel with each value labeled.

    Only draws if skills expectations are non-null.
    """
    if skills_expected is None:
        return

    icon_pos = skills_result.get("icon_position")
    if icon_pos is None:
        return

    panel_x = icon_pos[0]
    panel_y = icon_pos[1]
    panel_w = 170
    panel_h = 200

    # Green border around the skills panel
    cv2.rectangle(image, (panel_x - 2, panel_y - 2),
                  (panel_x + panel_w + 2, panel_y + panel_h + 2), COLOR_DETECTED, 2)

    # Show each skill value as a label next to the panel
    skill_fields = [
        ("level", "Level"),
        ("experience", "Exp"),
        ("hp", "HP"),
        ("mana", "Mana"),
        ("capacity", "Cap"),
        ("speed", "Speed"),
        ("food", "Food"),
        ("stamina", "Stam"),
    ]

    label_x = panel_x + panel_w + 6
    label_y = panel_y + 12
    line_h = 14

    for key, label in skill_fields:
        val = skills_result.get(key)
        if val is None:
            continue
        text = f"{label}: {val}"
        cv2.rectangle(image, (label_x - 2, label_y - 11),
                      (label_x + len(text) * 7 + 4, label_y + 3), (0, 0, 0), -1)
        cv2.putText(image, text, (label_x, label_y),
                    FONT, FONT_SCALE_LABEL, COLOR_DETECTED, 1)
        label_y += line_h


def annotate_depot_slots(image, depot_result, depot_expected):
    """Draw green borders around detected depot slot icons.

    Only draws if depot_slots expectations are non-null.
    """
    if depot_expected is None:
        return
    if not depot_result:
        return

    labels = {
        "locker": "Locker",
        "depot": "Depot",
        "stash": "Stash",
        "depot_chest_1": "Chest I",
        "depot_chest_2": "Chest II",
        "depot_chest_3": "Chest III",
        "depot_chest_4": "Chest IV",
    }

    for key, label in labels.items():
        pos = depot_result.get(key)
        if pos is None:
            continue
        x, y = pos
        cv2.rectangle(image, (x - 2, y - 2), (x + 34, y + 34), COLOR_DETECTED, 2)
        cv2.putText(image, label, (x, y - 6), FONT, 0.4, COLOR_DETECTED, 1)


def annotate_connection(image, connection_result, connection_expected):
    """Draw green markers on connection/login screen elements.

    Only draws if connection expectations are non-null.
    """
    if connection_expected is None:
        return
    if not connection_result:
        return

    elements = [
        ("login_button", "Login Button"),
        ("email_field", "Email Field"),
        ("password_field", "Password Field"),
        ("enter_game_button", "Enter Game"),
    ]

    for key, label in elements:
        pos = connection_result.get(key)
        if pos is None:
            continue
        x, y = pos
        cv2.circle(image, (x, y), 8, COLOR_DETECTED, 2)
        cv2.putText(image, label, (x + 12, y + 5), FONT, 0.5, COLOR_DETECTED, 1)

    y_offset = 60
    if connection_result.get("is_login_screen"):
        cv2.putText(image, "LOGIN SCREEN DETECTED", (10, y_offset),
                    FONT, 0.6, COLOR_DETECTED, 2)
        y_offset += 25
    if connection_result.get("is_character_list"):
        cv2.putText(image, "CHARACTER LIST DETECTED", (10, y_offset),
                    FONT, 0.6, COLOR_DETECTED, 2)
        y_offset += 25
    if connection_result.get("is_disconnected"):
        cv2.putText(image, "DISCONNECTED", (10, y_offset),
                    FONT, 0.6, (0, 0, 255), 2)

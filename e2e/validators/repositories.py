"""Repository validators — compare detector output against .expected.json values."""

from e2e.validators import make_check


def validate_battlelist(bl_result, expected):
    """Validate BattleList detector output against expected values."""
    if expected is None:
        return []

    checks = []

    bl_count = bl_result["creature_count"]
    exp_count = expected["count"]
    checks.append(make_check(
        "BL creature count",
        "battlelist",
        bl_count == exp_count,
        exp_count,
        bl_count,
        f"BattleList found {bl_count} creatures but expected {exp_count}. "
        f"Possible causes: hash lookup failure, BL icon not found, "
        f"or creature name not in hash table.",
    ))

    actual_names = sorted(set(c["name"] for c in bl_result["diagnostics"]["creatures"]))
    exp_names = sorted(set(expected["names"]))
    names_match = actual_names == exp_names
    checks.append(make_check(
        "BL creature names",
        "battlelist",
        names_match,
        exp_names,
        actual_names,
        f"Expected names {exp_names} but got {actual_names}. "
        f"The creature hash may not exist in the hash table, "
        f"or NV12 color shift changed the hash.",
    ))

    attacking = expected.get("attacking")
    if attacking is None:
        return checks

    # attacking can be a string (creature name) or False
    # Any truthy value means "should be attacking"
    exp_attacking = bool(attacking)
    any_attacked = any(c["is_being_attacked"] for c in bl_result["diagnostics"]["creatures"])
    checks.append(make_check(
        "BL attack detection",
        "battlelist",
        any_attacked == exp_attacking,
        "attacking" if exp_attacking else "not attacking",
        "attacking" if any_attacked else "not attacking",
        f"BL attack detection {'missed attack border' if exp_attacking else 'false positive'}. "
        f"On capture card, R-channel detection should find red border. "
        f"Creatures: {bl_result['diagnostics']['creatures']}",
    ))

    return checks


def validate_gamewindow(gw_result, expected, bl_count=0):
    """Validate GameWindow detector output against expected values."""
    if expected is None:
        return []

    checks = []
    diag = gw_result["diagnostics"]

    gw_monsters = diag.get("monster_count", 0)
    exp_monsters = expected["monster_count"]
    checks.append(make_check(
        "GW monster count",
        "gamewindow",
        gw_monsters >= exp_monsters,
        exp_monsters,
        gw_monsters,
        f"GameWindow identified {gw_monsters}/{exp_monsters} monsters. "
        f"HP bar detection may have missed bars (BLACK_THRESHOLD too low), "
        f"or template matching / OCR failed to identify the creature name. "
        f"BL had {bl_count} creatures, bars detected: {diag.get('bar_count', '?')}.",
    ))

    fp_count = diag.get("player_count", 0)
    max_fp = expected["max_false_positives"]
    checks.append(make_check(
        "GW false positives",
        "gamewindow",
        fp_count <= max_fp,
        f"<= {max_fp}",
        fp_count,
        f"{fp_count} unidentified 'Player' creatures detected (max allowed: {max_fp}). "
        f"These are HP bars from terrain noise or creatures without template/OCR match. "
        f"Total bars: {diag.get('bar_count', '?')}, slot dedup reduced to {diag.get('total_creatures', '?')}.",
    ))

    bar_count = diag.get("bar_count", 0)
    max_bars = expected["max_bar_noise"]
    checks.append(make_check(
        "GW bar noise",
        "gamewindow",
        bar_count <= max_bars,
        f"<= {max_bars}",
        bar_count,
        f"Detected {bar_count} HP bars but max expected is {max_bars}. "
        f"Terrain (lava, fire) creates dark horizontal lines that pass bar detection. "
        f"The vertical proximity filter (BAR_MIN_VERTICAL_GAP) should reduce this. "
        f"Consider increasing the gap or adding additional terrain filtering.",
    ))

    attacking = expected.get("attacking")
    if attacking is None:
        return checks

    if gw_monsters == 0:
        return checks

    gw_any_attacked = any(m.get("is_being_attacked", False) for m in diag.get("monsters", []))
    checks.append(make_check(
        "GW attack detection",
        "gamewindow",
        gw_any_attacked == attacking,
        "attacking" if attacking else "not attacking",
        "attacking" if gw_any_attacked else "not attacking",
        f"GW R-channel attack detection {'missed red border around creature tile' if attacking else 'false positive'}. "
        f"Monsters: {diag.get('monsters', [])}",
    ))

    return checks


def validate_radar(radar_result, expected):
    """Validate Radar detector output against expected values."""
    if expected is None:
        return []

    found = radar_result["found"]
    exp_found = expected["found"]
    return [make_check(
        "Radar coordinate",
        "radar",
        found == exp_found,
        "found" if exp_found else "not found",
        "found" if found else "not found",
        "Radar failed to find coordinate. Floor image may not match "
        "(different resolution, NV12 color shift, or floor not in database).",
    )]


def validate_statusbar(sb_result, expected):
    """Validate StatusBar detector output against expected values."""
    if expected is None:
        return []

    checks = []

    hp_range = expected.get("hp_range")
    if hp_range is not None:
        hp = sb_result.get("hp_percent")
        hp_min, hp_max = hp_range
        hp_ok = hp is not None and hp_min <= hp <= hp_max
        checks.append(make_check(
            "StatusBar HP",
            "statusbar",
            hp_ok,
            f"{hp_min}-{hp_max}%",
            f"{hp}%",
            f"HP detection returned {hp}% but expected {hp_min}-{hp_max}%. "
            f"HP icon may not be found, or bar colors shifted by NV12.",
        ))

    mana_range = expected.get("mana_range")
    if mana_range is not None:
        mana = sb_result.get("mana_percent")
        mn_min, mn_max = mana_range
        mana_ok = mana is not None and mn_min <= mana <= mn_max
        checks.append(make_check(
            "StatusBar Mana",
            "statusbar",
            mana_ok,
            f"{mn_min}-{mn_max}%",
            f"{mana}%",
            f"Mana detection returned {mana}% but expected {mn_min}-{mn_max}%. "
            f"Mana icon may not be found, or bar colors shifted by NV12.",
        ))

    return checks


def validate_skills(skills_result, expected):
    """Validate Skills detector output against expected values."""
    if expected is None:
        return []

    checks = []

    if expected.get("detected") is not None:
        actual = skills_result.get("icon_position") is not None
        checks.append(make_check(
            "Skills detected",
            "skills",
            actual == expected["detected"],
            "detected" if expected["detected"] else "not detected",
            "detected" if actual else "not detected",
            "Skills panel icon not found in screenshot.",
        ))

    # Exact value checks for each skill
    exact_fields = [
        ("level", "Skills level"),
        ("hp", "Skills HP"),
        ("mana", "Skills Mana"),
        ("capacity", "Skills Capacity"),
        ("speed", "Skills Speed"),
        ("stamina", "Skills Stamina"),
    ]
    for key, check_name in exact_fields:
        exp_val = expected.get(key)
        if exp_val is None:
            continue
        actual_val = skills_result.get(key)
        checks.append(make_check(
            check_name, "skills",
            actual_val == exp_val,
            str(exp_val), str(actual_val),
            f"{check_name} returned {actual_val} but expected {exp_val}. "
            f"Digit recognition may have failed.",
        ))

    return checks


def validate_actionbar(actionbar_result, expected):
    """Validate ActionBar detector output against expected values."""
    if expected is None:
        return []

    diag = actionbar_result["diagnostics"]
    slot_count = diag.get("detected_slots", 0)
    exp_slot_count = expected["slot_count"]
    return [make_check(
        "ActionBar slot count",
        "actionbar",
        slot_count == exp_slot_count,
        exp_slot_count,
        slot_count,
        f"ActionBar detected {slot_count} slots but expected {exp_slot_count}. "
        f"Arrow templates may not be loaded or slot detection failed.",
    )]


def validate_inventory(inventory_result, expected):
    """Validate Inventory detector output against expected values."""
    if expected is None:
        return []

    checks = []

    containers_found = expected.get("containers_found")
    if containers_found is not None:
        depot_open = inventory_result["diagnostics"].get("depot_open", False)
        checks.append(make_check(
            "Inventory containers found",
            "inventory",
            depot_open == containers_found,
            "found" if containers_found else "not found",
            "found" if depot_open else "not found",
            f"Inventory depot_open={depot_open} but expected containers_found={containers_found}. "
            f"Depot icon may not be detected or container detection failed.",
        ))

    min_containers = expected.get("min_containers")
    if min_containers is not None:
        depot_open = inventory_result["diagnostics"].get("depot_open", False)
        actual_count = 1 if depot_open else 0
        checks.append(make_check(
            "Inventory min containers",
            "inventory",
            actual_count >= min_containers,
            f">= {min_containers}",
            actual_count,
            f"Inventory found {actual_count} containers but expected at least {min_containers}. "
            f"Container detection may have missed open containers.",
        ))

    return checks


def validate_depot_slots(depot_result, expected):
    """Validate depot slot icon detection."""
    if expected is None:
        return []

    checks = []

    slot_names = [
        ("locker", "Locker"),
        ("depot", "Depot"),
        ("stash", "Stash"),
        ("depot_chest_1", "Depot Chest 1"),
        ("depot_chest_2", "Depot Chest 2"),
        ("depot_chest_3", "Depot Chest 3"),
        ("depot_chest_4", "Depot Chest 4"),
    ]

    for key, label in slot_names:
        exp = expected.get(key)
        if exp is None:
            continue
        actual = depot_result.get(key) is not None
        checks.append(make_check(
            f"Depot {label}",
            "depot_slots",
            actual == exp,
            "found" if exp else "not found",
            "found" if actual else "not found",
            f"{label} icon not detected. Template may not match screenshot resolution.",
        ))

    return checks


def validate_connection(connection_result, expected):
    """Validate connection/login screen detection."""
    if expected is None:
        return []

    checks = []

    if expected.get("is_login_screen") is not None:
        actual = connection_result.get("is_login_screen", False)
        checks.append(make_check(
            "Connection login screen",
            "connection",
            actual == expected["is_login_screen"],
            str(expected["is_login_screen"]),
            str(actual),
            "Login screen detection failed. Template may not match.",
        ))

    if expected.get("is_character_list") is not None:
        actual = connection_result.get("is_character_list", False)
        checks.append(make_check(
            "Connection character list",
            "connection",
            actual == expected["is_character_list"],
            str(expected["is_character_list"]),
            str(actual),
            "Character list detection failed.",
        ))

    if expected.get("login_button") is not None:
        actual = connection_result.get("login_button") is not None
        checks.append(make_check(
            "Connection login button",
            "connection",
            actual == expected["login_button"],
            "found" if expected["login_button"] else "not found",
            "found" if actual else "not found",
            "Login button not detected. Template may not match.",
        ))

    if expected.get("email_field") is not None:
        actual = connection_result.get("email_field") is not None
        checks.append(make_check(
            "Connection email field",
            "connection",
            actual == expected["email_field"],
            "found" if expected["email_field"] else "not found",
            "found" if actual else "not found",
            "Email field not detected.",
        ))

    if expected.get("password_field") is not None:
        actual = connection_result.get("password_field") is not None
        checks.append(make_check(
            "Connection password field",
            "connection",
            actual == expected["password_field"],
            "found" if expected["password_field"] else "not found",
            "found" if actual else "not found",
            "Password field not detected.",
        ))

    if expected.get("enter_game_button") is not None:
        actual = connection_result.get("enter_game_button") is not None
        checks.append(make_check(
            "Connection enter game button",
            "connection",
            actual == expected["enter_game_button"],
            "found" if expected["enter_game_button"] else "not found",
            "found" if actual else "not found",
            "Enter game button not detected.",
        ))

    return checks

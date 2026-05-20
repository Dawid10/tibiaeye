"""CLI for adding new screenshots to the E2E framework.

Two modes:
  Live capture:   python e2e/capture.py --os macos
  Import file:    python e2e/capture.py --file ~/screenshot.png --os macos

Runs all detectors in discovery mode and generates a .discovered.json
with detected values for review.
"""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
from datetime import date
from pathlib import Path

import cv2
import numpy as np

from e2e.config import SCREENSHOTS_DIR, SUPPORTED_OS
from e2e.detectors.repositories import (
    reset_caches,
    detect_battlelist,
    detect_radar,
    detect_gamewindow,
    detect_statusbar,
)


def _capture_live() -> np.ndarray:
    """Capture the current screen using src.core.screen."""
    from src.core.screen import get_screen_capture
    screen = get_screen_capture()
    return screen.capture()


def _load_file(path: str) -> np.ndarray:
    """Load a screenshot from disk (BGR)."""
    img = cv2.imread(path)
    if img is None:
        raise ValueError(f"Cannot read image: {path}")
    return img


def _prompt_name() -> str:
    """Interactively ask the user for a screenshot name."""
    while True:
        name = input("Screenshot name (without .png): ").strip()
        if name:
            return name
        print("Name cannot be empty.")


def _build_discovered(
    screenshot_bgr: np.ndarray,
    target_os: str,
    bl_result: dict,
    gw_result: dict,
    radar_result: dict,
    sb_result: dict,
) -> dict:
    """Assemble the discovered JSON structure from pre-computed detector results."""
    h, w = screenshot_bgr.shape[:2]
    resolution = f"{w}x{h}"
    capture_method = "capture_card" if target_os == "windows" else "screen_capture"

    return {
        "description": "TODO: describe this scenario",
        "resolution": resolution,
        "capture_method": capture_method,
        "capture_date": str(date.today()),
        "tibia_client_version": None,
        "repositories": {
            "battlelist": _build_battlelist_entry(bl_result),
            "gamewindow": _build_gamewindow_entry(gw_result),
            "radar": _build_radar_entry(radar_result),
            "statusbar": _build_statusbar_entry(sb_result),
            "skills": None,
            "actionbar": None,
            "inventory": None,
        },
        "pathfinding": None,
        "gameplay": None,
    }


def _build_battlelist_entry(bl_result: dict) -> dict:
    creatures = bl_result["creatures"]
    attacking = None
    for c in creatures:
        if c.is_being_attacked:
            attacking = c.name
            break
    names = [c.name for c in creatures]
    return {
        "count": len(creatures),
        "names": names,
        "attacking": attacking,
    }


def _build_gamewindow_entry(gw_result: dict) -> dict:
    monsters = gw_result["monsters"]
    players = gw_result["players"]
    bars = gw_result["bars"]
    bar_noise = max(0, len(bars) - len(monsters))
    attacking = any(m.is_being_attacked for m in monsters)
    return {
        "monster_count": len(monsters),
        "max_false_positives": len(players),
        "max_bar_noise": bar_noise,
        "attacking": attacking,
    }


def _build_radar_entry(radar_result: dict) -> dict:
    return {"found": radar_result["found"]}


def _build_statusbar_entry(sb_result: dict) -> dict | None:
    hp = sb_result["hp_percent"]
    mana = sb_result["mana_percent"]
    if hp is None and mana is None:
        return None
    hp_range = [hp, hp] if hp is not None else None
    mana_range = [mana, mana] if mana is not None else None
    return {
        "hp_range": hp_range,
        "mana_range": mana_range,
    }


def _print_discovery(name: str, target_os: str, bl_result: dict, gw_result: dict,
                     radar_result: dict, sb_result: dict, discovered_path: Path) -> None:
    """Print discovery summary to console."""
    print(f"\nDiscovery: {name}.png ({target_os})\n")

    creatures = bl_result["creatures"]
    creature_names = [c.name for c in creatures]
    attacking_name = None
    for c in creatures:
        if c.is_being_attacked:
            attacking_name = c.name
            break
    names_str = ", ".join(creature_names) if creature_names else "none"
    attacking_str = attacking_name if attacking_name else "none"
    print(f"BattleList:  {len(creatures)} creatures [{names_str}] (attacking: {attacking_str})")

    monsters = gw_result["monsters"]
    players = gw_result["players"]
    bars = gw_result["bars"]
    bar_noise = max(0, len(bars) - len(monsters))
    print(f"GameWindow:  {len(monsters)} monsters, {len(players)} FP, {bar_noise} bars")

    coord = radar_result["coordinate"]
    if coord is not None:
        print(f"Radar:       found ({coord[0]}, {coord[1]}, {coord[2]})")
    else:
        print("Radar:       not found")

    hp = sb_result["hp_percent"]
    mana = sb_result["mana_percent"]
    if hp is not None or mana is not None:
        hp_str = f"{hp}%" if hp is not None else "N/A"
        mana_str = f"{mana}%" if mana is not None else "N/A"
        print(f"StatusBar:   HP {hp_str}, Mana {mana_str}")
    else:
        print("StatusBar:   not detected")

    print(f"\nSaved: {discovered_path}")
    print("Review and rename to .expected.json when ready.")


def run(target_os: str, file_path: str | None, name: str | None) -> None:
    """Main capture flow."""
    if file_path is not None:
        screenshot_bgr = _load_file(file_path)
    else:
        print("Capturing screen...")
        screenshot_bgr = _capture_live()

    if name is None:
        name = _prompt_name()

    os_dir = SCREENSHOTS_DIR / target_os
    os_dir.mkdir(parents=True, exist_ok=True)

    png_path = os_dir / f"{name}.png"
    cv2.imwrite(str(png_path), screenshot_bgr)

    screenshot_gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)

    reset_caches()

    bl_result = detect_battlelist(screenshot_gray, screenshot_bgr)
    radar_result = detect_radar(screenshot_gray)
    creature_names = [c.name for c in bl_result["creatures"]]
    attacked_name = None
    for c in bl_result["creatures"]:
        if c.is_being_attacked:
            attacked_name = c.name
            break
    gw_result = detect_gamewindow(
        screenshot_bgr,
        radar_result["coordinate"],
        creature_names,
        attacked_name,
    )
    sb_result = detect_statusbar(screenshot_gray)

    discovered = _build_discovered(screenshot_bgr, target_os, bl_result, gw_result, radar_result, sb_result)

    discovered_path = os_dir / f"{name}.discovered.json"
    with open(discovered_path, "w", encoding="utf-8") as f:
        json.dump(discovered, f, indent=2)

    _print_discovery(name, target_os, bl_result, gw_result, radar_result, sb_result, discovered_path)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Capture or import a screenshot and run discovery detectors."
    )
    parser.add_argument(
        "--os",
        required=True,
        choices=SUPPORTED_OS,
        help="Target OS folder (macos, windows, linux).",
    )
    parser.add_argument(
        "--file",
        default=None,
        help="Import existing screenshot instead of live capture.",
    )
    parser.add_argument(
        "--name",
        default=None,
        help="Screenshot name without .png. Prompted interactively if not provided.",
    )

    args = parser.parse_args()

    file_path = None
    if args.file is not None:
        file_path = str(Path(args.file).expanduser().resolve())

    run(target_os=args.os, file_path=file_path, name=args.name)


if __name__ == "__main__":
    main()

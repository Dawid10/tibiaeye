"""E2E test runner — orchestrates detection pipeline against real screenshots."""
import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import argparse
import json
import subprocess
import time
from datetime import datetime
from pathlib import Path

import cv2
import numpy as np

from e2e.config import (
    IMAGES_DIR,
    MARKER_FIXED,
    MARKER_NEW,
    MARKER_REGRESSION,
    OUTPUT_DIR,
    REPORTS_DIR,
    SCREENSHOTS_DIR,
    SUPPORTED_OS,
)
from e2e.detectors.repositories import (
    detect_actionbar,
    detect_battlelist,
    detect_connection,
    detect_depot_slots,
    detect_gamewindow,
    detect_inventory,
    detect_radar,
    detect_skills,
    detect_statusbar,
)
from e2e.detectors.pathfinding import detect_walkable_grid, detect_bfs_path
from e2e.detectors.gameplay import build_context, detect_targeting, detect_decision, detect_task_sequence
from e2e.validators.repositories import (
    validate_actionbar,
    validate_battlelist,
    validate_connection,
    validate_depot_slots,
    validate_gamewindow,
    validate_inventory,
    validate_radar,
    validate_skills,
    validate_statusbar,
)
from e2e.validators.pathfinding import validate_pathfinding
from e2e.validators.gameplay import validate_gameplay
from e2e.annotators.repositories import (
    annotate_battlelist,
    annotate_connection,
    annotate_depot_slots,
    annotate_gamewindow_creatures,
    annotate_hp_bars,
    annotate_radar,
    annotate_skills,
    annotate_statusbar,
)
from e2e.annotators.pathfinding import annotate_walkable_grid, annotate_bfs_path
from e2e.annotators.gameplay import annotate_decision_badge, annotate_task_sequence


def load_expected(json_path):
    """Load .expected.json from path."""
    with open(json_path, encoding="utf-8") as f:
        return json.load(f)


def discover_screenshots(os_filter=None, image_filter=None):
    """Find all PNG + .expected.json pairs under screenshots/.

    Returns list of dicts: {os, name, png_path, expected_path, expected}.
    """
    entries = []

    os_dirs = [d for d in SCREENSHOTS_DIR.iterdir() if d.is_dir() and d.name in SUPPORTED_OS]

    for os_dir in sorted(os_dirs):
        if os_filter and os_dir.name != os_filter:
            continue

        for png_path in sorted(os_dir.glob("*.png")):
            name = png_path.stem
            if image_filter and image_filter not in name:
                continue

            expected_path = png_path.with_suffix(".expected.json")
            if not expected_path.exists():
                print(f"[DISCOVERY] {os_dir.name}/{name} — no .expected.json")
                continue

            expected = load_expected(expected_path)
            entries.append({
                "os": os_dir.name,
                "name": name,
                "png_path": png_path,
                "expected_path": expected_path,
                "expected": expected,
            })

    return entries


def get_git_hash():
    """Return git rev-parse --short HEAD or 'unknown'."""
    try:
        result = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


def load_previous_report():
    """Load reports/latest.json for regression comparison."""
    latest = REPORTS_DIR / "latest.json"
    if not latest.exists():
        return None
    try:
        with open(latest, encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return None


def get_regression_status(image_key, passed, previous_report):
    """Return REGRESSION/FIXED/NEW/None based on comparison with previous report."""
    if previous_report is None:
        return MARKER_NEW

    prev_results = {
        f"{r.get('os', 'unknown')}/{r.get('name', r.get('image', ''))}": r
        for r in previous_report.get("results", [])
    }

    if image_key not in prev_results:
        return MARKER_NEW

    prev = prev_results[image_key]
    prev_passed = prev.get("failed", 1) == 0

    if prev_passed and not passed:
        return MARKER_REGRESSION
    if not prev_passed and passed:
        return MARKER_FIXED
    return None


def run_single(entry, module_filter=None, verbose=False, no_annotate=False):
    """Run full pipeline on one screenshot. Returns result dict."""
    from e2e.detectors.repositories import reset_caches, set_platform

    png_path = entry["png_path"]
    expected = entry["expected"]
    name = entry["name"]
    os_name = entry["os"]

    set_platform(os_name)
    reset_caches()

    screenshot_bgr = cv2.imread(str(png_path))
    if screenshot_bgr is None:
        return {
            "os": os_name,
            "name": name,
            "error": f"Could not load: {png_path}",
            "checks": [],
            "passed": 0,
            "failed": 1,
            "timing": {"total_ms": 0},
            "diagnostics": {},
        }

    screenshot_gray = cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY)
    resolution = f"{screenshot_bgr.shape[1]}x{screenshot_bgr.shape[0]}"

    t0 = time.perf_counter()

    # 1. BattleList
    bl_result = detect_battlelist(screenshot_gray, screenshot_bgr)
    creature_names = [
        c.name for c in bl_result["creatures"]
        if c.name not in ("Unknown", "Player")
    ]

    # 2. Radar
    radar_result = detect_radar(screenshot_gray)

    # 3. GameWindow
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

    # 4. StatusBar
    sb_result = detect_statusbar(screenshot_gray)

    # 5. Skills
    skills_result = detect_skills(screenshot_gray)

    # 6. ActionBar
    actionbar_result = detect_actionbar(screenshot_gray)

    # 7. Inventory
    inventory_result = detect_inventory(screenshot_gray)

    # 8. Depot slots
    depot_slots_result = detect_depot_slots(screenshot_gray)

    # 9. Connection
    connection_result = detect_connection(screenshot_gray)

    # 9. Pathfinding
    pf_walkable = detect_walkable_grid(gw_result, radar_result["coordinate"])
    pf_path = detect_bfs_path(gw_result, gw_result.get("closest"), radar_result["coordinate"])

    # 9. Gameplay
    gameplay_overrides = expected.get("gameplay", {}) or {}
    context_overrides = gameplay_overrides.get("context_overrides")
    gp_context = build_context(bl_result, radar_result, gw_result, sb_result, context_overrides)
    gp_targeting = detect_targeting(gw_result.get("monsters", []), context_overrides)
    gp_decision = detect_decision(gp_context)
    gp_target = gw_result.get("closest")
    if gp_decision.get("decision") == "attack":
        filtered = gp_targeting.get("filtered", [])
        if filtered:
            gp_target = gw_result.get("closest") or filtered[0]
    gp_tasks = detect_task_sequence(gp_context, gp_decision, gp_target)

    total_ms = round((time.perf_counter() - t0) * 1000, 1)

    repos_expected = expected.get("repositories", {})

    def _should_run(module_name):
        if module_filter is None:
            return True
        return module_name == module_filter

    checks = []
    if _should_run("battlelist"):
        checks.extend(validate_battlelist(bl_result, repos_expected.get("battlelist")))
    if _should_run("gamewindow"):
        checks.extend(validate_gamewindow(
            gw_result,
            repos_expected.get("gamewindow"),
            bl_count=bl_result["creature_count"],
        ))
    if _should_run("radar"):
        checks.extend(validate_radar(radar_result, repos_expected.get("radar")))
    if _should_run("statusbar"):
        checks.extend(validate_statusbar(sb_result, repos_expected.get("statusbar")))
    if _should_run("skills"):
        checks.extend(validate_skills(skills_result, repos_expected.get("skills")))
    if _should_run("actionbar"):
        checks.extend(validate_actionbar(actionbar_result, repos_expected.get("actionbar")))
    if _should_run("inventory"):
        checks.extend(validate_inventory(inventory_result, repos_expected.get("inventory")))
    if _should_run("depot_slots"):
        checks.extend(validate_depot_slots(depot_slots_result, repos_expected.get("depot_slots")))
    if _should_run("connection"):
        checks.extend(validate_connection(connection_result, repos_expected.get("connection")))
    if _should_run("pathfinding"):
        checks.extend(validate_pathfinding(pf_walkable, pf_path, expected.get("pathfinding")))
    if _should_run("gameplay"):
        checks.extend(validate_gameplay(gp_decision, gp_tasks, gameplay_overrides if gameplay_overrides.get("decision") else None))

    passed_count = sum(1 for c in checks if c["passed"])
    failed_count = len(checks) - passed_count

    annotated_image = None
    if not no_annotate:
        annotated_image = screenshot_bgr.copy()
        # Only annotate modules with non-null expectations
        annotate_gamewindow_creatures(annotated_image, gw_result, repos_expected.get("gamewindow"))
        annotate_hp_bars(annotated_image, gw_result, repos_expected.get("gamewindow"))
        annotate_battlelist(annotated_image, bl_result, repos_expected.get("battlelist"), screenshot_gray)
        annotate_radar(annotated_image, radar_result, repos_expected.get("radar"), screenshot_gray)
        annotate_statusbar(annotated_image, sb_result, repos_expected.get("statusbar"), screenshot_gray)
        annotate_depot_slots(annotated_image, depot_slots_result, repos_expected.get("depot_slots"))
        annotate_connection(annotated_image, connection_result, repos_expected.get("connection"))
        # Pathfinding only if expected
        if expected.get("pathfinding") is not None:
            annotate_walkable_grid(annotated_image, gw_result, pf_walkable)
            annotate_bfs_path(annotated_image, gw_result, pf_path)
        annotate_skills(annotated_image, skills_result, repos_expected.get("skills"))
        # Gameplay only if expected
        gameplay_exp = expected.get("gameplay") or {}
        if gameplay_exp.get("decision") is not None:
            annotate_decision_badge(annotated_image, gp_decision)
            annotate_task_sequence(annotated_image, gp_tasks)

    timing = {
        "battlelist_ms": round(bl_result["timing_ms"], 1),
        "radar_ms": round(radar_result["timing_ms"], 1),
        "gamewindow_ms": round(gw_result["timing_ms"], 1),
        "statusbar_ms": round(sb_result["timing_ms"], 1),
        "skills_ms": round(skills_result["timing_ms"], 1),
        "actionbar_ms": round(actionbar_result["timing_ms"], 1),
        "inventory_ms": round(inventory_result["timing_ms"], 1),
        "depot_slots_ms": round(depot_slots_result["timing_ms"], 1),
        "connection_ms": round(connection_result["timing_ms"], 1),
        "pathfinding_ms": round(pf_walkable["timing_ms"] + pf_path["timing_ms"], 1),
        "gameplay_ms": round(gp_decision["timing_ms"] + gp_tasks["timing_ms"], 1),
        "total_ms": total_ms,
    }

    return {
        "os": os_name,
        "name": name,
        "resolution": resolution,
        "description": expected.get("description", ""),
        "checks": checks,
        "passed": passed_count,
        "failed": failed_count,
        "timing": timing,
        "diagnostics": {
            "battlelist": bl_result["diagnostics"],
            "radar": radar_result["diagnostics"],
            "gamewindow": gw_result["diagnostics"],
            "statusbar": sb_result["diagnostics"],
            "skills": skills_result["diagnostics"],
            "actionbar": actionbar_result["diagnostics"],
            "inventory": inventory_result["diagnostics"],
            "depot_slots": depot_slots_result["diagnostics"],
            "connection": connection_result["diagnostics"],
            "pathfinding": pf_walkable["diagnostics"],
            "gameplay": gp_decision["diagnostics"],
        },
        "original_image": screenshot_bgr,
        "annotated_image": annotated_image,
    }


def generate_side_by_side(original, annotated):
    """Create side-by-side composite image."""
    if original is None or annotated is None:
        return annotated if annotated is not None else original
    h = max(original.shape[0], annotated.shape[0])
    orig_padded = np.zeros((h, original.shape[1], 3), dtype=np.uint8)
    orig_padded[:original.shape[0], :] = original
    ann_padded = np.zeros((h, annotated.shape[1], 3), dtype=np.uint8)
    ann_padded[:annotated.shape[0], :] = annotated
    return np.hstack([orig_padded, ann_padded])


def save_outputs(results, dry_run=False, side_by_side=False):
    """Save annotated images + JSON report. Mutates results by popping image arrays."""
    if not dry_run:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    total_checks = sum(r.get("passed", 0) + r.get("failed", 0) for r in results)
    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)

    summary_by_os = {}
    for os_name in SUPPORTED_OS:
        os_results = [r for r in results if r.get("os") == os_name]
        if not os_results:
            summary_by_os[os_name] = {"images": 0, "passed": 0, "failed": 0}
            continue
        summary_by_os[os_name] = {
            "images": len(os_results),
            "passed": sum(1 for r in os_results if r.get("failed", 1) == 0),
            "failed": sum(1 for r in os_results if r.get("failed", 0) > 0),
        }

    # Pop images from results before serializing
    for result in results:
        original = result.pop("original_image", None)
        annotated = result.pop("annotated_image", None)

        if dry_run or annotated is None:
            continue

        os_name = result.get("os", "unknown")
        name = result.get("name", "unknown")
        image_dir = IMAGES_DIR / os_name
        image_dir.mkdir(parents=True, exist_ok=True)

        cv2.imwrite(str(image_dir / f"{name}.png"), annotated)
        if side_by_side and original is not None:
            composite = generate_side_by_side(original, annotated)
            cv2.imwrite(str(image_dir / f"{name}_sidebyside.png"), composite)

    report = {
        "timestamp": datetime.now().isoformat(timespec="seconds"),
        "git_hash": get_git_hash(),
        "total_images": len(results),
        "total_checks": total_checks,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "summary_by_os": summary_by_os,
        "results": results,
    }

    if not dry_run:
        report_path = REPORTS_DIR / f"report_{timestamp}.json"
        latest_path = REPORTS_DIR / "latest.json"
        with open(report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)
        with open(latest_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2, ensure_ascii=False, default=str)

    return report


def print_summary_table(results, previous_report):
    """Print console table with OS, image, BL, GW, FP, Bars, Checks, Time."""
    header = f"{'OS':<8} {'Image':<35} {'BL':>3} {'GW':>3} {'FP':>3} {'Bars':>5} {'Checks':>8} {'Time':>7}"
    sep = f"{'-'*8} {'-'*35} {'-'*3} {'-'*3} {'-'*3} {'-'*5} {'-'*8} {'-'*7}"
    print(header)
    print(sep)

    for r in results:
        if "error" in r and r.get("checks") == []:
            print(f"{r.get('os',''):<8} {r['name']:<35} {'ERROR':>28}")
            continue

        diag = r.get("diagnostics", {})
        bl_count = diag.get("battlelist", {}).get("creature_count", 0)
        gw_diag = diag.get("gamewindow", {})
        gw_monsters = gw_diag.get("monster_count", 0)
        gw_fp = gw_diag.get("player_count", 0)
        gw_bars = gw_diag.get("bar_count", 0)
        passed = r.get("passed", 0)
        total = passed + r.get("failed", 0)
        checks_str = f"{passed}/{total}"
        timing = r.get("timing", {})
        total_ms = timing.get("total_ms", 0)

        image_key = f"{r.get('os', 'unknown')}/{r.get('name', '')}"
        is_passed = r.get("failed", 1) == 0
        regression = get_regression_status(image_key, is_passed, previous_report)
        marker = f"  {regression}" if regression else ""

        print(
            f"{r.get('os',''):<8} {r['name']:<35} {bl_count:>3} {gw_monsters:>3} "
            f"{gw_fp:>3} {gw_bars:>5} {checks_str:>8} {total_ms:>6.0f}ms{marker}"
        )


def print_failures(results, verbose=False):
    """Print detailed failure info."""
    failed_results = [r for r in results if r.get("failed", 0) > 0]
    if not failed_results:
        return

    print()
    for r in failed_results:
        os_name = r.get("os", "unknown")
        name = r.get("name", "?")
        print(f"  {os_name}/{name}:")
        for check in r.get("checks", []):
            if not check["passed"]:
                print(f"    FAIL {check['name']}: expected={check['expected']}, actual={check['actual']}")
                if check.get("rationale"):
                    print(f"         Rationale: {check['rationale']}")
        if verbose:
            for check in r.get("checks", []):
                if check["passed"]:
                    print(f"    PASS {check['name']}: {check['actual']}")


def print_os_summary(results):
    """Print per-OS pass/fail counts."""
    os_stats = {}
    for r in results:
        os_name = r.get("os", "unknown")
        if os_name not in os_stats:
            os_stats[os_name] = {"passed": 0, "failed": 0}
        if r.get("failed", 0) == 0:
            os_stats[os_name]["passed"] += 1
        else:
            os_stats[os_name]["failed"] += 1

    parts = []
    for os_name in SUPPORTED_OS:
        stats = os_stats.get(os_name, {"passed": 0, "failed": 0})
        total = stats["passed"] + stats["failed"]
        parts.append(f"{os_name} {stats['passed']}/{total}")
    print("OS: " + " | ".join(parts))


def print_coverage_warnings():
    """List monsters in battlelist image dir without e2e coverage."""
    monsters_dir = Path(__file__).parent.parent / "src" / "repositories" / "battlelist" / "images" / "monsters"
    if not monsters_dir.exists():
        return

    covered_names = set()
    for json_path in SCREENSHOTS_DIR.rglob("*.expected.json"):
        try:
            data = load_expected(json_path)
            bl = data.get("repositories", {}).get("battlelist", {})
            for name in bl.get("names", []):
                covered_names.add(name.lower())
        except Exception:
            pass

    uncovered = []
    for img_path in sorted(monsters_dir.glob("*.png")):
        monster_name = img_path.stem.lower().replace("_", " ")
        if monster_name not in covered_names:
            uncovered.append(img_path.stem)

    if uncovered:
        print()
        print(f"[COVERAGE] {len(uncovered)} monster(s) without e2e coverage:")
        for name in uncovered:
            print(f"  - {name}")


def _build_expected_from_diagnostics(result):
    """Build .expected.json content from detector diagnostics."""
    diag = result.get("diagnostics", {})
    bl = diag.get("battlelist", {})
    gw = diag.get("gamewindow", {})
    radar = diag.get("radar", {})
    sb = diag.get("statusbar", {})

    attacked_name = None
    for c in bl.get("creatures", []):
        if c.get("is_being_attacked"):
            attacked_name = c["name"]
            break

    statusbar = None
    hp = sb.get("hp_percent")
    mana = sb.get("mana_percent")
    if hp is not None or mana is not None:
        statusbar = {}
        if hp is not None:
            statusbar["hp_range"] = [hp, hp]
        if mana is not None:
            statusbar["mana_range"] = [mana, mana]

    return {
        "description": result.get("description", "TODO: describe this scenario"),
        "resolution": result.get("resolution", ""),
        "capture_method": None,
        "capture_date": None,
        "tibia_client_version": None,
        "repositories": {
            "battlelist": {
                "count": bl.get("creature_count", 0),
                "names": sorted(set(c["name"] for c in bl.get("creatures", []))),
                "attacking": attacked_name,
            },
            "gamewindow": {
                "monster_count": gw.get("monster_count", 0),
                "max_false_positives": gw.get("player_count", 0),
                "max_bar_noise": gw.get("bar_count", 0),
                "attacking": any(
                    m.get("is_being_attacked", False) for m in gw.get("monsters", [])),
            },
            "radar": {"found": radar.get("found", False)},
            "statusbar": statusbar,
            "skills": None,
            "actionbar": None,
            "inventory": None,
        },
        "pathfinding": None,
        "gameplay": None,
    }


def _update_expected_files(entries, results):
    """Overwrite .expected.json files with detected values."""
    entry_map = {e["name"]: e for e in entries}
    for result in results:
        name = result.get("name")
        entry = entry_map.get(name)
        if not entry or not entry.get("expected_path"):
            continue

        new_expected = _build_expected_from_diagnostics(result)
        # Preserve existing description and metadata
        old = entry.get("expected", {})
        if old.get("description"):
            new_expected["description"] = old["description"]
        if old.get("capture_method"):
            new_expected["capture_method"] = old["capture_method"]
        if old.get("capture_date"):
            new_expected["capture_date"] = old["capture_date"]
        if old.get("tibia_client_version"):
            new_expected["tibia_client_version"] = old["tibia_client_version"]

        confirm = input(f"Update {entry['expected_path']}? [y/N] ")
        if confirm.lower() != "y":
            continue

        with open(entry["expected_path"], "w", encoding="utf-8") as f:
            json.dump(new_expected, f, indent=2, ensure_ascii=False)
        print(f"  Updated: {entry['expected_path']}")


def main():
    parser = argparse.ArgumentParser(description="E2E test runner for detection pipeline")
    parser.add_argument("--os", dest="os_filter", choices=SUPPORTED_OS, default=None,
                        help="Filter by OS")
    parser.add_argument("--image", dest="image_filter", default=None,
                        help="Filter by image name (substring match)")
    parser.add_argument("--module", dest="module_filter", default=None,
                        help="Filter which validators run (not detectors)")
    parser.add_argument("--verbose", "-v", action="store_true",
                        help="Detailed output with timing per module")
    parser.add_argument("--dry-run", action="store_true",
                        help="Run without saving output")
    parser.add_argument("--fail-fast", action="store_true",
                        help="Stop on first failure")
    parser.add_argument("--json", dest="json_output", action="store_true",
                        help="JSON-only output")
    parser.add_argument("--no-annotate", action="store_true",
                        help="Skip image annotation")
    parser.add_argument("--side-by-side", action="store_true",
                        help="Generate side-by-side images (opt-in)")
    parser.add_argument("--update-expected", action="store_true",
                        help="Overwrite .expected.json with detected values")
    args = parser.parse_args()

    entries = discover_screenshots(args.os_filter, args.image_filter)

    if not entries:
        if not args.json_output:
            print("No screenshots found.")
        sys.exit(0)

    git_hash = get_git_hash()
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    previous_report = load_previous_report()

    if not args.json_output:
        print(f"E2E Test Results — {now} (commit {git_hash})")
        print(f"Screenshots: {len(entries)}")
        print()

    results = []
    for entry in entries:
        result = run_single(
            entry,
            module_filter=args.module_filter,
            verbose=args.verbose,
            no_annotate=args.no_annotate,
        )
        results.append(result)

        if not args.json_output and args.verbose:
            timing = result.get("timing", {})
            print(f"  [{result['os']}/{result['name']}]  "
                  f"BL={timing.get('battlelist_ms', 0):.0f}ms  "
                  f"Radar={timing.get('radar_ms', 0):.0f}ms  "
                  f"GW={timing.get('gamewindow_ms', 0):.0f}ms  "
                  f"Total={timing.get('total_ms', 0):.0f}ms")

        if args.fail_fast and result.get("failed", 0) > 0:
            if not args.json_output:
                print(f"[FAIL-FAST] Stopping at {result['name']}")
            break

    if args.update_expected:
        _update_expected_files(entries, results)

    report = save_outputs(results, dry_run=args.dry_run, side_by_side=args.side_by_side)

    if args.json_output:
        print(json.dumps(report, indent=2, default=str))
        total_failed = sum(r.get("failed", 0) for r in results)
        sys.exit(1 if total_failed > 0 else 0)

    print_summary_table(results, previous_report)

    total_checks = sum(r.get("passed", 0) + r.get("failed", 0) for r in results)
    total_passed = sum(r.get("passed", 0) for r in results)
    total_failed = sum(r.get("failed", 0) for r in results)

    regression_count = sum(
        1 for r in results
        if get_regression_status(
            f"{r.get('os', 'unknown')}/{r.get('name', '')}",
            r.get("failed", 1) == 0,
            previous_report,
        ) == MARKER_REGRESSION
    )
    fixed_count = sum(
        1 for r in results
        if get_regression_status(
            f"{r.get('os', 'unknown')}/{r.get('name', '')}",
            r.get("failed", 1) == 0,
            previous_report,
        ) == MARKER_FIXED
    )

    print()
    summary_parts = [f"{total_passed}/{total_checks} checks passed"]
    if regression_count:
        summary_parts.append(f"{regression_count} REGRESSION")
    if fixed_count:
        summary_parts.append(f"{fixed_count} FIXED")
    print("Summary: " + " | ".join(summary_parts))
    print_os_summary(results)

    print_failures(results, verbose=args.verbose)
    print_coverage_warnings()

    sys.exit(1 if total_failed > 0 else 0)


if __name__ == "__main__":
    main()

#!/usr/bin/env python3
"""
Tibia Bot - PyTibia Style

Main entry point for the bot.

Usage:
    python main.py                          # Run with default settings (local env)
    python main.py --env prod               # Run with production environment
    python main.py --gui --env prod         # GUI with production environment
    python main.py --waypoints hunt.json    # Load waypoints from file

Controls:
    Ctrl+C  - Stop the bot
"""
import sys
import os
import argparse
import time

# Add src to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file based on --env flag (peek at argv before argparse)
from dotenv import load_dotenv

def _load_env():
    env = "local"
    for i, arg in enumerate(sys.argv):
        if arg == "--env" and i + 1 < len(sys.argv):
            env = sys.argv[i + 1]
            break
        if arg.startswith("--env="):
            env = arg.split("=", 1)[1]
            break
    project_root = os.path.dirname(os.path.abspath(__file__))
    env_file = os.path.join(project_root, f".env.{env}")
    if not os.path.exists(env_file):
        print(f"ERROR: Environment file not found: {env_file}")
        print(f"Available: .env.local, .env.prod")
        sys.exit(1)
    load_dotenv(env_file)
    os.environ["TIBIAEYE_ENV"] = env
    return env

_current_env = _load_env()

import pyautogui
pyautogui.FAILSAFE = False  # Don't stop when mouse moves to corner
pyautogui.PAUSE = 0  # No delay between pyautogui commands (critical for macOS)

import src.utils.input  # noqa: F401 - patches pyautogui with screen offset

from src.gameplay.context import get_context
from src.gameplay.gameloop import GameLoop
from src.gameplay.cavebot import load_waypoints_from_file
from src.license import LicenseValidator, LicenseExpiredException, LicenseInvalidException


def parse_args():
    parser = argparse.ArgumentParser(description='Tibia Bot - PyTibia Style')
    parser.add_argument('--waypoints', '-w', type=str, help='Waypoints JSON file')
    parser.add_argument('--start-waypoint', '-s', type=int, default=0,
                        help='Start from waypoint index (0-based)')
    parser.add_argument('--tick-rate', '-t', type=float, default=0.100,
                        help='Tick rate in seconds (default: 0.100)')
    parser.add_argument('--no-healing', action='store_true',
                        help='Disable healing system')
    parser.add_argument('--no-cavebot', action='store_true',
                        help='Disable cavebot (only healing)')
    parser.add_argument('--log', '-l', action='store_true',
                        help='Enable detailed session logging (saves to logs/)')
    parser.add_argument('--log-dir', type=str, default='logs',
                        help='Directory for log files (default: logs/)')
    parser.add_argument('--debug-pathfinding', action='store_true',
                        help='Debug pathfinding (shows walkable matrix)')
    parser.add_argument('--gui', action='store_true',
                        help='Launch with graphical interface')
    parser.add_argument('--hardware', choices=['software', 'arduino', 'full_hardware'],
                        default='software', help='Hardware mode (default: software)')
    parser.add_argument('--arduino-port', type=str, default='',
                        help='Serial port for Arduino (auto-detect if empty)')
    parser.add_argument('--capture-device', type=int, default=0,
                        help='OpenCV device index for capture card (default: 0)')
    parser.add_argument('--debug-hardware', action='store_true',
                        help='Log every command sent to Arduino')
    parser.add_argument('--env', choices=['local', 'prod'], default='local',
                        help='Environment to use (default: local)')
    return parser.parse_args()


def print_banner():
    env_label = "PROD" if _current_env == "prod" else "LOCAL"
    print("=" * 60)
    print(f"  TIBIA BOT - PyTibia Style  [{env_label}]")
    print("=" * 60)
    print()


def setup_context(args) -> dict:
    """Setup the game context with configuration."""
    context = get_context()

    # Enable cavebot
    context['cavebot']['enabled'] = not args.no_cavebot

    # Enable healing
    context['healing']['enabled'] = not args.no_healing

    # Configure healing spells (press hotkey when HP below threshold)
    context['healing']['spells'] = [
        {'hotkey': '3', 'hpPercentageLessThanOrEqual': 60, 'enabled': True},  # Light heal
    ]

    # Configure healing potions
    context['healing']['potions'] = [
        {'hotkey': '2', 'type': 'mana', 'hpPercentageLessThanOrEqual': 30, 'enabled': True},  # Mana potion
        {'hotkey': '1', 'type': 'hp', 'hpPercentageLessThanOrEqual': 30, 'enabled': True},    # Health potion
    ]

    # High priority healing (emergency)
    context['healing']['highPriority'] = {
        'enabled': True,
        'hpPercentageLessThanOrEqual': 30,
        'manaPercentageGreaterThanOrEqual': 10,
    }

    # Eat food when hungry (like PyTibia - reads from Skills window)
    # DISABLED: Food detection needs calibration
    context['healing']['eatFood'] = {
        'enabled': False,  # Disabled for now
        'hotkey': 'f',  # Hotkey for food
        'eatWhenFoodIsLessOrEqual': 5,  # Eat when food <= 5 minutes
    }

    # Enable loot
    context['loot']['enabled'] = True
    context['loot']['hotkey'] = 'g'

    # Stuck alert config (set to 10 seconds for testing, change to 120 for production)
    context['cavebot']['stuckAlert'] = {
        'enabled': True,
        'timeoutSeconds': 120,
    }

    # Load waypoints
    if args.waypoints:
        waypoints = load_waypoints_from_file(args.waypoints)
        context['cavebot']['waypoints']['items'] = waypoints
        # Start from specified waypoint index
        start_index = args.start_waypoint
        if start_index >= len(waypoints):
            print(f"Warning: start-waypoint {start_index} >= total waypoints {len(waypoints)}, starting from 0")
            start_index = 0
        context['cavebot']['waypoints']['currentIndex'] = start_index
        if start_index > 0:
            print(f"Starting from waypoint {start_index}")

    return context


def validate_license():
    """Validate license key before starting the bot.

    Returns:
        LicenseValidator if valid or offline, None if no key configured.
    """
    api_key = os.getenv("TELEMETRY_API_KEY")
    if not api_key:
        print("No TELEMETRY_API_KEY configured - running without license/telemetry")
        return None

    print("Validating license...")
    validator = LicenseValidator(api_key=api_key)

    try:
        validator.validate(raise_on_error=True)
    except LicenseExpiredException as e:
        print(f"ERROR: Your license has expired on {e.expires_at}")
        print("Please renew your subscription at https://tibiaeye.com")
        sys.exit(1)
    except LicenseInvalidException as e:
        print(f"ERROR: Invalid license key - {e}")
        sys.exit(1)
    except Exception as e:
        print(f"WARNING: Could not validate license ({e})")
        print("Continuing in offline mode...")

    if validator.is_valid:
        print(f"  License valid! Days remaining: {validator.days_remaining}")
        if validator.status and validator.status.is_expiring_soon:
            print(f"  WARNING: License expiring soon! Please renew.")

    return validator


def check_battlelist():
    """Check if battle list is detected."""
    from src.repositories.battlelist import BattleListRepository

    print("Checking battle list detection...")
    repo = BattleListRepository()

    if repo.is_detected:
        print("  Battle list: OK")
        return True
    else:
        print("  Battle list: NOT DETECTED")
        print()
        print("Make sure:")
        print("  1. Tibia is running")
        print("  2. Battle list window is open")
        return False


def display_skills_info() -> bool:
    """
    Display current player skills from the skills window.

    Returns True if skills were read successfully, False otherwise.
    """
    from src.repositories.skills.core import (
        get_hp, get_mana, get_capacity, get_speed, get_food, get_stamina
    )
    from src.repositories.skills.locators import get_skills_icon_position
    from mss import mss
    import cv2
    import numpy as np

    print("Reading player skills...")

    # Capture screenshot
    with mss() as sct:
        screenshot = np.array(sct.grab(sct.monitors[1]))
        gray = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)

    # Check if skills window is visible
    skills_pos = get_skills_icon_position(gray)
    if skills_pos is None:
        print()
        print("-" * 40)
        print("  ERROR: Skills window not detected!")
        print("-" * 40)
        print("  Make sure the Skills window is open in Tibia.")
        print("  (Press Ctrl+S in game to open it)")
        print("-" * 40)
        print()
        return False

    # Read all skills
    hp = get_hp(gray)
    mana = get_mana(gray)
    capacity = get_capacity(gray)
    speed = get_speed(gray)
    food = get_food(gray)
    stamina = get_stamina(gray)

    # Check if we got valid data
    all_none = all(v is None for v in [hp, mana, capacity, speed, food, stamina])
    all_zero = all(v == 0 for v in [hp, mana, capacity, speed])

    if all_none:
        print()
        print("-" * 40)
        print("  ERROR: Could not read skills data!")
        print("-" * 40)
        print("  The skills window was found but values")
        print("  could not be read. Check if:")
        print("  1. The skills panel is fully visible")
        print("  2. No windows are overlapping it")
        print("-" * 40)
        print()
        return False

    if all_zero and hp == 0:
        print()
        print("-" * 40)
        print("  WARNING: All skill values are 0")
        print("-" * 40)
        print("  This may indicate a detection problem.")
        print("  Verify the values match your character.")
        print("-" * 40)
        print()

    # Display skills info
    print()
    print("-" * 40)
    print("  PLAYER STATUS")
    print("-" * 40)
    print(f"  HP:       {hp if hp is not None else 'Error'}")
    print(f"  Mana:     {mana if mana is not None else 'Error'}")
    print(f"  Capacity: {capacity if capacity is not None else 'Error'}")
    print(f"  Speed:    {speed if speed is not None else 'Error'}")
    print(f"  Food:     {food if food is not None else 'Error'} minutes")

    if stamina is not None:
        hours = stamina // 60
        mins = stamina % 60
        print(f"  Stamina:  {stamina} minutes ({hours}h {mins}m)")
    else:
        print(f"  Stamina:  Error")

    print("-" * 40)
    print()

    return True


def check_radar():
    """Check if radar/minimap is at correct zoom level."""
    from src.repositories.radar import check_radar_zoom

    print("Checking radar/minimap...")
    ok, message = check_radar_zoom()

    if ok:
        print(f"  {message}")
        return True
    else:
        print(f"  Radar: ERROR")
        print()
        print(f"  Problem: {message}")
        print()
        print("  How to fix:")
        print("  1. Open the minimap in Tibia")
        print("  2. Click the CENTER button (between + and -) to reset zoom")
        print("  3. Make sure the minimap is fully visible")
        return False


def main():
    args = parse_args()

    # Launch GUI mode if requested
    if args.gui:
        from src.gui import TibiaVisionGUI
        print("Launching GUI mode...")
        app = TibiaVisionGUI()
        app.run()
        return

    print_banner()

    # Initialize hardware mode (must run after input.py import)
    if args.hardware != 'software':
        from src.hardware import init_hardware
        init_hardware(args.hardware, args.arduino_port, args.capture_device, args.debug_hardware)

    # Validate license (before anything else)
    license_validator = validate_license()

    # Check battle list
    if not check_battlelist():
        print("\nCannot start without battle list detection.")
        print("Please ensure Tibia is running with battle list visible.")
        sys.exit(1)

    # Check radar zoom
    if not check_radar():
        print("\nCannot start without correct radar zoom.")
        print("Please reset the minimap zoom to default.")
        sys.exit(1)

    # Display player skills (HP, Mana, Capacity, etc.)
    if not display_skills_info():
        print("\nCannot start without reading player skills.")
        print("Please ensure the Skills window is open and visible.")
        sys.exit(1)

    # Setup context
    context = setup_context(args)

    # Print configuration
    print()
    print("Configuration:")
    print(f"  Cavebot: {'Enabled' if context['cavebot']['enabled'] else 'Disabled'}")
    print(f"  Healing: {'Enabled' if context['healing']['enabled'] else 'Disabled'}")
    print(f"  Loot: {'Enabled' if context['loot']['enabled'] else 'Disabled'}")
    print(f"  Tick rate: {args.tick_rate * 1000:.0f}ms")

    waypoints = context['cavebot']['waypoints']['items']
    print(f"  Waypoints: {len(waypoints)}")

    print()
    print("Starting in 3 seconds... (Ctrl+C to cancel)")
    time.sleep(3)

    # Create and run game loop
    loop = GameLoop(
        tick_rate=args.tick_rate,
        license_validator=license_validator,
        character_id=os.getenv("CHARACTER_ID"),
    )
    loop.setup_default_middlewares()

    if not args.no_healing:
        loop.setup_default_healing()

    # Enable session logging if requested
    if args.log:
        loop.enable_session_logging(args.log_dir)

    # Enable pathfinding debug if requested
    if args.debug_pathfinding:
        loop.debug_pathfinding = True
        print("Pathfinding debug ENABLED - will print walkable matrix")

    # Start unpaused
    loop.paused = False

    print()
    print("Bot running! Press Ctrl+C to stop.")
    print("-" * 40)

    loop.run()


if __name__ == "__main__":
    main()

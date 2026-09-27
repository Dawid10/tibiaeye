#!/usr/bin/env python3
"""
Tibia-Vision Bot - GUI Mode

Launch the graphical interface for the bot.

Usage:
    python gui.py                # Local environment (default)
    python gui.py --env prod     # Production environment
    python gui.py --dry-run      # Log key/mouse input instead of sending it

Requires:
    pip install customtkinter
"""
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

# Load .env file based on --env flag
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
pyautogui.PAUSE = 0  # No delay between pyautogui commands

import src.utils.input  # noqa: F401 - patches pyautogui with screen offset

if "--dry-run" in sys.argv:
    from src.utils.dry_run import enable_dry_run
    enable_dry_run()

from src.gui import TibiaVisionGUI


def main():
    """Launch the GUI application."""
    env_label = "PROD" if _current_env == "prod" else "LOCAL"
    print("=" * 50)
    print(f"  TIBIA-VISION BOT - GUI Mode  [{env_label}]")
    print("=" * 50)
    print()
    print(f"Environment: {_current_env} (.env.{_current_env})")
    print()

    app = TibiaVisionGUI()
    app.run()


if __name__ == "__main__":
    main()

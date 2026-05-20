#!/usr/bin/env python3
"""
Waypoint Recorder - Record waypoints while you play.

Controls:
    F6  - Add WALK waypoint at current position
    F7  - Add ROPE waypoint (use rope here)
    F8  - Add SHOVEL waypoint (use shovel here)
    F9  - Add LABEL waypoint (asks for label name)
    F10 - Add REFILL CHECKER waypoint
    F11 - Save waypoints to file
    F12 - Stop recording

Usage:
    python waypoint_recorder.py output.json
    python waypoint_recorder.py routes/my_hunt.json
"""
import sys
import os
import json
import time
import threading

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from pynput import keyboard
from src.core import get_screen_capture
from src.repositories.radar import get_coordinate
import cv2


class WaypointRecorder:
    def __init__(self, output_file: str):
        self.output_file = output_file
        self.waypoints = []
        self.running = True
        self.screen = get_screen_capture()
        self._previous_coord = None
        self._label_counter = 0

        # Load existing waypoints if file exists
        if os.path.exists(output_file):
            try:
                with open(output_file, 'r') as f:
                    data = json.load(f)
                    self.waypoints = data.get('waypoints', [])
                    # Ensure all waypoints have correct IDs
                    for i, wp in enumerate(self.waypoints):
                        wp['id'] = i
                    print(f"Loaded {len(self.waypoints)} existing waypoints")
            except:
                pass

    def get_current_coordinate(self):
        """Get current coordinate from radar."""
        img = self.screen.capture()
        gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        coord = get_coordinate(gray, self._previous_coord)
        if coord:
            self._previous_coord = coord
        return coord

    def add_waypoint(self, wp_type: str, options: dict = None, label: str = ""):
        """Add a waypoint at current position."""
        coord = self.get_current_coordinate()
        if coord is None:
            print("ERROR: Could not detect current coordinate!")
            return False

        waypoint_id = len(self.waypoints)  # 0-based index
        waypoint = {
            "id": waypoint_id,
            "type": wp_type,
            "coordinate": list(coord),
            "label": label,
            "options": options or {}
        }

        self.waypoints.append(waypoint)
        print(f"[{waypoint_id}] Added {wp_type} at {coord} {f'({label})' if label else ''}")
        return True

    def add_walk(self):
        """Add walk waypoint."""
        self.add_waypoint("walk")

    def add_rope(self):
        """Add rope waypoint."""
        self.add_waypoint("useRope", {"hotkey": "t"})

    def add_shovel(self):
        """Add shovel waypoint."""
        self.add_waypoint("useShovel", {"hotkey": "r"})

    def add_label(self, name: str = None):
        """Add label waypoint."""
        if name is None:
            self._label_counter += 1
            name = f"label_{self._label_counter}"
        self.add_waypoint("label", label=name)

    def add_refill_checker(self):
        """Add refill checker waypoint."""
        options = {
            "minimumAmountOfHealthPotions": 50,
            "minimumAmountOfManaPotions": 100,
            "minimumAmountOfCap": 300,
            "waypointLabelToRedirect": "huntStart"
        }
        self.add_waypoint("refillChecker", options, label="checkSupplies")

    def add_move_down(self, direction: str = "south"):
        """Add moveDown waypoint."""
        self.add_waypoint("moveDown", {"direction": direction})

    def add_move_up(self, direction: str = "south"):
        """Add moveUp waypoint."""
        self.add_waypoint("moveUp", {"direction": direction})

    def save(self):
        """Save waypoints to file."""
        # Ensure directory exists
        os.makedirs(os.path.dirname(self.output_file) or '.', exist_ok=True)

        data = {
            "name": os.path.splitext(os.path.basename(self.output_file))[0],
            "waypoints": self.waypoints,
            "metadata": {
                "recorded_at": time.strftime("%Y-%m-%d %H:%M:%S")
            }
        }

        with open(self.output_file, 'w') as f:
            json.dump(data, f, indent=2)

        print(f"\nSaved {len(self.waypoints)} waypoints to {self.output_file}")

    def undo(self):
        """Remove last waypoint."""
        if self.waypoints:
            removed = self.waypoints.pop()
            print(f"Removed: {removed['type']} at {removed['coordinate']}")
        else:
            print("No waypoints to remove")

    def stop(self):
        """Stop recording."""
        self.running = False


def main():
    if len(sys.argv) < 2:
        print("Usage: python waypoint_recorder.py <output_file.json>")
        print("Example: python waypoint_recorder.py routes/my_hunt.json")
        sys.exit(1)

    output_file = sys.argv[1]
    recorder = WaypointRecorder(output_file)

    print("=" * 60)
    print("  WAYPOINT RECORDER")
    print("=" * 60)
    print()
    print("Controls:")
    print("  F6  - Add WALK waypoint")
    print("  F7  - Add ROPE waypoint")
    print("  F8  - Add SHOVEL waypoint")
    print("  F9  - Add LABEL (type name in terminal)")
    print("  F10 - Add REFILL CHECKER")
    print("  F5  - UNDO last waypoint")
    print("  F11 - SAVE to file")
    print("  F12 - STOP recording")
    print()
    print("  Shift+F6 - Add MOVE DOWN (stairs)")
    print("  Shift+F7 - Add MOVE UP (stairs)")
    print()
    print(f"Output: {output_file}")
    print("=" * 60)
    print()

    # Show current position
    coord = recorder.get_current_coordinate()
    if coord:
        print(f"Current position: {coord}")
    else:
        print("WARNING: Could not detect position. Make sure Tibia is visible!")

    print()
    print("Recording... Press F12 to stop.")
    print()

    # Track shift state
    shift_pressed = False

    def on_press(key):
        nonlocal shift_pressed

        try:
            if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
                shift_pressed = True
                return

            if key == keyboard.Key.f6:
                if shift_pressed:
                    recorder.add_move_down()
                else:
                    recorder.add_walk()

            elif key == keyboard.Key.f7:
                if shift_pressed:
                    recorder.add_move_up()
                else:
                    recorder.add_rope()

            elif key == keyboard.Key.f8:
                recorder.add_shovel()

            elif key == keyboard.Key.f9:
                print("Enter label name: ", end="", flush=True)
                name = input()
                recorder.add_label(name)

            elif key == keyboard.Key.f10:
                recorder.add_refill_checker()

            elif key == keyboard.Key.f5:
                recorder.undo()

            elif key == keyboard.Key.f11:
                recorder.save()

            elif key == keyboard.Key.f12:
                recorder.save()
                recorder.stop()
                return False  # Stop listener

        except Exception as e:
            print(f"Error: {e}")

    def on_release(key):
        nonlocal shift_pressed
        if key == keyboard.Key.shift or key == keyboard.Key.shift_r:
            shift_pressed = False

    # Start keyboard listener
    with keyboard.Listener(on_press=on_press, on_release=on_release) as listener:
        while recorder.running:
            time.sleep(0.1)
        listener.stop()

    print()
    print("Recording stopped.")
    print(f"Total waypoints: {len(recorder.waypoints)}")


if __name__ == "__main__":
    main()

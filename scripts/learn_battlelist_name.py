"""
Teach the bot a battle list name it can't read on this client.

When the log repeats "[BattleList] Template match FAILED", the shipped template for that
monster was captured on another client. With the monster on the battle list, run:

    ./venv/bin/python scripts/learn_battlelist_name.py "Stonerefiner"            # slot 1, live screen
    ./venv/bin/python scripts/learn_battlelist_name.py "Swamp Troll" --slot 2
    ./venv/bin/python scripts/learn_battlelist_name.py "Bat" --file shot.png

Saves the slot's name fingerprint to learned_hashes.json (O(1) lookup from then on).
"""
import argparse
import difflib
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.battlelist import BattleListRepository  # noqa: E402
from src.repositories.battlelist.config import MONSTERS_PATH  # noqa: E402


def grab_gray(file_path):
    if file_path:
        return cv2.cvtColor(cv2.imread(file_path), cv2.COLOR_BGR2GRAY)
    import mss
    with mss.mss() as screen:
        return cv2.cvtColor(np.array(screen.grab(screen.monitors[1])), cv2.COLOR_BGRA2GRAY)


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument('name', help='Exact monster name as shown in Tibia')
    parser.add_argument('--slot', type=int, default=1, help='Battle list row, 1 = top (default 1)')
    parser.add_argument('--file', help='Use a screenshot instead of the live screen')
    args = parser.parse_args()

    known = sorted(f[:-4] for f in os.listdir(MONSTERS_PATH) if f.endswith('.png'))
    if args.name not in known:
        suggestions = difflib.get_close_matches(args.name, known, n=3)
        print(f"'{args.name}' is not a known monster name. Did you mean: {suggestions}?")
        return 1

    gray = grab_gray(args.file)
    repo = BattleListRepository()
    name_hash = repo.get_slot_hash(gray, args.slot - 1)
    if name_hash is None:
        print(f"No creature in battle list row {args.slot} (is the battle list visible, filter buttons hidden?).")
        return 1
    repo.learn_name(name_hash, args.name)

    names = [c.name for c in BattleListRepository().get_creatures(gray)]
    print(f"Saved {name_hash} -> '{args.name}'. Battle list now reads: {names}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

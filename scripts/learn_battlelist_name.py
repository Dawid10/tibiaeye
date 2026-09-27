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
from src.repositories.battlelist.config import (  # noqa: E402
    MONSTERS_PATH, hashit, normalize_text_pixels, save_learned_hash,
)


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
    content = repo._get_content(gray)
    if content is None:
        print("Battle list not found on screen (is it visible, filter buttons hidden?).")
        return 1
    filled = repo._get_filled_slots_count(content)
    if not 1 <= args.slot <= filled:
        print(f"Battle list shows {filled} creature(s); slot {args.slot} is empty.")
        return 1

    y = repo.SLOT_START_Y + (args.slot - 1) * repo.SLOT_HEIGHT
    row = content[y, repo.NAME_START_X:min(content.shape[1], repo.NAME_START_X + repo.NAME_WIDTH)]
    name_hash = hashit(normalize_text_pixels(row, repo.NAME_WIDTH))
    save_learned_hash(name_hash, args.name, overwrite=True)

    names = [c.name for c in BattleListRepository().get_creatures(gray)]
    print(f"Saved {name_hash} -> '{args.name}'. Battle list now reads: {names}")
    return 0


if __name__ == '__main__':
    sys.exit(main())

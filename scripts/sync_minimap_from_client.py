"""
Update the bot's radar map from the Tibia client's own explored minimap.

The shipped floor images come from PyTibia's copy of the official map. Where this server differs
(new or changed areas), the radar can't find the position there and the recorder says it can't
detect it. The client saves every tile you have seen as Minimap_Color_X_Y_Z.png (what the minimap
shows) and Minimap_WaypointCost_X_Y_Z.png (walkability). Explored pixels from those files replace
the bot's, everything else is kept.

    ./venv/bin/python scripts/sync_minimap_from_client.py            # merge and save
    ./venv/bin/python scripts/sync_minimap_from_client.py --check    # only report what would change

The client writes a floor to disk after you leave it (or log out): walk the new area, change floor
or log out, then run this and restart the bot. Undo with: git checkout src/repositories/radar/images
"""
import argparse
import glob
import os
import sys

import cv2
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.repositories.radar.config import IMAGES_PATH  # noqa: E402

CLIENT_MINIMAP_DIR = os.path.expanduser(
    "~/Library/Application Support/CipSoft GmbH/Tibia/packages/Tibia.app/Contents/Resources/minimap")
MAP_ORIGIN_X = 31744
MAP_ORIGIN_Y = 30976
FLOORS = range(16)
UNEXPLORED_COLOR = (0, 0, 0)


def load_client_floor(minimap_dir, kind, floor, shape):
    """Stitch the client's 256x256 tiles of one floor into a bot-sized image (zeros where no file)."""
    height, width = shape[:2]
    stitched = np.zeros((height, width, 3), np.uint8)
    for path in glob.glob(os.path.join(minimap_dir, f"Minimap_{kind}_*_*_{floor}.png")):
        _, _, tile_x, tile_y, _ = os.path.basename(path)[:-4].split("_")
        left, top = int(tile_x) - MAP_ORIGIN_X, int(tile_y) - MAP_ORIGIN_Y
        tile = cv2.imread(path)
        tile_height, tile_width = tile.shape[:2]
        x0, y0 = max(left, 0), max(top, 0)
        x1, y1 = min(left + tile_width, width), min(top + tile_height, height)
        if x1 <= x0 or y1 <= y0:
            continue
        stitched[y0:y1, x0:x1] = tile[y0 - top:y1 - top, x0 - left:x1 - left]
    return stitched


def merge_floor(minimap_dir, floor, check_only):
    color_path = IMAGES_PATH / f"floor-{floor}.png"
    paths_path = IMAGES_PATH / "paths" / f"floor-{floor}.png"
    if not color_path.exists() or not paths_path.exists():
        return 0
    bot_color = cv2.imread(str(color_path))
    bot_paths = cv2.imread(str(paths_path))
    client_color = load_client_floor(minimap_dir, "Color", floor, bot_color.shape)
    client_paths = load_client_floor(minimap_dir, "WaypointCost", floor, bot_paths.shape)

    explored = np.any(client_color != UNEXPLORED_COLOR, axis=2)
    changed = explored & (np.any(client_color != bot_color, axis=2) | np.any(client_paths != bot_paths, axis=2))
    count = int(changed.sum())
    if count == 0 or check_only:
        return count

    bot_color[explored] = client_color[explored]
    bot_paths[explored] = client_paths[explored]
    cv2.imwrite(str(color_path), bot_color)
    cv2.imwrite(str(paths_path), bot_paths)
    return count


def main():
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="only report, don't save")
    parser.add_argument("--minimap-dir", default=CLIENT_MINIMAP_DIR)
    args = parser.parse_args()

    if not os.path.isdir(args.minimap_dir):
        sys.exit(f"Client minimap folder not found: {args.minimap_dir} (pass --minimap-dir)")

    total = 0
    for floor in FLOORS:
        count = merge_floor(args.minimap_dir, floor, args.check)
        total += count
        if count:
            print(f"floor {floor}: {count} tiles {'differ' if args.check else 'updated'}")

    if total == 0:
        print("Bot map already matches everything the client has saved.")
        return
    if args.check:
        print(f"{total} tiles differ - run without --check to update the bot's map.")
        return
    print(f"Updated {total} tiles. Restart the bot (GUI) to load the new map.")


if __name__ == "__main__":
    main()

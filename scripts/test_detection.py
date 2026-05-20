"""
Test creature and statusbar detection on a capture card image.
Draws green rectangles around detected elements.
"""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import cv2
import numpy as np


def main():
    image_path = sys.argv[1] if len(sys.argv) > 1 else "device_0_twoswamptroll.png"
    output_path = sys.argv[2] if len(sys.argv) > 2 else "debug_detection_result.png"

    frame = cv2.imread(image_path)
    if frame is None:
        print(f"Failed to load {image_path}")
        return

    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
    annotated = frame.copy()
    print(f"Image: {frame.shape[1]}x{frame.shape[0]}")

    # ===================== STATUSBAR =====================
    print("\n=== STATUSBAR ===")
    from src.repositories.statusbar.locators import get_hp_icon_position, get_mana_icon_position
    from src.repositories.statusbar.extractors import get_hp_bar, get_mana_bar
    from src.repositories.statusbar.core import get_filled_percentage
    from src.repositories.statusbar.config import HP_BAR_COLORS, MANA_BAR_COLORS

    hp_pos = get_hp_icon_position(gray)
    mana_pos = get_mana_icon_position(gray)

    if hp_pos:
        x, y, w, h = hp_pos
        print(f"HP icon: ({x}, {y}, {w}, {h})")
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 0), 2)

        bar = get_hp_bar(gray, hp_pos)
        pct = get_filled_percentage(bar, HP_BAR_COLORS)
        bar_x, bar_y = x + 13, y + 5
        cv2.rectangle(annotated, (bar_x, bar_y - 1), (bar_x + 94, bar_y + 2), (0, 255, 0), 1)
        cv2.putText(annotated, f"HP: {pct}%", (bar_x + 100, bar_y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
        print(f"HP: {pct}%")
        print(f"  ALL bar values ({len(bar)}): {bar}")
        print(f"  HP_BAR_COLORS range: {HP_BAR_COLORS.min()}-{HP_BAR_COLORS.max()}")

        # Show which pixels match and which don't
        matches = np.isin(bar, HP_BAR_COLORS)
        print(f"  Matching pixels: {matches.sum()}/{len(bar)}")
        non_match_vals = bar[~matches]
        if len(non_match_vals) > 0:
            print(f"  Non-matching values: {np.unique(non_match_vals)}")

        # Also show the RGB values at bar position to understand the actual colors
        bar_rgb = frame[bar_y, bar_x:bar_x + min(20, len(bar))]
        print(f"  RGB of first 20 bar pixels:")
        for i, px in enumerate(bar_rgb):
            gray_val = bar[i] if i < len(bar) else -1
            print(f"    [{i}] B={px[0]:3d} G={px[1]:3d} R={px[2]:3d} -> gray={gray_val}")
    else:
        print("HP icon: NOT FOUND")

    if mana_pos:
        x, y, w, h = mana_pos
        print(f"\nMana icon: ({x}, {y}, {w}, {h})")
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (255, 0, 0), 2)

        bar = get_mana_bar(gray, mana_pos)
        pct = get_filled_percentage(bar, MANA_BAR_COLORS)
        bar_x, bar_y = x + 14, y + 5
        cv2.rectangle(annotated, (bar_x, bar_y - 1), (bar_x + 94, bar_y + 2), (255, 0, 0), 1)
        cv2.putText(annotated, f"MP: {pct}%", (bar_x + 100, bar_y + 5),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 0, 0), 1)
        print(f"Mana: {pct}%")
        print(f"  ALL bar values ({len(bar)}): {bar}")
        print(f"  Matching pixels: {np.isin(bar, MANA_BAR_COLORS).sum()}/{len(bar)}")
    else:
        print("Mana icon: NOT FOUND")

    # ===================== BATTLELIST =====================
    print("\n=== BATTLELIST ===")
    from src.repositories.battlelist.core import BattleListRepository
    bl_repo = BattleListRepository()
    creatures = bl_repo.get_creatures(gray)
    print(f"Creatures found: {len(creatures)}")
    for c in creatures:
        print(f"  - {c}")

    # ===================== RADAR =====================
    print("\n=== RADAR ===")
    from src.repositories.radar.core import get_coordinate, get_floor_level, set_capture_card_mode
    set_capture_card_mode(True)
    from src.repositories.radar.locators import get_radar_tools_position
    tools_pos = get_radar_tools_position(gray, use_cache=False)
    if tools_pos:
        x, y, w, h = tools_pos
        cv2.rectangle(annotated, (x, y), (x + w, y + h), (0, 255, 255), 2)

    floor = get_floor_level(gray)
    coord = get_coordinate(gray)
    print(f"Floor: {floor}, Coordinate: {coord}")

    # ===================== GAME WINDOW CREATURE BARS =====================
    print("\n=== GAME WINDOW (creature bars) ===")
    from src.repositories.gamewindow.config import load_arrow_images, BLACK_THRESHOLD
    print(f"BLACK_THRESHOLD = {BLACK_THRESHOLD}")

    arrow_imgs = load_arrow_images()
    left_arrows = {k: v for k, v in arrow_imgs.items() if k.startswith('left')}
    right_arrows = {k: v for k, v in arrow_imgs.items() if k.startswith('right')}

    # Find game window manually via arrows
    from src.core.constants import CONFIDENCE_ARROW_HIGH, CONFIDENCE_ARROW_MED, CONFIDENCE_ARROW_LOW
    left_pos = None
    right_pos = None

    for name, tmpl in left_arrows.items():
        result = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(result)
        if mv >= CONFIDENCE_ARROW_LOW:
            left_pos = (ml[0], ml[1], tmpl.shape[1], tmpl.shape[0])
            print(f"Left arrow '{name}': score={mv:.4f} at {ml}")
            break

    for name, tmpl in right_arrows.items():
        result = cv2.matchTemplate(gray, tmpl, cv2.TM_CCOEFF_NORMED)
        _, mv, _, ml = cv2.minMaxLoc(result)
        if mv >= CONFIDENCE_ARROW_LOW:
            right_pos = (ml[0], ml[1], tmpl.shape[1], tmpl.shape[0])
            print(f"Right arrow '{name}': score={mv:.4f} at {ml}")
            break

    if left_pos and right_pos:
        gx = left_pos[0] + left_pos[2]
        gy = left_pos[1]
        gw = right_pos[0] - gx
        gh = right_pos[3]
        print(f"Game window region: ({gx}, {gy}, {gw}, {gh})")
        cv2.rectangle(annotated, (gx, gy), (gx + gw, gy + gh), (0, 200, 200), 1)

        game_img = gray[gy:gy + gh, gx:gx + gw]

        # Look for dark horizontal bars (creature HP bars = dark lines)
        # Scan each row for runs of dark pixels >= 27 wide
        bars_found = []
        for row in range(game_img.shape[0]):
            run_start = -1
            run_len = 0
            for col in range(game_img.shape[1]):
                if game_img[row, col] <= BLACK_THRESHOLD:
                    if run_start < 0:
                        run_start = col
                    run_len += 1
                else:
                    if run_len >= 25:
                        bars_found.append((run_start, row, run_len))
                    run_start = -1
                    run_len = 0

        print(f"Dark bar segments found: {len(bars_found)}")
        for bx, by, bw in bars_found[:20]:
            cv2.rectangle(annotated,
                         (gx + bx, gy + by),
                         (gx + bx + bw, gy + by + 1),
                         (0, 255, 0), 2)
            print(f"  Bar at ({bx}, {by}), width={bw}")

        # If no bars, show pixel value histogram of game window
        if not bars_found:
            print(f"\n  Game window pixel stats: min={game_img.min()}, max={game_img.max()}")
            print(f"  Pixels <= 5: {np.sum(game_img <= 5)}")
            print(f"  Pixels <= 15: {np.sum(game_img <= 15)}")
            print(f"  Pixels <= 25: {np.sum(game_img <= 25)}")
            print(f"  Pixels <= 35: {np.sum(game_img <= 35)}")
    else:
        print("Could not find game window arrows")

    # ===================== SAVE =====================
    cv2.imwrite(output_path, annotated)
    print(f"\nSaved: {output_path}")


if __name__ == "__main__":
    main()

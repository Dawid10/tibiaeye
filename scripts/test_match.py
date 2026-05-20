"""
Test template matching - draws green rectangles where templates match.

Usage:
    python scripts/test_match.py [screenshot] [template1] [template2] ...

Defaults to device_0.png with statusbar heart + mana templates.
"""
import sys
import cv2
import numpy as np


def match_template(screenshot_gray, template_gray, threshold=0.7):
    """Find all matches above threshold. Returns list of (x, y, w, h, score)."""
    if template_gray is None or screenshot_gray is None:
        return []
    result = cv2.matchTemplate(screenshot_gray, template_gray, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)
    h, w = template_gray.shape[:2]
    if max_val >= threshold:
        return [(max_loc[0], max_loc[1], w, h, max_val)]
    return []


def main():
    screenshot_path = sys.argv[1] if len(sys.argv) > 1 else "device_0.png"
    template_paths = sys.argv[2:] if len(sys.argv) > 2 else [
        # statusbar
        "src/repositories/statusbar/images/win32/heart.png",
        "src/repositories/statusbar/images/win32/mana.png",
        # radar
        "src/repositories/radar/images/win32/buttons/radarTools.png",
        "src/repositories/radar/images/win32/floorLevels/0.png",
        "src/repositories/radar/images/win32/floorLevels/1.png",
        "src/repositories/radar/images/win32/floorLevels/2.png",
        "src/repositories/radar/images/win32/floorLevels/3.png",
        "src/repositories/radar/images/win32/floorLevels/4.png",
        "src/repositories/radar/images/win32/floorLevels/5.png",
        "src/repositories/radar/images/win32/floorLevels/6.png",
        "src/repositories/radar/images/win32/floorLevels/7.png",
        "src/repositories/radar/images/win32/floorLevels/8.png",
        "src/repositories/radar/images/win32/floorLevels/9.png",
        "src/repositories/radar/images/win32/floorLevels/10.png",
        "src/repositories/radar/images/win32/floorLevels/11.png",
        "src/repositories/radar/images/win32/floorLevels/12.png",
        "src/repositories/radar/images/win32/floorLevels/13.png",
        "src/repositories/radar/images/win32/floorLevels/14.png",
        "src/repositories/radar/images/win32/floorLevels/15.png",
        # skills
        "src/repositories/skills/images/win32/icons/skills.png",
        "src/repositories/skills/images/win32/digits/0.png",
        "src/repositories/skills/images/win32/digits/1.png",
        "src/repositories/skills/images/win32/digits/2.png",
        "src/repositories/skills/images/win32/digits/3.png",
        "src/repositories/skills/images/win32/digits/4.png",
        "src/repositories/skills/images/win32/digits/5.png",
        "src/repositories/skills/images/win32/digits/6.png",
        "src/repositories/skills/images/win32/digits/7.png",
        "src/repositories/skills/images/win32/digits/8.png",
        "src/repositories/skills/images/win32/digits/9.png",
    ]

    screenshot = cv2.imread(screenshot_path)
    if screenshot is None:
        print(f"Could not load: {screenshot_path}")
        sys.exit(1)

    gray = cv2.cvtColor(screenshot, cv2.COLOR_BGR2GRAY)
    output = screenshot.copy()

    print(f"Screenshot: {screenshot.shape[1]}x{screenshot.shape[0]}")

    for tpath in template_paths:
        template = cv2.imread(tpath, cv2.IMREAD_GRAYSCALE)
        if template is None:
            print(f"  SKIP: {tpath} (not found)")
            continue

        th, tw = template.shape[:2]
        matches = match_template(gray, template, threshold=0.5)

        if matches:
            for x, y, w, h, score in matches:
                cv2.rectangle(output, (x, y), (x + w, y + h), (0, 255, 0), 2)
                label = f"{tpath.split('/')[-1]} ({score:.2f})"
                cv2.putText(output, label, (x, y - 5),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 255, 0), 1)
                print(f"  MATCH: {tpath} -> ({x},{y}) {w}x{h} score={score:.3f}")
        else:
            print(f"  NO MATCH: {tpath} ({tw}x{th})")

    out_path = "match_result.png"
    cv2.imwrite(out_path, output)
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()

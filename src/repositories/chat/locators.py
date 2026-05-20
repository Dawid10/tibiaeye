"""Chat locators - find chat area, tabs, and loot lines on screen."""
from typing import List, Optional, Tuple

import cv2
import numpy as np

from .config import GrayImage
from ...core.constants import CONFIDENCE_CHAT_TAB, CONFIDENCE_LOOT_TEXT


BBox = Tuple[int, int, int, int]  # (x, y, w, h)


def get_loot_tab_position(screenshot: GrayImage, tab_templates: dict) -> Optional[BBox]:
    """Locate the 'Loot' tab in chat via template matching.

    Tries selected, unselected, and new_message variants.
    Returns (x, y, w, h) or None.
    """
    if not tab_templates:
        return None

    for key in ('loot_selected', 'loot_unselected', 'loot_new_message'):
        template = tab_templates.get(key)
        if template is None:
            continue
        if template.shape[0] > screenshot.shape[0] or template.shape[1] > screenshot.shape[1]:
            continue
        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)
        if max_val >= CONFIDENCE_CHAT_TAB:
            x, y = max_loc
            h, w = template.shape[:2]
            return (x, y, w, h)

    return None


def _find_chat_left_edge(screenshot: GrayImage, tab_x: int, tab_y: int) -> int:
    """Find left edge of chat panel by scanning left from tab for dark border.

    The chat panel has a dark vertical border. Scan the row at tab_y
    going left from the tab until we hit a dark column (pixel < 40).
    """
    row = screenshot[tab_y, :]
    for x in range(tab_x, -1, -1):
        if row[x] < 40:
            return x + 1
    return 0


def _find_chat_right_edge(screenshot: GrayImage, tab_x: int, tab_w: int, tab_y: int) -> int:
    """Find right edge of chat panel by scanning right from tab for dark border."""
    row = screenshot[tab_y, :]
    start = min(tab_x + tab_w, screenshot.shape[1] - 1)
    for x in range(start, screenshot.shape[1]):
        if row[x] < 40:
            return x
    return screenshot.shape[1]


def get_chat_content_area(screenshot: GrayImage, tab_position: BBox) -> Optional[BBox]:
    """Calculate chat content area from tab position.

    Detects the actual chat panel borders by scanning for dark edges
    left and right of the tab. Content starts below the tab row.
    Returns (x, y, w, h) or None.
    """
    if tab_position is None:
        return None

    tab_x, tab_y, tab_w, tab_h = tab_position

    content_x = _find_chat_left_edge(screenshot, tab_x, tab_y)
    right_edge = _find_chat_right_edge(screenshot, tab_x, tab_w, tab_y)
    content_y = tab_y + tab_h + 2
    content_w = right_edge - content_x
    content_h = min(screenshot.shape[0] - content_y, 300)

    if content_h <= 0 or content_w <= 0:
        return None

    return (content_x, content_y, content_w, content_h)


def get_loot_lines(chat_image: GrayImage, loot_of_template: GrayImage,
                   confidence: float = CONFIDENCE_LOOT_TEXT) -> List[Tuple[GrayImage, BBox]]:
    """Find all lines containing 'Loot of' in the chat area.

    Returns list of (line_image, bbox) tuples.
    """
    if chat_image is None or loot_of_template is None:
        return []

    if (loot_of_template.shape[0] > chat_image.shape[0] or
            loot_of_template.shape[1] > chat_image.shape[1]):
        return []

    result = cv2.matchTemplate(chat_image, loot_of_template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= confidence)

    lines = []
    used_y = set()
    template_h = loot_of_template.shape[0]

    for pt_y, pt_x in zip(*locations):
        # Deduplicate close matches on same line
        rounded_y = pt_y // template_h
        if rounded_y in used_y:
            continue
        used_y.add(rounded_y)

        # Extract line from left edge, excluding scrollbar (~15px from right)
        line_y = max(0, pt_y - 1)
        line_h = template_h + 2
        if line_y + line_h > chat_image.shape[0]:
            line_h = chat_image.shape[0] - line_y

        line_w = max(1, chat_image.shape[1] - 15)
        line_image = chat_image[line_y:line_y + line_h, :line_w]
        bbox = (0, line_y, line_w, line_h)
        lines.append((line_image, bbox))

    return lines

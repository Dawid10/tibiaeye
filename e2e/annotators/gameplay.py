"""Gameplay annotators — draw bot decision and task sequence overlays."""
import cv2
import numpy as np

from e2e.config import (
    COLOR_FAIL,
    COLOR_MONSTER,
    COLOR_PASS,
    FONT,
    FONT_SCALE_DECISION,
    FONT_SCALE_STATUS,
)

# Decision badge colors (BGR)
_DECISION_COLORS = {
    "attack": (0, 0, 220),    # Red
    "loot": (0, 180, 255),    # Orange
    "walk": (200, 200, 0),    # Teal
    "idle": (128, 128, 128),  # Gray
}


def annotate_decision_badge(image: np.ndarray, decision_result: dict) -> None:
    """Draw decision badge in top-right corner.

    Shows: ATTACK, LOOT, WALK, or IDLE with decision reason.
    """
    decision = decision_result.get("decision", "idle")
    reason = decision_result.get("reason", "")

    color = _DECISION_COLORS.get(decision, (128, 128, 128))
    label = decision.upper()

    h, w = image.shape[:2]
    badge_w = 200
    badge_h = 44
    x0 = w - badge_w - 8
    y0 = 8

    cv2.rectangle(image, (x0, y0), (x0 + badge_w, y0 + badge_h), color, -1)
    cv2.rectangle(image, (x0, y0), (x0 + badge_w, y0 + badge_h), (255, 255, 255), 1)

    cv2.putText(image, label, (x0 + 6, y0 + 18),
                FONT, FONT_SCALE_DECISION, (255, 255, 255), 2)

    if reason:
        display_reason = reason[:28]
        cv2.putText(image, display_reason, (x0 + 6, y0 + 36),
                    FONT, FONT_SCALE_STATUS, (255, 255, 255), 1)


def annotate_task_sequence(image: np.ndarray, task_result: dict) -> None:
    """Draw task sequence legend in bottom-left corner.

    Lists each task that would be created given the current game state.
    """
    task_sequence = task_result.get("task_sequence", [])
    if not task_sequence:
        return

    h, w = image.shape[:2]
    line_h = 18
    padding = 6
    box_h = len(task_sequence) * line_h + padding * 2
    box_w = 240
    x0 = 8
    y0 = h - box_h - 8

    cv2.rectangle(image, (x0, y0), (x0 + box_w, y0 + box_h), (30, 30, 30), -1)
    cv2.rectangle(image, (x0, y0), (x0 + box_w, y0 + box_h), (200, 200, 200), 1)

    for i, task_label in enumerate(task_sequence):
        ty = y0 + padding + (i + 1) * line_h - 4
        display = task_label[:34]
        cv2.putText(image, display, (x0 + padding, ty),
                    FONT, FONT_SCALE_STATUS, (200, 200, 200), 1)

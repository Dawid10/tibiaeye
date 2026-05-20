"""Tibia window detection using macOS Quartz APIs."""
from typing import Optional

from Quartz import (
    CGWindowListCopyWindowInfo,
    kCGNullWindowID,
    kCGWindowListOptionOnScreenOnly,
    kCGWindowListOptionIncludingWindow,
)

from ..core.screen import Region

TIBIA_OWNER_NAME = "Tibia"


def get_tibia_windows() -> list[dict]:
    """Return list of Tibia windows with {title, owner, id, region}."""
    window_list = CGWindowListCopyWindowInfo(
        kCGWindowListOptionOnScreenOnly, kCGNullWindowID
    )
    if window_list is None:
        return []

    results = []
    for window in window_list:
        owner = window.get("kCGWindowOwnerName", "")
        if TIBIA_OWNER_NAME not in owner:
            continue

        bounds = window.get("kCGWindowBounds", {})
        if not bounds:
            continue

        width = int(bounds.get("Width", 0))
        height = int(bounds.get("Height", 0))
        if width <= 0 or height <= 0:
            continue

        results.append({
            "title": window.get("kCGWindowName", "") or owner,
            "owner": owner,
            "id": int(window.get("kCGWindowNumber", 0)),
            "region": Region(
                x=int(bounds.get("X", 0)),
                y=int(bounds.get("Y", 0)),
                width=width,
                height=height,
            ),
        })

    return results


def get_window_region(window_id: int) -> Optional[Region]:
    """Return the current Region of a window by its ID, or None if gone."""
    window_list = CGWindowListCopyWindowInfo(
        kCGWindowListOptionIncludingWindow, window_id
    )
    if not window_list:
        return None

    for window in window_list:
        if int(window.get("kCGWindowNumber", 0)) != window_id:
            continue

        bounds = window.get("kCGWindowBounds", {})
        if not bounds:
            return None

        return Region(
            x=int(bounds.get("X", 0)),
            y=int(bounds.get("Y", 0)),
            width=int(bounds.get("Width", 0)),
            height=int(bounds.get("Height", 0)),
        )

    return None

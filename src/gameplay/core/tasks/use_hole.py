"""UseHole Task - Right-click on ladder/hole to go up/down."""
from typing import Optional, Tuple

import pyautogui

from .base import BaseTask, Context
from ....core.constants import DELAY_FLOOR_CHANGE, WAIT_DEPOSIT


class UseHoleTask(BaseTask):
    """Right-click on a ladder/hole to descend."""

    def __init__(self, coordinate: Optional[Tuple[int, int, int]] = None):
        super().__init__("UseHole")
        self.coordinate = coordinate
        self.delay_before_start = WAIT_DEPOSIT
        self.delay_after_complete = DELAY_FLOOR_CHANGE
        self._gamewindow = None

    def do(self, context: Context) -> Context:
        """Right-click on the ladder/hole."""
        target = self.coordinate
        if target is None:
            target = context.get('radar', {}).get('coordinate')

        if target is None:
            print("[UseHole] No target coordinate!")
            return context

        player_coord = context.get('radar', {}).get('coordinate')
        if player_coord is None:
            print("[UseHole] No player coordinate!")
            return context

        if self._gamewindow is None:
            from ....repositories.gamewindow import get_gamewindow_repository
            self._gamewindow = get_gamewindow_repository()

        slot = self._gamewindow.get_slot_from_coordinate(player_coord, target)
        if slot is None:
            print(f"[UseHole] Target {target} out of range from {player_coord}")
            return context

        print(f"[UseHole] Right-clicking slot {slot} for coordinate {target}")
        self._gamewindow.right_click_slot(slot)

        return context

"""
Anti-Trap Task - Attacks creatures when surrounded (no BFS path available).

Clicks directly on the closest monster in the game window.
Falls back to Space if click doesn't register attack within timeout.
"""
import time

import pyautogui

from .base import BaseTask, Context
from ...trap_detector import get_closest_trapped_creature
from ....core.constants import TRAP_FALLBACK_TIMEOUT
from ....utils.input import alt_click


class AttackTrappedCreatureTask(BaseTask):
    """Click directly on closest monster when trapped (bypasses pathfinding)."""

    def __init__(self):
        super().__init__("AttackTrappedCreature")
        self.delay_of_timeout = 5.0
        self._click_time = 0

    def should_ignore(self, context: Context) -> bool:
        """Skip if already attacking."""
        return context.get('cavebot', {}).get('isAttackingSomeCreature', False)

    def do(self, context: Context) -> Context:
        """Click on closest trapped creature."""
        creature = get_closest_trapped_creature(context)
        if creature is None:
            pyautogui.press('space')
            print("[AntiTrap] No visible monster — pressing Space")
            return context

        has_players = context.get('cavebot', {}).get('hasPlayers', False)
        id_method = getattr(creature, 'id_method', '')
        safe_to_click = not has_players or id_method in ('TM', 'OCR', 'BL')

        if hasattr(creature, 'window_coordinate') and safe_to_click:
            x, y = creature.window_coordinate
            alt_click(x, y)
            self._click_time = time.time()
            print(f"[AntiTrap] Alt+Click {creature.name} at ({x}, {y})")
        else:
            pyautogui.press('space')
            self._click_time = time.time()
            print(f"[AntiTrap] Space ({creature.name}, players={has_players})")

        gui_logger = context.get('gui_logger')
        if gui_logger:
            gui_logger(f"Anti-trap: atacando {creature.name}", "warning")

        return context

    def ping(self, context: Context) -> Context:
        """Fallback to Space if click didn't register attack within timeout."""
        if self._click_time == 0:
            return context
        if context.get('cavebot', {}).get('isAttackingSomeCreature', False):
            return context
        if time.time() - self._click_time < TRAP_FALLBACK_TIMEOUT:
            return context

        has_players = context.get('cavebot', {}).get('hasPlayers', False)
        if has_players:
            return context

        pyautogui.press('space')
        self._click_time = 0
        print("[AntiTrap] Click missed, fallback Space")
        return context

    def did(self, context: Context) -> bool:
        """Done when attack is confirmed."""
        return context.get('cavebot', {}).get('isAttackingSomeCreature', False)

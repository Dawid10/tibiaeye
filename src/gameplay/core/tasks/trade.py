"""
Trade Tasks - Tasks for NPC trade window automation.

Includes:
- BuyItemTask: Buy a specific item from NPC trade window
- CloseNpcTradeTask: Close the NPC trade window
"""
from typing import Any, Dict

import pyautogui

from .base import BaseTask, Context


class BuyItemTask(BaseTask):
    """
    Buy a specific item from the NPC trade window.

    Requires trade window to be already open.
    """

    def __init__(self, item_name: str, quantity: int):
        super().__init__(f"Buy({item_name}x{quantity})")
        self.item_name = item_name
        self.quantity = quantity
        self.delay_before_start = 0.2
        self.delay_after_complete = 0.3

    def should_ignore(self, context: Context) -> bool:
        """Skip if quantity is 0 or negative."""
        return self.quantity <= 0

    def do(self, context: Context) -> Context:
        from ....repositories.refill.core import buy_item

        screenshot = context.get('screenshot')
        success = buy_item(screenshot, self.item_name, self.quantity)

        if not success:
            print(f"[BuyItemTask] Failed to buy {self.quantity}x {self.item_name}")

        return context


class CloseNpcTradeTask(BaseTask):
    """Close the NPC trade window by pressing Escape."""

    def __init__(self):
        super().__init__("CloseNpcTrade")
        self.delay_after_complete = 0.3

    def do(self, context: Context) -> Context:
        pyautogui.press('escape')
        return context


class WaitForTradeWindowTask(BaseTask):
    """
    Wait for NPC trade window to appear.

    Times out after max_wait seconds.
    """

    def __init__(self, max_wait: float = 3.0):
        super().__init__("WaitForTradeWindow")
        self.delay_of_timeout = max_wait

    def did(self, context: Context) -> bool:
        from ....repositories.refill.core import is_trade_window_open

        screenshot = context.get('screenshot')
        if is_trade_window_open(screenshot):
            return True

        return False

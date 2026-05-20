"""Refill Tasks - Tasks for checking supplies and restocking."""
import time
from typing import Any, Dict

import pyautogui

from .base import BaseTask, Context
from .vector import VectorTask
from ....core.constants import (
    DELAY_KEY_PRESS, DELAY_HOTKEY, DELAY_SAY_BEFORE, DELAY_SAY_AFTER,
    DELAY_TYPEWRITE, DELAY_TRADE_ACTION, WAIT_TRADE_WINDOW, WAIT_LOCKER_OPEN,
    WAIT_NPC_RESPONSE, WAIT_DEPOSIT, MAX_TRADE_RETRIES, JITTER_SIGMA_TYPING,
)
from ....utils.jitter import jitter


class KeyPressTask(BaseTask):
    """Base task for pressing a single key."""

    def __init__(self, key: str, name: str, delay_after: float = DELAY_KEY_PRESS):
        super().__init__(name)
        self.key = key
        self.delay_after_complete = delay_after

    def do(self, context: Context) -> Context:
        pyautogui.press(self.key)
        return context


class EnableChatTask(KeyPressTask):
    """Enable chat input by pressing Enter."""

    def __init__(self):
        super().__init__('enter', "EnableChat")


class DisableChatTask(KeyPressTask):
    """Disable chat input by pressing Escape."""

    def __init__(self):
        super().__init__('escape', "DisableChat")


class CloseDepotTask(KeyPressTask):
    """Close the depot window by pressing Escape."""

    def __init__(self):
        super().__init__('escape', "CloseDepot")


class SayTask(BaseTask):
    """Say something in the game chat."""

    def __init__(self, message: str, delay_before: float = DELAY_SAY_BEFORE):
        name = f"Say({message[:20]}...)" if len(message) > 20 else f"Say({message})"
        super().__init__(name)
        self.message = message
        self.delay_before_start = delay_before
        self.delay_after_complete = DELAY_SAY_AFTER

    def do(self, context: Context) -> Context:
        pyautogui.press('enter')
        time.sleep(jitter(DELAY_HOTKEY))
        pyautogui.write(self.message, interval=jitter(DELAY_TYPEWRITE, JITTER_SIGMA_TYPING))
        time.sleep(jitter(DELAY_HOTKEY))
        pyautogui.press('enter')
        return context


class WaitTask(BaseTask):
    """Wait for a specified duration."""

    def __init__(self, duration: float):
        super().__init__(f"Wait({duration}s)")
        self.duration = duration
        self._started_at = 0

    def do(self, context: Context) -> Context:
        self._started_at = time.time()
        return context

    def did(self, context: Context) -> bool:
        return time.time() - self._started_at >= self.duration


class LazyVectorTask(VectorTask):
    """VectorTask that creates sub-tasks lazily on first on_before_start()."""

    def __init__(self, name: str):
        super().__init__(name)
        self._tasks_created = False

    def create_tasks(self, context: Context) -> None:
        """Override to create sub-tasks. Called once on first on_before_start()."""
        pass

    def on_before_start(self, context: Context) -> Context:
        if not self._tasks_created:
            self.create_tasks(context)
            self._tasks_created = True
        return super().on_before_start(context)

    def did(self, context: Context) -> bool:
        if not self._tasks_created:
            return False
        return super().did(context)


class RefillCheckerTask(BaseTask):
    """Check if refill is needed based on potions and capacity."""

    def __init__(self, waypoint: Dict[str, Any] = None):
        super().__init__("RefillChecker")
        self.waypoint = waypoint or {}
        self._checked = False
        self._needs_refill = False

    def do(self, context: Context) -> Context:
        from ....repositories.actionBar import ActionBarRepository
        from ....repositories.skills.core import get_capacity as skills_get_capacity

        screenshot = context.get('screenshot')
        action_bar = ActionBarRepository()

        health_potions = action_bar.get_slot_count(screenshot, 1) or 0
        mana_potions = action_bar.get_slot_count(screenshot, 2) or 0
        capacity = skills_get_capacity(screenshot)

        refill_config = context.get('refill', {})
        min_health = refill_config.get('hpPotionMin', 50)
        min_mana = refill_config.get('mpPotionMin', 100)
        min_cap = refill_config.get('capMin', 200)
        check_capacity = refill_config.get('checkCapacity', True)
        return_label = refill_config.get('returnLabel', 'caveStart')

        has_enough_health = health_potions > min_health
        has_enough_mana = mana_potions > min_mana
        has_enough_cap = (not check_capacity) or capacity is None or capacity > min_cap

        cap_status = f"{capacity}/{min_cap}" if check_capacity else f"{capacity} (disabled)"
        print(f"[RefillChecker] HP: {health_potions}/{min_health}, MP: {mana_potions}/{min_mana}, Cap: {cap_status}")

        gui_logger = context.get('gui_logger')

        if has_enough_health and has_enough_mana and has_enough_cap:
            self._jump_to_label(context, return_label)
            print(f"[RefillChecker] Supplies OK, jumping to '{return_label}'")
            if gui_logger:
                gui_logger(f"Continuando hunt (HP:{health_potions} MP:{mana_potions})", "success")
        else:
            print(f"[RefillChecker] Need refill, continuing to depot...")
            self._advance_waypoint(context)
            if gui_logger:
                gui_logger(f"Voltando para o depot (HP:{health_potions} MP:{mana_potions})", "warning")

        self._checked = True
        return context

    def _advance_waypoint(self, context: Context) -> None:
        waypoints = context.get('cavebot', {}).get('waypoints', {})
        items = waypoints.get('items', [])
        current_index = waypoints.get('currentIndex', 0)

        next_index = (current_index + 1) % max(1, len(items))
        context['cavebot']['waypoints']['currentIndex'] = next_index

    def _jump_to_label(self, context: Context, label: str) -> None:
        waypoints = context.get('cavebot', {}).get('waypoints', {})
        items = waypoints.get('items', [])

        for i, wp in enumerate(items):
            if wp.get('label') == label:
                context['cavebot']['waypoints']['currentIndex'] = i
                return

        print(f"[RefillChecker] WARNING: Label '{label}' not found!")

    def did(self, context: Context) -> bool:
        return self._checked


class DepositGoldTask(LazyVectorTask):
    """Deposit gold at the banker."""

    def __init__(self, waypoint: Dict[str, Any] = None):
        super().__init__("DepositGold")

    def create_tasks(self, context: Context) -> None:
        from .cavebot import SetNextWaypointTask

        refill_config = context.get('refill', {})
        deposit_gold = refill_config.get('depositGold', True)

        if not deposit_gold:
            print("[DepositGold] Disabled in GUI, skipping")
            self.add_task(SetNextWaypointTask())
            return

        print("[DepositGold] Depositing gold at banker...")
        self.add_task(SayTask('hi', delay_before=DELAY_SAY_BEFORE))
        self.add_task(WaitTask(WAIT_NPC_RESPONSE))
        self.add_task(SayTask('deposit all', delay_before=DELAY_HOTKEY))
        self.add_task(WaitTask(WAIT_NPC_RESPONSE))
        self.add_task(SayTask('yes', delay_before=DELAY_HOTKEY))
        self.add_task(WaitTask(WAIT_DEPOSIT))
        self.add_task(DisableChatTask())
        self.add_task(SetNextWaypointTask())


class RefillTask(VectorTask):
    """Buy potions from NPC using chat commands."""

    def __init__(self, waypoint: Dict[str, Any]):
        super().__init__("Refill")
        self.waypoint = waypoint
        self.options = waypoint.get('options', {})

        from .cavebot import SetNextWaypointTask

        self.add_task(SayTask('hi'))
        self.add_task(SayTask('trade'))
        self.add_task(WaitTask(WAIT_NPC_RESPONSE))

        health_opts = self.options.get('healthPotion', {})
        if health_opts:
            item = health_opts.get('item', 'health potion')
            qty = health_opts.get('quantity', 100)
            self.add_task(SayTask(f'buy {qty} {item}'))

        mana_opts = self.options.get('manaPotion', {})
        if mana_opts:
            item = mana_opts.get('item', 'mana potion')
            qty = mana_opts.get('quantity', 100)
            self.add_task(SayTask(f'buy {qty} {item}'))

        self.add_task(DisableChatTask())
        self.add_task(SetNextWaypointTask())


class DepositItemsTask(LazyVectorTask):
    """Deposit items at the depot."""

    def __init__(self, waypoint: Dict[str, Any] = None):
        super().__init__("DepositItems")
        self.waypoint = waypoint or {}

    def create_tasks(self, context: Context) -> None:
        from .cavebot import SetNextWaypointTask
        from .depot import (
            GoToFreeDepotTask, OpenLockerTask, OpenBackpackTask,
            OpenDepotTask, OpenDepotChestTask, CloseContainerTask,
            DragItemsTask, DropBackpackIntoStashTask, ScrollToItemTask,
            ExpandBackpackTask,
        )

        refill_config = context.get('refill', {})
        city = refill_config.get('city', 'Venore')
        loot_backpack = refill_config.get('lootBackpack', 'Beach Backpack')
        main_backpack = refill_config.get('mainBackpack', 'Backpack')
        stash_backpack = refill_config.get('stashBackpack', loot_backpack)
        deposit_loot = refill_config.get('depositLoot', True)
        depot_chest = refill_config.get('depotChest', 1)
        chest_index = max(0, depot_chest - 1)

        if not deposit_loot:
            print("[DepositItems] Disabled in GUI, skipping")
            self.add_task(SetNextWaypointTask())
            return

        print(f"[DepositItems] City: {city}, Stash: {stash_backpack}, Loot(depot): {loot_backpack}, Main: {main_backpack}, Chest: {depot_chest}")
        self.add_task(GoToFreeDepotTask(city))
        self.add_task(CloseContainerTask(stash_backpack))
        if loot_backpack != stash_backpack:
            self.add_task(CloseContainerTask(loot_backpack))
        self.add_task(CloseContainerTask(main_backpack))
        self.add_task(OpenLockerTask())
        self.add_task(WaitForLockerOpenTask())
        self.add_task(OpenBackpackTask(main_backpack))
        self.add_task(ScrollToItemTask(main_backpack, stash_backpack))
        self.add_task(DropBackpackIntoStashTask(stash_backpack))
        self.add_task(OpenDepotTask())
        self.add_task(OpenDepotChestTask(chest_index))
        self.add_task(OpenBackpackTask(loot_backpack))
        self.add_task(ExpandBackpackTask(loot_backpack))
        self.add_task(DragItemsTask(loot_backpack, 'Depot Box'))
        self.add_task(CloseContainerTask(loot_backpack))
        self.add_task(SetNextWaypointTask())


class WaitForLockerOpenTask(BaseTask):
    """Wait for the locker window to open."""

    def __init__(self, max_wait: float = WAIT_LOCKER_OPEN):
        super().__init__("WaitForLockerOpen")
        self.delay_of_timeout = max_wait

    def did(self, context: Context) -> bool:
        from ....repositories.inventory import is_container_open, get_container_position

        screenshot = context.get('screenshot')

        if is_container_open(screenshot, 'locker'):
            print("[WaitForLockerOpen] Locker is open!")
            return True

        pos = get_container_position(screenshot, 'depot')
        if pos is not None:
            print(f"[WaitForLockerOpen] Found depot container at {pos}")
            return True

        return False


class DropFlasksTask(BaseTask):
    """Drop empty flasks using hotkey."""

    def __init__(self, hotkey: str = 'f'):
        super().__init__("DropFlasks")
        self.hotkey = hotkey
        self.delay_after_complete = DELAY_TRADE_ACTION

    def do(self, context: Context) -> Context:
        refill_config = context.get('refill', {})
        drop_flasks = refill_config.get('dropFlasks', True)

        if not drop_flasks:
            print("[DropFlasks] Disabled in GUI, skipping")
            return context

        print(f"[DropFlasks] Dropping flasks with hotkey '{self.hotkey}'")
        pyautogui.press(self.hotkey)
        return context


class WaitForTradeWindowTask(BaseTask):
    """Wait for NPC trade window to open with retry logic."""

    def __init__(self, max_wait: float = WAIT_TRADE_WINDOW, max_retries: int = MAX_TRADE_RETRIES):
        super().__init__("WaitForTradeWindow")
        self._max_retries = max_retries
        self._wait_per_attempt = max_wait
        self.delay_of_timeout = max_wait * (max_retries + 1)
        self._attempt_started_at = 0.0
        self._retries = 0

    def do(self, context: Context) -> Context:
        self._attempt_started_at = time.time()
        return context

    def did(self, context: Context) -> bool:
        from ....repositories.refill.core import is_trade_window_open

        screenshot = context.get('screenshot')

        if is_trade_window_open(screenshot):
            print("[WaitForTradeWindow] Trade window is open!")
            return True

        elapsed = time.time() - self._attempt_started_at
        if elapsed < self._wait_per_attempt:
            return False

        self._retries += 1
        if self._retries >= self._max_retries:
            print("[WaitForTradeWindow] Max retries reached")
            return False

        print(f"[WaitForTradeWindow] Timeout, retrying ({self._retries}/{self._max_retries})")
        self._retry_open_trade()
        self._attempt_started_at = time.time()
        return False

    def _retry_open_trade(self) -> None:
        pyautogui.press('enter')
        time.sleep(jitter(DELAY_HOTKEY))
        pyautogui.write('hi', interval=jitter(DELAY_TYPEWRITE, JITTER_SIGMA_TYPING))
        pyautogui.press('enter')
        time.sleep(jitter(WAIT_NPC_RESPONSE))
        pyautogui.press('enter')
        time.sleep(jitter(DELAY_HOTKEY))
        pyautogui.write('trade', interval=jitter(DELAY_TYPEWRITE, JITTER_SIGMA_TYPING))
        pyautogui.press('enter')


class CloseNpcTradeTask(BaseTask):
    """Close the NPC trade window."""

    def __init__(self):
        super().__init__("CloseNpcTrade")
        self.delay_after_complete = 0.3

    def do(self, context: Context) -> Context:
        from ....repositories.refill.core import close_trade_window
        close_trade_window()
        return context


class BuyItemWithVerificationTask(BaseTask):
    """Buy item from NPC trade window with verification."""

    def __init__(self, item_name: str, quantity: int, slot: int = 1):
        super().__init__(f"BuyVerified({item_name[:15]}x{quantity})")
        self.item_name = item_name
        self.quantity = quantity
        self.slot = slot
        self.delay_before_start = 0.3
        self.delay_after_complete = 0.5
        self._initial_count = 0
        self._bought = False
        self._verified = False

    def do(self, context: Context) -> Context:
        from ....repositories.actionBar import ActionBarRepository
        from ....repositories.refill.core import buy_item_with_search

        if self.quantity <= 0:
            print(f"[BuyVerified] Skipping {self.item_name} (quantity=0)")
            self._bought = True
            self._verified = True
            return context

        screenshot = context.get('screenshot')
        action_bar = ActionBarRepository()

        self._initial_count = action_bar.get_slot_count(screenshot, self.slot) or 0
        print(f"[BuyVerified] Initial count slot {self.slot}: {self._initial_count}")

        success = buy_item_with_search(screenshot, self.item_name, self.quantity)
        self._bought = success
        if not success:
            print(f"[BuyVerified] Failed to buy '{self.item_name}'")

        return context

    def did(self, context: Context) -> bool:
        if not self._bought:
            return True

        if self._verified:
            return True

        from ....repositories.actionBar import ActionBarRepository

        screenshot = context.get('screenshot')
        action_bar = ActionBarRepository()

        final_count = action_bar.get_slot_count(screenshot, self.slot) or 0
        actual_increase = final_count - self._initial_count

        if final_count >= self._initial_count:
            print(f"[BuyVerified] Success! {self._initial_count} → {final_count} (+{actual_increase})")
        else:
            print(f"[BuyVerified] WARNING: Count did not increase! {self._initial_count} → {final_count}")

        self._verified = True
        return True


class RefillPotionsTask(LazyVectorTask):
    """Complete task for buying potions from NPC."""

    def __init__(self, waypoint: Dict[str, Any]):
        super().__init__("RefillPotions")
        self.waypoint = waypoint
        self.options = waypoint.get('options', {})
        self.delay_after_complete = DELAY_TRADE_ACTION

    def create_tasks(self, context: Context) -> None:
        from .cavebot import SetNextWaypointTask

        hp_to_buy, mp_to_buy, hp_item, mp_item = self._calculate_quantities(context)

        # Track refill via telemetry
        telemetry = context.get('telemetry')
        if telemetry:
            telemetry.track_refill(potions_bought=hp_to_buy + mp_to_buy)

        print(f"[RefillPotions] Creating sub-tasks...")
        self.add_task(SayTask('hi', delay_before=DELAY_SAY_BEFORE))
        self.add_task(WaitTask(WAIT_NPC_RESPONSE))
        self.add_task(SayTask('trade', delay_before=DELAY_HOTKEY))
        self.add_task(WaitForTradeWindowTask(max_wait=WAIT_TRADE_WINDOW))

        if hp_to_buy > 0:
            self.add_task(BuyItemWithVerificationTask(hp_item, hp_to_buy, slot=1))

        if mp_to_buy > 0:
            self.add_task(BuyItemWithVerificationTask(mp_item, mp_to_buy, slot=2))

        self.add_task(CloseNpcTradeTask())
        self.add_task(DisableChatTask())
        self.add_task(SetNextWaypointTask())

        print(f"[RefillPotions] Created {len(self.tasks)} sub-tasks")

    def _calculate_quantities(self, context: Context) -> tuple:
        refill_config = context.get('refill', {})
        target_hp = refill_config.get('hpPotionTarget', 100)
        target_mp = refill_config.get('mpPotionTarget', 200)
        hp_item = refill_config.get('hpPotionItem', 'Health Potion')
        mp_item = refill_config.get('mpPotionItem', 'Mana Potion')

        try:
            from ....repositories.actionBar import ActionBarRepository

            screenshot = context.get('screenshot')
            if screenshot is None:
                return target_hp, target_mp, hp_item, mp_item

            action_bar = ActionBarRepository()
            current_hp = action_bar.get_slot_count(screenshot, 1) or 0
            current_mp = action_bar.get_slot_count(screenshot, 2) or 0

            hp_to_buy = max(0, target_hp - current_hp)
            mp_to_buy = max(0, target_mp - current_mp)

            print(f"[RefillPotions] HP: {current_hp}/{target_hp} (buy {hp_to_buy})")
            print(f"[RefillPotions] MP: {current_mp}/{target_mp} (buy {mp_to_buy})")

            self._log_estimated_cost(hp_item, hp_to_buy, mp_item, mp_to_buy)

            return hp_to_buy, mp_to_buy, hp_item, mp_item

        except Exception as e:
            print(f"[RefillPotions] Error reading supplies: {e}")
            return target_hp, target_mp, hp_item, mp_item

    def _log_estimated_cost(self, hp_item: str, hp_to_buy: int,
                            mp_item: str, mp_to_buy: int) -> None:
        try:
            from ....wiki.potions import calculate_refill_cost
            cost = calculate_refill_cost(hp_item, hp_to_buy, mp_item, mp_to_buy)
            print(f"[RefillPotions] Estimated cost: {cost} gold")
        except Exception:
            pass

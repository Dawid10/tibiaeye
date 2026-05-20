"""
Depot Tasks - PyTibia style depot automation.

Includes:
- GoToFreeDepotTask: Walk to free depot using walkpoints + scipy.cdist
- OpenLockerTask: Right-click locker via slot system
- ScrollToItemTask: Scroll container to find item
- OpenBackpackTask: Open a specific backpack
- OpenDepotChestTask: Open a depot chest
- CloseContainerTask: Close a container window
- DragItemsTask: Drag items one-per-tick between containers
- DropBackpackIntoStashTask: Move loot backpack to stash
"""
import time

import numpy as np

from .base import BaseTask, Context
from .vector import VectorTask


class GoToFreeDepotTask(VectorTask):
    """
    Find an unoccupied depot and walk there via walkpoints.

    PyTibia style:
    1. Get depot coords for city, filter same floor
    2. Filter visible depots (±7x, ±5y from player)
    3. Remove occupied by players via gameWindow['players']
    4. Pick closest free depot using scipy.cdist (euclidean)
    5. Generate walkpoints and create WalkTask for each step
    6. On arrival, set context['deposit']['lockerCoordinate']
    """

    def __init__(self, city: str = 'Venore'):
        super().__init__(f"GoToFreeDepot({city})")
        self.city = city
        self._done = False
        self._target_coord = None
        self._locker_coord = None
        self._occupied_depots = set()

    def on_before_start(self, context: Context) -> Context:
        occupied = context.get('deposit', {}).get('occupiedDepots', [])
        self._occupied_depots = set(tuple(c) for c in occupied)
        self._build_walk_tasks(context)
        return super().on_before_start(context)

    def _build_walk_tasks(self, context: Context) -> None:
        from ....wiki.cities import get_depot_coordinates, get_depot_goal_coordinate
        from ...cavebot.radar import (
            generate_floor_walkpoints,
            get_direction_between_coordinates,
        )
        from ..waypoint import generate_global_walkpoints
        from .common import WalkTask

        current_pos = context.get('radar', {}).get('coordinate')
        if current_pos is None:
            print("[GoToFreeDepot] No current position")
            self._done = True
            return

        all_depots = get_depot_coordinates(self.city)
        if not all_depots:
            print(f"[GoToFreeDepot] No depot coordinates for '{self.city}'")
            self._done = True
            return

        same_floor = [d for d in all_depots if d[2] == current_pos[2]]
        if not same_floor:
            print(f"[GoToFreeDepot] No depots on floor {current_pos[2]}")
            self._done = True
            return

        player_coords = self._get_player_coordinates(context)
        if player_coords:
            print(f"[GoToFreeDepot] Players detected at: {player_coords}")
        if self._occupied_depots:
            print(f"[GoToFreeDepot] Previously occupied depots: {self._occupied_depots}")

        goal_coord, locker_coord = self._find_closest_free_depot(
            current_pos, same_floor, player_coords
        )

        if goal_coord is None:
            print("[GoToFreeDepot] No depot found")
            self._done = True
            return

        self._target_coord = goal_coord
        self._locker_coord = locker_coord

        if (current_pos[0] == goal_coord[0] and
                current_pos[1] == goal_coord[1]):
            print(f"[GoToFreeDepot] Already at depot {goal_coord}")
            self._done = True
            return

        obstacles = self._collect_obstacles(context)
        walkpoints = generate_floor_walkpoints(
            current_pos, goal_coord, obstacles
        )

        if len(walkpoints) <= 1 and self._distance(current_pos, goal_coord) > 10:
            walkpoints = generate_global_walkpoints(
                current_pos, goal_coord, max_path_length=30
            )

        if not walkpoints:
            print(f"[GoToFreeDepot] No path to {goal_coord}")
            self._done = True
            return

        prev = current_pos
        for wp in walkpoints:
            direction = get_direction_between_coordinates(prev, wp)
            if direction is None:
                continue
            self.add_task(WalkTask(direction))
            prev = wp

        print(f"[GoToFreeDepot] {len(self.tasks)} steps to {goal_coord}")

    def _get_player_coordinates(self, context: Context) -> set:
        players = context.get('gameWindow', {}).get('players', [])
        coords = set()
        for player in players:
            coord = getattr(player, 'coordinate', None)
            if coord is not None:
                coords.add(tuple(coord))
        return coords

    def _find_closest_free_depot(self, current_pos, depots, player_coords):
        from ....wiki.cities import get_depot_goal_coordinate

        try:
            from scipy.spatial.distance import cdist
            return self._find_closest_scipy(
                current_pos, depots, player_coords, cdist
            )
        except ImportError:
            return self._find_closest_manual(
                current_pos, depots, player_coords
            )

    def _find_closest_scipy(self, current_pos, depots, player_coords, cdist):
        from ....wiki.cities import get_depot_goal_coordinate

        goals = []
        locker_map = {}
        for depot in depots:
            if depot in self._occupied_depots:
                continue
            goal = get_depot_goal_coordinate(self.city, depot)
            if tuple(goal) in player_coords:
                continue
            goals.append(goal)
            locker_map[goal] = depot

        if not goals:
            return self._fallback_closest(current_pos, depots)

        player_arr = np.array([[current_pos[0], current_pos[1]]])
        goals_arr = np.array([[g[0], g[1]] for g in goals])
        distances = cdist(player_arr, goals_arr, metric='euclidean')[0]
        closest_idx = int(np.argmin(distances))
        goal = goals[closest_idx]
        return goal, locker_map[goal]

    def _find_closest_manual(self, current_pos, depots, player_coords):
        from ....wiki.cities import get_depot_goal_coordinate

        best_goal = None
        best_locker = None
        best_dist = float('inf')

        for depot in depots:
            if depot in self._occupied_depots:
                continue
            goal = get_depot_goal_coordinate(self.city, depot)
            if tuple(goal) in player_coords:
                continue
            dist = self._distance(current_pos, goal)
            if dist < best_dist:
                best_dist = dist
                best_goal = goal
                best_locker = depot

        if best_goal is None:
            return self._fallback_closest(current_pos, depots)
        return best_goal, best_locker

    def _fallback_closest(self, current_pos, depots):
        from ....wiki.cities import get_depot_goal_coordinate

        if self._occupied_depots:
            self._occupied_depots.clear()
            return self._find_closest_manual(current_pos, depots, set())

        best_goal = None
        best_locker = None
        best_dist = float('inf')
        for depot in depots:
            goal = get_depot_goal_coordinate(self.city, depot)
            dist = self._distance(current_pos, goal)
            if dist < best_dist:
                best_dist = dist
                best_goal = goal
                best_locker = depot
        return best_goal, best_locker

    def _collect_obstacles(self, context: Context) -> list:
        obstacles = []
        monsters = context.get('gameWindow', {}).get('monsters', [])
        for m in monsters:
            coord = getattr(m, 'coordinate', None)
            if coord is not None:
                obstacles.append(coord)
        return obstacles

    def _distance(self, a, b) -> float:
        return ((a[0] - b[0]) ** 2 + (a[1] - b[1]) ** 2) ** 0.5

    def did(self, context: Context) -> bool:
        if self._done:
            return True
        if not self.tasks:
            return False
        return super().did(context)

    def on_complete(self, context: Context) -> Context:
        if self._locker_coord is not None:
            context.setdefault('deposit', {})['lockerCoordinate'] = self._locker_coord
            context.setdefault('deposit', {})['occupiedDepots'] = []
            print(f"[GoToFreeDepot] Arrived, locker at {self._locker_coord}")
        return context

    def on_timeout(self, context: Context) -> Context:
        self._mark_depot_occupied(context)
        return context

    def _mark_depot_occupied(self, context: Context) -> None:
        if self._locker_coord is None:
            return
        deposit = context.setdefault('deposit', {})
        occupied = deposit.setdefault('occupiedDepots', [])
        locker = list(self._locker_coord) if not isinstance(self._locker_coord, list) else self._locker_coord
        if locker not in occupied:
            occupied.append(locker)
        print(f"[GoToFreeDepot] Marked depot {self._locker_coord} as occupied, will try another")


class OpenLockerTask(BaseTask):
    """
    Open the depot locker by right-clicking its slot in the game window.

    Uses get_slot_from_coordinate + right_click_slot (PyTibia style).
    """

    def __init__(self):
        super().__init__("OpenLocker")
        self.delay_before_start = 0.3
        self.delay_after_complete = 0.8
        self._opened = False
        self._attempts = 0
        self._max_attempts = 3

    def should_ignore(self, context: Context) -> bool:
        from ....repositories.inventory import is_container_open

        screenshot = context.get('screenshot')
        if screenshot is None:
            return False
        return is_container_open(screenshot, 'locker')

    def do(self, context: Context) -> Context:
        from ....repositories.gamewindow import get_gamewindow_repository

        screenshot = context.get('screenshot')
        current_pos = context.get('radar', {}).get('coordinate')
        if current_pos is None:
            self._attempts += 1
            return context

        locker_coord = context.get('deposit', {}).get('lockerCoordinate')
        if locker_coord is None:
            locker_coord = context.get('depot_locker_coord')

        gw_repo = get_gamewindow_repository()
        gw_repo.get_game_window_position(screenshot)

        if locker_coord is not None:
            slot = gw_repo.get_slot_from_coordinate(current_pos, locker_coord)
            if slot is not None:
                success = gw_repo.right_click_slot(slot)
                if success:
                    print(f"[OpenLocker] Right-clicked slot {slot} for locker {locker_coord}")
                    self._opened = True
                    return context

        # Fallback: try adjacent tiles
        for dx, dy in [(0, -1), (0, 1), (-1, 0), (1, 0)]:
            adj = (current_pos[0] + dx, current_pos[1] + dy, current_pos[2])
            slot = gw_repo.get_slot_from_coordinate(current_pos, adj)
            if slot is None:
                continue
            success = gw_repo.right_click_slot(slot)
            if success:
                print(f"[OpenLocker] Fallback: right-clicked adjacent slot {slot}")
                self._opened = True
                return context

        self._attempts += 1
        return context

    def did(self, context: Context) -> bool:
        if self._attempts >= self._max_attempts:
            print("[OpenLocker] Max attempts reached")
            return True
        return self._opened

    def on_complete(self, context: Context) -> Context:
        context.setdefault('deposit', {})['lockerCoordinate'] = None
        return context


class ScrollToItemTask(BaseTask):
    """
    Scroll a container until a specific item is visible.

    Uses template matching to detect when the item appears.
    """

    def __init__(self, container_name: str, item_name: str, max_scrolls: int = 10):
        super().__init__(f"ScrollToItem({item_name})")
        self.container_name = container_name
        self.item_name = item_name
        self.max_scrolls = max_scrolls
        self._scrolls = 0
        self._found = False
        self.delay_after_complete = 0.3

    def should_ignore(self, context: Context) -> bool:
        return self._is_item_visible(context)

    def do(self, context: Context) -> Context:
        self._scroll_container(context)
        return context

    def ping(self, context: Context) -> Context:
        if self._found:
            return context
        if self._scrolls >= self.max_scrolls:
            return context
        if self._is_item_visible(context):
            self._found = True
            return context
        self._scroll_container(context)
        return context

    def _is_item_visible(self, context: Context) -> bool:
        from ....repositories.inventory.config import images
        import cv2

        screenshot = context.get('screenshot')
        if screenshot is None:
            return False

        item_key = self.item_name.lower()
        template = images['slots'].get(item_key)
        if template is None:
            return False

        result = cv2.matchTemplate(screenshot, template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= 0.7

    def _scroll_container(self, context: Context) -> None:
        import pyautogui
        from ....repositories.inventory import get_container_position

        screenshot = context.get('screenshot')
        pos = get_container_position(screenshot, self.container_name)
        if pos is None:
            self._scrolls += 1
            return

        center_x = pos[0] + pos[2] // 2
        center_y = pos[1] + pos[3] // 2
        pyautogui.scroll(10, center_x, center_y)
        self._scrolls += 1
        print(f"[ScrollToItem] Scrolled {self.container_name} ({self._scrolls}/{self.max_scrolls})")

    def did(self, context: Context) -> bool:
        if self._found:
            return True
        return self._scrolls >= self.max_scrolls


class OpenBackpackTask(BaseTask):
    """Open a specific backpack container."""

    def __init__(self, backpack_name: str):
        super().__init__(f"OpenBackpack({backpack_name})")
        self.backpack_name = backpack_name
        self.delay_after_complete = 0.3
        self._opened = False

    def do(self, context: Context) -> Context:
        from ....repositories.inventory import open_container

        screenshot = context.get('screenshot')
        success = open_container(screenshot, self.backpack_name)

        if success:
            print(f"[OpenBackpack] Opening {self.backpack_name}")
            self._opened = True
        else:
            print(f"[OpenBackpack] Could not find backpack '{self.backpack_name}'")

        return context

    def did(self, context: Context) -> bool:
        return self._opened


class OpenDepotTask(BaseTask):
    """Open the depot container by right-clicking the depot icon in the locker."""

    def __init__(self):
        super().__init__("OpenDepot")
        self.delay_before_start = 0.3
        self.delay_after_complete = 0.5
        self._opened = False

    def do(self, context: Context) -> Context:
        from ....repositories.inventory import open_depot_slot

        screenshot = context.get('screenshot')
        success = open_depot_slot(screenshot)

        if success:
            print("[OpenDepot] Right-clicked depot icon")
            self._opened = True
        else:
            print("[OpenDepot] Could not find depot icon")

        return context

    def did(self, context: Context) -> bool:
        return self._opened


class OpenDepotChestTask(BaseTask):
    """Open a specific depot chest by right-clicking its icon."""

    def __init__(self, chest_index: int = 0):
        super().__init__(f"OpenDepotChest({chest_index})")
        self.chest_index = chest_index
        self.delay_before_start = 0.3
        self.delay_after_complete = 0.5
        self._opened = False

    def do(self, context: Context) -> Context:
        from ....repositories.inventory import open_depot_chest

        screenshot = context.get('screenshot')
        success = open_depot_chest(screenshot, self.chest_index)

        if success:
            print(f"[OpenDepotChest] Opening chest {self.chest_index}")
            self._opened = True
        else:
            print(f"[OpenDepotChest] Could not find depot chest {self.chest_index}")

        return context

    def did(self, context: Context) -> bool:
        return self._opened


class CloseContainerTask(BaseTask):
    """Close a container window."""

    def __init__(self, container_name: str):
        super().__init__(f"CloseContainer({container_name})")
        self.container_name = container_name
        self.delay_after_complete = 0.2
        self._closed = False

    def do(self, context: Context) -> Context:
        from ....repositories.inventory import close_container

        screenshot = context.get('screenshot')
        success = close_container(screenshot, self.container_name)

        if success:
            print(f"[CloseContainer] Closed {self.container_name}")
        else:
            print(f"[CloseContainer] Could not close '{self.container_name}'")

        self._closed = True
        return context

    def did(self, context: Context) -> bool:
        return self._closed


class ExpandBackpackTask(BaseTask):
    """
    Expand a backpack container to show all slots.

    PyTibia style: locates the container top bar and bottom bar, then drags
    the bottom bar downward so the container reaches CONTAINER_EXPANDED_HEIGHT.
    If already expanded, finishes immediately.
    """

    def __init__(self, backpack_name: str):
        super().__init__(f"ExpandBackpack({backpack_name})")
        self.backpack_name = backpack_name
        self.delay_before_start = 1.0
        self.delay_after_complete = 1.0
        self._expanded = False

    def do(self, context: Context) -> Context:
        import cv2
        from ....repositories.inventory.config import images, CONTAINER_EXPANDED_HEIGHT
        from ....repositories.inventory.core import _locate

        screenshot = context.get('screenshot')
        if screenshot is None:
            self._expanded = True
            return context

        backpack_key = self.backpack_name.lower()
        bar_template = images['containers'].get(backpack_key)
        if bar_template is None:
            print(f"[ExpandBackpack] No template for '{backpack_key}'")
            self._expanded = True
            return context

        bar_pos = _locate(screenshot, bar_template, confidence=0.8)
        if bar_pos is None:
            print(f"[ExpandBackpack] Container bar not found for '{backpack_key}'")
            self._expanded = True
            return context

        bottom_template = images['containers'].get('backpack bottom')
        if bottom_template is None:
            print("[ExpandBackpack] 'backpack bottom' template not found")
            self._expanded = True
            return context

        cropped = screenshot[bar_pos[1]:, bar_pos[0]:]
        bottom_pos = _locate(cropped, bottom_template, confidence=0.8)
        if bottom_pos is None:
            print("[ExpandBackpack] Bottom bar not found")
            self._expanded = True
            return context

        bottom_x = bottom_pos[0] + bar_pos[0]
        bottom_y = bottom_pos[1] + bar_pos[1]
        y_difference = bottom_y - bar_pos[1]
        scroll_y = CONTAINER_EXPANDED_HEIGHT - y_difference

        if scroll_y <= 0:
            print(f"[ExpandBackpack] Already expanded ({y_difference}px >= {CONTAINER_EXPANDED_HEIGHT}px)")
            self._expanded = True
            return context

        import pyautogui
        pyautogui.moveTo(bottom_x, bottom_y)
        pyautogui.mouseDown()
        pyautogui.moveTo(bottom_x, bottom_y + scroll_y, duration=0.3)
        pyautogui.mouseUp()

        print(f"[ExpandBackpack] Expanded by {scroll_y}px")
        self._expanded = True
        return context

    def did(self, context: Context) -> bool:
        return self._expanded


class DragItemsTask(BaseTask):
    """
    Drag items from source to dest container, one per tick via ping().

    PyTibia style: always drags from _start_slot. When an item is dragged,
    remaining items shift left, so the next item appears at the same slot.
    Backpacks are skipped by incrementing _start_slot.
    Hidden items (below the visible 8-slot fold) appear automatically as
    items are removed.
    """

    BACKPACK_MATCH_THRESHOLD = 0.80
    EMPTY_MATCH_THRESHOLD = 0.80
    MAX_CONSECUTIVE_EMPTY = 3
    MAX_SLOT_INDEX = 20

    def __init__(self, source_container: str, dest_container: str, max_items: int = 20):
        super().__init__(f"DragItems({source_container}->{dest_container})")
        self.source_container = source_container
        self.dest_container = dest_container
        self.max_items = max_items
        self._start_slot = 0
        self._items_moved = 0
        self._done = False
        self._consecutive_empty = 0
        self.delay_after_complete = 0.3

    def do(self, context: Context) -> Context:
        self._drag_one(context)
        return context

    def ping(self, context: Context) -> Context:
        if self._done:
            return context
        self._drag_one(context)
        return context

    def _find_dest_center(self, screenshot):
        """Find destination: try container bar first, then slot icon."""
        from ....repositories.inventory import get_container_position, get_slot_position
        from ....repositories.inventory.config import images
        from ....repositories.inventory.core import _locate, CONFIDENCE_UI_BUTTON

        dest_pos = get_container_position(screenshot, self.dest_container)
        if dest_pos is not None:
            return get_slot_position(dest_pos, 0)

        slot_template = images['slots'].get(self.dest_container.lower())
        if slot_template is None:
            return None

        pos = _locate(screenshot, slot_template, confidence=CONFIDENCE_UI_BUTTON)
        if pos is None:
            return None

        return (pos[0] + pos[2] // 2, pos[1] + pos[3] // 2)

    def _extract_slot_image(self, screenshot, container_pos, slot_index):
        """Extract the 32x32 image of a slot from the screenshot."""
        from ....repositories.inventory import get_slot_position
        from ....repositories.inventory.config import SLOT_SIZE

        cx, cy = get_slot_position(container_pos, slot_index)
        half = SLOT_SIZE // 2
        top = max(cy - half, 0)
        bottom = min(cy + half, screenshot.shape[0])
        left = max(cx - half, 0)
        right = min(cx + half, screenshot.shape[1])
        slot_img = screenshot[top:bottom, left:right]
        if slot_img.size == 0:
            return None
        return slot_img

    def _is_slot_backpack(self, slot_img):
        """Check if a slot contains a backpack via template matching."""
        import cv2
        from ....repositories.inventory.config import images

        for name, template in images['slots'].items():
            if 'backpack' not in name:
                continue
            if template is None:
                continue
            if (template.shape[0] > slot_img.shape[0] or
                    template.shape[1] > slot_img.shape[1]):
                continue
            result = cv2.matchTemplate(slot_img, template, cv2.TM_CCOEFF_NORMED)
            _, max_val, _, _ = cv2.minMaxLoc(result)
            if max_val >= self.BACKPACK_MATCH_THRESHOLD:
                return True
        return False

    def _is_slot_empty(self, slot_img):
        """Check if a slot is empty via template matching."""
        import cv2
        from ....repositories.inventory.config import images

        empty_template = images['slots'].get('empty')
        if empty_template is None:
            return False
        if (empty_template.shape[0] > slot_img.shape[0] or
                empty_template.shape[1] > slot_img.shape[1]):
            return False
        result = cv2.matchTemplate(slot_img, empty_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)
        return max_val >= self.EMPTY_MATCH_THRESHOLD

    def _drag_one(self, context: Context) -> None:
        from ....repositories.inventory import (
            get_container_position,
            get_slot_position,
            drag_item,
        )

        if self._items_moved >= self.max_items:
            print(f"[DragItems] Max items ({self.max_items}) reached")
            self._done = True
            return

        if self._start_slot >= self.MAX_SLOT_INDEX:
            print(f"[DragItems] Reached max slot index ({self.MAX_SLOT_INDEX}), done")
            self._done = True
            return

        screenshot = context.get('screenshot')
        source_pos = get_container_position(screenshot, self.source_container)

        if source_pos is None:
            print(f"[DragItems] Source '{self.source_container}' not found, done")
            self._done = True
            return

        slot_img = self._extract_slot_image(screenshot, source_pos, self._start_slot)
        if slot_img is None:
            self._done = True
            return

        if self._is_slot_backpack(slot_img):
            print(f"[DragItems] Slot {self._start_slot} is backpack, skipping")
            self._start_slot += 1
            return

        if self._is_slot_empty(slot_img):
            self._consecutive_empty += 1
            if self._consecutive_empty >= self.MAX_CONSECUTIVE_EMPTY:
                print(f"[DragItems] {self.MAX_CONSECUTIVE_EMPTY} consecutive empty slots, done")
                self._done = True
            return
        self._consecutive_empty = 0

        to_pos = self._find_dest_center(screenshot)
        if to_pos is None:
            print(f"[DragItems] Dest '{self.dest_container}' not found, done")
            self._done = True
            return

        from_pos = get_slot_position(source_pos, self._start_slot)
        drag_item(from_pos, to_pos, duration=0.2)
        self._items_moved += 1
        print(f"[DragItems] Dragged item {self._items_moved}/{self.max_items} from slot {self._start_slot}")

    def did(self, context: Context) -> bool:
        return self._done


class DropBackpackIntoStashTask(BaseTask):
    """
    Drop a backpack into the stash via template matching + drag.

    Finds backpack slot icon and stash icon, then drags.
    """

    def __init__(self, backpack_name: str):
        super().__init__(f"DropBackpackIntoStash({backpack_name})")
        self.backpack_name = backpack_name
        self.delay_after_complete = 1.0
        self._done = False

    def do(self, context: Context) -> Context:
        from ....repositories.inventory.core import drag_item
        from ....repositories.inventory.config import images
        import cv2

        screenshot = context.get('screenshot')

        backpack_key = self.backpack_name.lower()
        backpack_template = images['slots'].get(backpack_key)

        if backpack_template is None:
            print(f"[DropBackpackIntoStash] Template '{backpack_key}' not found")
            self._done = True
            return context

        stash_template = images['slots'].get('stash')
        if stash_template is None:
            print(f"[DropBackpackIntoStash] Stash template not found")
            self._done = True
            return context

        result = cv2.matchTemplate(screenshot, backpack_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < 0.7:
            print(f"[DropBackpackIntoStash] Backpack not found (match={max_val:.2f})")
            self._done = True
            return context

        backpack_pos = (max_loc[0] + backpack_template.shape[1] // 2,
                        max_loc[1] + backpack_template.shape[0] // 2)

        result = cv2.matchTemplate(screenshot, stash_template, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, max_loc = cv2.minMaxLoc(result)

        if max_val < 0.7:
            print(f"[DropBackpackIntoStash] Stash not found (match={max_val:.2f})")
            self._done = True
            return context

        stash_pos = (max_loc[0] + stash_template.shape[1] // 2,
                     max_loc[1] + stash_template.shape[0] // 2)

        drag_item(backpack_pos, stash_pos, duration=0.3)
        print(f"[DropBackpackIntoStash] Dropped {self.backpack_name} into stash")
        self._done = True

        return context

    def did(self, context: Context) -> bool:
        return self._done

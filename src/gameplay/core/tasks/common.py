"""Common Tasks - Basic reusable tasks for gameplay."""
import random
import time
from typing import Optional

import pyautogui

from .base import BaseTask, Context
from ....core.constants import (
    DELAY_HOTKEY, DELAY_WALK_STEP, DELAY_CLICK,
    WALK_COOLDOWN, WALK_TIMEOUT, WALK_STEP_TIMEOUT,
    WALK_PROGRESS_TIMEOUT, WALK_STUCK_COUNT, WALK_MAX_RECALCULATIONS,
    WALK_RETRY_SAME_DIRECTION, DEFAULT_PLAYER_SPEED, DEFAULT_TILE_FRICTION,
    WALK_MAX_CONSECUTIVE_SKIPS, WALK_PREWALK_RATIO,
    WALK_MAP_CLICK_ENABLED, WALK_MAP_CLICK_MIN_DISTANCE, WALK_MAP_CLICK_STALL_TIMEOUT,
    WALK_MAP_CLICK_MAX_RETRIES, MINIMAP_CLICK_MARGIN,
)
from ....repositories.radar.friction import TileFrictionCalculator
from ....repositories.radar.locators import get_radar_tools_position
from ....repositories.radar.extractors import get_minimap_pixel
from ....utils.jitter import jitter


WASD_MAP = {'up': 'w', 'down': 's', 'left': 'a', 'right': 'd',
            'north': 'w', 'south': 's', 'west': 'a', 'east': 'd'}


def get_creature_coordinate(creature) -> Optional[tuple]:
    """Extract coordinate from creature object or dict."""
    if creature is None:
        return None
    if hasattr(creature, 'coordinate'):
        return creature.coordinate
    if isinstance(creature, dict):
        return creature.get('coordinate')
    return None


def coordinates_equal(coord_a: tuple, coord_b: tuple) -> bool:
    """Check if two coordinates are equal."""
    if coord_a is None or coord_b is None:
        return False
    return coord_a[0] == coord_b[0] and coord_a[1] == coord_b[1] and coord_a[2] == coord_b[2]


def collect_obstacles(context: Context, exclude_coord: tuple = None) -> list:
    """Collect non-walkable coordinates from context."""
    obstacles = []

    holes_or_stairs = context.get('cavebot', {}).get('holesOrStairs', [])
    obstacles.extend(holes_or_stairs)

    monsters = context.get('gameWindow', {}).get('monsters', [])
    for monster in monsters:
        coord = get_creature_coordinate(monster)
        if coord is None:
            continue
        if exclude_coord is not None and coordinates_equal(coord, exclude_coord):
            continue
        obstacles.append(coord)

    return obstacles


class UseHotkeyTask(BaseTask):
    """Press a hotkey."""

    def __init__(self, hotkey: str, name: str = None):
        super().__init__(name or f"UseHotkey({hotkey})")
        self.hotkey = hotkey
        self.delay_after_complete = DELAY_HOTKEY

    def do(self, context: Context) -> Context:
        pyautogui.press(self.hotkey)
        return context


class WalkTask(BaseTask):
    """Walk one tile in a direction using WASD with dynamic friction-based delay."""

    def __init__(self, direction: str):
        super().__init__(f"Walk({direction})")
        self.direction = direction
        self.delay_of_timeout = WALK_STEP_TIMEOUT
        self.delay_after_complete = DELAY_WALK_STEP
        self._start_coordinate = None
        self._friction_calculator = TileFrictionCalculator()

    def do(self, context: Context) -> Context:
        self._start_coordinate = context.get('radar', {}).get('coordinate')
        self._calculate_movement_delay(context)
        key = WASD_MAP.get(self.direction.lower(), self.direction)
        pyautogui.press(key)
        return context

    def _calculate_movement_delay(self, context: Context) -> None:
        """Calculate delay based on player speed and tile friction."""
        player_speed = context.get('playerSpeed', DEFAULT_PLAYER_SPEED)
        destination = self._get_destination_coordinate(context)
        tile_friction = self._friction_calculator.get_tile_friction(destination)
        movement_time = self._friction_calculator.get_movement_time_seconds(
            player_speed, tile_friction
        )
        self.delay_after_complete = movement_time

    def _get_destination_coordinate(self, context: Context) -> Optional[tuple]:
        """Get the destination coordinate based on current position and direction."""
        current = context.get('radar', {}).get('coordinate')
        if current is None:
            return None

        direction_offsets = {
            'up': (0, -1), 'north': (0, -1), 'w': (0, -1),
            'down': (0, 1), 'south': (0, 1), 's': (0, 1),
            'left': (-1, 0), 'west': (-1, 0), 'a': (-1, 0),
            'right': (1, 0), 'east': (1, 0), 'd': (1, 0),
        }

        offset = direction_offsets.get(self.direction.lower(), (0, 0))
        return (current[0] + offset[0], current[1] + offset[1], current[2])

    def did(self, context: Context) -> bool:
        current = context.get('radar', {}).get('coordinate')
        if current is None or self._start_coordinate is None:
            return False
        return current != self._start_coordinate


class WalkToCoordinateTask(BaseTask):
    """Walk to coordinate with dynamic obstacle avoidance and friction-based delays."""

    def __init__(self, goal: tuple, arrive_distance: int = 0):
        super().__init__(f"WalkTo({goal})")
        self.goal = goal
        self._arrive_distance = arrive_distance
        self._map_walking = False
        self._map_click_time = 0
        self._map_retries = 0
        self.delay_of_timeout = WALK_TIMEOUT

        self._path = []
        self._path_index = 0
        self._last_pos = None
        self._stuck_count = 0
        self._last_walk_time = 0
        self._walk_cooldown = WALK_COOLDOWN
        self._is_walking = False

        self._recalculation_count = 0
        self._max_recalculations = WALK_MAX_RECALCULATIONS
        self._last_progress_time = 0
        self._progress_timeout = WALK_PROGRESS_TIMEOUT
        self._best_distance = float('inf')
        self._force_complete = False
        self._wrong_floor = False

        self._last_obstacle_hash = None
        self._retry_same_direction = 0
        self._max_retry_same_direction = WALK_RETRY_SAME_DIRECTION

        self._friction_calculator = TileFrictionCalculator()

    def _distance_to_goal(self, coord: tuple) -> float:
        if coord is None:
            return float('inf')
        return abs(coord[0] - self.goal[0]) + abs(coord[1] - self.goal[1])

    def _obstacle_hash(self, obstacles: list) -> int:
        return hash(tuple(tuple(c) if isinstance(c, (list, tuple)) else c for c in obstacles))

    def do(self, context: Context) -> Context:
        from ...cavebot.radar import generate_floor_walkpoints
        from ..waypoint import generate_global_walkpoints

        current = context.get('radar', {}).get('coordinate')
        if current is None:
            return context

        if current[2] != self.goal[2]:
            print(f"[Walk] Cannot walk to different floor {self.goal} from {current} - skipping")
            self._force_complete = True
            self._wrong_floor = True
            return context

        obstacles = collect_obstacles(context)
        self._last_obstacle_hash = self._obstacle_hash(obstacles)

        if obstacles:
            print(f"[Walk] Avoiding {len(obstacles)} obstacles")

        self._path = generate_floor_walkpoints(current, self.goal, obstacles)

        # If path is just 1 step and goal is far, use global pathfinding
        if len(self._path) == 1 and self._distance_to_goal(current) > 10:
            print(f"[Walk] Goal outside radar range, using global pathfinding...")
            self._path = generate_global_walkpoints(current, self.goal, max_path_length=30)

        self._path_index = 0
        self._last_pos = current
        self._last_progress_time = time.time()
        self._best_distance = self._distance_to_goal(current)
        self._recalculation_count = 0
        self._force_complete = False

        if not self._path:
            print(f"[Walk] No path to {self.goal} - marking unreachable")
            self._force_complete = True
            return context

        print(f"[Walk] Path to {self.goal}: {len(self._path)} steps")
        if self._click_minimap(context, current):
            return context
        return self.ping(context)

    def _chebyshev_to_goal(self, coord: tuple) -> int:
        return max(abs(coord[0] - self.goal[0]), abs(coord[1] - self.goal[1]))

    def _click_minimap(self, context: Context, current: tuple) -> bool:
        """Let the client auto-walk: click the goal on the minimap. Returns True if clicked."""
        if not context.get('cavebot', {}).get('mapClickWalking', WALK_MAP_CLICK_ENABLED):
            return False
        if self._chebyshev_to_goal(current) < WALK_MAP_CLICK_MIN_DISTANCE:
            return False
        screenshot = context.get('screenshot')
        tools = get_radar_tools_position(screenshot) if screenshot is not None else None
        if tools is None:
            return False
        pixel = get_minimap_pixel(tools, current, self.goal, MINIMAP_CLICK_MARGIN)
        if pixel is None:
            return False

        pyautogui.click(*pixel)
        self._map_walking = True
        self._map_click_time = time.time()
        self._last_pos = current
        print(f"[Walk] Map click to {self.goal}")
        return True

    def _ping_map_walk(self, context: Context) -> Context:
        """Watch the client auto-walk; re-click once if it stalls, then fall back to keys."""
        current = context.get('radar', {}).get('coordinate')
        if current is None:
            return context

        now = time.time()
        if current != self._last_pos:
            self._last_pos = current
            self._map_click_time = now
            return context

        if now - self._map_click_time < WALK_MAP_CLICK_STALL_TIMEOUT:
            return context

        if self._map_retries < WALK_MAP_CLICK_MAX_RETRIES:
            self._map_retries += 1
            print(f"[Walk] Map walk stalled at {current} - clicking again")
            if self._click_minimap(context, current):
                return context

        print(f"[Walk] Map walk stalled at {current} - switching to keys")
        self._map_walking = False
        return self._fall_back_to_keys(context, current, now)

    def _fall_back_to_keys(self, context: Context, current: tuple, now: float) -> Context:
        from ...cavebot.radar import generate_floor_walkpoints

        self._path = generate_floor_walkpoints(current, self.goal, collect_obstacles(context))
        self._path_index = 0
        self._is_walking = False
        self._last_progress_time = now
        if not self._path:
            print(f"[Walk] No path to {self.goal} - marking unreachable")
            self._force_complete = True
        return context

    def ping(self, context: Context) -> Context:
        if self._force_complete:
            return context

        if self._map_walking:
            return self._ping_map_walk(context)

        if self._path_index >= len(self._path):
            return context

        current = context.get('radar', {}).get('coordinate')
        if current is None:
            return context

        now = time.time()

        if self._handle_obstacle_change(context, current):
            return context

        if self._path_index >= len(self._path):
            return context

        target = self._path[self._path_index]
        moved = self._last_pos is not None and current != self._last_pos

        if moved:
            self._handle_movement(current, now)

        if self._check_progress_timeout(now):
            return context

        if self._at_path_target(current, target, now):
            return context

        if self._handle_stuck(context, current, moved, target, now):
            return context

        self._last_pos = current
        self._try_walk(current, target, now, context)

        return context

    def _handle_obstacle_change(self, context: Context, current: tuple) -> bool:
        """Recalculate path if obstacles changed. Returns True if recalculated."""
        from ...cavebot.radar import generate_floor_walkpoints

        obstacles = collect_obstacles(context)
        current_hash = self._obstacle_hash(obstacles)

        if current_hash == self._last_obstacle_hash:
            return False

        self._last_obstacle_hash = current_hash
        new_path = generate_floor_walkpoints(current, self.goal, obstacles)

        if new_path:
            self._path = new_path
            self._path_index = 0
            self._stuck_count = 0
            self._is_walking = False

        return True

    def _handle_movement(self, current: tuple, now: float) -> None:
        """Handle successful movement."""
        self._is_walking = False
        self._stuck_count = 0
        self._retry_same_direction = 0

        current_distance = self._distance_to_goal(current)
        if current_distance < self._best_distance:
            self._best_distance = current_distance
            self._last_progress_time = now

    def _check_progress_timeout(self, now: float) -> bool:
        """Check if we've timed out making progress. Returns True if timed out."""
        time_since_progress = now - self._last_progress_time
        if time_since_progress <= self._progress_timeout:
            return False

        print(f"[Walk] No progress for {time_since_progress:.1f}s - skipping {self.goal}")
        self._force_complete = True
        return True

    def _at_path_target(self, current: tuple, target: tuple, now: float) -> bool:
        """Check if at current path target. Returns True if at target."""
        if current[0] != target[0] or current[1] != target[1]:
            return False

        self._path_index += 1
        self._is_walking = False
        self._last_pos = current
        self._last_progress_time = now
        return True

    def _handle_stuck(self, context: Context, current: tuple, moved: bool,
                      target: tuple, now: float) -> bool:
        """Handle stuck detection. Returns True if stuck handling triggered."""
        if not self._is_walking or moved:
            return False

        self._stuck_count += 1

        if self._stuck_count >= 8 and self._retry_same_direction < self._max_retry_same_direction:
            if not self._is_monster_blocking(context, target):
                self._retry_same_direction += 1
                print(f"[Walk] Blocked - retry {self._retry_same_direction}/{self._max_retry_same_direction}")
                self._is_walking = False
                self._stuck_count = 0
                return True

        if self._stuck_count <= WALK_STUCK_COUNT:
            return False

        return self._recalculate_path(context, current)

    def _is_monster_blocking(self, context: Context, target: tuple) -> bool:
        """Check if a monster is blocking the target tile."""
        monsters = context.get('gameWindow', {}).get('monsters', [])
        for monster in monsters:
            coord = get_creature_coordinate(monster)
            if coord is None:
                continue
            if coord[0] == target[0] and coord[1] == target[1]:
                return True
        return False

    def _recalculate_path(self, context: Context, current: tuple) -> bool:
        """Recalculate path when stuck. Returns True."""
        from ...cavebot.radar import generate_floor_walkpoints

        self._retry_same_direction = 0
        self._recalculation_count += 1

        if self._recalculation_count >= self._max_recalculations:
            print(f"[Walk] Max recalculations reached - skipping {self.goal}")
            self._force_complete = True
            return True

        print(f"[Walk] Stuck, recalculating ({self._recalculation_count}/{self._max_recalculations})")
        obstacles = collect_obstacles(context)
        self._path = generate_floor_walkpoints(current, self.goal, obstacles)
        self._path_index = 0
        self._stuck_count = 0
        self._is_walking = False

        if not self._path:
            print(f"[Walk] No path after recalculation - skipping {self.goal}")
            self._force_complete = True

        return True

    def _try_walk(self, current: tuple, target: tuple, now: float, context: Context = None) -> None:
        """Try to walk toward target with friction-based cooldown."""
        if self._is_walking:
            return
        if now - self._last_walk_time < self._walk_cooldown * WALK_PREWALK_RATIO:
            return

        from ...cavebot.radar import get_direction_between_coords
        direction = get_direction_between_coords(current, target)
        if direction is None:
            return

        key = WASD_MAP.get(direction, direction)
        pyautogui.press(key)
        self._last_walk_time = now
        self._is_walking = True

        self._update_walk_cooldown(target, context)

    def _update_walk_cooldown(self, target: tuple, context: Context) -> None:
        """Update walk cooldown based on tile friction and player speed."""
        if context is None:
            return

        player_speed = context.get('playerSpeed', DEFAULT_PLAYER_SPEED)
        tile_friction = self._friction_calculator.get_tile_friction(target)
        self._walk_cooldown = self._friction_calculator.get_movement_time_seconds(
            player_speed, tile_friction
        )
        self._is_walking = True

    def did(self, context: Context) -> bool:
        if self._force_complete:
            return True

        current = context.get('radar', {}).get('coordinate')
        if current is None:
            return False

        if self._arrive_distance and current[2] == self.goal[2]:
            if self._chebyshev_to_goal(current) <= self._arrive_distance:
                return True

        return (current[0] == self.goal[0] and
                current[1] == self.goal[1] and
                current[2] == self.goal[2])

    def on_complete(self, context: Context) -> Context:
        if not self._force_complete:
            context.get('cavebot', {}).pop('_skipState', None)
            return context

        if self._wrong_floor:
            from ..waypoint import jump_back_to_current_floor
            jump_back_to_current_floor(context)
            return context

        current = context.get('radar', {}).get('coordinate')
        skip_state = context.get('cavebot', {}).get('_skipState', {})
        last_pos = skip_state.get('position')
        count = skip_state.get('count', 0)

        if current == last_pos:
            count += 1
        else:
            count = 1

        context.setdefault('cavebot', {})['_skipState'] = {
            'position': current,
            'count': count,
        }

        if count >= WALK_MAX_CONSECUTIVE_SKIPS:
            print(f"[Walk] CIRCUIT BREAKER: {count} consecutive skips at {current} - emergency random walk")
            self._emergency_random_walk()
            context['cavebot']['_skipState']['count'] = 0
        else:
            print(f"[Walk] Waypoint {self.goal} skipped ({count}/{WALK_MAX_CONSECUTIVE_SKIPS}) - finding closest waypoint")
            self._jump_to_closest_waypoint(context)

        return context

    def _jump_to_closest_waypoint(self, context: Context) -> None:
        """When stuck, jump to the closest reachable waypoint."""
        from ..waypoint import jump_to_closest_waypoint
        jump_to_closest_waypoint(context)

    def _emergency_random_walk(self) -> None:
        """Press random WASD keys to try to unstick."""
        keys = ['w', 'a', 's', 'd']
        for _ in range(3):
            pyautogui.press(random.choice(keys))
            time.sleep(jitter(0.3))


class ClickTask(BaseTask):
    """Click at a screen position."""

    def __init__(self, x: int, y: int, button: str = 'left'):
        super().__init__(f"Click({x}, {y})")
        self.x = x
        self.y = y
        self.button = button
        self.delay_after_complete = DELAY_CLICK

    def do(self, context: Context) -> Context:
        pyautogui.click(self.x, self.y, button=self.button)
        return context

"""
Cavebot Tasks - Tasks for cave exploration and combat.

Attack system uses VectorTask composition:
- ClickInClosestCreatureTask: initiates attack on closest creature (Alt+Click)
- WalkToTargetCreatureTask: waits for creature death (Tibia auto-chase handles walking)
- AttackClosestCreatureTask: orchestrates click → wait → loot cycle
"""
import time

import pyautogui

from .base import BaseTask, Context
from .vector import VectorTask
from src.wiki.creatures import get_creature
from .common import WalkToCoordinateTask
from ....utils.jitter import jitter
from ....core.constants import (
    WALK_CREATURE_TIMEOUT, CAVEBOT_ATTACK_STUCK_TIMEOUT,
)


class ClickInClosestCreatureTask(BaseTask):
    """
    Initiate attack on closest reachable creature, then wait for confirmation.

    - Alt+Click on closestCreature.window_coordinate (targets BFS-reachable creature)
    - If click misses after grace period, fallback to Space (only without players)
    - Press Space directly when closestCreature is None
    - Completes when isAttackingSomeCreature becomes True
    """

    CLICK_GRACE_PERIOD = 0.5

    def __init__(self):
        super().__init__("ClickInClosestCreature")
        self.delay_of_timeout = 2.0
        self._click_time = 0

    def should_ignore(self, context: Context) -> bool:
        """Skip if already attacking."""
        return context.get('cavebot', {}).get('isAttackingSomeCreature', False)

    def do(self, context: Context) -> Context:
        """Click on closest creature to initiate attack."""
        closest = context.get('cavebot', {}).get('closestCreature')
        if closest is None:
            pyautogui.press('space')
            print("[Click] Press Space (attack nearest, no pathfinding target)")
            return context

        has_players = context.get('cavebot', {}).get('hasPlayers', False)
        id_method = getattr(closest, 'id_method', '')

        name = getattr(closest, 'name', 'Unknown')

        safe_to_click = not has_players or id_method in ('TM', 'OCR', 'BL')

        if hasattr(closest, 'window_coordinate') and safe_to_click:
            x, y = closest.window_coordinate
            pyautogui.keyDown('alt')
            pyautogui.click(x, y)
            pyautogui.keyUp('alt')
            self._click_time = time.time()
            print(f"[Click] Alt+Click {name} at ({x}, {y})")
        else:
            pyautogui.press('space')
            print(f"[Click] Space ({name}, players={has_players}, method={id_method})")

        telemetry = context.get('telemetry')
        if telemetry:
            coord = context.get('radar', {}).get('coordinate')
            position = (coord[0], coord[1], coord[2]) if coord else None
            telemetry.track_attack_start(name, position=position)

        gui_logger = context.get('gui_logger')
        if gui_logger:
            gui_logger(f"Atacando {name}", "info")

        return context

    def ping(self, context: Context) -> Context:
        """Fallback to Space if click didn't register attack within grace period."""
        if self._click_time == 0:
            return context
        if context.get('cavebot', {}).get('isAttackingSomeCreature', False):
            return context
        if time.time() - self._click_time < self.CLICK_GRACE_PERIOD:
            return context
        has_players = context.get('cavebot', {}).get('hasPlayers', False)
        if has_players:
            return context
        pyautogui.press('space')
        self._click_time = 0
        print("[Click] Click missed, fallback Space")
        return context

    def did(self, context: Context) -> bool:
        """Done when attack is confirmed."""
        return context.get('cavebot', {}).get('isAttackingSomeCreature', False)


class WalkToTargetCreatureTask(BaseTask):
    """
    Actively walk to target creature using A* pathfinding after Alt+Click.

    Does NOT rely on Tibia's auto-chase. Immediately starts walking toward
    the creature using the same A* pathfinding as waypoint walking (avoids
    walls). Re-clicks the creature every 4s as backup for missed clicks.
    """

    WALK_COOLDOWN = 0.35
    RECLICK_INTERVAL = 4.0

    def __init__(self):
        super().__init__("WalkToTargetCreature")
        self.delay_of_timeout = WALK_CREATURE_TIMEOUT
        self._last_walk_time = 0
        self._last_reclick_time = 0
        self._is_walking = False
        self._last_pos = None
        self._path = []
        self._path_index = 0
        self._last_target_coord = None

    def do(self, context: Context) -> Context:
        coord = context.get('radar', {}).get('coordinate')
        self._last_pos = coord
        self._last_reclick_time = time.time()
        self._recalculate_path(context)
        return context

    def _get_gw_creature(self, context: Context):
        """Get GameWindowCreature with coordinate (closestCreature from GW middleware)."""
        closest = context.get('cavebot', {}).get('closestCreature')
        if closest is not None and hasattr(closest, 'coordinate'):
            return closest
        return None

    def _recalculate_path(self, context: Context):
        """Calculate A* path from player to creature, avoiding walls and monsters."""
        from ..waypoint import generate_floor_walkpoints
        from .common import collect_obstacles

        coord = context.get('radar', {}).get('coordinate')
        target = self._get_gw_creature(context)
        if coord is None or target is None:
            self._path = []
            return

        target_coord = target.coordinate
        self._last_target_coord = target_coord

        if target_coord[0] == coord[0] and target_coord[1] == coord[1]:
            self._path = []
            return

        obstacles = collect_obstacles(context, exclude_coord=target_coord)
        self._path = generate_floor_walkpoints(coord, target_coord, obstacles)
        self._path_index = 0
        self._is_walking = False

    def ping(self, context: Context) -> Context:
        """Walk toward creature every tick using A* pathfinding."""
        from ...cavebot.radar import get_direction_between_coords
        from .common import WASD_MAP

        coord = context.get('radar', {}).get('coordinate')
        if coord is None:
            return context

        target = self._get_gw_creature(context)
        now = time.time()

        # Re-click creature periodically (backup for missed clicks)
        if target is not None and now - self._last_reclick_time > self.RECLICK_INTERVAL:
            if hasattr(target, 'window_coordinate'):
                x, y = target.window_coordinate
                pyautogui.keyDown('alt')
                pyautogui.click(x, y)
                pyautogui.keyUp('alt')
                self._last_reclick_time = now
                print(f"[Walk] Re-click {target.name} at ({x}, {y})")

        if target is None:
            return context

        # Detect movement
        moved = self._last_pos is not None and coord != self._last_pos
        if moved:
            self._is_walking = False
        self._last_pos = coord

        target_coord = target.coordinate
        if target_coord[0] == coord[0] and target_coord[1] == coord[1]:
            return context

        # Recalculate path when target moved or path exhausted
        target_moved = (self._last_target_coord is None or
                        target_coord[0] != self._last_target_coord[0] or
                        target_coord[1] != self._last_target_coord[1])
        path_exhausted = self._path_index >= len(self._path)

        if target_moved or path_exhausted:
            self._recalculate_path(context)

        # Advance past completed path steps
        while (self._path_index < len(self._path) and
               coord[0] == self._path[self._path_index][0] and
               coord[1] == self._path[self._path_index][1]):
            self._path_index += 1
            self._is_walking = False

        # Cooldown between walk steps
        if self._is_walking:
            return context
        if now - self._last_walk_time < self.WALK_COOLDOWN:
            return context

        # Walk next A* step
        if self._path and self._path_index < len(self._path):
            next_step = self._path[self._path_index]
            direction = get_direction_between_coords(coord, next_step)
            if direction:
                key = WASD_MAP.get(direction, direction)
                pyautogui.press(key)
                self._last_walk_time = now
                self._is_walking = True
                dx = target_coord[0] - coord[0]
                dy = target_coord[1] - coord[1]
                print(f"[Walk] A* toward {target.name}: {key} (dx={dx}, dy={dy}, path={len(self._path) - self._path_index})")
                return context

        # No A* path — direct WASD as last resort
        dx = target_coord[0] - coord[0]
        dy = target_coord[1] - coord[1]
        if dx == 0 and dy == 0:
            return context
        if abs(dx) >= abs(dy):
            key = 'd' if dx > 0 else 'a'
        else:
            key = 's' if dy > 0 else 'w'
        pyautogui.press(key)
        self._last_walk_time = now
        self._is_walking = True
        print(f"[Walk] Direct toward {target.name}: {key} (dx={dx}, dy={dy})")
        return context

    def did(self, context: Context) -> bool:
        """Done when creature died (no longer attacking)."""
        is_attacking = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        if not is_attacking:
            return True
        battle_list = context.get('battleList', {}).get('creatures', [])
        if len(battle_list) == 0:
            return True
        return False


class AttackClosestCreatureTask(VectorTask):
    """
    Composite task orchestrating click → walk → loot cycle.

    1. ClickInClosestCreatureTask → initiates attack
    2. WalkToTargetCreatureTask → walks to creature
    3. Creature dies → should_restart checks for more creatures
    4. on_before_restart → loot, reset children
    5. No more creatures → on_complete → final loot, restore waypoint

    Tibia's auto-chase handles walking; bot handles looting between kills.
    """

    def __init__(self):
        super().__init__("AttackClosestCreature")
        self.max_retries = 100
        self.delay_of_timeout = CAVEBOT_ATTACK_STUCK_TIMEOUT
        self._last_target_name = None

    def on_before_start(self, context: Context) -> Context:
        """Save waypoint index and create children."""
        cavebot = context.get('cavebot')
        if cavebot is not None:
            waypoints = cavebot.get('waypoints')
            if waypoints is not None:
                current_index = waypoints.get('currentIndex', 0)
                waypoints['indexBeforeCombat'] = current_index

        closest = context.get('cavebot', {}).get('closestCreature')
        if closest:
            self._last_target_name = getattr(closest, 'name', None)

        self.tasks = []
        self.add_task(ClickInClosestCreatureTask())
        self.add_task(WalkToTargetCreatureTask())

        return context

    def should_restart(self, context: Context) -> bool:
        """Restart if there are still creatures to fight.

        Uses battlelist (stable) instead of closestCreature (set by gamewindow
        middleware at freq 2, becomes stale between ticks causing phantom silence).
        """
        if context.get('cavebot', {}).get('_targetUnreachable', False):
            context['cavebot']['_targetUnreachable'] = False
            return False
        battle_list = context.get('battleList', {}).get('creatures', [])
        return len(battle_list) > 0

    def on_before_restart(self, context: Context) -> Context:
        """Loot before attacking next creature."""
        # Signal kill to gameloop (for combat timeout tracking)
        context['cavebot']['lastKillTime'] = time.time()

        # Track kill via telemetry
        telemetry = context.get('telemetry')
        if telemetry:
            target = context.get('cavebot', {}).get('targetCreature')
            coord = context.get('radar', {}).get('coordinate')
            creature_name = getattr(target, 'name', None) if target else self._last_target_name
            position = (coord[0], coord[1], coord[2]) if coord else None
            wiki_creature = get_creature(creature_name) if creature_name else None
            experience = wiki_creature.exp if wiki_creature else None
            telemetry.track_kill(creature_name or 'Unknown', experience=experience, position=position)

        if context.get('loot', {}).get('enabled', False):
            hotkey = context.get('loot', {}).get('hotkey', 'g')
            pyautogui.press(hotkey)
            print("[Attack] Looting before next target")

        gui_logger = context.get('gui_logger')
        if gui_logger:
            gui_logger("Looteando corpo", "success")

        # Capture next target name before resetting children
        closest = context.get('cavebot', {}).get('closestCreature')
        if closest:
            self._last_target_name = getattr(closest, 'name', None)

        # Reset children for next cycle
        self.tasks = []
        self.add_task(ClickInClosestCreatureTask())
        self.add_task(WalkToTargetCreatureTask())
        return super().on_before_restart(context)

    def on_complete(self, context: Context) -> Context:
        """Final loot and restore waypoint index.

        The orchestrator calls on_complete() BEFORE checking should_restart().
        Only do final cleanup when combat is truly over (no more reachable creatures).
        """
        # Walk task couldn't reach target — disengage immediately
        if context.get('cavebot', {}).get('_targetUnreachable', False):
            context['cavebot']['_targetUnreachable'] = False

            # Request blacklist so gameloop won't re-target this creature
            target = context.get('cavebot', {}).get('targetCreature')
            if target and hasattr(target, 'name') and hasattr(target, 'coordinate'):
                context['cavebot']['_blacklistCreature'] = {
                    'name': target.name,
                    'coordinate': target.coordinate,
                }

            pyautogui.press('escape')
            context['cavebot']['isAttackingSomeCreature'] = False
            context['cavebot']['targetCreature'] = None
            context['cavebot']['closestCreature'] = None
            print("[Attack] Target unreachable — disengaging + blacklisting")
            self._restore_waypoint_index(context)
            return context

        battle_list = context.get('battleList', {}).get('creatures', [])
        if len(battle_list) > 0:
            # Will restart — on_before_restart handles looting
            return context

        # Signal kill to gameloop (for combat timeout tracking)
        context['cavebot']['lastKillTime'] = time.time()

        # Track final kill via telemetry
        telemetry = context.get('telemetry')
        if telemetry:
            target = context.get('cavebot', {}).get('targetCreature')
            coord = context.get('radar', {}).get('coordinate')
            creature_name = getattr(target, 'name', None) if target else self._last_target_name
            position = (coord[0], coord[1], coord[2]) if coord else None
            wiki_creature = get_creature(creature_name) if creature_name else None
            experience = wiki_creature.exp if wiki_creature else None
            telemetry.track_kill(creature_name or 'Unknown', experience=experience, position=position)

        context['cavebot']['targetCreature'] = None

        is_still_attacking = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        if is_still_attacking:
            pyautogui.press('escape')
            context['cavebot']['isAttackingSomeCreature'] = False

        if context.get('loot', {}).get('enabled', False):
            hotkey = context.get('loot', {}).get('hotkey', 'g')
            pyautogui.press(hotkey)

        self._restore_waypoint_index(context)

        return context

    def on_timeout(self, context: Context) -> Context:
        """Clear target and deselect creature when attack times out."""
        cavebot = context.get('cavebot')
        if cavebot is not None:
            # Request blacklist so gameloop won't re-target this creature
            target = cavebot.get('targetCreature')
            if target and hasattr(target, 'name') and hasattr(target, 'coordinate'):
                cavebot['_blacklistCreature'] = {
                    'name': target.name,
                    'coordinate': target.coordinate,
                }

            cavebot['targetCreature'] = None
            cavebot['isAttackingSomeCreature'] = False

        pyautogui.press('escape')
        print("[Attack] Timeout — target cleared + blacklisted")

        self._restore_waypoint_index(context)

        return context

    def _restore_waypoint_index(self, context: Context) -> None:
        """Find best waypoint index after combat ends."""
        from ....repositories.radar import get_closest_waypoint_index
        from ....core.constants import CAVEBOT_MAX_WAYPOINT_SKIP

        waypoints_data = context.get('cavebot', {}).get('waypoints', {})
        saved_index = waypoints_data.get('indexBeforeCombat')

        if saved_index is None:
            return

        current_coord = context.get('radar', {}).get('coordinate')
        if current_coord is None:
            return

        waypoints = waypoints_data.get('items', [])
        if not waypoints:
            return

        closest_index = get_closest_waypoint_index(current_coord, waypoints)
        if closest_index is None:
            return

        new_index = self._calculate_best_index(saved_index, closest_index, CAVEBOT_MAX_WAYPOINT_SKIP, len(waypoints))

        context['cavebot']['waypoints']['currentIndex'] = new_index
        context['cavebot']['waypoints']['indexBeforeCombat'] = None

        print(f"[Attack] Waypoint restored: saved={saved_index}, closest={closest_index}, using={new_index}")

    def _calculate_best_index(self, saved: int, closest: int, max_skip: int, total: int) -> int:
        """Calculate best waypoint index using closest forward with max skip."""
        if closest == saved or total == 0:
            return saved

        forward_distance = (closest - saved) % total
        if forward_distance <= max_skip:
            return closest

        return saved


class LootCorpseTask(BaseTask):
    """Loot a corpse using hotkey."""

    def __init__(self, hotkey: str = 'g'):
        super().__init__("LootCorpse")
        self.hotkey = hotkey
        self.delay_after_complete = 0.3

    def do(self, context: Context) -> Context:
        pyautogui.press(self.hotkey)
        return context


class SetNextWaypointTask(BaseTask):
    """Advance to the next waypoint in the route."""

    def __init__(self):
        super().__init__("SetNextWaypoint")

    def do(self, context: Context) -> Context:
        waypoints = context.get('cavebot', {}).get('waypoints', {})
        items = waypoints.get('items', [])
        current_index = waypoints.get('currentIndex', 0)

        next_index = current_index + 1
        if next_index >= len(items):
            next_index = 0

        context['cavebot']['waypoints']['currentIndex'] = next_index

        telemetry = context.get('telemetry')
        if telemetry:
            coord = context.get('radar', {}).get('coordinate')
            position = (coord[0], coord[1], coord[2]) if coord else None
            waypoint_type = None
            if next_index < len(items):
                waypoint_type = items[next_index].get('type') if isinstance(items[next_index], dict) else getattr(items[next_index], 'type', None)
            route_name = context.get('cavebot', {}).get('routeName')
            telemetry.track_waypoint_reached(
                next_index,
                waypoint_type=waypoint_type,
                position=position,
                route_name=route_name,
                total_waypoints=len(items),
            )

        return context


class WalkToWaypointTask(VectorTask):
    """Walk to a waypoint coordinate."""

    def __init__(self, coordinate: tuple):
        super().__init__(f"WalkToWaypoint({coordinate})")
        self.add_task(WalkToCoordinateTask(coordinate))
        self.add_task(SetNextWaypointTask())


class UseRopeTask(BaseTask):
    """Use rope on a tile."""

    def __init__(self, hotkey: str = 'o', target_coord: tuple = None):
        super().__init__("UseRope")
        self.hotkey = hotkey
        self.target_coord = target_coord
        self.delay_after_complete = 1.0
        self._gamewindow = None

    def do(self, context: Context) -> Context:
        target = self.target_coord
        if target is None:
            target = context.get('radar', {}).get('coordinate')

        if target is None:
            print("[UseRope] No target coordinate!")
            return context

        player_coord = context.get('radar', {}).get('coordinate')
        if player_coord is None:
            print("[UseRope] No player coordinate!")
            return context

        if self._gamewindow is None:
            from ....repositories.gamewindow import get_gamewindow_repository
            self._gamewindow = get_gamewindow_repository()

        print(f"[UseRope] Pressing hotkey '{self.hotkey}'")
        pyautogui.press(self.hotkey)
        time.sleep(jitter(0.15))

        slot = self._gamewindow.get_slot_from_coordinate(player_coord, target)
        if slot is None:
            print(f"[UseRope] Target {target} out of range from {player_coord}")
            return context

        print(f"[UseRope] Clicking slot {slot} for coordinate {target}")
        self._gamewindow.click_slot(slot)

        return context


class UseShovelTask(BaseTask):
    """Use shovel on a tile."""

    DIRECTION_OFFSETS = {
        'north': (0, -1),
        'south': (0, 1),
        'east': (1, 0),
        'west': (-1, 0),
    }

    def __init__(self, hotkey: str = 'p', target_coord: tuple = None, direction: str = None):
        super().__init__("UseShovel")
        self.hotkey = hotkey
        self.target_coord = target_coord
        self.direction = direction
        self.delay_after_complete = 1.0
        self._gamewindow = None

    def do(self, context: Context) -> Context:
        player_coord = context.get('radar', {}).get('coordinate')
        if player_coord is None:
            print("[UseShovel] No player coordinate!")
            return context

        if self.direction and self.direction in self.DIRECTION_OFFSETS:
            dx, dy = self.DIRECTION_OFFSETS[self.direction]
            target = (player_coord[0] + dx, player_coord[1] + dy, player_coord[2])
            print(f"[UseShovel] Digging {self.direction} from {player_coord} -> {target}")
        elif self.target_coord:
            target = self.target_coord
        else:
            print("[UseShovel] No direction or target coordinate!")
            return context

        if self._gamewindow is None:
            from ....repositories.gamewindow import get_gamewindow_repository
            self._gamewindow = get_gamewindow_repository()

        print(f"[UseShovel] Pressing hotkey '{self.hotkey}'")
        pyautogui.press(self.hotkey)
        time.sleep(jitter(0.15))

        slot = self._gamewindow.get_slot_from_coordinate(player_coord, target)
        if slot is None:
            print(f"[UseShovel] Target {target} out of range from {player_coord}")
            return context

        print(f"[UseShovel] Clicking slot {slot} for coordinate {target}")
        self._gamewindow.click_slot(slot)

        return context


class UseLadderTask(BaseTask):
    """Use ladder/stairs/hole by walking into it."""

    DIRECTION_KEYS = {
        'up': 'w', 'down': 's', 'left': 'a', 'right': 'd',
        'north': 'w', 'south': 's', 'west': 'a', 'east': 'd',
    }

    def __init__(self, direction: str = 'south'):
        super().__init__(f"UseLadder({direction})")
        self.direction = direction
        self.delay_after_complete = 0.8

    def do(self, context: Context) -> Context:
        key = self.DIRECTION_KEYS.get(self.direction.lower(), self.direction)
        print(f"[UseLadder] Walking {self.direction} (pressing {key})")
        pyautogui.press(key)
        return context


class CheckMonstersTask(BaseTask):
    """Check if there are monsters to attack."""

    def __init__(self):
        super().__init__("CheckMonsters")
        self._has_monsters = False

    def do(self, context: Context) -> Context:
        creatures = context.get('gameWindow', {}).get('creatures', [])
        monsters = context.get('gameWindow', {}).get('monsters', [])
        hp_bars = context.get('gameWindow', {}).get('monstersBars', [])

        self._has_monsters = (
            len(creatures) > 0 or
            len(monsters) > 0 or
            len(hp_bars) > 0
        )

        return context

    @property
    def has_monsters(self) -> bool:
        return self._has_monsters

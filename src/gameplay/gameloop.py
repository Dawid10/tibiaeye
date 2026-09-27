"""Game Loop - PyTibia style main loop."""
import time
from typing import Any, Dict, Callable, List, Optional

import cv2

from .context import get_context
from .targeting import TargetingFilter
from .stuck_detector import StuckDetector
from .trap_detector import TrapDetector
from .reconnect_detector import ReconnectDetector
from .server_save import get_server_save_state
from .core.tasks import TasksOrchestrator
from .cavebot import handle_cavebot
from ..core.constants import (
    TICK_RATE_DEFAULT, TICK_RATE_COMBAT, TICK_RATE_IDLE, TICK_RATE_PAUSED,
    FREQ_SCREENSHOT, FREQ_STATUSBAR, FREQ_BATTLELIST, FREQ_GAMEWINDOW,
    FREQ_RADAR, FREQ_SKILLS, FREQ_CHAT, DELAY_FOOD_COOLDOWN, DELAY_DEBUG_INTERVAL,
    UNREACHABLE_TARGET_GRACE_SECONDS, UNREACHABLE_BLACKLIST_DURATION,
    UNREACHABLE_BLACKLIST_RADIUS, COMBAT_NO_KILL_TIMEOUT,
    SAFE_MODE_RECOVERY_INTERVAL, SAFE_MODE_RECOVERY_TIMEOUT,
    CHASE_WITH_CLIENT, CHASE_MODE_HOTKEY, CHASE_CHECK_INTERVAL, CHASE_PRESS_COOLDOWN,
)
from ..repositories.combat_mode import count_chase_button_green, is_chase_mode_on
from ..repositories.radar.locators import get_radar_tools_position
from .bot_health import BotHealth
from ..utils.session_logger import SessionLogger
from ..utils.alerts import get_alert_system
from ..utils.jitter import jitter
from ..telemetry import TelemetryClient
from ..license import LicenseValidator

Context = Dict[str, Any]


class GameLoop:
    """
    Main game loop - PyTibia style.

    Runs continuously, processing:
    1. Middlewares (data extraction)
    2. Gameplay tasks (combat, navigation)
    3. Task orchestrator (action execution)
    4. Healing observers (reactive healing)

    CPU OPTIMIZED:
    - Tick rate 100ms (game server is 100ms anyway)
    - Middleware frequency control (not all need to run every tick)
    - Single screenshot per tick (shared across all middlewares)
    """

    def __init__(
        self,
        tick_rate: float = TICK_RATE_DEFAULT,
        license_validator: Optional[LicenseValidator] = None,
        character_id: Optional[str] = None,
    ):
        """
        Initialize game loop.

        Args:
            tick_rate: Time between ticks in seconds (default 100ms - matches game server)
            license_validator: License validator instance (optional)
            character_id: Character UUID from dashboard (optional)

        CPU OPTIMIZATION: Changed from 45ms to 100ms.
        The game server processes actions every 100ms anyway, so faster polling
        just wastes CPU without gaining any responsiveness.
        """
        self.tick_rate = tick_rate
        self.running = False
        self.paused = True

        # Context
        self.context = get_context()

        # Task orchestrator
        self.orchestrator = TasksOrchestrator()
        self.context['tasksOrchestrator'] = self.orchestrator

        # Middleware pipeline with frequency control
        self.middlewares: List[Callable[[Dict], Dict]] = []
        self._middleware_frequencies: Dict[Callable, int] = {}
        self._middleware_names: Dict[Callable, str] = {}

        # Healing observers
        self.healing_observers: List[Callable[[Dict], Dict]] = []

        # Stats
        self.tick_count = 0
        self.start_time = 0

        # Cached repositories (created once, reused)
        self._battlelist_repo = None
        self._gamewindow_repo = None
        self._statusbar_repo = None
        self._screen = None

        # Chat repository (loot detection)
        self._chat_repo = None

        # Previous coordinate for faster radar detection
        self._previous_coordinate = None

        # Direction tracking (PyTibia style)
        self._coming_from_direction = None
        self._walked_pixels_in_sqm = 0

        # Previous monsters for loot detection
        self._previous_monsters = []

        # Floor change detection for gamewindow
        self._last_gamewindow_floor = None

        # Game window change detection (skip expensive pathfinding when nothing changed)
        self._prev_gw_hash = None
        self._gw_change_detection_active = False

        # Food timer
        self._last_food_time = 0
        self._last_chase_check = 0
        self._last_chase_press = 0

        # Session logger for detailed tracking
        self.session_logger: Optional[SessionLogger] = None

        # Debug pathfinding (prints walkable matrix when attacking)
        self.debug_pathfinding = False
        self._last_debug_time = 0

        # Targeting filter, stuck detector, and reconnect detector
        self._targeting_filter = TargetingFilter()
        self._stuck_detector = StuckDetector()
        self._trap_detector = TrapDetector()
        self._reconnect_detector = ReconnectDetector()

        # Bot health tracker (safe mode)
        self._bot_health = BotHealth()
        self._in_safe_mode = False

        # Spell attack cooldowns (simple dict, separate from healing)
        self._spell_attack_cooldowns = {}

        # Unreachable target tracking
        self._unreachable_target_start = 0.0
        self._unreachable_target_name = None
        self._unreachable_blacklist = []  # [(name, x, y, z, expiry_time)]

        # Combat without kill timeout
        self._combat_no_kill_time = 0.0

        # Player detection throttle
        self._last_player_warning_time = 0.0

        # Server save
        self._server_save_time = None
        self._server_save_enabled = False
        self._last_server_save_state = 'normal'

        # License
        self.license = license_validator
        self.context['license'] = self.license

        # Character ID (from GUI or env)
        import os
        self.character_id = character_id or os.getenv("CHARACTER_ID")
        self.context['character_id'] = self.character_id

        # Telemetry client
        self.telemetry = TelemetryClient(
            api_url=os.getenv("TELEMETRY_API_URL"),
            api_key=self.license.api_key if self.license else os.getenv("TELEMETRY_API_KEY"),
            flush_interval=5.0,
        )
        self.context['telemetry'] = self.telemetry

        # Wire telemetry to reconnect detector
        self._reconnect_detector.set_telemetry(self.telemetry)

        # Timers for telemetry
        self._last_xp_snapshot = 0
        self._xp_snapshot_interval = 60.0  # 1 minute
        self._last_license_check = 0
        self._license_check_interval = 3600.0  # 1 hour
        self._previous_hp = 100  # For death detection
        self._initial_stats_sent = False

    def enable_session_logging(self, log_dir: str = "logs") -> None:
        """Enable detailed session logging for overnight runs."""
        self.session_logger = SessionLogger(log_dir)
        self._stuck_detector.set_session_logger(self.session_logger)
        self._reconnect_detector.set_session_logger(self.session_logger)
        print(f"Session logging enabled. Logs will be saved to: {log_dir}/")

    def configure_reconnect(self, reconnect_config: dict) -> None:
        """Configure auto-reconnect from GUI settings."""
        self._reconnect_detector.configure(reconnect_config)

    def configure_server_save(self, server_save_config: dict) -> None:
        """Configure server save handling from GUI settings."""
        self._server_save_enabled = server_save_config.get('enabled', True)
        self._server_save_time = server_save_config.get('time', '10:00')

    @property
    def reconnect_state(self) -> str:
        """Current reconnect state."""
        return self._reconnect_detector.state.value

    @property
    def is_reconnecting(self) -> bool:
        """Whether the bot is currently reconnecting."""
        return self._reconnect_detector.is_reconnecting

    def add_middleware(self, middleware: Callable[[Dict], Dict], frequency: int = 1) -> None:
        """
        Add a middleware to the pipeline.

        Args:
            middleware: The middleware function
            frequency: Run every N ticks (1 = every tick, 2 = every other tick, etc.)

        CPU OPTIMIZATION: Middlewares can now specify how often they need to run.
        This dramatically reduces CPU usage for expensive operations that don't
        need to run every tick.
        """
        self.middlewares.append(middleware)
        self._middleware_frequencies[middleware] = frequency

    def add_healing_observer(self, observer: Callable[[Dict], Dict]) -> None:
        """Add a healing observer."""
        self.healing_observers.append(observer)

    def setup_default_middlewares(self) -> None:
        """
        Setup default middlewares for data extraction.

        CPU OPTIMIZATION: Each middleware has a frequency that determines
        how often it runs. This dramatically reduces CPU usage.

        Frequencies:
        - Screenshot: Every tick (needed by others)
        - Status bar: Every tick (critical for healing)
        - Battle list: Every 2 ticks (creature changes are not instant)
        - Game window: Every 2 ticks (pathfinding is expensive)
        - Radar: Every 3 ticks (coordinate doesn't change fast)
        - Skills: Every 10 ticks (food changes very slowly)
        """
        # Screenshot middleware - MUST run every tick
        self.add_middleware(self._screenshot_middleware, frequency=FREQ_SCREENSHOT)

        # Status bar middleware - critical for healing (every tick)
        self.add_middleware(self._statusbar_middleware, frequency=FREQ_STATUSBAR)

        # Battle list middleware - creature detection
        self.add_middleware(self._battlelist_middleware, frequency=FREQ_BATTLELIST)

        # Radar middleware (coordinate detection) - MUST run before gamewindow
        # so gamewindow uses the correct floor's walkable matrix after floor changes
        self.add_middleware(self._radar_middleware, frequency=FREQ_RADAR)

        # Game window middleware (HP bars, pathfinding)
        self.add_middleware(self._gamewindow_middleware, frequency=FREQ_GAMEWINDOW)

        # Skills middleware (food detection) - very slow changing
        self.add_middleware(self._skills_middleware, frequency=FREQ_SKILLS)

        # Chat middleware (loot detection from chat channel)
        self.add_middleware(self._chat_middleware, frequency=FREQ_CHAT)

        # Map middleware functions to names for BotHealth reporting
        self._middleware_names = {
            self._screenshot_middleware: 'screenshot',
            self._statusbar_middleware: 'statusbar',
            self._battlelist_middleware: 'battlelist',
            self._radar_middleware: 'radar',
            self._gamewindow_middleware: 'gamewindow',
            self._skills_middleware: 'skills',
            self._chat_middleware: 'chat',
        }

    def _screenshot_middleware(self, context: Dict) -> Dict:
        """Capture screenshot."""
        if self._screen is None:
            from ..core import get_screen_capture
            self._screen = get_screen_capture()

        if self.tick_count % 30 == 0:
            self._screen.refresh_capture_region()
            from ..utils.input import refresh_screen_offset
            refresh_screen_offset()

        screenshot_bgr = self._screen.capture(grayscale=False)
        if screenshot_bgr is None:
            self._bot_health.report_failure('screenshot', RuntimeError("Screenshot returned None"))
            return context

        # Reuse the ScreenCapture gray buffer to avoid allocating ~3 MB per tick
        self._screen._ensure_buffers(*screenshot_bgr.shape[:2])
        cv2.cvtColor(screenshot_bgr, cv2.COLOR_BGR2GRAY, dst=self._screen._buf_gray)

        self._bot_health.report_success('screenshot')
        context['screenshot'] = self._screen._buf_gray
        context['screenshotBgr'] = screenshot_bgr
        return context

    def _radar_middleware(self, context: Dict) -> Dict:
        """Detect current coordinate from radar/minimap."""
        from ..repositories.radar import get_coordinate

        screenshot = context.get('screenshot')
        if screenshot is None:
            return context

        coord = get_coordinate(screenshot, self._previous_coordinate)

        if coord is not None:
            context['radar']['coordinate'] = coord
            context['radar']['previousCoordinate'] = self._previous_coordinate

            # Track direction for creature detection
            if self._previous_coordinate is not None:
                dx = coord[0] - self._previous_coordinate[0]
                dy = coord[1] - self._previous_coordinate[1]
                self._coming_from_direction = self._direction_from_delta(dx, dy)

            self._previous_coordinate = coord

            # Debug: print coordinate every 50 ticks
            if self.tick_count % 50 == 0:
                print(f"[Radar] Coordinate: {coord}")

        self._bot_health.report_success('radar')
        return context

    def _battlelist_middleware(self, context: Dict) -> Dict:
        """
        Extract battle list data.

        CPU OPTIMIZATION:
        - Removed separate is_attacking() call
        - Passes whitelist to limit template matching (HUGE CPU savings!)
        """
        if self._battlelist_repo is None:
            from ..repositories.battlelist import BattleListRepository
            self._battlelist_repo = BattleListRepository()

        # CPU OPTIMIZATION: Get target names from whitelist (if using whitelist mode)
        # This limits template matching to only the creatures we care about!
        target_names = self._get_target_names_for_detection(context)

        creatures = self._battlelist_repo.get_creatures(
            context.get('screenshot'),
            target_names=target_names,
            color_img=context.get('screenshotBgr')
        )

        context['battleList']['creatures'] = creatures

        # Attack state from BL R-channel detection (works on capture card + native)
        attacked_creature = None
        for c in creatures:
            if c.is_being_attacked:
                attacked_creature = c
                break

        if attacked_creature is not None:
            context['cavebot']['isAttackingSomeCreature'] = True
            context['cavebot']['targetCreature'] = attacked_creature
        else:
            context['cavebot']['isAttackingSomeCreature'] = False
            context['cavebot']['targetCreature'] = None

        # Also set in gameWindow for compatibility
        context['gameWindow']['creatures'] = creatures
        context['gameWindow']['monstersBars'] = creatures

        self._bot_health.report_success('battlelist')
        return context

    def _get_target_names_for_detection(self, context: Dict) -> Optional[List[str]]:
        """Get list of creature names to detect based on targeting settings."""
        return self._targeting_filter.get_target_names(context)

    def _gamewindow_middleware(self, context: Dict) -> Dict:
        """Extract game window data (creatures with slot positions for pathfinding)."""
        if self._gamewindow_repo is None:
            from ..repositories.gamewindow import get_gamewindow_repository
            self._gamewindow_repo = get_gamewindow_repository()

        screenshot = context.get('screenshot')
        coordinate = context.get('radar', {}).get('coordinate')

        # Track whether change detection is active (only in combat-boosted ticks)
        in_combat = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        self._gw_change_detection_active = in_combat

        # Change detection: skip expensive pathfinding when game window hasn't changed.
        # Only active during combat mode (when frequency is boosted to every tick).
        if self._gw_change_detection_active and screenshot is not None:
            gw_pos = self._gamewindow_repo.get_game_window_position(screenshot)
            if gw_pos is not None:
                x, y, w, h = gw_pos
                gw_region = screenshot[y:y + h, x:x + w]
                small = cv2.resize(gw_region, (32, 32), interpolation=cv2.INTER_AREA)
                current_hash = small.tobytes()
                if current_hash == self._prev_gw_hash:
                    self._bot_health.report_success('gamewindow')
                    return context
                self._prev_gw_hash = current_hash

        # Get battle list creature names (for matching)
        # IMPORTANT: Only pass MONSTER names to gamewindow, not players!
        # The battlelist marks unknown creatures as PLAYER, so we filter them out here.
        # This prevents the gamewindow from treating players as monsters.
        from ..core import CreatureType
        battle_creatures = context.get('battleList', {}).get('creatures', [])
        creature_names = []
        skipped_players = []
        for c in battle_creatures:
            if hasattr(c, 'name') and hasattr(c, 'creature_type'):
                # Only include monsters, skip players/NPCs
                if c.creature_type == CreatureType.MONSTER:
                    creature_names.append(c.name)
                else:
                    skipped_players.append(c.name)
            elif hasattr(c, 'name'):
                # Fallback: include if we can't check type (shouldn't happen)
                creature_names.append(c.name)

        # Log skipped players from battlelist
        if skipped_players and self.tick_count % 50 == 0:
            print(f"[Battlelist] Filtered out {len(skipped_players)} players/unknown: {skipped_players}")

        # Floor change detection: skip creature detection for 1 tick after floor change
        # to let the walkable matrix update to the new floor
        if coordinate:
            current_floor = coordinate[2]
            if self._last_gamewindow_floor is not None and current_floor != self._last_gamewindow_floor:
                self._last_gamewindow_floor = current_floor
                context['cavebot']['closestCreature'] = None
                self._prev_gw_hash = None  # Invalidate hash on floor change
                self._bot_health.report_success('gamewindow')
                return context
            self._last_gamewindow_floor = current_floor

        # Full creature detection with slots (needed for pathfinding)
        if coordinate and screenshot is not None and len(battle_creatures) > 0:
            creatures = self._gamewindow_repo.get_creatures(
                creature_names, coordinate, screenshot,
                direction=self._coming_from_direction,
                walked_pixels=self._walked_pixels_in_sqm,
                screenshot_bgr=context.get('screenshotBgr'))

            # Cross-reference BL attack info to mark correct GW creature.
            # GW grayscale detection (76/166) fails on capture card;
            # BL R-channel detection is reliable, so we use BL as authority.
            bl_target = context.get('cavebot', {}).get('targetCreature')
            attacked_name = bl_target.name if bl_target is not None else None
            self._gamewindow_repo.mark_attacked(
                creatures, attacked_name, context.get('screenshotBgr'))

            context['gameWindow']['creatures'] = creatures
            context['gameWindow']['previousMonsters'] = self._previous_monsters

            # OCR learning: teach atlas from BL-identified creatures
            if creatures and creature_names:
                game_window_image = self._gamewindow_repo.capture(screenshot)
                if game_window_image is not None:
                    self._gamewindow_repo.learn_from_creatures(
                        game_window_image, creatures, creature_names
                    )

            # Separate monsters from players (for targeting)
            monsters = self._gamewindow_repo.get_monsters(creatures)
            players = self._gamewindow_repo.get_players(creatures)
            context['gameWindow']['monsters'] = monsters
            context['gameWindow']['players'] = players  # Save players for pass-through detection
            context['cavebot']['hasPlayers'] = len(players) > 0

            # Log and track when players are detected
            if players and self.tick_count % 50 == 0:
                player_names = [p.name for p in players]
                print(f"[Cavebot] Ignoring {len(players)} players: {player_names} (only attacking monsters)")

            if players and (time.time() - self._last_player_warning_time > 30):
                player_names = [p.name for p in players]
                coord = context.get('radar', {}).get('coordinate')
                self.telemetry.track_warning(
                    f"Player detected: {', '.join(player_names)}",
                    level="warning",
                    position=(coord[0], coord[1], coord[2]) if coord else None,
                )
                self._last_player_warning_time = time.time()

            # Apply targeting filter (whitelist/blacklist)
            filtered_monsters = self._filter_monsters_by_targeting(monsters, context)

            # Filter out temporarily blacklisted creatures (unreachable)
            filtered_monsters = self._filter_unreachable_blacklist(filtered_monsters)

            # Log creature identification methods (every 50 ticks)
            if self.tick_count % 50 == 0 and monsters:
                method_counts = {}
                for m in monsters:
                    method = m.id_method or 'none'
                    method_counts[method] = method_counts.get(method, 0) + 1
                method_str = ', '.join(f'{m}={c}' for m, c in sorted(method_counts.items()))
                print(f"[GW-OCR] {len(monsters)} monsters identified: {method_str}")

            # Debug targeting (log every 100 ticks)
            if self.tick_count % 100 == 0 and monsters:
                targeting = context.get('targeting', {})
                print(f"[Targeting] Mode: {targeting.get('mode', 'all')}, Enabled: {targeting.get('enabled', True)}, "
                      f"Monsters: {len(monsters)} -> Filtered: {len(filtered_monsters)}")

            # Get closest MONSTER using pathfinding (ignore players!)
            if filtered_monsters:
                closest = self._gamewindow_repo.get_closest_creature(
                    filtered_monsters, coordinate, debug=self.debug_pathfinding)
                context['cavebot']['closestCreature'] = closest

                if closest and self.tick_count % 50 == 0:
                    method_label = {'BL': 'Battlelist', 'OCR': 'OCR', 'TM': 'Template'}.get(closest.id_method, 'Fallback')
                    print(f"[GW-OCR] Target: {closest.name} via {method_label} (id_method={closest.id_method})")

                # Debug: print walkable matrix periodically when debugging
                if self.debug_pathfinding and time.time() - self._last_debug_time > DELAY_DEBUG_INTERVAL:
                    self._last_debug_time = time.time()
                    self._gamewindow_repo.debug_walkable_matrix(coordinate, filtered_monsters)
            else:
                context['cavebot']['closestCreature'] = None

            # Suppress attacks after stuck recovery to prevent re-engaging unreachable creatures
            if self._stuck_detector.is_attack_suppressed:
                context['cavebot']['closestCreature'] = None

            # Validate current target is still reachable (not behind a wall)
            is_attacking = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
            if is_attacking and filtered_monsters:
                target_gw = self._gamewindow_repo.get_target_creature(filtered_monsters)
                if target_gw is not None:
                    has_target = self._gamewindow_repo.has_target_to_creature(
                        filtered_monsters, target_gw, coordinate)
                    if not has_target:
                        context = self._handle_unreachable_target(context, target_gw)
                    else:
                        self._unreachable_target_start = 0.0
                        self._unreachable_target_name = None
                else:
                    self._unreachable_target_start = 0.0
                    self._unreachable_target_name = None
            else:
                self._unreachable_target_start = 0.0
                self._unreachable_target_name = None

            # Save current monsters for loot detection next tick
            self._previous_monsters = monsters

        else:
            # No battle creatures — clear stale closestCreature to prevent
            # phantom restarts in AttackClosestCreatureTask
            context['cavebot']['closestCreature'] = None

            # Fallback: just HP bars count (only when full detection didn't run)
            img = self._gamewindow_repo.capture(screenshot)
            if img is not None:
                bars = self._gamewindow_repo.get_creatures_bars(img)
                context['gameWindow']['monstersBars'] = bars

        self._bot_health.report_success('gamewindow')
        return context

    def _statusbar_middleware(self, context: Dict) -> Dict:
        """
        Extract HP/Mana status.

        CPU OPTIMIZATION: Uses screenshot from context instead of capturing a new one.
        """
        if self._statusbar_repo is None:
            from ..repositories.statusbar import StatusBarRepository
            self._statusbar_repo = StatusBarRepository()

        # OPTIMIZATION: Reuse screenshot from context (don't capture again!)
        screenshot = context.get('screenshot')

        context['statusBar']['hpPercentage'] = self._statusbar_repo.get_hp_percentage(screenshot)
        context['statusBar']['manaPercentage'] = self._statusbar_repo.get_mp_percentage(screenshot)

        self._bot_health.report_success('statusbar')
        return context

    def _skills_middleware(self, context: Dict) -> Dict:
        """Extract skills from skills window (food, speed, capacity, stamina, experience)."""
        from ..repositories.skills import get_food, get_speed, get_capacity, get_stamina, get_experience

        screenshot = context.get('screenshot')
        if screenshot is None:
            return context

        context['skills'] = context.get('skills', {})

        food = get_food(screenshot)
        if food is not None:
            context['skills']['food'] = food

        speed = get_speed(screenshot)
        # Buffed/debuffed speed is drawn green/red, too dark in grayscale; brightest channel keeps it readable
        screenshot_bgr = context.get('screenshotBgr')
        if not speed and screenshot_bgr is not None:
            speed = get_speed(screenshot_bgr.max(axis=2))
        if speed is not None and speed > 0:
            context['skills']['speed'] = speed
            context['playerSpeed'] = speed

        capacity = get_capacity(screenshot)
        if capacity is not None:
            context['skills']['capacity'] = capacity

        stamina = get_stamina(screenshot)
        if stamina is not None:
            context['skills']['stamina'] = stamina

        experience = get_experience(screenshot)
        if experience is not None and experience > 0:
            context['skills']['experience'] = experience

        self._bot_health.report_success('skills')
        return context

    def _chat_middleware(self, context: Dict) -> Dict:
        """Extract loot messages from chat loot channel and send loot telemetry."""
        if self._chat_repo is None:
            from ..repositories.chat import get_chat_repository
            self._chat_repo = get_chat_repository()

        screenshot = context.get('screenshot')
        if screenshot is None:
            return context

        messages = self._chat_repo.get_new_loot_messages(screenshot)
        context['chat']['lootMessages'] = messages

        if messages:
            from ..wiki.items import get_item_value
            telemetry = context.get('telemetry')

            for msg in messages:
                items_str = ', '.join(
                    f"{i['quantity']}x {i['name']}" for i in msg.get('items', [])
                )
                print(f"[Chat] Loot of {msg['creature']}: {items_str}")

                # Send loot telemetry immediately when detected
                if telemetry:
                    creature = msg.get('creature')
                    for item in msg.get('items', []):
                        value = get_item_value(item['name'])
                        telemetry.track_loot(
                            item_name=item['name'],
                            quantity=item.get('quantity', 1),
                            value=value if value > 0 else None,
                            creature_name=creature,
                        )

        self._bot_health.report_success('chat')
        return context

    @staticmethod
    def _direction_from_delta(dx: int, dy: int) -> Optional[str]:
        if dx == 0 and dy == 0:
            return None
        directions = {
            (0, -1): 'north', (0, 1): 'south',
            (1, 0): 'east', (-1, 0): 'west',
            (1, -1): 'northeast', (-1, -1): 'northwest',
            (1, 1): 'southeast', (-1, 1): 'southwest',
        }
        clamped = (max(-1, min(1, dx)), max(-1, min(1, dy)))
        return directions.get(clamped)

    def _filter_monsters_by_targeting(self, monsters: list, context: Dict) -> list:
        """Filter monsters based on targeting settings."""
        self._targeting_filter.set_tick_count(self.tick_count)
        return self._targeting_filter.filter(monsters, context)

    def _handle_unreachable_target(self, context: Dict, target_creature) -> Dict:
        """Grace period timer + force disengage + blacklist for unreachable targets."""
        import pyautogui

        now = time.time()
        name = target_creature.name

        # Grace period uses name only (creature moves between ticks)
        if self._unreachable_target_start == 0.0:
            self._unreachable_target_start = now
            self._unreachable_target_name = name
            return context

        if self._unreachable_target_name != name:
            self._unreachable_target_start = now
            self._unreachable_target_name = name
            return context

        elapsed = now - self._unreachable_target_start
        if elapsed < UNREACHABLE_TARGET_GRACE_SECONDS:
            return context

        # Grace period exceeded — disengage
        coord = target_creature.coordinate
        msg = f"Target '{name}' unreachable for {elapsed:.1f}s — disengaging at ({coord[0]},{coord[1]},{coord[2]})"
        print(f"[GameWindow] {msg}")
        self.telemetry.track_warning(msg, level="warning", position=(coord[0], coord[1], coord[2]))
        pyautogui.press('escape')

        context['cavebot']['isAttackingSomeCreature'] = False
        context['cavebot']['targetCreature'] = None
        context['cavebot']['closestCreature'] = None
        self.orchestrator.clear()

        # Blacklist creature by name + position (proximity-based matching)
        self._unreachable_blacklist.append(
            (name, coord[0], coord[1], coord[2], now + UNREACHABLE_BLACKLIST_DURATION)
        )
        print(f"[GameWindow] Blacklisted '{name}' near ({coord[0]},{coord[1]},{coord[2]}) for {UNREACHABLE_BLACKLIST_DURATION}s")

        self._unreachable_target_start = 0.0
        self._unreachable_target_name = None

        return context

    def _filter_unreachable_blacklist(self, monsters: list) -> list:
        """Remove blacklisted creatures using proximity match (handles creature movement)."""
        if not self._unreachable_blacklist:
            return monsters

        now = time.time()

        # Expire old entries
        self._unreachable_blacklist = [
            entry for entry in self._unreachable_blacklist if entry[4] > now
        ]

        if not self._unreachable_blacklist:
            return monsters

        result = []
        for m in monsters:
            mx, my, mz = m.coordinate[0], m.coordinate[1], m.coordinate[2]
            is_blacklisted = False
            for name, bx, by, bz, _ in self._unreachable_blacklist:
                if m.name != name:
                    continue
                if mz != bz:
                    continue
                if abs(mx - bx) <= UNREACHABLE_BLACKLIST_RADIUS and abs(my - by) <= UNREACHABLE_BLACKLIST_RADIUS:
                    is_blacklisted = True
                    break
            if not is_blacklisted:
                result.append(m)
        return result

    def _process_blacklist_requests(self) -> None:
        """Process blacklist requests from tasks (unreachable/timeout)."""
        request = self.context.get('cavebot', {}).get('_blacklistCreature')
        if not request:
            return

        name = request.get('name')
        coord = request.get('coordinate')
        if name and coord:
            now = time.time()
            self._unreachable_blacklist.append(
                (name, coord[0], coord[1], coord[2], now + UNREACHABLE_BLACKLIST_DURATION)
            )
            print(f"[GameLoop] Blacklisted '{name}' near ({coord[0]},{coord[1]},{coord[2]}) for {UNREACHABLE_BLACKLIST_DURATION}s")

        self.context['cavebot'].pop('_blacklistCreature', None)

    def _check_combat_timeout(self) -> None:
        """Force target switch if in combat too long without a kill."""
        import pyautogui

        is_attacking = self.context.get('cavebot', {}).get('isAttackingSomeCreature', False)

        if not is_attacking:
            self._combat_no_kill_time = 0.0
            return

        now = time.time()

        if self._combat_no_kill_time == 0.0:
            self._combat_no_kill_time = now
            return

        # Reset timer when a kill happened
        last_kill = self.context.get('cavebot', {}).get('lastKillTime', 0)
        if last_kill > self._combat_no_kill_time:
            self._combat_no_kill_time = now
            return

        elapsed = now - self._combat_no_kill_time
        if elapsed < COMBAT_NO_KILL_TIMEOUT:
            return

        # Blacklist current target to force switch
        target = self.context.get('cavebot', {}).get('targetCreature')
        if not target or not hasattr(target, 'name') or not hasattr(target, 'coordinate'):
            self._combat_no_kill_time = now
            return

        coord = target.coordinate
        self._unreachable_blacklist.append(
            (target.name, coord[0], coord[1], coord[2], now + UNREACHABLE_BLACKLIST_DURATION)
        )

        pyautogui.press('escape')
        self.context['cavebot']['isAttackingSomeCreature'] = False
        self.context['cavebot']['targetCreature'] = None
        self.context['cavebot']['closestCreature'] = None
        self.orchestrator.clear()

        msg = f"Combat timeout: no kill for {elapsed:.0f}s — forcing target switch, blacklisted '{target.name}'"
        print(f"[Combat] {msg}")
        coord_tuple = (coord[0], coord[1], coord[2])
        self.telemetry.track_warning(msg, level="error", position=coord_tuple)
        if self.session_logger:
            self.session_logger.log_error(msg, "combat_timeout")

        self._combat_no_kill_time = 0.0

    def setup_default_healing(self) -> None:
        """Setup default healing observers."""
        self.add_healing_observer(self._healing_observer)

    def _healing_observer(self, context: Dict) -> Dict:
        """Check and execute healing."""
        import pyautogui

        healing = context.get('healing', {})
        if not healing.get('enabled', False):
            return context

        hp_percent = context.get('statusBar', {}).get('hpPercentage', 100)
        mana_percent = context.get('statusBar', {}).get('manaPercentage', 100)

        if self._try_emergency_heal(healing, hp_percent, mana_percent):
            return context

        if self._try_potion(healing, hp_percent, mana_percent):
            return context

        if self._try_spell(healing, hp_percent):
            return context

        return context

    def _try_emergency_heal(self, healing: Dict, hp_percent: float,
                            mana_percent: float) -> bool:
        """Try emergency heal. Returns True if healed.

        When HP is critically low, tries spell first (if mana allows),
        then falls back to HP potion if mana is insufficient.
        """
        import pyautogui

        high_priority = healing.get('highPriority', {})
        if not high_priority.get('enabled', False):
            return False

        hp_threshold = high_priority.get('hpPercentageLessThanOrEqual', 30)

        if hp_percent > hp_threshold:
            return False

        mana_threshold = high_priority.get('manaPercentageGreaterThanOrEqual', 10)

        # Try spell if mana is sufficient
        if mana_percent >= mana_threshold:
            spells = healing.get('spells', [])
            if spells:
                hotkey = spells[0].get('hotkey')
                if hotkey:
                    pyautogui.press(hotkey)
                    self.telemetry.track_event("heal", {
                        "healType": "emergency_spell",
                        "hotkey": hotkey,
                        "hpPercent": hp_percent,
                        "manaPercent": mana_percent,
                    })
                    return True

        # Fallback: try HP potion when mana is too low for spell
        for potion in healing.get('potions', []):
            if not potion.get('enabled', False):
                continue
            if potion.get('type', 'hp') != 'hp':
                continue
            hotkey = potion.get('hotkey')
            if hotkey:
                pyautogui.press(hotkey)
                self.telemetry.track_event("heal", {
                    "healType": "emergency_potion",
                    "hotkey": hotkey,
                    "potionType": "hp",
                    "hpPercent": hp_percent,
                    "manaPercent": mana_percent,
                })
                return True

        return False

    def _try_potion(self, healing: Dict, hp_percent: float,
                    mana_percent: float) -> bool:
        """Try using a potion. Returns True if used."""
        import pyautogui

        potions = healing.get('potions', [])
        for potion in potions:
            if not potion.get('enabled', False):
                continue

            hotkey = potion.get('hotkey')
            if not hotkey:
                continue

            potion_type = potion.get('type', 'hp')
            threshold = potion.get('hpPercentageLessThanOrEqual', 50)

            if potion_type == 'hp' and hp_percent <= threshold:
                pyautogui.press(hotkey)
                self.telemetry.track_event("heal", {
                    "healType": "potion",
                    "hotkey": hotkey,
                    "potionType": "hp",
                    "hpPercent": hp_percent,
                })
                return True

            if potion_type == 'mana' and mana_percent <= threshold:
                pyautogui.press(hotkey)
                self.telemetry.track_event("heal", {
                    "healType": "potion",
                    "hotkey": hotkey,
                    "potionType": "mana",
                    "manaPercent": mana_percent,
                })
                return True

        return False

    def _try_spell(self, healing: Dict, hp_percent: float) -> bool:
        """Try casting a healing spell. Returns True if cast."""
        import pyautogui

        spells = healing.get('spells', [])
        for spell in spells:
            if not spell.get('enabled', False):
                continue

            hotkey = spell.get('hotkey')
            if not hotkey:
                continue

            threshold = spell.get('hpPercentageLessThanOrEqual', 70)
            if hp_percent <= threshold:
                pyautogui.press(hotkey)
                self.telemetry.track_event("heal", {
                    "healType": "spell",
                    "hotkey": hotkey,
                    "hpPercent": hp_percent,
                })
                return True

        return False

    def tick(self) -> None:
        """Process one game loop tick."""
        if self.paused:
            return

        # Safe mode check: if critical middlewares are failing, pause gameplay
        if self._bot_health.should_pause():
            self._enter_safe_mode()
            self.tick_count += 1
            return

        # Check if we're in combat (some middlewares run more frequently in combat)
        in_combat = self.context.get('cavebot', {}).get('isAttackingSomeCreature', False)

        # 1. Run middlewares (with frequency control)
        for middleware in self.middlewares:
            frequency = self._middleware_frequencies.get(middleware, 1)

            # In combat, critical middlewares run every tick
            if in_combat and middleware in (self._battlelist_middleware, self._radar_middleware, self._gamewindow_middleware):
                frequency = 1

            # Check if this middleware should run this tick
            if self.tick_count % frequency != 0:
                continue

            try:
                self.context = middleware(self.context)

                # After screenshot middleware, check reconnect before running others
                if middleware == self._screenshot_middleware:
                    if self._reconnect_detector.check_and_reconnect(self.context, self.tick_count):
                        self.context['reconnect']['state'] = self._reconnect_detector.state.value
                        self.context['reconnect']['retryCount'] = self._reconnect_detector.retry_count
                        self.tick_count += 1
                        return

                # Report middleware success for secondary disconnect detection
                if middleware in (self._radar_middleware, self._statusbar_middleware):
                    self._reconnect_detector.report_middleware_success()

            except Exception as e:
                middleware_name = self._middleware_names.get(middleware, 'unknown')
                self._bot_health.report_failure(middleware_name, e)

                if self.session_logger:
                    self.session_logger.log_error(str(e), f"middleware_{middleware_name}")

                # Report middleware failure for secondary disconnect detection
                if middleware in (self._radar_middleware, self._statusbar_middleware):
                    self._reconnect_detector.report_middleware_failure()

        # Check again after middlewares ran — a critical one may have just failed
        if self._bot_health.should_pause():
            self.tick_count += 1
            return

        # Debug: show status every 50 ticks (only if no session logger)
        if self.tick_count % 50 == 0 and not self.session_logger:
            creatures = self.context.get('battleList', {}).get('creatures', [])
            is_attacking = self.context.get('cavebot', {}).get('isAttackingSomeCreature', False)
            task = self.orchestrator.current_task_name
            hp = self.context.get('statusBar', {}).get('hpPercentage', -1)
            mana = self.context.get('statusBar', {}).get('manaPercentage', -1)
            food = self.context.get('skills', {}).get('food', -1)
            speed = self.context.get('playerSpeed', -1)
            print(f"[Tick {self.tick_count}] HP: {hp}% | Mana: {mana}% | Food: {food}min | Speed: {speed} | Creatures: {len(creatures)} | Attacking: {is_attacking} | Task: {task}")

        # 2. Handle gameplay tasks (cavebot)
        try:
            self.context = handle_cavebot(self.context, self.orchestrator)
        except Exception as e:
            self._bot_health.report_failure('cavebot', e)
            if self.session_logger:
                self.session_logger.log_error(str(e), "cavebot")

        # 2.5 Anti-trap: attack directly when surrounded (no BFS path)
        self._check_trap()

        # Cavebot switched off live ([ hotkey): drop its walk/attack task, healing keeps running
        if not self.context.get('cavebot', {}).get('enabled', False) and not self.orchestrator.is_idle:
            self.orchestrator.clear()

        # 3. Execute task orchestrator
        try:
            self.context = self.orchestrator.do(self.context)
        except Exception as e:
            self._bot_health.report_failure('orchestrator', e)
            self.orchestrator.clear()
            if self.session_logger:
                self.session_logger.log_error(str(e), "orchestrator")

        # 3.1 Process blacklist requests from tasks (unreachable/timeout)
        self._process_blacklist_requests()

        # 3.5 Spell attack (cast offensive spells while in combat)
        try:
            from .spell_attack import handle_spell_attack
            self.context = handle_spell_attack(self.context, self._spell_attack_cooldowns)
        except Exception as e:
            self._bot_health.report_failure('spell_attack', e)

        # 4. Run healing observers
        for observer in self.healing_observers:
            try:
                self.context = observer(self.context)
            except Exception as e:
                self._bot_health.report_failure('healing', e)
                if self.session_logger:
                    self.session_logger.log_error(str(e), "healing")

        # 5. Eat food periodically
        self._eat_food_if_needed()

        # 5.5 Keep the client's Chase Opponent mode on
        self._ensure_chase_mode()

        # 6. Check if character is stuck
        self._check_stuck()

        # 6.5 Force target switch if in combat too long without kill
        self._check_combat_timeout()

        # 7. License check + telemetry updates (every 5 ticks)
        if self.tick_count % 5 == 0:
            self._update_telemetry()

        # 8. Update session logger
        if self.session_logger:
            self.session_logger.update(self.context, self.tick_count)

        # 9. Push debug overlay data (every tick — BFS on 11x15 is <0.1ms)
        self._push_debug_data()

        self.tick_count += 1

    def _push_debug_data(self) -> None:
        """Push context data to debug overlay (thread-safe shared dict)."""
        try:
            from ..gui.overlay.debug_data import update_debug_data, is_debug_overlay_enabled
        except ImportError:
            return

        if not is_debug_overlay_enabled():
            return

        gw_pos = None
        slot_width = 64
        walkable = None
        bfs_distances = None
        creatures_data = []

        if self._gamewindow_repo is not None:
            gw_pos = self._gamewindow_repo._game_window_position
            slot_width = self._gamewindow_repo._slot_width

        coordinate = self.context.get('radar', {}).get('coordinate')

        # Walkable matrix + BFS
        if gw_pos and coordinate and self._gamewindow_repo:
            try:
                local_walkable = self._gamewindow_repo._get_game_window_walkable(coordinate)
                if local_walkable is not None:
                    from ..repositories.gamewindow.creatures import bfs_flood_fill
                    from ..repositories.gamewindow.config import PLAYER_SLOT_X, PLAYER_SLOT_Y

                    walkable = local_walkable.copy()

                    monsters = self.context.get('gameWindow', {}).get('monsters', [])
                    creature_slots = set()
                    for c in monsters:
                        sx, sy = c.slot
                        if 0 <= sx < 15 and 0 <= sy < 11:
                            if not (sx == PLAYER_SLOT_X and sy == PLAYER_SLOT_Y):
                                creature_slots.add((sx, sy))

                    bfs_distances = bfs_flood_fill(
                        local_walkable, PLAYER_SLOT_Y, PLAYER_SLOT_X, creature_slots
                    )
            except Exception:
                pass

        # Creatures
        closest = self.context.get('cavebot', {}).get('closestCreature')
        closest_slot = closest.slot if closest else None
        target_creature = self.context.get('cavebot', {}).get('targetCreature')
        target_name_str = None
        if target_creature and hasattr(target_creature, 'name'):
            target_name_str = target_creature.name

        monsters = self.context.get('gameWindow', {}).get('monsters', [])
        for m in monsters:
            bfs_dist = None
            if bfs_distances:
                sy, sx = m.slot[1], m.slot[0]
                bfs_dist = bfs_distances.get((sy, sx))
                if bfs_dist is None:
                    for dy in (-1, 0, 1):
                        for dx in (-1, 0, 1):
                            d = bfs_distances.get((sy + dy, sx + dx))
                            if d is not None and (bfs_dist is None or d < bfs_dist):
                                bfs_dist = d

            creatures_data.append({
                'name': m.name,
                'slot': m.slot,
                'id_method': m.id_method or '',
                'is_target': m.slot == closest_slot if closest_slot else False,
                'is_attacking': m.is_being_attacked,
                'bfs_distance': bfs_dist,
            })

        update_debug_data({
            'gw_position': gw_pos,
            'slot_width': slot_width,
            'coordinate': coordinate,
            'walkable': walkable,
            'bfs_distances': bfs_distances,
            'creatures': creatures_data,
            'hp_percent': self.context.get('statusBar', {}).get('hpPercentage', -1),
            'mana_percent': self.context.get('statusBar', {}).get('manaPercentage', -1),
            'is_attacking': self.context.get('cavebot', {}).get('isAttackingSomeCreature', False),
            'target_name': target_name_str or 'None',
            'task_name': self.orchestrator.current_task_name or 'idle',
            'tick_count': self.tick_count,
        })

    def _enter_safe_mode(self) -> None:
        """Enter safe mode when critical middlewares are failing.

        Stops gameplay actions, attempts recovery by re-initializing screen
        capture and retrying critical middlewares.
        """
        if not self._in_safe_mode:
            self._in_safe_mode = True
            failing = self._bot_health.get_failing_critical()
            msg = f"SAFE MODE: Critical middleware(s) failing: {failing}"
            print(f"[BotHealth] {msg}")

            self.orchestrator.clear()
            self.telemetry.track_warning(msg, level="error")
            if self.session_logger:
                self.session_logger.log_error(msg, "safe_mode")

        # Attempt recovery: re-init screen capture
        try:
            from ..core import get_screen_capture
            from ..core.screen import ScreenCapture
            ScreenCapture._instance = None
            self._screen = get_screen_capture()
        except Exception as e:
            print(f"[BotHealth] Screen re-init failed: {e}")

        # Try running screenshot + statusbar to see if we recover
        try:
            self.context = self._screenshot_middleware(self.context)
        except Exception:
            return

        try:
            self.context = self._statusbar_middleware(self.context)
        except Exception:
            return

        # If we reach here, critical middlewares recovered
        if not self._bot_health.should_pause():
            self._in_safe_mode = False
            self._bot_health.reset()
            print("[BotHealth] Recovery successful — resuming normal operation")
            self.telemetry.track_event("safe_mode_recovery")
            if self.session_logger:
                self.session_logger.log_error("Safe mode recovery successful", "safe_mode")

    @property
    def bot_health(self) -> BotHealth:
        """Expose bot health for GUI/telemetry status."""
        return self._bot_health

    def start_telemetry_session(self, hunt_location: str = None, route_id: str = None) -> None:
        """Start a telemetry session if character_id is configured."""
        if not self.character_id:
            return
        self.telemetry.start_session(
            character_id=self.character_id,
            hunt_location=hunt_location,
            route_id=route_id,
        )

    def stop_telemetry_session(self) -> None:
        """Stop the telemetry session with final level/experience."""
        if not self.telemetry:
            return

        final_level = None
        final_experience = self.context.get('skills', {}).get('experience')
        if final_experience:
            from ..wiki.experience import level_from_experience
            final_level = level_from_experience(final_experience)

        self.telemetry.end_session(
            final_level=final_level,
            final_experience=final_experience,
        )

    def _update_telemetry(self) -> None:
        """License check + telemetry position/XP updates."""
        now = time.time()

        # Periodic license check (every 1 hour)
        if self.license and (now - self._last_license_check >= self._license_check_interval):
            self._last_license_check = now
            if not self.license.check_periodically():
                print("WARNING: License expired! Please renew your subscription.")

        if not self.telemetry or not self.telemetry.is_enabled:
            return

        # Update position for live tracking (~0.1us)
        coord = self.context.get('radar', {}).get('coordinate')
        if coord:
            self.telemetry.update_position(coord[0], coord[1], coord[2])

        # Calculate experience and level for status + snapshots
        experience = self.context.get('skills', {}).get('experience')
        level = None
        if experience:
            from ..wiki.experience import level_from_experience
            level = level_from_experience(experience)

        # Update status (HP, mana, bot state) for live dashboard
        hp = self.context.get('statusBar', {}).get('hpPercentage', 100)
        mana = self.context.get('statusBar', {}).get('manaPercentage', 100)
        is_attacking = self.context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        target = self.context.get('cavebot', {}).get('targetCreature')
        bot_state = "combat" if is_attacking else ("paused" if self.paused else "hunting")
        target_name = target.name if target and hasattr(target, 'name') else None
        task_name = self.orchestrator.current_task_name

        skills = self.context.get('skills', {})
        speed = skills.get('speed')
        stamina = skills.get('stamina')
        capacity = skills.get('capacity')

        self.telemetry.update_status(
            hp_percent=hp,
            mana_percent=mana,
            bot_state=bot_state,
            target_creature=target_name,
            current_task=task_name,
            experience=experience,
            level=level,
            is_stuck=self._stuck_detector.is_stuck,
            speed=speed,
            stamina=stamina,
            capacity=capacity,
        )

        # Initial stats: send experience snapshot immediately on first detection
        if experience and level and not self._initial_stats_sent:
            self.telemetry.track_experience(experience, level)
            self._last_xp_snapshot = now
            self._initial_stats_sent = True

        # Experience snapshot (every 60s)
        if experience and level and (now - self._last_xp_snapshot >= self._xp_snapshot_interval):
            self._last_xp_snapshot = now
            self.telemetry.track_experience(experience, level)

        # Death detection (HP drops to 0 from a positive value)
        if self._previous_hp > 0 and hp == 0:
            position = (coord[0], coord[1], coord[2]) if coord else None
            self.telemetry.track_death(position=position)
            print("[Telemetry] Death detected!")
        self._previous_hp = hp

    def _eat_food_if_needed(self) -> None:
        """Eat food when food level is low (like PyTibia)."""
        import pyautogui

        eat_food_config = self.context.get('healing', {}).get('eatFood', {})
        if not eat_food_config.get('enabled', False):
            return

        hotkey = eat_food_config.get('hotkey')
        threshold = eat_food_config.get('eatWhenFoodIsLessOrEqual', 5)  # Eat when food <= 5 minutes

        if not hotkey:
            return

        # Get current food level
        food = self.context.get('skills', {}).get('food')
        if food is None:
            return  # Skills window not detected

        # Eat if food is low
        if food <= threshold:
            # Cooldown to avoid spamming
            now = time.time()
            if now - self._last_food_time >= jitter(DELAY_FOOD_COOLDOWN):
                pyautogui.press(hotkey)
                self._last_food_time = now
                print(f"[Food] Eating food! Food was: {food} min (hotkey: {hotkey})")

    def _ensure_chase_mode(self) -> None:
        """Press the chase hotkey when the chase button isn't green (like the Real-tibia-heal bot)."""
        cavebot = self.context.get('cavebot', {})
        if not cavebot.get('chaseWithClient', CHASE_WITH_CLIENT) or not cavebot.get('enabled', False):
            return
        now = time.time()
        if now - self._last_chase_check < CHASE_CHECK_INTERVAL:
            return
        self._last_chase_check = now

        screenshot = self.context.get('screenshot')
        screenshot_bgr = self.context.get('screenshotBgr')
        if screenshot is None or screenshot_bgr is None:
            return
        tools = get_radar_tools_position(screenshot)
        if tools is None:
            return
        green = count_chase_button_green(screenshot_bgr, tools)
        if green is None or is_chase_mode_on(green):
            return
        if now - self._last_chase_press < CHASE_PRESS_COOLDOWN:
            return

        import pyautogui
        hotkey = cavebot.get('chaseHotkey', CHASE_MODE_HOTKEY)
        pyautogui.press(hotkey)
        self._last_chase_press = now
        print(f"[Chase] Chase mode OFF ({green} green px) - pressing {hotkey.upper()}")

    def _check_trap(self) -> None:
        """Engage anti-trap attack when surrounded by creatures with no BFS path."""
        if not self.context.get('cavebot', {}).get('enabled', False):
            return
        if not self.orchestrator.is_idle:
            return
        if self.context.get('cavebot', {}).get('isAttackingSomeCreature', False):
            return
        if self._stuck_detector.is_attack_suppressed:
            return
        if not self._trap_detector.should_engage(self.context):
            return

        from .core.tasks.trap import AttackTrappedCreatureTask
        self.orchestrator.set_root_task(AttackTrappedCreatureTask())
        self._trap_detector.reset()
        print("[AntiTrap] Trapped! Engaging closest creature directly")

    def _check_stuck(self) -> None:
        """Check if character is stuck and attempt recovery."""
        # Server save suppression
        if self._server_save_enabled and self._server_save_time:
            ss_state = get_server_save_state(self._server_save_time)

            # Log state transitions
            if ss_state != self._last_server_save_state:
                if ss_state == 'approaching':
                    print(f"[ServerSave] Server save approaching ({self._server_save_time})")
                elif ss_state == 'active':
                    print("[ServerSave] Server save active — suppressing stuck/reconnect alerts")
                elif ss_state == 'recovering':
                    print("[ServerSave] Server save recovering — waiting for servers")
                elif ss_state == 'normal' and self._last_server_save_state != 'normal':
                    print("[ServerSave] Server save window ended — resuming normal operation")
                self._last_server_save_state = ss_state

            if ss_state in ('active', 'recovering'):
                self._stuck_detector.suppress(60)
                self._reconnect_detector.set_server_save_mode(True)
                return

            self._reconnect_detector.set_server_save_mode(False)

        if self._stuck_detector.is_suppressed:
            return

        self._stuck_detector.check_and_recover(self.context, self.orchestrator)

    def run(self) -> None:
        """Main loop - runs until stopped."""
        self.running = True
        self.start_time = time.time()
        self.tick_count = 0

        # Start telemetry session
        self.start_telemetry_session()

        print("Game loop started (CPU OPTIMIZED)")
        print(f"Tick rate: {self.tick_rate * 1000:.0f}ms ({1/self.tick_rate:.0f} TPS target)")
        print(f"Middleware frequencies: screenshot={FREQ_SCREENSHOT}, statusbar={FREQ_STATUSBAR}, "
              f"battlelist={FREQ_BATTLELIST}, gamewindow={FREQ_GAMEWINDOW}, "
              f"radar={FREQ_RADAR}, skills={FREQ_SKILLS}")

        try:
            while self.running:
                tick_start = time.time()

                self.tick()

                # Adaptive tick rate based on game state
                current_tick_rate = self._get_adaptive_tick_rate()

                # Sleep to maintain tick rate (subtle jitter for anti-detection)
                from ..core.constants import JITTER_SIGMA_TICK
                elapsed = time.time() - tick_start
                sleep_time = current_tick_rate - elapsed
                if sleep_time > 0:
                    time.sleep(jitter(sleep_time, JITTER_SIGMA_TICK))

        except KeyboardInterrupt:
            pass
        finally:
            self.running = False
            # Stop telemetry session
            self.stop_telemetry_session()
            self._print_stats()
            # Finalize session logger
            if self.session_logger:
                self.session_logger.finalize()

    def _get_adaptive_tick_rate(self) -> float:
        """Get adaptive tick rate based on game state."""
        if self.paused:
            return TICK_RATE_PAUSED

        in_combat = self.context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        has_creatures = len(self.context.get('battleList', {}).get('creatures', [])) > 0

        if in_combat or has_creatures:
            return TICK_RATE_COMBAT

        if not self.orchestrator.is_idle:
            return TICK_RATE_DEFAULT

        return TICK_RATE_IDLE

    def pause(self) -> None:
        """Pause the game loop."""
        self.paused = True
        self.telemetry.track_event("pause")
        self.telemetry.update_session_status("paused")
        self.telemetry.update_status(
            hp_percent=self.context.get('statusBar', {}).get('hpPercentage', 100),
            mana_percent=self.context.get('statusBar', {}).get('manaPercentage', 100),
            bot_state="paused",
        )
        print("Game loop paused")

    def resume(self) -> None:
        """Resume the game loop."""
        self.paused = False
        self.telemetry.track_event("resume")
        self.telemetry.update_session_status("active")
        self.telemetry.update_status(
            hp_percent=self.context.get('statusBar', {}).get('hpPercentage', 100),
            mana_percent=self.context.get('statusBar', {}).get('manaPercentage', 100),
            bot_state="hunting",
        )
        print("Game loop resumed")

    def stop(self) -> None:
        """Stop the game loop."""
        self.running = False
        self.stop_telemetry_session()
        alert_system = get_alert_system()
        print(f"[DEBUG] Stopping alert, is_looping={alert_system.is_looping()}")
        alert_system.stop_stuck_alert()
        print("Game loop stopping...")

    def _print_stats(self) -> None:
        """Print statistics."""
        runtime = time.time() - self.start_time
        tps = self.tick_count / runtime if runtime > 0 else 0

        print(f"\n{'=' * 40}")
        print("Game Loop Stats")
        print(f"{'=' * 40}")
        print(f"Runtime: {runtime:.1f}s")
        print(f"Ticks: {self.tick_count}")
        print(f"TPS: {tps:.1f}")
        print(f"{'=' * 40}")

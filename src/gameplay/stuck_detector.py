"""Stuck Detector - detects if character is stuck and performs tiered recovery."""
import random
import time
from typing import Any, Dict, Optional, Tuple

import pyautogui

from ..core.constants import (
    STUCK_RECOVERY_TIER_1, STUCK_RECOVERY_TIER_2, STUCK_RECOVERY_TIER_3,
    STUCK_RECOVERY_COOLDOWN, STUCK_ATTACK_SUPPRESSION_DURATION,
    STUCK_ATTACK_SUPPRESSION_CLEAR_DISTANCE, STUCK_FIGHT_GRACE,
)
from ..core.defaults import get_default
from ..utils.alerts import get_alert_system
from ..utils.jitter import jitter


RANDOM_WALK_KEYS = ['w', 'a', 's', 'd']
RANDOM_WALK_STEPS = 3
RANDOM_WALK_DELAY = 0.3


def _skip_current_waypoint(context: Dict) -> bool:
    """Advance to the next waypoint on the same floor."""
    waypoints_data = context.get('cavebot', {}).get('waypoints', {})
    items = waypoints_data.get('items', [])
    if not items:
        return False

    current_coord = context.get('radar', {}).get('coordinate')
    if current_coord is None:
        return False

    current_floor = current_coord[2]
    current_index = waypoints_data.get('currentIndex', 0)

    for offset in range(1, len(items)):
        candidate_index = (current_index + offset) % len(items)
        candidate_coord = items[candidate_index].get('coordinate')
        if candidate_coord is None:
            continue
        if candidate_coord[2] == current_floor:
            context['cavebot']['waypoints']['currentIndex'] = candidate_index
            print(f"[StuckRecovery] Skipped to same-floor waypoint {current_index} -> {candidate_index}")
            return True

    return False


class StuckDetector:
    """Detects if character is stuck and triggers tiered recovery."""

    def __init__(self, session_logger=None):
        self._last_known_position: Optional[Tuple] = None
        self._last_position_change_time: float = 0
        self._session_logger = session_logger

        # Recovery state
        self._recovery_tier: int = 0
        self._last_recovery_time: float = 0

        # Public stuck state (for telemetry)
        self._is_stuck: bool = False

        # Attack suppression after recovery (prevents re-engaging unreachable creatures)
        self._attack_suppressed_until: float = 0
        self._stuck_position: Optional[Tuple] = None

        # Server save suppression
        self._suppressed_until: float = 0

        # When the current attack started (0 = not attacking)
        self._fight_since: float = 0

    @property
    def is_stuck(self) -> bool:
        """Whether the character is currently stuck."""
        return self._is_stuck

    @property
    def is_attack_suppressed(self) -> bool:
        """Whether attacks are suppressed after stuck recovery.

        Prevents the bot from immediately re-engaging unreachable creatures
        after stuck recovery fires. Clears when timer expires or bot moves
        far enough from stuck position.
        """
        if self._attack_suppressed_until == 0:
            return False
        if time.time() >= self._attack_suppressed_until:
            self._attack_suppressed_until = 0
            self._stuck_position = None
            return False
        return True

    def suppress(self, duration: float) -> None:
        """Suppress stuck alerts for duration seconds."""
        self._suppressed_until = time.time() + duration

    @property
    def is_suppressed(self) -> bool:
        """Whether stuck detection is currently suppressed (e.g. during server save)."""
        return time.time() < self._suppressed_until

    def set_session_logger(self, session_logger) -> None:
        """Set session logger for error reporting."""
        self._session_logger = session_logger

    def check(self, context: Dict[str, Any]) -> None:
        """
        Check if character is stuck (legacy — alert only).

        Plays a looping alert sound if stuck for too long.
        Stops the loop when the character moves.
        """
        alert_system = get_alert_system()

        if not self._is_cavebot_enabled(context):
            self._stop_alert_if_active(alert_system)
            return

        if not self._is_stuck_alert_enabled(context):
            self._stop_alert_if_active(alert_system)
            return

        current_pos = context.get('radar', {}).get('coordinate')
        if current_pos is None:
            return

        now = time.time()

        if self._last_known_position is None:
            self._initialize_position(current_pos, now)
            return

        if current_pos != self._last_known_position:
            self._handle_position_changed(current_pos, now, alert_system)
            return

        self._handle_position_unchanged(context, current_pos, now, alert_system)

    def check_and_recover(self, context: Dict[str, Any], orchestrator) -> None:
        """
        Check if character is stuck and perform tiered recovery.

        Stage 1/3 (30s):  Clear current task + Escape + skip waypoint
        Stage 2/3 (60s):  Jump to closest waypoint (force, ignores creatures)
        Stage 3/3 (120s): Random walk keys + sound alert
        """
        alert_system = get_alert_system()

        if not self._is_cavebot_enabled(context):
            self._stop_alert_if_active(alert_system)
            return

        current_pos = context.get('radar', {}).get('coordinate')
        if current_pos is None:
            return

        now = time.time()

        if self._last_known_position is None:
            self._initialize_position(current_pos, now)
            return

        if current_pos != self._last_known_position or self._is_fighting(context, now):
            self._handle_position_changed(current_pos, now, alert_system)
            self._recovery_tier = 0
            self._is_stuck = False
            return

        time_stuck = now - self._last_position_change_time

        if time_stuck >= STUCK_RECOVERY_TIER_1 and not self._is_stuck:
            self._is_stuck = True
            msg = f"STUCK DETECTED! Same position {current_pos} for {time_stuck:.0f}s"
            print(f"[StuckRecovery] {msg}")
            self._track_warning(context, msg, "warning", current_pos)

        if now - self._last_recovery_time < STUCK_RECOVERY_COOLDOWN:
            return

        if time_stuck >= STUCK_RECOVERY_TIER_3 and self._recovery_tier < 3:
            self._execute_tier_3(context, current_pos, time_stuck, alert_system)
            self._last_recovery_time = now
            return

        if time_stuck >= STUCK_RECOVERY_TIER_2 and self._recovery_tier < 2:
            self._execute_tier_2(context, orchestrator, current_pos, time_stuck)
            self._last_recovery_time = now
            return

        if time_stuck >= STUCK_RECOVERY_TIER_1 and self._recovery_tier < 1:
            self._execute_tier_1(context, orchestrator, current_pos, time_stuck)
            self._last_recovery_time = now
            return

    def _is_fighting(self, context: Dict[str, Any], now: float) -> bool:
        """
        Attacking counts as progress: a melee fight stands on one tile for minutes, and treating
        it as stuck pressed escape and skipped waypoints mid-fight. Only while the fight goes
        somewhere - STUCK_FIGHT_GRACE without a kill (an unreachable target) is stuck again.
        """
        cavebot = context.get('cavebot', {})
        if not cavebot.get('isAttackingSomeCreature', False):
            self._fight_since = 0
            return False
        if self._fight_since == 0:
            self._fight_since = now
        last_progress = max(self._fight_since, cavebot.get('lastKillTime', 0))
        return now - last_progress < STUCK_FIGHT_GRACE

    def _execute_tier_1(self, context: Dict, orchestrator, position: Tuple,
                        time_stuck: float) -> None:
        """Stage 1/3: Clear task + Escape + skip current waypoint + suppress attacks."""
        self._recovery_tier = 1
        orchestrator.clear()
        pyautogui.press('escape')
        skipped = _skip_current_waypoint(context)
        self._suppress_attacks(position)

        wp_info = f", skipped waypoint" if skipped else ""
        msg = f"[StuckRecovery] Stage 1/3 ({time_stuck:.0f}s): cleared task + escape{wp_info} at {position}"
        print(msg)
        self._log_recovery(msg)
        self._track_warning(context, msg, "warning", position)

    def _execute_tier_2(self, context: Dict, orchestrator, position: Tuple,
                        time_stuck: float) -> None:
        """Stage 2/3: Clear + Escape + jump to closest waypoint (force) + suppress attacks."""
        self._recovery_tier = 2
        orchestrator.clear()
        pyautogui.press('escape')
        self._suppress_attacks(position)

        from .core.waypoint import jump_to_closest_waypoint
        jumped = jump_to_closest_waypoint(context, force=True)

        action = "jumped to closest waypoint" if jumped else "no waypoint found"
        msg = f"[StuckRecovery] Stage 2/3 ({time_stuck:.0f}s): {action} at {position}"
        print(msg)
        self._log_recovery(msg)
        self._track_warning(context, msg, "error", position)

    def _execute_tier_3(self, context: Dict, position: Tuple, time_stuck: float,
                        alert_system) -> None:
        """Stage 3/3: Random walk + sound alert + suppress attacks.

        Resets tier to 0 so the full recovery cycle repeats if still stuck.
        """
        self._recovery_tier = 0
        self._suppress_attacks(position)

        for _ in range(RANDOM_WALK_STEPS):
            key = random.choice(RANDOM_WALK_KEYS)
            pyautogui.press(key)
            time.sleep(jitter(RANDOM_WALK_DELAY))

        alert_system.stuck_alert(time_stuck)

        msg = f"[StuckRecovery] Stage 3/3 ({time_stuck:.0f}s): random walk + alert at {position} (attacks suppressed {STUCK_ATTACK_SUPPRESSION_DURATION}s)"
        print(msg)
        self._log_recovery(msg)
        self._track_warning(context, msg, "error", position)

    def _suppress_attacks(self, position: Tuple) -> None:
        """Suppress attacks for a period after stuck recovery."""
        self._attack_suppressed_until = time.time() + STUCK_ATTACK_SUPPRESSION_DURATION
        self._stuck_position = position

    def _track_warning(self, context: Dict, message: str, level: str,
                       position: Tuple) -> None:
        """Send warning to telemetry timeline."""
        telemetry = context.get('telemetry')
        if telemetry is None:
            return
        telemetry.track_warning(message, level=level, position=position)

    def _log_recovery(self, message: str) -> None:
        """Log recovery action."""
        if self._session_logger is None:
            return
        self._session_logger.log_error(message, "stuck_recovery")

    # ========== Shared helpers (used by both check and check_and_recover) ==========

    def _is_cavebot_enabled(self, context: Dict) -> bool:
        """Check if cavebot is enabled."""
        return context.get('cavebot', {}).get('enabled', False)

    def _is_stuck_alert_enabled(self, context: Dict) -> bool:
        """Check if stuck alert is enabled."""
        stuck_config = context.get('cavebot', {}).get('stuckAlert', {})
        return stuck_config.get('enabled', True)

    def _get_timeout(self, context: Dict) -> float:
        """Get configured timeout or default (from context; fallback in core.defaults)."""
        stuck_config = context.get('cavebot', {}).get('stuckAlert', {})
        return stuck_config.get('timeoutSeconds', get_default('general.stuckAlertTimeout'))

    def _stop_alert_if_active(self, alert_system) -> None:
        """Stop any active alert."""
        if alert_system.is_looping():
            alert_system.stop_stuck_alert()

    def _initialize_position(self, pos: Tuple, now: float) -> None:
        """Initialize position tracking on first run."""
        self._last_known_position = pos
        self._last_position_change_time = now

    def _handle_position_changed(self, new_pos: Tuple, now: float,
                                  alert_system) -> None:
        """Handle case where position has changed."""
        self._last_known_position = new_pos
        self._last_position_change_time = now

        # Clear attack suppression if moved far enough from stuck position
        if self._stuck_position and self._attack_suppressed_until > 0:
            dx = abs(new_pos[0] - self._stuck_position[0])
            dy = abs(new_pos[1] - self._stuck_position[1])
            if dx + dy >= STUCK_ATTACK_SUPPRESSION_CLEAR_DISTANCE:
                self._attack_suppressed_until = 0
                self._stuck_position = None
                print("[StuckRecovery] Moved away from stuck position — attacks re-enabled")

        if alert_system.is_looping():
            alert_system.stop_stuck_alert()

    def _handle_position_unchanged(self, context: Dict, current_pos: Tuple,
                                    now: float, alert_system) -> None:
        """Handle case where position hasn't changed (legacy alert-only path)."""
        time_stuck = now - self._last_position_change_time
        timeout = self._get_timeout(context)

        if time_stuck < timeout:
            return

        if alert_system.is_looping():
            return

        alert_system.stuck_alert(time_stuck)
        self._log_stuck_error(current_pos, time_stuck)

    def _log_stuck_error(self, position: Tuple, time_stuck: float) -> None:
        """Log stuck error if session logger is available."""
        if self._session_logger is None:
            return

        self._session_logger.log_error(
            f"Character stuck for {time_stuck:.0f}s at {position}",
            "stuck_detection"
        )

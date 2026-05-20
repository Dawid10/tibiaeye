"""
Session Logger - Detailed logging for overnight bot sessions.

Tracks:
- Bot runtime
- Character alive time
- Death events with timestamps and causes
- Position tracking (stuck detection)
- HP/Mana history
- Errors and warnings
"""
import os
import time
import json
from datetime import datetime
from typing import Optional, Dict, Any, List, Tuple
from dataclasses import dataclass, field, asdict


@dataclass
class DeathEvent:
    """Record of a character death."""
    timestamp: str
    runtime_seconds: float
    alive_seconds: float
    last_hp: float
    last_mana: float
    last_position: Optional[Tuple[int, int, int]]
    position_history: List[Tuple[int, int, int]]  # Last 10 positions
    possible_cause: str
    last_task: str
    creatures_nearby: int
    last_error: Optional[str]


@dataclass
class SessionStats:
    """Statistics for the entire session."""
    start_time: str
    end_time: Optional[str] = None
    total_runtime_seconds: float = 0
    total_alive_seconds: float = 0
    deaths: List[DeathEvent] = field(default_factory=list)
    min_hp_reached: float = 100.0
    min_mana_reached: float = 100.0
    total_heals: int = 0
    total_potions_used: int = 0
    stuck_events: int = 0
    errors: List[Dict[str, Any]] = field(default_factory=list)
    waypoints_completed: int = 0
    creatures_killed: int = 0


class SessionLogger:
    """
    Comprehensive session logger for bot monitoring.

    Creates detailed logs to diagnose issues overnight.
    """

    # Death detection thresholds
    DEATH_HP_THRESHOLD = 1.0  # HP below this = death
    STUCK_POSITION_COUNT = 20  # Same position for this many checks = stuck
    STUCK_CHECK_INTERVAL = 50  # Check stuck every N ticks

    def __init__(self, log_dir: str = "logs"):
        """
        Initialize session logger.

        Args:
            log_dir: Directory to store log files
        """
        self.log_dir = log_dir
        os.makedirs(log_dir, exist_ok=True)

        # Session tracking
        self.session_start = time.time()
        self.last_alive_time = time.time()
        self.is_alive = True
        self.respawn_count = 0

        # Position tracking for stuck detection
        self.position_history: List[Tuple[int, int, int]] = []
        self.last_position: Optional[Tuple[int, int, int]] = None
        self.same_position_count = 0

        # HP/Mana tracking
        self.last_hp = 100.0
        self.last_mana = 100.0
        self.hp_history: List[Tuple[float, float]] = []  # (timestamp, hp)

        # Error tracking
        self.last_error: Optional[str] = None
        self.error_count = 0

        # Task tracking
        self.last_task = "idle"
        self.task_history: List[Tuple[float, str]] = []

        # Creature tracking
        self.last_creature_count = 0

        # Session stats
        self.stats = SessionStats(
            start_time=datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        )

        # Log file
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = os.path.join(log_dir, f"session_{timestamp}.log")
        self.json_file = os.path.join(log_dir, f"session_{timestamp}.json")

        self._log("=" * 60)
        self._log("SESSION STARTED")
        self._log(f"Start time: {self.stats.start_time}")
        self._log("=" * 60)

    def _log(self, message: str, level: str = "INFO") -> None:
        """Write to log file with timestamp."""
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        line = f"[{timestamp}] [{level}] {message}"

        # Print to console
        print(line)

        # Write to file
        with open(self.log_file, "a", encoding="utf-8") as f:
            f.write(line + "\n")

    def _analyze_death_cause(self) -> str:
        """Analyze what might have caused the death."""
        causes = []

        # Check if stuck
        if self.same_position_count >= self.STUCK_POSITION_COUNT:
            causes.append(f"STUCK at same position for {self.same_position_count} checks")

        # Check HP history for sudden drop
        if len(self.hp_history) >= 2:
            recent_hp = [hp for _, hp in self.hp_history[-10:]]
            if len(recent_hp) >= 2:
                hp_drop = recent_hp[0] - recent_hp[-1]
                if hp_drop > 50:
                    causes.append(f"Rapid HP drop: {hp_drop:.1f}% in last 10 readings")

        # Check if many creatures nearby
        if self.last_creature_count > 3:
            causes.append(f"Many creatures nearby: {self.last_creature_count}")

        # Check for recent errors
        if self.last_error:
            causes.append(f"Recent error: {self.last_error}")

        # Check task
        if self.last_task == "idle":
            causes.append("Bot was idle (not attacking/moving)")

        if not causes:
            causes.append("Unknown - check HP history for patterns")

        return " | ".join(causes)

    def update(self, context: Dict[str, Any], tick_count: int) -> None:
        """
        Update logger with current game state.

        Call this every tick to track state.
        """
        now = time.time()

        # Extract data from context
        hp = context.get('statusBar', {}).get('hpPercentage', 100)
        mana = context.get('statusBar', {}).get('manaPercentage', 100)
        position = context.get('radar', {}).get('coordinate')
        creatures = context.get('battleList', {}).get('creatures', [])
        task = context.get('tasksOrchestrator')
        if task:
            task_name = getattr(task, 'current_task_name', 'unknown')
        else:
            task_name = context.get('currentTask', 'idle')

        # Update tracking
        self.last_hp = hp
        self.last_mana = mana
        self.last_creature_count = len(creatures)
        self.last_task = task_name

        # Track min HP/Mana
        if hp < self.stats.min_hp_reached:
            self.stats.min_hp_reached = hp
            self._log(f"New minimum HP reached: {hp:.1f}%", "WARNING")

        if mana < self.stats.min_mana_reached:
            self.stats.min_mana_reached = mana

        # HP history (every 10 ticks)
        if tick_count % 10 == 0:
            self.hp_history.append((now, hp))
            # Keep last 100 readings
            if len(self.hp_history) > 100:
                self.hp_history = self.hp_history[-100:]

        # Position tracking
        if position:
            if position != self.last_position:
                self.same_position_count = 0
                self.last_position = position
                self.position_history.append(position)
                # Keep last 20 positions
                if len(self.position_history) > 20:
                    self.position_history = self.position_history[-20:]
            else:
                self.same_position_count += 1

            # Stuck detection
            if tick_count % self.STUCK_CHECK_INTERVAL == 0:
                if self.same_position_count >= self.STUCK_POSITION_COUNT:
                    self.stats.stuck_events += 1
                    self._log(
                        f"STUCK DETECTED! Same position {position} for "
                        f"{self.same_position_count} checks. Task: {task_name}",
                        "WARNING"
                    )

        # Task changes
        if self.task_history and self.task_history[-1][1] != task_name:
            self.task_history.append((now, task_name))
            # Keep last 50 task changes
            if len(self.task_history) > 50:
                self.task_history = self.task_history[-50:]
        elif not self.task_history:
            self.task_history.append((now, task_name))

        # Death detection
        if hp <= self.DEATH_HP_THRESHOLD and self.is_alive:
            self._record_death(context, tick_count)

        # Respawn detection (HP back after death)
        if hp > 50 and not self.is_alive:
            self._record_respawn()

        # Periodic status log (every 500 ticks ~= 22 seconds)
        if tick_count % 500 == 0 and tick_count > 0:
            runtime = now - self.session_start
            alive_time = now - self.last_alive_time if self.is_alive else 0
            speed = context.get('playerSpeed', 0)
            self._log(
                f"STATUS: Runtime={self._format_time(runtime)} | "
                f"Alive={self._format_time(alive_time)} | "
                f"HP={hp:.1f}% | Mana={mana:.1f}% | Speed={speed} | "
                f"Pos={position} | Creatures={len(creatures)} | "
                f"Task={task_name} | Deaths={len(self.stats.deaths)}"
            )

    def _record_death(self, context: Dict[str, Any], tick_count: int) -> None:
        """Record a death event."""
        now = time.time()
        runtime = now - self.session_start
        alive_time = now - self.last_alive_time

        # Analyze cause
        cause = self._analyze_death_cause()

        death = DeathEvent(
            timestamp=datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            runtime_seconds=runtime,
            alive_seconds=alive_time,
            last_hp=self.last_hp,
            last_mana=self.last_mana,
            last_position=self.last_position,
            position_history=self.position_history[-10:],
            possible_cause=cause,
            last_task=self.last_task,
            creatures_nearby=self.last_creature_count,
            last_error=self.last_error
        )

        self.stats.deaths.append(death)
        self.stats.total_alive_seconds += alive_time
        self.is_alive = False

        self._log("=" * 60, "CRITICAL")
        self._log("☠️  CHARACTER DIED!", "CRITICAL")
        self._log(f"Time of death: {death.timestamp}", "CRITICAL")
        self._log(f"Alive for: {self._format_time(alive_time)}", "CRITICAL")
        self._log(f"Total runtime: {self._format_time(runtime)}", "CRITICAL")
        self._log(f"Last HP: {death.last_hp:.1f}%", "CRITICAL")
        self._log(f"Last Mana: {death.last_mana:.1f}%", "CRITICAL")
        self._log(f"Last Position: {death.last_position}", "CRITICAL")
        self._log(f"Creatures nearby: {death.creatures_nearby}", "CRITICAL")
        self._log(f"Last task: {death.last_task}", "CRITICAL")
        self._log(f"POSSIBLE CAUSE: {cause}", "CRITICAL")
        if death.last_error:
            self._log(f"Last error: {death.last_error}", "CRITICAL")
        self._log("=" * 60, "CRITICAL")

        # Save JSON immediately after death
        self._save_json()

    def _record_respawn(self) -> None:
        """Record when character respawns."""
        self.is_alive = True
        self.last_alive_time = time.time()
        self.respawn_count += 1
        self.same_position_count = 0
        self.position_history.clear()

        self._log(f"Character respawned! (Respawn #{self.respawn_count})", "INFO")

    def log_error(self, error: str, context: str = "") -> None:
        """Log an error."""
        self.last_error = error
        self.error_count += 1

        error_entry = {
            "timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "error": error,
            "context": context
        }
        self.stats.errors.append(error_entry)

        self._log(f"ERROR in {context}: {error}", "ERROR")

    def log_heal(self, heal_type: str, hp_before: float) -> None:
        """Log a healing action."""
        self.stats.total_heals += 1
        if "potion" in heal_type.lower():
            self.stats.total_potions_used += 1

    def log_waypoint_reached(self, waypoint_index: int, waypoint_type: str) -> None:
        """Log waypoint completion."""
        self.stats.waypoints_completed += 1
        self._log(f"Waypoint {waypoint_index} ({waypoint_type}) reached")

    def log_creature_killed(self, creature_name: str) -> None:
        """Log creature kill."""
        self.stats.creatures_killed += 1

    def _format_time(self, seconds: float) -> str:
        """Format seconds as human-readable time."""
        hours = int(seconds // 3600)
        minutes = int((seconds % 3600) // 60)
        secs = int(seconds % 60)

        if hours > 0:
            return f"{hours}h {minutes}m {secs}s"
        elif minutes > 0:
            return f"{minutes}m {secs}s"
        else:
            return f"{secs}s"

    def _save_json(self) -> None:
        """Save stats to JSON file."""
        now = time.time()
        self.stats.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stats.total_runtime_seconds = now - self.session_start

        # Compute alive time locally to avoid double-counting
        total_alive = self.stats.total_alive_seconds
        if self.is_alive:
            total_alive += (now - self.last_alive_time)

        # Convert to dict for JSON
        data = asdict(self.stats)
        data['total_alive_seconds'] = total_alive

        with open(self.json_file, "w") as f:
            json.dump(data, f, indent=2)

    def finalize(self) -> None:
        """Finalize the session and write final report."""
        now = time.time()
        runtime = now - self.session_start

        # Update alive time if still alive
        if self.is_alive:
            alive_time = now - self.last_alive_time
            self.stats.total_alive_seconds += alive_time

        self.stats.end_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        self.stats.total_runtime_seconds = runtime

        # Print final report
        self._log("")
        self._log("=" * 60)
        self._log("SESSION ENDED - FINAL REPORT")
        self._log("=" * 60)
        self._log(f"Start time: {self.stats.start_time}")
        self._log(f"End time: {self.stats.end_time}")
        self._log(f"Total runtime: {self._format_time(runtime)}")
        self._log(f"Total alive time: {self._format_time(self.stats.total_alive_seconds)}")

        if runtime > 0:
            alive_percent = (self.stats.total_alive_seconds / runtime) * 100
            self._log(f"Alive percentage: {alive_percent:.1f}%")

        self._log("")
        self._log(f"Deaths: {len(self.stats.deaths)}")

        if self.stats.deaths:
            self._log("")
            self._log("DEATH SUMMARY:")
            for i, death in enumerate(self.stats.deaths, 1):
                self._log(f"  Death #{i}:")
                self._log(f"    Time: {death.timestamp}")
                self._log(f"    Alive for: {self._format_time(death.alive_seconds)}")
                self._log(f"    Cause: {death.possible_cause}")

        self._log("")
        self._log(f"Minimum HP reached: {self.stats.min_hp_reached:.1f}%")
        self._log(f"Minimum Mana reached: {self.stats.min_mana_reached:.1f}%")
        self._log(f"Stuck events: {self.stats.stuck_events}")
        self._log(f"Errors: {len(self.stats.errors)}")
        self._log(f"Waypoints completed: {self.stats.waypoints_completed}")

        self._log("")
        self._log(f"Log file: {self.log_file}")
        self._log(f"JSON file: {self.json_file}")
        self._log("=" * 60)

        # Save JSON
        self._save_json()

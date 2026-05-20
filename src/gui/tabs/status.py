"""
Status Tab - Real-time monitoring of player and bot status.
"""
import customtkinter as ctk
from typing import Dict, Any, List, Optional
import time
import os

try:
    import psutil
    PSUTIL_AVAILABLE = True
except ImportError:
    PSUTIL_AVAILABLE = False

from ..components.stat_bar import StatBar, CompactStatBar
from ..theme import (
    BG_ELEVATED, TEXT_PRIMARY, TEXT_MUTED,
    COLOR_SUCCESS, COLOR_WARNING, COLOR_ERROR,
    resolve,
)
from ..styles import create_section, create_button, create_description, create_stat_label


class StatusTab(ctk.CTkScrollableFrame):
    """Real-time status monitoring tab."""

    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)

        self._setup_ui()
        self.start_time = time.time()
        self.tick_count = 0

        # Initialize process for CPU/memory monitoring
        self._process = psutil.Process(os.getpid()) if PSUTIL_AVAILABLE else None
        self._last_cpu_times = None
        self._last_cpu_check = time.time()

        # Prime cpu_percent (first call always returns 0)
        if PSUTIL_AVAILABLE:
            psutil.cpu_percent(percpu=False)

        # Start system resources update loop
        self._schedule_system_update()

    def _setup_ui(self):
        """Setup the status tab UI."""
        # System Resources Section (CPU/Memory)
        if PSUTIL_AVAILABLE:
            system_section = create_section(self, "System Resources")
            system_section.pack(fill="x", padx=10, pady=(10, 5))

            system_content = ctk.CTkFrame(system_section, fg_color="transparent")
            system_content.pack(fill="x", padx=10, pady=10)

            # CPU and Memory bars side by side
            bars_row = ctk.CTkFrame(system_content, fg_color="transparent")
            bars_row.pack(fill="x")

            # Left column - CPU
            left_col = ctk.CTkFrame(bars_row, fg_color="transparent")
            left_col.pack(side="left", fill="x", expand=True, padx=(0, 10))

            self.cpu_bar = StatBar(left_col, label="CPU", bar_type="cpu", initial_value=0)
            self.cpu_bar.pack(fill="x")

            # Right column - Memory
            right_col = ctk.CTkFrame(bars_row, fg_color="transparent")
            right_col.pack(side="left", fill="x", expand=True)

            self.memory_bar = StatBar(right_col, label="RAM", bar_type="memory", initial_value=0)
            self.memory_bar.pack(fill="x")

            # Detailed stats row
            details_row = ctk.CTkFrame(system_content, fg_color="transparent")
            details_row.pack(fill="x", pady=(8, 0))

            self.cpu_detail_label = ctk.CTkLabel(
                details_row,
                text="CPU: 0.0%",
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED
            )
            self.cpu_detail_label.pack(side="left")

            self.memory_detail_label = ctk.CTkLabel(
                details_row,
                text="Memory: 0 MB",
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED
            )
            self.memory_detail_label.pack(side="left", padx=(20, 0))

            self.threads_label = ctk.CTkLabel(
                details_row,
                text="Threads: 0",
                font=ctk.CTkFont(size=11),
                text_color=TEXT_MUTED
            )
            self.threads_label.pack(side="left", padx=(20, 0))

        # Player Stats Section
        stats_section = create_section(self, "Player Stats")
        stats_section.pack(fill="x", padx=10, pady=(10, 5))

        stats_content = ctk.CTkFrame(stats_section, fg_color="transparent")
        stats_content.pack(fill="x", padx=10, pady=10)

        # HP and MP bars
        self.hp_bar = StatBar(stats_content, label="HP", bar_type="hp", initial_value=100)
        self.hp_bar.pack(fill="x", pady=5)

        self.mp_bar = StatBar(stats_content, label="MP", bar_type="mp", initial_value=100)
        self.mp_bar.pack(fill="x", pady=5)

        # Other stats
        other_stats = ctk.CTkFrame(stats_content, fg_color="transparent")
        other_stats.pack(fill="x", pady=(10, 0))

        # Left column
        left_col = ctk.CTkFrame(other_stats, fg_color="transparent")
        left_col.pack(side="left", fill="x", expand=True)

        self.capacity_label = self._create_stat_row(left_col, "Capacity:", "0 oz")
        self.speed_label = self._create_stat_row(left_col, "Speed:", "0")

        # Right column
        right_col = ctk.CTkFrame(other_stats, fg_color="transparent")
        right_col.pack(side="left", fill="x", expand=True)

        self.food_label = self._create_stat_row(right_col, "Food:", "0 min")
        self.stamina_label = self._create_stat_row(right_col, "Stamina:", "00:00")

        # Position Section
        position_section = create_section(self, "Position")
        position_section.pack(fill="x", padx=10, pady=5)

        position_content = ctk.CTkFrame(position_section, fg_color="transparent")
        position_content.pack(fill="x", padx=10, pady=10)

        # Coordinates row with copy button
        coord_row = ctk.CTkFrame(position_content, fg_color="transparent")
        coord_row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            coord_row,
            text="Coordinates:",
            font=ctk.CTkFont(size=12),
            width=120,
            anchor="w"
        ).pack(side="left")

        self.coord_label = ctk.CTkLabel(
            coord_row,
            text="(0, 0, 0)",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        self.coord_label.pack(side="left")

        self.copy_coord_btn = create_button(
            coord_row,
            text="Copy",
            command=self._copy_coordinates,
            width=60,
        )
        self.copy_coord_btn.configure(height=24, font=ctk.CTkFont(size=11))
        self.copy_coord_btn.pack(side="left", padx=(10, 0))

        self._current_coordinate = None
        self._last_update_time = time.time()
        self.floor_label = self._create_stat_row(position_content, "Floor:", "Unknown")
        self.update_label = self._create_stat_row(position_content, "Last Update:", "---")

        # Battle Info Section
        battle_section = create_section(self, "Battle Info")
        battle_section.pack(fill="x", padx=10, pady=5)

        battle_content = ctk.CTkFrame(battle_section, fg_color="transparent")
        battle_content.pack(fill="x", padx=10, pady=10)

        self.creatures_label = self._create_stat_row(battle_content, "Creatures in range:", "0")
        self.attacking_label = self._create_stat_row(battle_content, "Currently attacking:", "None")

        # Battle list
        ctk.CTkLabel(
            battle_content,
            text="Battle List:",
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        ).pack(anchor="w", pady=(10, 5))

        self.battle_list_frame = ctk.CTkFrame(battle_content, fg_color=BG_ELEVATED, corner_radius=6)
        self.battle_list_frame.pack(fill="x")

        self.battle_list_label = ctk.CTkLabel(
            self.battle_list_frame,
            text="No creatures",
            font=ctk.CTkFont(size=11),
            text_color=TEXT_MUTED,
            anchor="w",
            justify="left"
        )
        self.battle_list_label.pack(anchor="w", padx=10, pady=10)

        # Action Bar Section
        action_section = create_section(self, "Action Bar (Potions)")
        action_section.pack(fill="x", padx=10, pady=5)

        action_content = ctk.CTkFrame(action_section, fg_color="transparent")
        action_content.pack(fill="x", padx=10, pady=10)

        self.slot_labels = []
        for i in range(3):
            row = ctk.CTkFrame(action_content, fg_color="transparent")
            row.pack(fill="x", pady=2)

            slot_label = ctk.CTkLabel(row, text=f"Slot {i+1}:", width=60, anchor="w")
            slot_label.pack(side="left")

            count_label = ctk.CTkLabel(row, text="---", font=ctk.CTkFont(weight="bold"))
            count_label.pack(side="left")

            desc_label = ctk.CTkLabel(row, text="", text_color=TEXT_MUTED)
            desc_label.pack(side="left", padx=10)

            self.slot_labels.append((count_label, desc_label))

        # Session Stats Section (hidden by default, shown when cavebot is active)
        self.session_section = create_section(self, "Session Stats")
        # Don't pack yet - will be shown when cavebot is active

        session_content = ctk.CTkFrame(self.session_section, fg_color="transparent")
        session_content.pack(fill="x", padx=10, pady=10)

        # Left column
        left_session = ctk.CTkFrame(session_content, fg_color="transparent")
        left_session.pack(side="left", fill="x", expand=True)

        self.session_time_label = self._create_stat_row(left_session, "Session Time:", "00:00:00")
        self.ticks_label = self._create_stat_row(left_session, "Ticks:", "0")

        # Right column
        right_session = ctk.CTkFrame(session_content, fg_color="transparent")
        right_session.pack(side="left", fill="x", expand=True)

        self.tps_label = self._create_stat_row(right_session, "TPS:", "0.0")
        self.avg_tick_label = self._create_stat_row(right_session, "Avg Tick:", "0.0ms")

        # Track session stats visibility
        self._session_stats_visible = False

    def _create_stat_row(self, parent, label: str, initial_value: str) -> ctk.CTkLabel:
        """Create a stat display row."""
        row = ctk.CTkFrame(parent, fg_color="transparent")
        row.pack(fill="x", pady=2)

        ctk.CTkLabel(
            row,
            text=label,
            font=ctk.CTkFont(size=12),
            text_color=TEXT_MUTED,
            width=120,
            anchor="w"
        ).pack(side="left")

        value_label = ctk.CTkLabel(
            row,
            text=initial_value,
            font=ctk.CTkFont(size=12, weight="bold"),
            anchor="w"
        )
        value_label.pack(side="left")

        return value_label

    def update_from_context(self, context: Dict[str, Any]):
        """Update all status displays from game context."""
        # Player stats
        status_bar = context.get('statusBar', {})
        hp = status_bar.get('hpPercentage', 100)
        mana = status_bar.get('manaPercentage', 100)

        self.hp_bar.set_value(hp)
        self.mp_bar.set_value(mana)

        # Skills
        skills = context.get('skills', {})
        capacity = skills.get('capacity')
        speed = skills.get('speed')
        food = skills.get('food')
        stamina = skills.get('stamina')

        if capacity is not None:
            self.capacity_label.configure(text=f"{capacity:,} oz")
        if speed is not None:
            self.speed_label.configure(text=str(speed))
        if food is not None:
            self.food_label.configure(text=f"{food} min")
        if stamina is not None:
            hours = stamina // 60
            mins = stamina % 60
            self.stamina_label.configure(text=f"{hours:02d}:{mins:02d}")

        # Position
        radar = context.get('radar', {})
        coord = radar.get('coordinate')
        if coord:
            self._current_coordinate = coord
            self.coord_label.configure(text=f"({coord[0]}, {coord[1]}, {coord[2]})")

            # Floor description
            z = coord[2]
            if z == 7:
                floor_desc = "Surface (0)"
            elif z < 7:
                floor_desc = f"Above ground (+{7 - z})"
            else:
                floor_desc = f"Underground (-{z - 7})"
            self.floor_label.configure(text=floor_desc)

        # Battle info
        battle_list = context.get('battleList', {})
        creatures = battle_list.get('creatures', [])
        self.creatures_label.configure(text=str(len(creatures)))

        is_attacking = context.get('cavebot', {}).get('isAttackingSomeCreature', False)
        closest = context.get('cavebot', {}).get('closestCreature')

        if is_attacking and closest:
            name = getattr(closest, 'name', 'Unknown')
            self.attacking_label.configure(text=name, text_color=COLOR_ERROR)
        elif is_attacking:
            self.attacking_label.configure(text="Yes", text_color=COLOR_ERROR)
        else:
            self.attacking_label.configure(text="None", text_color=TEXT_MUTED)

        # Update battle list display
        self._update_battle_list(creatures)

    def _update_battle_list(self, creatures: List):
        """Update the battle list display."""
        if not creatures:
            self.battle_list_label.configure(text="No creatures", text_color=TEXT_MUTED)
            return

        lines = []
        for creature in creatures[:5]:  # Show max 5
            name = getattr(creature, 'name', 'Unknown')
            hp_percent = getattr(creature, 'hpPercentage', 100)

            # Create HP bar visual
            bar_width = 8
            filled = int((hp_percent / 100) * bar_width)
            bar = chr(9608) * filled + chr(9617) * (bar_width - filled)

            lines.append(f"  {bar} {hp_percent}% {name}")

        if len(creatures) > 5:
            lines.append(f"  ... and {len(creatures) - 5} more")

        self.battle_list_label.configure(text="\n".join(lines), text_color=TEXT_PRIMARY)

    def update_action_bar(self, slot_counts: Dict[int, Optional[int]]):
        """Update action bar slot displays."""
        slot_names = {1: "(HP Pot)", 2: "(MP Pot)", 3: "(Strong HP)"}

        for slot in range(1, 4):
            count = slot_counts.get(slot)
            count_label, desc_label = self.slot_labels[slot - 1]

            if count is not None:
                count_label.configure(text=str(count))
                desc_label.configure(text=slot_names.get(slot, ""))
            else:
                count_label.configure(text="---")
                desc_label.configure(text="")

    def update_session_stats(self, tick_count: int, start_time: float):
        """Update session statistics."""
        self.tick_count = tick_count
        self.start_time = start_time

        # Session time
        elapsed = time.time() - start_time
        hours = int(elapsed // 3600)
        minutes = int((elapsed % 3600) // 60)
        seconds = int(elapsed % 60)
        self.session_time_label.configure(text=f"{hours:02d}:{minutes:02d}:{seconds:02d}")

        # Tick count
        self.ticks_label.configure(text=f"{tick_count:,}")

        # TPS
        tps = tick_count / elapsed if elapsed > 0 else 0
        self.tps_label.configure(text=f"{tps:.1f}")

        # Average tick time
        avg_tick = (elapsed / tick_count * 1000) if tick_count > 0 else 0
        self.avg_tick_label.configure(text=f"{avg_tick:.1f}ms")

        # Update last update time
        now = time.time()
        update_elapsed = now - self._last_update_time
        self._last_update_time = now
        self.update_label.configure(text=f"{update_elapsed:.3f}s ago")

    def update_coordinate_only(self, coord):
        """Update only the coordinate display (when bot is not running)."""
        if not coord:
            return
        self._current_coordinate = coord
        self.coord_label.configure(text=f"({coord[0]}, {coord[1]}, {coord[2]})")

        # Floor description
        z = coord[2]
        if z == 7:
            floor_desc = "Surface (0)"
        elif z < 7:
            floor_desc = f"Above ground (+{7 - z})"
        else:
            floor_desc = f"Underground (-{z - 7})"
        self.floor_label.configure(text=floor_desc)

    def _copy_coordinates(self):
        """Copy current coordinates to clipboard."""
        if not self._current_coordinate:
            return
        coord_str = f"{self._current_coordinate[0]}, {self._current_coordinate[1]}, {self._current_coordinate[2]}"
        try:
            self.clipboard_clear()
            self.clipboard_append(coord_str)
            # Visual feedback
            original_text = self.copy_coord_btn.cget("text")
            self.copy_coord_btn.configure(text="Copied!")
            self.after(1000, lambda: self.copy_coord_btn.configure(text=original_text))
        except Exception:
            pass

    def set_session_stats_visible(self, visible: bool):
        """Show or hide the session stats section."""
        if visible and not self._session_stats_visible:
            self.session_section.pack(fill="x", padx=10, pady=(5, 10))
            self._session_stats_visible = True
        elif not visible and self._session_stats_visible:
            self.session_section.pack_forget()
            self._session_stats_visible = False

    def update_realtime(self, hp: float = None, mp: float = None,
                        capacity: int = None, speed: int = None,
                        food: int = None, stamina: int = None,
                        coord: tuple = None, creatures: list = None,
                        is_attacking: bool = False, slot_counts: dict = None):
        """
        Update status display from direct repository reads (when bot is not running).

        This allows real-time monitoring without the bot being active.
        """
        # Player stats
        if hp is not None:
            self.hp_bar.set_value(hp)
        if mp is not None:
            self.mp_bar.set_value(mp)

        # Skills
        if capacity is not None:
            self.capacity_label.configure(text=f"{capacity:,} oz")
        if speed is not None:
            self.speed_label.configure(text=str(speed))
        if food is not None:
            self.food_label.configure(text=f"{food} min")
        if stamina is not None:
            hours = stamina // 60
            mins = stamina % 60
            self.stamina_label.configure(text=f"{hours:02d}:{mins:02d}")

        # Position
        if coord:
            self._current_coordinate = coord
            self.coord_label.configure(text=f"({coord[0]}, {coord[1]}, {coord[2]})")

            # Floor description
            z = coord[2]
            if z == 7:
                floor_desc = "Surface (0)"
            elif z < 7:
                floor_desc = f"Above ground (+{7 - z})"
            else:
                floor_desc = f"Underground (-{z - 7})"
            self.floor_label.configure(text=floor_desc)

        # Battle info
        if creatures is not None:
            self.creatures_label.configure(text=str(len(creatures)))
            self._update_battle_list(creatures)

            # Check if any creature is being attacked
            attacked_creature = None
            for c in creatures:
                if getattr(c, 'is_being_attacked', False):
                    attacked_creature = c
                    break

            if attacked_creature:
                name = getattr(attacked_creature, 'name', 'Unknown')
                self.attacking_label.configure(text=name, text_color=COLOR_ERROR)
            elif is_attacking:
                self.attacking_label.configure(text="Yes", text_color=COLOR_ERROR)
            else:
                self.attacking_label.configure(text="None", text_color=TEXT_MUTED)

        # Action bar
        if slot_counts:
            self.update_action_bar(slot_counts)

        # Update last update time
        now = time.time()
        elapsed = now - self._last_update_time
        self._last_update_time = now
        self.update_label.configure(text=f"{elapsed:.3f}s ago")

    def _schedule_system_update(self):
        """Schedule periodic system resources update."""
        if not PSUTIL_AVAILABLE:
            return

        try:
            self._update_system_resources()
        except Exception:
            pass

        # Update every 1 second (CPU measurement needs time interval)
        self.after(1000, self._schedule_system_update)

    def _update_system_resources(self):
        """Update CPU and memory usage display."""
        if not PSUTIL_AVAILABLE or not self._process:
            return

        try:
            # Get system-wide CPU usage (process.cpu_percent returns 0 for idle GUI)
            cpu_percent = psutil.cpu_percent(percpu=False)

            # Get memory usage
            memory_info = self._process.memory_info()
            memory_mb = memory_info.rss / (1024 * 1024)  # Convert to MB

            # Get total system memory for percentage
            total_memory = psutil.virtual_memory().total / (1024 * 1024)
            memory_percent = (memory_mb / total_memory) * 100

            # Get thread count
            thread_count = self._process.num_threads()

            # Update bars (cap at 100% for display)
            self.cpu_bar.set_value(min(100, int(cpu_percent)))
            self.memory_bar.set_value(min(100, int(memory_percent)))

            # Update detail labels
            self.cpu_detail_label.configure(text=f"CPU: {cpu_percent:.1f}%")
            self.memory_detail_label.configure(text=f"Memory: {memory_mb:.0f} MB")
            self.threads_label.configure(text=f"Threads: {thread_count}")

        except Exception:
            pass

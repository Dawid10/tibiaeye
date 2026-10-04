"""
Tibia-Vision Bot GUI Application.

Main GUI application using CustomTkinter with sidebar navigation.
"""
import customtkinter as ctk
import threading
import time
from typing import Optional, Dict, Any
import sys
import os

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from .config_manager import ConfigManager
from .profiles import (
    ensure_profiles, list_profiles, get_active_profile, set_active_profile,
    profile_config_path, create_profile, delete_profile,
)
from .tabs import BotControlTab, HealingTab, CavebotTab, TargetingTab, SpellAttackTab, StatusTab, RecorderTab, HardwareTab, DiagnosticsTab
from .tabs.dashboard import DashboardPage
from .components.status_bar_global import StatusBarGlobal
from .components.sidebar import Sidebar
from .components.status_strip import StatusStrip
from .theme import BG_APP, BORDER
from .global_hotkey import start_global_hotkeys
from .components.toast import show_toast
from ..core.constants import HOTKEY_TOGGLE_BOT, HOTKEY_TOGGLE_CAVEBOT


# CustomTkinter appearance settings
ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("blue")


class TibiaVisionGUI:
    """Main GUI application for Tibia-Vision Bot."""

    def __init__(self):
        self.root = ctk.CTk()
        self.root.title("TibiaEye")
        self.root.geometry("1050x720")
        self.root.minsize(900, 600)

        # Custom colors
        self.root.configure(fg_color=BG_APP)

        # Configuration (one gui_config.json per profile)
        ensure_profiles()
        self.config_manager = ConfigManager(profile_config_path(get_active_profile()))

        # Bot state
        self.game_loop = None
        self.bot_thread: Optional[threading.Thread] = None
        self.running = False
        self.paused = False
        self._realtime_update_count = 0
        self._context_lock = threading.Lock()
        self._cached_settings = {}
        self._last_remote_config_version = 0

        # Setup UI
        self._setup_ui()

        # Overlay controller (lazy import to defer cv2/AppKit/screen imports)
        from .overlay import OverlayController, DebugOverlayController
        self.overlay_controller = OverlayController(self.root)
        self.debug_overlay_controller = DebugOverlayController(self.root) if DebugOverlayController else None

        # Bind close event
        self.root.protocol("WM_DELETE_WINDOW", self._on_close)

        self._hotkey_listener = start_global_hotkeys(self.root, {
            HOTKEY_TOGGLE_BOT: self._toggle_bot,
            HOTKEY_TOGGLE_CAVEBOT: self._toggle_cavebot,
        })

        # Initialize realtime monitoring repositories (lazy loaded)
        self._realtime_repos = None

        # Start realtime status update loop (deferred so window appears instantly)
        self.root.after(1500, self._schedule_realtime_update)

    def _setup_ui(self):
        """Setup the main UI layout with sidebar navigation."""
        # --- Top: Status Strip ---
        self.status_strip = StatusStrip(
            self.root,
            on_start=self._start_bot,
            on_pause=self._pause_bot,
            on_stop=self._stop_bot,
        )
        self.status_strip.pack(fill="x")

        # --- Middle: Sidebar + Content ---
        body = ctk.CTkFrame(self.root, fg_color=BG_APP)
        body.pack(fill="both", expand=True)

        # Sidebar
        self.sidebar = Sidebar(body, on_navigate=self._navigate_to, on_theme_toggle=self._toggle_theme)
        self.sidebar.pack(side="left", fill="y")

        # Vertical separator
        ctk.CTkFrame(body, width=1, fg_color=BORDER).pack(side="left", fill="y")

        # Content area
        self._content_area = ctk.CTkFrame(body, fg_color=BG_APP)
        self._content_area.pack(side="left", fill="both", expand=True)

        # --- Bottom: Global Status Bar ---
        self.status_bar_global = StatusBarGlobal(self.root)
        self.status_bar_global.pack(fill="x")

        # --- Create all pages ---
        self._pages: Dict[str, Any] = {}
        self._active_page = None

        # Dashboard (new)
        self.dashboard = DashboardPage(self._content_area)
        self._pages["dashboard"] = self.dashboard

        self._create_settings_pages()

        # Status
        self.status_tab = StatusTab(self._content_area)
        self._pages["status"] = self.status_tab

        # Diagnostics
        self.diagnostics_tab = DiagnosticsTab(self._content_area)
        self._pages["diagnostics"] = self.diagnostics_tab

        # Show initial page
        self._navigate_to("dashboard")

    def _create_settings_pages(self):
        """Pages that read the active profile's config when built."""
        # Bot Control (Settings)
        self.bot_control_tab = BotControlTab(
            self._content_area,
            on_start=self._start_bot,
            on_pause=self._pause_bot,
            on_stop=self._stop_bot,
            on_overlay_toggle=self._toggle_overlay,
            on_debug_overlay_toggle=self._toggle_debug_overlay,
            config_manager=self.config_manager,
            profiles=list_profiles(),
            active_profile=get_active_profile(),
            on_profile_switch=self._switch_profile,
            on_profile_create=self._create_profile,
            on_profile_delete=self._delete_profile,
        )
        self._pages["control"] = self.bot_control_tab

        # Healing
        self.healing_tab = HealingTab(
            self._content_area,
            config_manager=self.config_manager
        )
        self._pages["healing"] = self.healing_tab

        # Spell Attack
        self.spell_attack_tab = SpellAttackTab(
            self._content_area,
            config_manager=self.config_manager
        )
        self._pages["spell_attack"] = self.spell_attack_tab

        # Cavebot
        self.cavebot_tab = CavebotTab(
            self._content_area,
            config_manager=self.config_manager,
            on_jump_to_waypoint=self._jump_to_waypoint,
        )
        self._pages["cavebot"] = self.cavebot_tab

        # Targeting
        self.targeting_tab = TargetingTab(
            self._content_area,
            config_manager=self.config_manager,
            on_scan_unknown=self._scan_unknown_monsters,
            on_learn_name=self._learn_monster_name,
        )
        self._pages["targeting"] = self.targeting_tab

        # Recorder
        self.recorder_tab = RecorderTab(
            self._content_area,
            config_manager=self.config_manager
        )
        self._pages["recorder"] = self.recorder_tab

        # Hardware
        self.hardware_tab = HardwareTab(
            self._content_area,
            config_manager=self.config_manager
        )
        self._pages["hardware"] = self.hardware_tab

    def _reload_settings_pages(self):
        """Put the active profile's settings into the existing widgets (rebuilding them is far too slow)."""
        self.config_manager.frozen = True
        try:
            self.bot_control_tab.reload(self.config_manager, list_profiles(), get_active_profile())
            for tab in (self.healing_tab, self.spell_attack_tab, self.cavebot_tab,
                        self.targeting_tab, self.recorder_tab, self.hardware_tab):
                tab.reload(self.config_manager)
        finally:
            self.config_manager.frozen = False

    def _save_settings_pages(self):
        """Write every widget into the profile (e.g. a new, not yet edited spell row)."""
        self.bot_control_tab._on_module_change()
        for tab in (self.healing_tab, self.spell_attack_tab, self.cavebot_tab,
                    self.targeting_tab, self.recorder_tab):
            tab._save_config()
        self.config_manager.save()

    def _load_profile(self, name, save_current=True):
        """Swap in a profile's config and show it in the settings pages."""
        if save_current:
            self._save_settings_pages()
        set_active_profile(name)
        self.config_manager = ConfigManager(profile_config_path(name))
        self._reload_settings_pages()
        self._toggle_overlay(self.config_manager.get('general.showOverlay', False))
        self._toggle_debug_overlay(self.config_manager.get('general.showDebugOverlay', False))
        self.bot_control_tab.log(f"Profile '{name}' loaded", "success")

    def _profile_change_blocked(self):
        if not self.running:
            return False
        self.bot_control_tab.profile_var.set(get_active_profile())
        self.bot_control_tab.log("Stop the bot before changing profiles.", "warning")
        return True

    def _switch_profile(self, name):
        if self._profile_change_blocked() or name == get_active_profile():
            return
        self._load_profile(name)

    def _create_profile(self, name):
        if self._profile_change_blocked():
            return
        self._save_settings_pages()
        error = create_profile(name, copy_from=get_active_profile())
        if error:
            self.bot_control_tab.log(error, "error")
            return
        self._load_profile(name.strip(), save_current=False)

    def _delete_profile(self, name):
        if self._profile_change_blocked():
            return
        error = delete_profile(name)
        if error:
            self.bot_control_tab.log(error, "error")
            return
        self._load_profile(list_profiles()[0], save_current=False)

    def _toggle_theme(self):
        """Toggle between dark and light mode."""
        current = ctk.get_appearance_mode()
        if current == "Dark":
            ctk.set_appearance_mode("light")
        else:
            ctk.set_appearance_mode("dark")

        # Re-apply raw tkinter tags that don't auto-switch
        self.dashboard.apply_theme()

    def _navigate_to(self, page_key: str):
        """Switch to a different page."""
        if self._active_page == page_key:
            return

        # Hide current page
        if self._active_page and self._active_page in self._pages:
            self._pages[self._active_page].pack_forget()

        # Show new page
        self._active_page = page_key
        if page_key in self._pages:
            self._pages[page_key].pack(fill="both", expand=True)

    def _start_bot(self):
        """Start the bot in a separate thread."""
        if self.running:
            return

        # Get settings from tabs
        healing_settings = self.healing_tab.get_settings()
        cavebot_settings = self.cavebot_tab.get_settings()
        hardware_settings = self.hardware_tab.get_settings()

        # Initialize hardware before preflight so capture card is available
        hw_mode = hardware_settings.get('mode', 'software')
        if hw_mode != 'software':
            from src.hardware import init_hardware
            init_hardware(
                hw_mode,
                hardware_settings.get('arduinoPort', ''),
                hardware_settings.get('captureDevice', 0),
                hardware_settings.get('debug', False),
            )
            self.bot_control_tab.log(f"Hardware mode: {hw_mode}", "info")

        # Pre-flight validation
        self.bot_control_tab.log("Running pre-flight checks...", "info")
        screenshot_gray = self._get_preflight_screenshot()
        if screenshot_gray is not None:
            h, w = screenshot_gray.shape[:2]
            self.bot_control_tab.log(f"  Screenshot: {w}x{h}", "info")
        else:
            self.bot_control_tab.log("  Screenshot: FAILED (None)", "error")

        from src.core.validation import run_preflight_checks
        critical_failures, warnings, all_results = run_preflight_checks(
            screenshot_gray, cavebot_settings, healing_settings, hardware_settings
        )

        # Log all results
        for name, passed, msg in all_results:
            level = "success" if passed else "error"
            self.bot_control_tab.log(f"  [{name}] {msg}", level)

        # Block on critical failures
        if critical_failures:
            self.bot_control_tab.log("Start blocked: critical checks failed.", "error")
            self._show_preflight_dialog(critical_failures, warnings)
            if hw_mode != 'software':
                try:
                    from src.hardware import shutdown_hardware
                    shutdown_hardware()
                except Exception:
                    pass
            return

        # Show warnings but allow continue
        for name, msg in warnings:
            self.bot_control_tab.log(f"  Warning: {msg}", "warning")

        self.running = True
        self.paused = False

        # Update UI
        self.bot_control_tab.log("Starting bot...", "info")
        self.status_strip.set_status("running")
        self.status_strip.set_button_states(running=True, paused=False)
        self.status_tab.set_session_stats_visible(True)

        # Start bot thread
        self.bot_thread = threading.Thread(target=self._run_bot, daemon=True)
        self.bot_thread.start()

        # Start status update loop
        self._schedule_status_update()

    def _run_bot(self):
        """Run the bot game loop (called in separate thread)."""
        try:
            from src.gameplay.gameloop import GameLoop
            from src.gameplay.context import get_context
            from src.gameplay.cavebot import load_waypoints_from_file

            # Get settings
            general_settings = self.bot_control_tab.get_settings()
            healing_settings = self.healing_tab.get_settings()
            cavebot_settings = self.cavebot_tab.get_settings()

            # Apply settings to context
            context = get_context()

            # GUI Logger for real-time logs
            context['gui_logger'] = self._log_safe

            # General settings
            context['cavebot']['enabled'] = general_settings.get('enableCavebot', True)
            context['healing']['enabled'] = general_settings.get('enableHealing', True)
            context['loot']['enabled'] = general_settings.get('enableLoot', True)
            context['loot']['hotkey'] = general_settings.get('lootHotkey', 'g')
            context['cavebot']['chaseWithClient'] = general_settings.get('chaseWithClient', True)
            context['cavebot']['chaseHotkey'] = general_settings.get('chaseHotkey', 'p')
            context['cavebot']['mapClickWalking'] = general_settings.get('mapClickWalking', True)

            # Stuck alert
            context['cavebot']['stuckAlert'] = {
                'enabled': general_settings.get('enableStuckAlert', True),
                'timeoutSeconds': general_settings.get('stuckAlertTimeout', 120)
            }

            # Healing potions
            potions = []
            hp_config = healing_settings.get('healthPotion', {})
            if hp_config.get('enabled', True):
                potions.append({
                    'hotkey': hp_config.get('hotkey', '1'),
                    'type': 'hp',
                    'hpPercentageLessThanOrEqual': hp_config.get('threshold', 30),
                    'cooldown': hp_config.get('cooldown', 1.0),
                    'enabled': True
                })

            mp_config = healing_settings.get('manaPotion', {})
            if mp_config.get('enabled', True):
                potions.append({
                    'hotkey': mp_config.get('hotkey', '2'),
                    'type': 'mana',
                    'hpPercentageLessThanOrEqual': mp_config.get('threshold', 50),
                    'cooldown': mp_config.get('cooldown', 1.0),
                    'enabled': True
                })
            context['healing']['potions'] = potions

            # Healing spells
            spells = []
            for spell_config in healing_settings.get('spells', []):
                if spell_config.get('enabled', True):
                    spells.append({
                        'hotkey': spell_config.get('hotkey'),
                        'hpPercentageLessThanOrEqual': spell_config.get('threshold', 70),
                        'enabled': True
                    })
            context['healing']['spells'] = spells

            # High priority healing
            context['healing']['highPriority'] = {
                'enabled': True,
                'hpPercentageLessThanOrEqual': 30,
                'manaPercentageGreaterThanOrEqual': 10
            }

            # Food
            food_config = healing_settings.get('food', {})
            context['healing']['eatFood'] = {
                'enabled': food_config.get('enabled', False),
                'hotkey': food_config.get('hotkey', 'f'),
                'eatWhenFoodIsLessOrEqual': food_config.get('threshold', 5)
            }

            # Load waypoints
            cavebot_data = cavebot_settings.get('cavebot', {})
            route_file = cavebot_data.get('routeFile', '')
            if route_file and os.path.exists(route_file):
                waypoints = load_waypoints_from_file(route_file)
                context['cavebot']['waypoints']['items'] = waypoints
                context['cavebot']['waypoints']['currentIndex'] = cavebot_data.get('startWaypoint', 0)
                context['cavebot']['routeName'] = os.path.splitext(os.path.basename(route_file))[0]
                self._log_safe(f"Loaded {len(waypoints)} waypoints from {os.path.basename(route_file)}", "success")
            else:
                context['cavebot']['waypoints']['items'] = cavebot_settings.get('waypoints', [])
                context['cavebot']['waypoints']['currentIndex'] = cavebot_data.get('startWaypoint', 0)

            # Refill settings
            refill_settings = cavebot_settings.get('refill', {})
            context['refill'] = {
                'hpPotionMin': refill_settings.get('hpPotionMin', 50),
                'mpPotionMin': refill_settings.get('mpPotionMin', 100),
                'capMin': refill_settings.get('capMin', 200),
                'checkCapacity': refill_settings.get('checkCapacity', True),
                'hpPotionTarget': refill_settings.get('hpPotionTarget', 200),
                'mpPotionTarget': refill_settings.get('mpPotionTarget', 400),
                'hpPotionItem': refill_settings.get('hpPotionItem', 'Health Potion'),
                'mpPotionItem': refill_settings.get('mpPotionItem', 'Mana Potion'),
                'returnLabel': refill_settings.get('returnLabel', 'caveStart'),
                'city': refill_settings.get('city', 'Darashia'),
                'depositGold': refill_settings.get('depositGold', True),
                'depositLoot': refill_settings.get('depositLoot', True),
                'dropFlasks': refill_settings.get('dropFlasks', True),
                'lootBackpack': refill_settings.get('lootBackpack', 'Beach Backpack'),
                'mainBackpack': refill_settings.get('mainBackpack', 'Golden Backpack'),
                'stashBackpack': refill_settings.get('stashBackpack', refill_settings.get('lootBackpack', 'Beach Backpack')),
                'depotChest': refill_settings.get('depotChest', 1),
            }
            cap_status = f"Cap<{refill_settings.get('capMin', 200)}" if refill_settings.get('checkCapacity', True) else "Cap: disabled"
            self._log_safe(f"Refill: HP<{refill_settings.get('hpPotionMin', 50)}, MP<{refill_settings.get('mpPotionMin', 100)}, {cap_status} -> return to '{refill_settings.get('returnLabel', 'caveStart')}'", "info")

            # Spell attack settings
            spell_attack_settings = self.spell_attack_tab.get_settings()
            context['spellAttack'] = {
                'enabled': spell_attack_settings.get('enabled', False),
                'manaReservePercent': spell_attack_settings.get('manaReservePercent', 30),
                'groups': spell_attack_settings.get('groups', []),
                'mantra': spell_attack_settings.get('mantra', {}),
                'lastCastSpell': None,
                'lastCastTime': 0,
            }
            if spell_attack_settings.get('enabled'):
                self._log_safe(f"Spell attack enabled ({len(spell_attack_settings.get('groups', []))} groups)", "info")

            # Targeting settings
            targeting_settings = self.targeting_tab.get_settings()
            context['targeting'] = {
                'enabled': targeting_settings.get('enabled', True),
                'mode': targeting_settings.get('mode', 'all'),
                'whitelist': set(targeting_settings.get('whitelist', [])),
                'blacklist': set(targeting_settings.get('blacklist', []))
            }

            if targeting_settings.get('mode') == 'whitelist' and targeting_settings.get('whitelist'):
                self._log_safe(f"Targeting whitelist: {', '.join(targeting_settings['whitelist'])}", "info")
            elif targeting_settings.get('mode') == 'blacklist' and targeting_settings.get('blacklist'):
                self._log_safe(f"Targeting blacklist: {', '.join(targeting_settings['blacklist'])}", "info")

            # Apply window region to screen capture
            self._apply_window_region()
            window_name = general_settings.get('window', 'Full Screen')
            if window_name and window_name != 'Full Screen':
                self._log_safe(f"Capturing window: {window_name}", "info")

            # Validate license
            from src.license import LicenseValidator
            license_validator = None
            api_key = os.getenv("TELEMETRY_API_KEY")
            if api_key:
                license_validator = LicenseValidator(api_key=api_key)
                try:
                    license_validator.validate(raise_on_error=False)
                    if license_validator.is_valid:
                        self._log_safe(f"License valid! Days remaining: {license_validator.days_remaining}", "success")
                    else:
                        self._log_safe("License invalid - telemetry disabled", "warning")
                except Exception as e:
                    self._log_safe(f"License check failed: {e} - continuing offline", "warning")

            # Create game loop
            tick_rate = general_settings.get('tickRate', 0.100)
            self.game_loop = GameLoop(
                tick_rate=tick_rate,
                license_validator=license_validator,
                character_id=os.getenv("CHARACTER_ID"),
            )
            self.game_loop.setup_default_middlewares()

            if general_settings.get('enableHealing', True):
                self.game_loop.setup_default_healing()

            if general_settings.get('enableLogging', False):
                self.game_loop.enable_session_logging()

            # Configure auto-reconnect
            reconnect_settings = general_settings.get('reconnect', {})
            if reconnect_settings.get('enabled', False):
                self.game_loop.configure_reconnect(reconnect_settings)
                self._log_safe("Auto-reconnect enabled", "info")

            # Configure server save handling
            server_save_settings = general_settings.get('serverSave', {})
            self.game_loop.configure_server_save(server_save_settings)
            if server_save_settings.get('enabled', True):
                self._log_safe(f"Server save handling enabled (time: {server_save_settings.get('time', '10:00')} CET)", "info")

            # Start unpaused
            self.game_loop.paused = False

            self._log_safe("Bot started successfully!", "success")
            self._log_safe(f"Tick rate: {tick_rate * 1000:.0f}ms", "info")

            # Start telemetry session
            hunt_location = None
            if route_file:
                hunt_location = os.path.splitext(os.path.basename(route_file))[0]
            route_id = cavebot_data.get('routeId')
            self.game_loop.start_telemetry_session(hunt_location=hunt_location, route_id=route_id)

            # Run the loop
            self.game_loop.running = True
            self.game_loop.start_time = time.time()

            while self.game_loop.running and self.running:
                tick_start = time.time()

                if not self.paused:
                    # Read cached settings
                    cached = self._cached_settings
                    sa_settings = cached.get('spell_attack', {})
                    targeting_settings = cached.get('targeting', {})
                    refill_settings = cached.get('cavebot', {}).get('refill', {})

                    # Brief lock: only update settings on context
                    with self._context_lock:
                        # Update spell attack settings
                        sa = self.game_loop.context.get('spellAttack', {})
                        sa['enabled'] = sa_settings.get('enabled', False)
                        sa['manaReservePercent'] = sa_settings.get('manaReservePercent', 30)
                        sa['groups'] = sa_settings.get('groups', [])
                        sa['mantra'] = sa_settings.get('mantra', {})

                        # Update targeting settings
                        self.game_loop.context['targeting'] = {
                            'enabled': targeting_settings.get('enabled', True),
                            'mode': targeting_settings.get('mode', 'all'),
                            'whitelist': set(targeting_settings.get('whitelist', [])),
                            'blacklist': set(targeting_settings.get('blacklist', []))
                        }

                        # Update refill settings
                        self.game_loop.context['refill'] = {
                            'hpPotionMin': refill_settings.get('hpPotionMin', 50),
                            'mpPotionMin': refill_settings.get('mpPotionMin', 100),
                            'capMin': refill_settings.get('capMin', 200),
                            'checkCapacity': refill_settings.get('checkCapacity', True),
                            'hpPotionTarget': refill_settings.get('hpPotionTarget', 200),
                            'mpPotionTarget': refill_settings.get('mpPotionTarget', 400),
                            'hpPotionItem': refill_settings.get('hpPotionItem', 'Health Potion'),
                            'mpPotionItem': refill_settings.get('mpPotionItem', 'Mana Potion'),
                            'returnLabel': refill_settings.get('returnLabel', 'caveStart'),
                            'city': refill_settings.get('city', 'Darashia'),
                            'depositGold': refill_settings.get('depositGold', True),
                            'depositLoot': refill_settings.get('depositLoot', True),
                            'dropFlasks': refill_settings.get('dropFlasks', True),
                            'lootBackpack': refill_settings.get('lootBackpack', 'Beach Backpack'),
                            'mainBackpack': refill_settings.get('mainBackpack', 'Golden Backpack'),
                            'stashBackpack': refill_settings.get('stashBackpack', refill_settings.get('lootBackpack', 'Beach Backpack')),
                            'depotChest': refill_settings.get('depotChest', 1),
                        }

                        # Remote config hot reload
                        self._apply_remote_config()

                    # tick() runs WITHOUT holding _context_lock
                    self.game_loop.tick()

                # Sleep to maintain tick rate
                elapsed = time.time() - tick_start
                sleep_time = tick_rate - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)

        except Exception as e:
            self._log_safe(f"Bot error: {e}", "error")
            import traceback
            traceback.print_exc()
        finally:
            if self.game_loop:
                self.game_loop.stop_telemetry_session()
            self.running = False
            self._log_safe("Bot stopped", "info")
            # Update UI on main thread
            try:
                self.root.after(0, self._on_bot_stopped)
            except Exception:
                pass

    def _on_bot_stopped(self):
        """Called on main thread when bot stops."""
        self.status_strip.set_status("stopped")
        self.status_strip.set_button_states(running=False, paused=False)
        self.status_strip.clear_uptime()

    def _apply_remote_config(self):
        """Apply remote config from dashboard if available. Called inside _context_lock."""
        if not self.game_loop or not self.game_loop.telemetry:
            return
        remote = self.game_loop.telemetry.remote_config
        if not remote or not remote.has_config:
            return

        current_version = remote.version
        if current_version <= self._last_remote_config_version:
            return

        from src.core.config_merge import deep_merge

        config = remote.get_config()
        ctx = self.game_loop.context

        # Apply healing config
        healing = config.get('healing', {})
        if healing:
            hp_config = healing.get('healthPotion', {})
            if hp_config:
                potions = ctx.get('healing', {}).get('potions', [])
                for p in potions:
                    if p.get('type') == 'hp':
                        if 'threshold' in hp_config:
                            p['hpPercentageLessThanOrEqual'] = hp_config['threshold']
                        if 'hotkey' in hp_config:
                            p['hotkey'] = hp_config['hotkey']

            mp_config = healing.get('manaPotion', {})
            if mp_config:
                potions = ctx.get('healing', {}).get('potions', [])
                for p in potions:
                    if p.get('type') == 'mana':
                        if 'threshold' in mp_config:
                            p['hpPercentageLessThanOrEqual'] = mp_config['threshold']
                        if 'hotkey' in mp_config:
                            p['hotkey'] = mp_config['hotkey']

            food_config = healing.get('food', {})
            if food_config:
                eat_food = ctx.get('healing', {}).get('eatFood', {})
                if 'enabled' in food_config:
                    eat_food['enabled'] = food_config['enabled']
                if 'threshold' in food_config:
                    eat_food['eatWhenFoodIsLessOrEqual'] = food_config['threshold']
                if 'hotkey' in food_config:
                    eat_food['hotkey'] = food_config['hotkey']

        # Apply targeting config
        targeting = config.get('targeting', {})
        if targeting:
            ctx['targeting'] = {
                'enabled': targeting.get('enabled', ctx.get('targeting', {}).get('enabled', True)),
                'mode': targeting.get('mode', ctx.get('targeting', {}).get('mode', 'all')),
                'whitelist': set(targeting.get('whitelist', list(ctx.get('targeting', {}).get('whitelist', [])))),
                'blacklist': set(targeting.get('blacklist', list(ctx.get('targeting', {}).get('blacklist', [])))),
            }

        # Apply spell attack config
        spell_attack = config.get('spellAttack', {})
        if spell_attack:
            sa = ctx.get('spellAttack', {})
            if 'enabled' in spell_attack:
                sa['enabled'] = spell_attack['enabled']
            if 'manaReservePercent' in spell_attack:
                sa['manaReservePercent'] = spell_attack['manaReservePercent']
            if 'groups' in spell_attack:
                sa['groups'] = spell_attack['groups']

        # Apply refill config
        refill = config.get('refill', {})
        if refill:
            ctx_refill = ctx.get('refill', {})
            for key in ['hpPotionMin', 'mpPotionMin', 'capMin', 'checkCapacity',
                        'hpPotionTarget', 'mpPotionTarget', 'city', 'depositGold',
                        'depositLoot', 'dropFlasks', 'lootBackpack', 'mainBackpack',
                        'stashBackpack', 'depotChest', 'returnLabel']:
                if key in refill:
                    ctx_refill[key] = refill[key]

        # Apply general config
        general = config.get('general', {})
        if general:
            if 'enableHealing' in general:
                ctx.get('healing', {})['enabled'] = general['enableHealing']
            if 'enableCavebot' in general:
                ctx.get('cavebot', {})['enabled'] = general['enableCavebot']
            if 'enableLoot' in general:
                ctx.get('loot', {})['enabled'] = general['enableLoot']
            if 'lootHotkey' in general:
                ctx.get('loot', {})['hotkey'] = general['lootHotkey']

        # Apply server save config
        server_save = config.get('serverSave', {})
        if server_save:
            if hasattr(self.game_loop, 'configure_server_save'):
                self.game_loop.configure_server_save(server_save)

        self._last_remote_config_version = current_version

        # Send ack
        realtime = self.game_loop.telemetry.realtime
        if realtime:
            realtime.send_config_ack(current_version)

        self._log_safe(f"[RemoteConfig] Applied v{current_version}", "info")

    def _pause_bot(self):
        """Toggle bot pause state."""
        if not self.running or not self.game_loop:
            return

        self.paused = not self.paused

        if self.paused:
            self.game_loop.pause()
            self.bot_control_tab.log("Bot paused", "warning")
            self.status_strip.set_status("paused")
            self.status_strip.set_button_states(running=True, paused=True)
            return

        self.game_loop.resume()
        self.bot_control_tab.log("Bot resumed", "success")
        self.status_strip.set_status("running")
        self.status_strip.set_button_states(running=True, paused=False)

    def _toggle_bot(self):
        """Global hotkey: start when stopped, stop when running."""
        if self.running:
            self.bot_control_tab.set_status("stopped")
            self._stop_bot()
            show_toast(self.root, "BOT STOPPED", "#cc3333")
            return
        self._start_bot()
        if self.running:
            self.bot_control_tab.set_status("running")
            show_toast(self.root, "BOT STARTED", "#00cc00")

    def _teach_battlelist_repo(self):
        if getattr(self, '_teach_repo', None) is None:
            from src.repositories.battlelist import BattleListRepository
            self._teach_repo = BattleListRepository()
        return self._teach_repo

    def _scan_unknown_monsters(self):
        """Battle list rows the bot can't read, from the current screen."""
        import cv2
        from src.core import get_screen_capture
        self._apply_window_region()
        gray = cv2.cvtColor(get_screen_capture().capture(), cv2.COLOR_BGR2GRAY)
        repo = self._teach_battlelist_repo()
        creature_count = len(repo.get_creatures(gray))
        unknown = repo.get_unknown_slots(gray)
        self.bot_control_tab.log(f"Teach scan: {creature_count} in battle list, {len(unknown)} unknown", "info")
        return creature_count, unknown

    def _learn_monster_name(self, name_hash, name):
        """Saved to learned_hashes.json and handed to the running bot, so no restart is needed."""
        self._teach_battlelist_repo().learn_name(name_hash, name)
        running_repo = getattr(self.game_loop, '_battlelist_repo', None) if self.game_loop else None
        if running_repo is not None:
            with self._context_lock:
                running_repo.learn_name(name_hash, name)
        self.bot_control_tab.log(f"Learned battle list name: {name}", "success")

    def _jump_to_waypoint(self, index):
        """Waypoint chosen in the Cavebot tab: a running bot goes there now; a stopped one starts there."""
        if not (self.running and self.game_loop):
            return
        with self._context_lock:
            self.game_loop.context['cavebot']['forceWaypoint'] = index
        self.bot_control_tab.log(f"Going to waypoint {index}", "info")

    def _toggle_cavebot(self):
        """Global hotkey: cavebot (walking + attacking) on/off, live. Healing keeps running."""
        enabled = not self.bot_control_tab.cavebot_var.get()
        self.bot_control_tab.cavebot_var.set(enabled)
        self.bot_control_tab._on_module_change()
        if self.running and self.game_loop:
            with self._context_lock:
                self.game_loop.context['cavebot']['enabled'] = enabled
        self.bot_control_tab.log(f"Cavebot {'ON' if enabled else 'OFF'}", "success" if enabled else "warning")
        show_toast(self.root, "CAVEBOT ON" if enabled else "CAVEBOT OFF", "#00cc00" if enabled else "#cc6600")

    def _stop_bot(self):
        """Stop the bot gracefully."""
        if not self.running:
            return

        self.running = False

        if self.game_loop:
            self.game_loop.stop()

        # Shutdown hardware backends
        try:
            from src.hardware import shutdown_hardware
            shutdown_hardware()
        except Exception:
            pass

        self.bot_control_tab.log("Stopping bot...", "warning")

        # Update UI
        self.status_strip.set_status("stopped")
        self.status_strip.set_button_states(running=False, paused=False)
        self.status_strip.clear_uptime()
        self.status_tab.set_session_stats_visible(False)
        self.dashboard.reset()

        # Wait for thread to finish
        if self.bot_thread and self.bot_thread.is_alive():
            self.bot_thread.join(timeout=2.0)

    def _schedule_status_update(self):
        """Schedule periodic status updates from the bot."""
        if not self.running:
            return

        try:
            # Snapshot GUI settings from main thread
            self._cached_settings = {
                'spell_attack': self.spell_attack_tab.get_settings(),
                'targeting': self.targeting_tab.get_settings(),
                'cavebot': self.cavebot_tab.get_settings(),
            }
            self._update_status()
        except Exception:
            pass

        if self.running:
            self.root.after(200, self._schedule_status_update)

    def _update_status(self):
        """Update status tab, diagnostics, dashboard, status strip, and global bar."""
        if not self.game_loop:
            return

        try:
            # Snapshot context under lock
            with self._context_lock:
                context = {
                    'statusBar': self.game_loop.context.get('statusBar', {}).copy(),
                    'battleList': self.game_loop.context.get('battleList', {}),
                    'cavebot': self.game_loop.context.get('cavebot', {}),
                    'skills': self.game_loop.context.get('skills', {}),
                    'gameWindow': self.game_loop.context.get('gameWindow', {}),
                    'radar': self.game_loop.context.get('radar', {}),
                }
                tick_count = self.game_loop.tick_count
                start_time = self.game_loop.start_time
                is_reconnecting = self.game_loop.is_reconnecting
                reconnect_state = self.game_loop.reconnect_state if is_reconnecting else None

                # Snapshot health data
                health_status = self.game_loop._bot_health.get_status()
                recent_errors = self.game_loop._bot_health.get_recent_errors()
                safe_mode = self.game_loop._bot_health.should_pause()
                is_stuck = getattr(self.game_loop, '_stuck_detected', False)

            # --- Update UI outside the lock ---

            # Status strip
            hp = context.get('statusBar', {}).get('hpPercentage')
            mp = context.get('statusBar', {}).get('manaPercentage')
            if hp is not None:
                self.status_strip.set_hp(int(hp))
            if mp is not None:
                self.status_strip.set_mp(int(mp))

            if is_reconnecting:
                self.status_strip.set_status("reconnecting")
                self.bot_control_tab.status_indicator.configure(
                    text=f"Reconnecting ({reconnect_state})", text_color="#ff6b6b"
                )
            elif not self.paused:
                self.bot_control_tab.status_indicator.configure(
                    text="Running", text_color="#4ecca3"
                )

            # Position
            coord = context.get('radar', {}).get('coordinate')
            if coord:
                self.status_strip.set_position(coord[0], coord[1], coord[2])

            # Uptime
            if start_time:
                elapsed = time.time() - start_time
                self.status_strip.set_uptime(elapsed)

            # Dashboard
            creatures = context.get('battleList', {}).get('creatures', [])
            elapsed_time = time.time() - start_time if start_time else 0
            self.dashboard.update_stats(
                hp=int(hp) if hp is not None else None,
                ticks=tick_count,
                creatures_count=len(creatures) if creatures else 0,
                elapsed=elapsed_time,
            )
            self.dashboard.update_battle_list(creatures)
            self.dashboard.update_health_dots(health_status)

            # Current task
            task_name = context.get('cavebot', {}).get('currentTask', '')
            if task_name:
                self.dashboard.update_task(task_name, "Running")
            else:
                self.dashboard.update_task("Idle")

            # Status tab
            self.status_tab.update_from_context(context)
            self.status_tab.update_session_stats(tick_count, start_time)

            # Cavebot current waypoint
            current_wp = context.get('cavebot', {}).get('waypoints', {}).get('currentIndex', 0)
            self.cavebot_tab.set_current_waypoint(current_wp)

            # Diagnostics
            self.diagnostics_tab.update_health(health_status)
            self.diagnostics_tab.update_recent_errors(recent_errors)
            self.diagnostics_tab.update_recovery(is_stuck, is_reconnecting, safe_mode)

            arduino_connected, arduino_port = self._get_arduino_status()
            telemetry_connected = self._get_telemetry_status()
            self.diagnostics_tab.update_connections(arduino_connected, arduino_port, telemetry_connected)

            # Global status bar
            screen_ok = context.get('statusBar', {}).get('hp') is not None
            bot_status = "yellow" if self.paused else ("red" if safe_mode else "green")
            if is_reconnecting:
                bot_status = "yellow"
            telemetry_status = "green" if telemetry_connected else "gray"
            hw_mode = self.hardware_tab.get_settings().get('mode', 'software')
            uses_arduino = hw_mode in ('arduino', 'full_hardware')
            if not uses_arduino:
                arduino_status = "gray"
            elif arduino_connected:
                arduino_status = "green"
            else:
                arduino_status = "red"
            self.status_bar_global.update_from_state(screen_ok, arduino_status, telemetry_status, bot_status)

        except Exception:
            pass

    def _get_preflight_screenshot(self):
        """Capture a grayscale screenshot for pre-flight checks."""
        try:
            import cv2
            from src.core import get_screen_capture
            self._apply_window_region()
            screen = get_screen_capture()
            img = screen.capture()
            if img is None:
                return None
            return cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        except Exception:
            return None

    def _show_preflight_dialog(self, critical_failures, warnings):
        """Show a dialog with pre-flight check results."""
        dialog = ctk.CTkToplevel(self.root)
        dialog.title("Pre-flight Check Failed")
        dialog.geometry("500x350")
        dialog.transient(self.root)
        dialog.grab_set()
        dialog.attributes("-topmost", True)

        ctk.CTkLabel(
            dialog,
            text="Cannot start: critical checks failed",
            font=ctk.CTkFont(size=15, weight="bold"),
            text_color="#e74c3c",
        ).pack(padx=20, pady=(15, 10))

        textbox = ctk.CTkTextbox(dialog, font=ctk.CTkFont(size=12), height=200)
        textbox.pack(fill="both", expand=True, padx=20, pady=5)

        textbox._textbox.tag_configure("fail", foreground="#e74c3c")
        textbox._textbox.tag_configure("warn", foreground="#ffc107")

        for name, msg in critical_failures:
            textbox._textbox.insert("end", f"  FAIL: [{name}] {msg}\n", "fail")
        for name, msg in warnings:
            textbox._textbox.insert("end", f"  WARN: [{name}] {msg}\n", "warn")

        textbox.configure(state="disabled")

        ctk.CTkButton(
            dialog, text="OK", width=100,
            command=dialog.destroy,
        ).pack(pady=(5, 15))

    def _log_safe(self, message, level="info"):
        """Thread-safe logging to GUI."""
        if level == "error":
            from src.utils.error_messages import friendly_error
            friendly_msg, suggestion = friendly_error(message)
            if suggestion:
                message = f"{friendly_msg} {suggestion}"
            else:
                message = friendly_msg
        try:
            self.root.after(0, lambda: self._dispatch_log(message, level))
        except Exception:
            pass

    def _dispatch_log(self, message, level):
        """Dispatch log to bot control tab and dashboard events."""
        self.bot_control_tab.log(message, level)
        self.dashboard.add_event(message, level)

    def _get_arduino_status(self):
        """Return (connected: bool, port: str) for Arduino."""
        try:
            from src.hardware.arduino import is_connected, _serial_connection
            connected = is_connected()
            port = ''
            if connected and _serial_connection:
                port = getattr(_serial_connection, 'port', '')
            return connected, port
        except Exception:
            pass
        return False, ''

    def _get_telemetry_status(self):
        """Return True if telemetry WebSocket is connected."""
        try:
            if self.game_loop and self.game_loop.telemetry:
                realtime = self.game_loop.telemetry.realtime
                if realtime:
                    return realtime.is_connected
        except Exception:
            pass
        return False

    def _apply_window_region(self):
        """Apply the selected Tibia window region to ScreenCapture."""
        try:
            from src.core import get_screen_capture
            from src.utils.window import get_window_region

            screen = get_screen_capture()

            if screen._window_id is not None:
                screen.refresh_capture_region()
                return

            settings = self.bot_control_tab.get_settings()
            window_id = settings.get('windowId', 0)

            if window_id == 0:
                screen.clear_capture_window()
                return

            region = get_window_region(window_id)
            if region is None:
                self._log_safe("Tibia window not found, falling back to full screen", "warning")
                screen.clear_capture_window()
                return

            screen.set_capture_window(window_id, region)
        except Exception as e:
            self._log_safe(f"Window region error: {e}", "error")

    def _init_realtime_repos(self):
        """Initialize repositories for realtime monitoring (lazy loaded)."""
        if self._realtime_repos is not None:
            return

        try:
            from src.core import get_screen_capture
            from src.repositories.statusbar import StatusBarRepository
            from src.repositories.actionBar import ActionBarRepository
            from src.repositories.battlelist import BattleListRepository

            self._realtime_repos = {
                'screen': get_screen_capture(),
                'statusbar': StatusBarRepository(),
                'actionbar': ActionBarRepository(),
                'battlelist': BattleListRepository(),
            }
        except Exception as e:
            print(f"Failed to init realtime repos: {e}")
            self._realtime_repos = {}

    def _schedule_realtime_update(self):
        """Schedule periodic realtime status updates (runs even when bot is stopped)."""
        if not self.running:
            try:
                self._update_realtime_status()
            except Exception:
                pass

            try:
                self.status_bar_global.update_from_state(
                    screen_ok=True, arduino_status="gray",
                    telemetry_status="gray", bot_status="gray",
                )
            except Exception:
                pass

        self.root.after(300, self._schedule_realtime_update)

    def _update_realtime_status(self):
        """Read all status directly from screen (when bot is not running)."""
        try:
            import cv2
            from src.repositories.radar import get_coordinate

            self._apply_window_region()

            self._init_realtime_repos()
            if not self._realtime_repos:
                return

            screen = self._realtime_repos['screen']
            img = screen.capture()
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

            hp = None
            mp = None
            capacity = None
            speed = None
            food = None
            stamina = None
            coord = None
            creatures = None
            slot_counts = {}

            try:
                statusbar = self._realtime_repos.get('statusbar')
                if statusbar:
                    hp = statusbar.get_hp_percentage(gray)
                    mp = statusbar.get_mp_percentage(gray)
            except Exception:
                pass

            try:
                from src.repositories.skills.core import get_capacity, get_speed, get_food, get_stamina
                capacity = get_capacity(gray)
                speed = get_speed(gray)
                food = get_food(gray)
                stamina = get_stamina(gray)
            except Exception:
                pass

            try:
                coord = get_coordinate(gray)
            except Exception:
                pass

            try:
                battlelist = self._realtime_repos.get('battlelist')
                if battlelist:
                    creatures = battlelist.get_creatures(gray)
            except Exception:
                pass

            try:
                actionbar = self._realtime_repos.get('actionbar')
                if actionbar:
                    for slot in range(1, 4):
                        count = actionbar.get_slot_count(gray, slot)
                        if count is not None:
                            slot_counts[slot] = count
            except Exception:
                pass

            # Update status tab
            self.status_tab.update_realtime(
                hp=hp, mp=mp, capacity=capacity, speed=speed,
                food=food, stamina=stamina, coord=coord,
                creatures=creatures, slot_counts=slot_counts
            )

            # Update status strip with realtime data
            if hp is not None:
                self.status_strip.set_hp(int(hp))
            if mp is not None:
                self.status_strip.set_mp(int(mp))
            if coord:
                self.status_strip.set_position(coord[0], coord[1], coord[2])

            # Update dashboard with realtime data
            self.dashboard.update_stats(
                hp=int(hp) if hp is not None else None,
                creatures_count=len(creatures) if creatures else 0,
            )
            self.dashboard.update_battle_list(creatures)

        except Exception:
            pass

    def _toggle_overlay(self, enabled):
        """Toggle overlay on/off."""
        if enabled:
            self.overlay_controller.start()
        else:
            self.overlay_controller.stop()

    def _toggle_debug_overlay(self, enabled):
        """Toggle debug overlay on/off."""
        if self.debug_overlay_controller is None:
            return
        if enabled:
            self.debug_overlay_controller.start()
        else:
            self.debug_overlay_controller.stop()

    def _on_close(self):
        """Handle window close event."""
        if self.running:
            self._stop_bot()

        self._hotkey_listener.stop()
        self.overlay_controller.stop()
        if self.debug_overlay_controller:
            self.debug_overlay_controller.stop()

        self.config_manager.save()
        self.root.destroy()

    def run(self):
        """Start the GUI main loop."""
        self.root.mainloop()


def main():
    """Entry point for GUI mode."""
    import pyautogui
    pyautogui.FAILSAFE = False
    pyautogui.PAUSE = 0

    app = TibiaVisionGUI()
    app.run()


if __name__ == "__main__":
    main()

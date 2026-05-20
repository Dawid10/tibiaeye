"""
Constants - technical / non-configurable values only.

User-configurable defaults (stuck timeout, tick rate, etc.) live in
src.core.defaults and gui_config.json. This file is for engine constants
(grid size, radar coords, delays, frequencies).
"""

# ============================================
# TICK RATES (game loop timing)
# ============================================
TICK_RATE_DEFAULT = 0.100      # 100ms - matches Tibia server tick
TICK_RATE_COMBAT = 0.080       # 80ms - faster when in combat
TICK_RATE_IDLE = 0.150         # 150ms - slower when idle (saves CPU)
TICK_RATE_PAUSED = 0.500       # 500ms - minimal CPU when paused

# ============================================
# MIDDLEWARE FREQUENCIES (run every N ticks)
# ============================================
FREQ_SCREENSHOT = 1            # Every tick - needed by all others
FREQ_STATUSBAR = 1             # Every tick - critical for healing
FREQ_BATTLELIST = 2            # Every 2 ticks - creature detection
FREQ_GAMEWINDOW = 2            # Every 2 ticks - pathfinding
FREQ_RADAR = 2                 # Every 2 ticks - coordinate detection (must match FREQ_GAMEWINDOW)
FREQ_SKILLS = 10               # Every 10 ticks - food check

# ============================================
# WALKING & MOVEMENT
# ============================================
WALK_COOLDOWN = 0.25           # Seconds between walk commands
WALK_TIMEOUT = 60.0            # Max seconds for WalkToCoordinate
WALK_CREATURE_TIMEOUT = 30.0   # Max seconds for WalkToCreature
WALK_STEP_TIMEOUT = 2.0        # Max seconds for single step
WALK_PROGRESS_TIMEOUT = 5.0    # Seconds without progress before skip
WALK_STUCK_COUNT = 15          # Stuck ticks before recalculating
WALK_MAX_RECALCULATIONS = 5    # Max path recalculations before skip
WALK_RETRY_SAME_DIRECTION = 2  # Retries in same direction when blocked
WALK_CREATURE_RECALC_DISTANCE = 2   # Min tiles target must move to trigger recalc
WALK_CREATURE_RECALC_INTERVAL = 0.5  # Seconds between forced recalcs when target jitters

# ============================================
# TILE FRICTION (movement speed calculation)
# ============================================
DEFAULT_PLAYER_SPEED = 110     # Base character speed (no boots/spells)
DEFAULT_TILE_FRICTION = 110    # Normal terrain friction
DEFAULT_MOVEMENT_TIME_MS = 450 # Fallback movement time in ms

# ============================================
# DELAYS (seconds)
# ============================================
DELAY_HOTKEY = 0.1             # After pressing a hotkey
DELAY_WALK_STEP = 0.15         # After each walk step
DELAY_FLOOR_CHANGE = 1.5       # After using rope/shovel/ladder
DELAY_CLICK = 0.1              # After mouse click
DELAY_SAY_BEFORE = 0.3         # Before typing in chat
DELAY_SAY_AFTER = 0.5          # After typing in chat
DELAY_KEY_PRESS = 0.2          # After generic key press
DELAY_TRADE_ACTION = 0.3       # After trade window action
DELAY_TYPEWRITE = 0.02         # Between each character typed
DELAY_FOOD_COOLDOWN = 2.0      # Between food eating attempts
DELAY_DEBUG_INTERVAL = 3.0     # Between debug prints

# ============================================
# WAIT TIMES (seconds)
# ============================================
WAIT_TRADE_WINDOW = 3.0        # Max wait for trade window to open
WAIT_LOCKER_OPEN = 3.0         # Max wait for locker to open
WAIT_NPC_RESPONSE = 1.0        # Wait for NPC to respond
WAIT_DEPOSIT = 0.5             # Wait after deposit action

# ============================================
# STUCK RECOVERY (tiered escalation)
# ============================================
STUCK_RECOVERY_TIER_1 = 30        # Clear task + Escape
STUCK_RECOVERY_TIER_2 = 60        # Jump to closest waypoint
STUCK_RECOVERY_TIER_3 = 120       # Random walk + alert
STUCK_RECOVERY_COOLDOWN = 10      # Min seconds between recovery actions
STUCK_ATTACK_SUPPRESSION_DURATION = 20   # Seconds to suppress attacks after stuck recovery
STUCK_ATTACK_SUPPRESSION_CLEAR_DISTANCE = 3  # Tiles moved from stuck pos to clear suppression
WALK_MAX_CONSECUTIVE_SKIPS = 5           # Consecutive unreachable waypoints before emergency random walk

# ============================================
# ANTI-TRAP (surrounded by creatures)
# ============================================
TRAP_DELAY_MOVING = 3.0                  # Seconds to wait before engaging when moving (avoids false positives)
TRAP_FALLBACK_TIMEOUT = 1.5              # Seconds before fallback to Space if click didn't register

# ============================================
# RETRIES
# ============================================
MAX_TRADE_RETRIES = 3          # Max retries opening trade window

# ============================================
# RADAR / MINIMAP
# ============================================
RADAR_LOCAL_START_X = 53       # Minimap start X coordinate
RADAR_LOCAL_START_Y = 54       # Minimap start Y coordinate

# ============================================
# GAME WINDOW
# ============================================
PLAYER_SLOT_X = 7              # Player X position in 15x11 grid
PLAYER_SLOT_Y = 5              # Player Y position in 15x11 grid
GRID_WIDTH = 15                # Game window grid width
GRID_HEIGHT = 11               # Game window grid height

# ============================================
# CAVEBOT
# ============================================
CAVEBOT_MAX_WAYPOINT_SKIP = 5  # Max waypoints to skip after combat
CAVEBOT_ATTACK_STUCK_TIMEOUT = 20.0  # Seconds stuck in same pos before skipping creature (unreachable)
UNREACHABLE_TARGET_GRACE_SECONDS = 3.0   # Grace period before declaring target unreachable
UNREACHABLE_BLACKLIST_DURATION = 15.0    # How long to skip an unreachable creature
UNREACHABLE_BLACKLIST_RADIUS = 3         # SQMs proximity to match blacklisted creature (handles movement)
COMBAT_NO_KILL_TIMEOUT = 60.0            # Seconds in combat without kill before forcing target switch

# ============================================
# CREATURE IDENTIFICATION
# ============================================
UNIDENTIFIED_CREATURE_NAME = 'Player'  # Name for unidentified creatures (safety: treated as player)

# ============================================
# TEMPLATE MATCHING THRESHOLDS
# ============================================
# Creature identification (battlelist + gamewindow)
CONFIDENCE_CREATURE = 0.80     # Template matching threshold for creature names

# UI element detection (buttons, windows, icons)
CONFIDENCE_UI_DEFAULT = 0.85   # Standard UI elements
CONFIDENCE_UI_LOW = 0.80       # UI elements that may vary slightly
CONFIDENCE_UI_BUTTON = 0.80    # Buttons (buy, ok, etc.)

# Specific UI elements
CONFIDENCE_DEPOT = 0.70        # Depot/locker detection (lower due to variations)
CONFIDENCE_TRADE_ITEM = 0.80   # Items in trade window

# Game window arrow detection (cascade: tries each in order)
CONFIDENCE_ARROW_HIGH = 0.95
CONFIDENCE_ARROW_MED = 0.85
CONFIDENCE_ARROW_LOW = 0.75

# Radar floor detection (per-floor array)
CONFIDENCE_RADAR_FLOORS = [
    0.80, 0.80, 0.85, 0.90, 0.90, 0.90,  # Floors 0-5
    0.90, 0.80, 0.90, 0.90, 0.90, 0.90,  # Floors 6-11
    0.90, 0.85, 0.80, 0.80               # Floors 12-15
]

# Skills/digit detection
CONFIDENCE_DIGIT = 0.75        # Template matching for digit recognition

# ============================================
# RECONNECT (auto-reconnect after disconnect)
# ============================================
RECONNECT_CHECK_FREQUENCY = 5             # Check every N ticks
RECONNECT_DELAY_CLICK_OK = 1.0            # After clicking OK on disconnect dialog
RECONNECT_DELAY_BEFORE_LOGIN = 2.0        # Before typing credentials
RECONNECT_DELAY_AFTER_LOGIN = 3.0         # After clicking Login button
RECONNECT_DELAY_CHAR_SELECT = 2.0         # After character list appears
RECONNECT_DELAY_GAME_LOAD = 8.0           # After clicking Enter Game
RECONNECT_DELAY_BETWEEN_RETRIES = 5.0     # Between retry attempts
RECONNECT_MAX_RETRIES = 10                # Max reconnect attempts
RECONNECT_TYPEWRITE_INTERVAL = 0.03       # Interval between typed characters
CONFIDENCE_RECONNECT = 0.85               # Template matching for reconnect UI
RECONNECT_CONSECUTIVE_FAILURES = 10       # Secondary detection: consecutive middleware failures
RECONNECT_INPUT_FIELD_OFFSET_X = 50       # Pixels to the right of label to reach input field
RECONNECT_CHAR_LIST_FIRST_ROW_OFFSET = 25 # Pixels below header bottom to first character row
RECONNECT_CHAR_LIST_ROW_HEIGHT = 22       # Pixels between character rows
RECONNECT_CHAR_LIST_MAX_ROWS = 10         # Max characters to scan in list

# ============================================
# SPELL ATTACK (offensive spell casting)
# ============================================
SPELL_ATTACK_GROUP_COOLDOWN_ATTACK = 2.0    # Tibia's attack group shared cooldown (seconds)
SPELL_ATTACK_GROUP_COOLDOWN_SUPPORT = 2.0   # Tibia's support group shared cooldown (seconds)
SPELL_ATTACK_MIN_CAST_INTERVAL = 0.3        # Minimum seconds between any two casts
SPELL_ATTACK_DEFAULT_MANA_RESERVE = 30      # Default mana reserve percentage (for healing)

# ============================================
# CHAT / LOOT CHANNEL
# ============================================
FREQ_CHAT = 5                              # Every 5 ticks
CONFIDENCE_CHAT_TAB = 0.85                 # Tab template matching
CONFIDENCE_LOOT_TEXT = 0.80                # "Loot of" text matching
CHAT_MAX_LOOT_LINES = 10                   # Max lines to track for hash comparison

# ============================================
# JITTER (human-like timing variation)
# ============================================
JITTER_SIGMA = 0.15                        # 15% standard deviation (default)
JITTER_SIGMA_TYPING = 0.30                 # 30% for typing (humans vary more)
JITTER_SIGMA_TICK = 0.05                   # 5% for tick rate (subtle)

# ============================================
# BOT HEALTH / SAFE MODE
# ============================================
MAX_CRITICAL_FAILURES = 3              # Consecutive failures before safe mode (screenshot, statusbar)
MAX_IMPORTANT_FAILURES = 10            # Consecutive failures before warning (battlelist, gamewindow, radar)
SAFE_MODE_RECOVERY_INTERVAL = 1.0      # Seconds between recovery attempts
SAFE_MODE_RECOVERY_TIMEOUT = 30.0      # Max seconds to attempt recovery before logout

# ============================================
# SERVER SAVE
# ============================================
SERVER_SAVE_WINDOW_MINUTES = 5             # Minutes around save to suppress alerts
SERVER_SAVE_RECONNECT_EXTRA_WAIT = 90      # Extra seconds to wait before reconnecting after SS

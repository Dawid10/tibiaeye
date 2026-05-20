"""Framework constants: colors, fonts, paths."""
import pathlib

# Paths
BASE_DIR = pathlib.Path(__file__).parent.resolve()
SCREENSHOTS_DIR = BASE_DIR / "screenshots"
OUTPUT_DIR = BASE_DIR / "output"
IMAGES_DIR = OUTPUT_DIR / "images"
REPORTS_DIR = OUTPUT_DIR / "reports"

# Annotation colors (BGR)
COLOR_MONSTER = (0, 255, 0)         # Green — identified monster
COLOR_FALSE_POSITIVE = (0, 0, 255)  # Red — unidentified creature
COLOR_ATTACKING = (0, 0, 255)       # Red — attacking creature
COLOR_TARGET = (0, 255, 255)        # Yellow — closest target
COLOR_BAR = (255, 255, 0)           # Cyan — HP bar
COLOR_PLAYER = (255, 136, 68)       # Blue — player position
COLOR_WALKABLE = (0, 200, 0)        # Green — walkable tile
COLOR_BLOCKED = (0, 0, 200)         # Red — blocked tile
COLOR_BFS_PATH = (0, 255, 255)      # Yellow — BFS path
COLOR_PASS = (0, 200, 0)            # Green — pass status
COLOR_FAIL = (0, 0, 220)            # Red — fail status

# Annotation settings
FONT = 0  # cv2.FONT_HERSHEY_SIMPLEX
FONT_SCALE_LABEL = 0.4
FONT_SCALE_STATUS = 0.45
FONT_SCALE_DECISION = 0.6
BL_INSET_SCALE = 2
GRID_OVERLAY_ALPHA = 0.3

# Supported OS values
SUPPORTED_OS = ("macos", "windows", "linux")

# Regression markers
MARKER_REGRESSION = "REGRESSION"
MARKER_FIXED = "FIXED"
MARKER_NEW = "NEW"

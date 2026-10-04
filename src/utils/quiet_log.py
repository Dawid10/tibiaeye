"""
Quiet console: hide the routine lines (walking, radar, OCR, loading) so fights are readable.
Start gui.py / main.py with --verbose to see everything.
"""
import sys

NOISY_PREFIXES = (
    "[Walk]", "[Cavebot] Processing waypoint", "[Cavebot] Created task", "[Cavebot] Ignoring",
    "[Radar]", "[OCR]", "[GW-OCR]", "[Targeting]", "[Tick", "[BL-Color]", "[BL-Diag]",
    "[CreatureHashTable]", "[BattleList] Hash collision", "[BattleList] Built hash", "[BattleList] Loaded",
    "[BattleList] Icon found", "[BattleList] Hash lookup", "[Battlelist] Filtered out", "[Attack] Waypoint restored",
    "[GameWindow] Loaded", "[GameWindow] Left arrow", "[GameWindow] Right arrow", "[Skills] Icon found",
    "[TargetingTab]", "Skills config loaded", "ActionBar:", "Loading radar data", "Radar data loaded",
    "Floor images", "Floor level", "Walkable matrix", "Radar tools template", "[Pathfinding]", "[UseLadder]", "[UseHole]",
)


class QuietStdout:
    def __init__(self, stream):
        self._stream = stream
        self._pending = ""

    def write(self, text):
        self._pending += text
        *lines, self._pending = self._pending.split("\n")
        for line in lines:
            if not line.lstrip().startswith(NOISY_PREFIXES):
                self._stream.write(line + "\n")
        return len(text)

    def flush(self):
        self._stream.flush()

    def __getattr__(self, name):
        return getattr(self._stream, name)


def install_quiet_log(argv):
    if "--verbose" in argv:
        return
    sys.stdout = QuietStdout(sys.stdout)

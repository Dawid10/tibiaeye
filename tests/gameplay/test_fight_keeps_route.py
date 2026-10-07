"""
A fight must not knock the cavebot off its route.

1. Stuck recovery treated a melee fight on one tile as "stuck": after 30s it pressed escape
   and skipped the waypoint, after 60s it jumped up to a third of the route ahead.
2. A skipped waypoint jumped to the closest of the next third of the route (31 waypoints on
   a 94-waypoint route) - past ladders and stairs.
"""
from unittest.mock import Mock, patch

from src.core.constants import (
    STUCK_FIGHT_GRACE, STUCK_RECOVERY_TIER_1, WAYPOINT_JUMP_MAX_FORWARD,
)


def _context(attacking, last_kill=0.0, coordinate=(100, 100, 7)):
    return {
        'radar': {'coordinate': coordinate},
        'cavebot': {
            'enabled': True,
            'isAttackingSomeCreature': attacking,
            'lastKillTime': last_kill,
            'waypoints': {'items': [{'type': 'walk', 'coordinate': [100, 100, 7]},
                                    {'type': 'walk', 'coordinate': [105, 100, 7]}],
                          'currentIndex': 0},
        },
    }


def _run(detector, context, at):
    with patch('src.gameplay.stuck_detector.time.time', return_value=at), \
            patch('src.gameplay.stuck_detector.pyautogui'), \
            patch('src.gameplay.stuck_detector.get_alert_system'):
        detector.check_and_recover(context, Mock())


class TestStuckWhileFighting:

    def test_long_fight_on_one_tile_is_not_stuck(self):
        from src.gameplay.stuck_detector import StuckDetector
        detector = StuckDetector()
        start = 1000.0
        _run(detector, _context(attacking=False), start)
        # fighting the whole time, a kill every 20s
        for second in range(1, 200, 5):
            _run(detector, _context(attacking=True, last_kill=start + (second // 20) * 20), start + second)
        assert detector.is_stuck is False

    def test_fight_without_kills_becomes_stuck_after_grace(self):
        """An attack frame on an unreachable creature must not hold the bot forever."""
        from src.gameplay.stuck_detector import StuckDetector
        detector = StuckDetector()
        start = 1000.0
        _run(detector, _context(attacking=False), start)
        end = start + STUCK_FIGHT_GRACE + STUCK_RECOVERY_TIER_1 + 5
        for second in range(1, int(end - start) + 1):
            _run(detector, _context(attacking=True), start + second)
        assert detector.is_stuck is True

    def test_standing_still_without_fight_is_still_stuck(self):
        from src.gameplay.stuck_detector import StuckDetector
        detector = StuckDetector()
        start = 1000.0
        _run(detector, _context(attacking=False), start)
        _run(detector, _context(attacking=False), start + STUCK_RECOVERY_TIER_1 + 1)
        assert detector.is_stuck is True


class TestWaypointJumpWindow:

    def test_jump_stays_within_a_few_waypoints(self):
        from src.gameplay.core.waypoint import jump_to_closest_waypoint
        # 94 waypoints in a line; the player stands right at waypoint 30
        items = [{'type': 'walk', 'coordinate': [100 + i * 10, 100, 7]} for i in range(94)]
        context = {
            'radar': {'coordinate': (400, 100, 7)},
            'battleList': {'creatures': []},
            'cavebot': {'isAttackingSomeCreature': False,
                        'waypoints': {'items': items, 'currentIndex': 0}},
        }

        jump_to_closest_waypoint(context, force=True)

        assert context['cavebot']['waypoints']['currentIndex'] == WAYPOINT_JUMP_MAX_FORWARD

    def test_jump_to_closest_within_window(self):
        from src.gameplay.core.waypoint import jump_to_closest_waypoint
        items = [{'type': 'walk', 'coordinate': [100 + i * 10, 100, 7]} for i in range(94)]
        context = {
            'radar': {'coordinate': (130, 100, 7)},
            'battleList': {'creatures': []},
            'cavebot': {'isAttackingSomeCreature': False,
                        'waypoints': {'items': items, 'currentIndex': 0}},
        }

        assert jump_to_closest_waypoint(context, force=True) is True
        assert context['cavebot']['waypoints']['currentIndex'] == 3

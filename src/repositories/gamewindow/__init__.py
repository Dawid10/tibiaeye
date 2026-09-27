"""GameWindow Repository - game window detection and interaction."""
from typing import Dict, List, Optional, Set, Tuple

import numpy as np

from ..core import get_screen_capture
from ...core.constants import UNIDENTIFIED_CREATURE_NAME
from ..utils.hash import FARMHASH_AVAILABLE
from .config import (
    load_arrow_images, load_monster_templates, IMAGES_PATH,
    NAME_HEIGHT, NAME_LEFT_OFFSET, NAME_RIGHT_OFFSET,
)
from .creatures import (
    GameWindowCreature,
    get_creatures,
    get_creatures_bars,
    get_closest_creature,
    has_target_to_creature,
    get_target_creature,
    get_monsters,
    get_players,
    get_different_creatures_by_slots,
    get_nearest_creatures_count,
    is_trapped_by_creatures,
    bfs_flood_fill,
    mark_attacked_from_bl,
)
from .core import (
    locate,
    get_game_window_position,
    capture_game_window,
    get_slot_from_coordinate,
    get_slot_screen_position,
    click_slot,
    right_click_slot,
    find_depot_locker,
)
from .ocr import CharAtlasManager


__all__ = ['GameWindowRepository', 'GameWindowCreature', 'get_gamewindow_repository']


class GameWindowRepository:
    """Thin facade delegating to creatures.py and core.py functions."""

    def __init__(self, monsters_folder: str = None):
        self._screen = get_screen_capture()
        self._arrow_images = load_arrow_images()
        self._game_window_position: Optional[Tuple[int, int, int, int]] = None
        self._left_arrow_cache: Dict = {'arrow': None, 'position': None, 'hash': None}
        self._right_arrow_cache: Dict = {'arrow': None, 'position': None, 'hash': None}
        self._map_top_cache: Dict = {}

        self._resolution = 1080
        self._slot_width = 64

        self._monster_templates = load_monster_templates(monsters_folder)
        self._logged_warnings: Set[str] = set()

        self._char_atlas_manager = CharAtlasManager(IMAGES_PATH)

    def get_game_window_position(self, screenshot: np.ndarray = None) -> Optional[Tuple[int, int, int, int]]:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)

        pos = get_game_window_position(
            screenshot, self._arrow_images,
            self._left_arrow_cache, self._right_arrow_cache,
            self._map_top_cache
        )
        if pos is not None:
            self._game_window_position = pos
            self._resolution = 1080
            self._slot_width = 64

        return self._game_window_position

    def capture(self, screenshot: np.ndarray = None) -> Optional[np.ndarray]:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)

        pos = self.get_game_window_position(screenshot)
        return capture_game_window(screenshot, pos)

    def get_creatures_bars(self, img: np.ndarray) -> List[Tuple[int, int]]:
        return get_creatures_bars(img)

    def _get_creatures_bars_vectorized(self, img: np.ndarray) -> List[Tuple[int, int]]:
        return get_creatures_bars(img)

    def get_creatures(self, battle_list_names: List[str],
                      coordinate: Tuple[int, int, int],
                      screenshot: np.ndarray = None,
                      direction: Optional[str] = None,
                      walked_pixels: int = 0,
                      screenshot_bgr: Optional[np.ndarray] = None) -> List[GameWindowCreature]:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)

        game_window = self.capture(screenshot)
        if game_window is None:
            return []

        gw_pos = self._game_window_position or (0, 0, 960, 704)
        color_game_window = None
        if screenshot_bgr is not None:
            x, y, w, h = gw_pos
            color_game_window = screenshot_bgr[y:y + h, x:x + w]

        return get_creatures(
            battle_list_names, coordinate, game_window, gw_pos,
            self._slot_width, self._monster_templates,
            self._logged_warnings, direction, walked_pixels,
            self._char_atlas_manager, color_game_window
        )

    def mark_attacked(self, creatures: List[GameWindowCreature],
                      attacked_name: Optional[str],
                      screenshot_bgr: Optional[np.ndarray] = None) -> None:
        """Cross-reference BL attack info to mark correct GW creature."""
        color_gw = None
        if screenshot_bgr is not None and self._game_window_position is not None:
            x, y, w, h = self._game_window_position
            color_gw = screenshot_bgr[y:y + h, x:x + w]
        mark_attacked_from_bl(creatures, attacked_name, color_gw, self._slot_width)

    def learn_from_creatures(self, game_window_image: np.ndarray,
                             creatures: List[GameWindowCreature],
                             battle_list_names: List[str]) -> None:
        """Learn OCR atlas from creatures identified via BL or template matching."""
        if game_window_image is None:
            return

        bl_name_set = set(battle_list_names)

        for creature in creatures:
            if creature.name == UNIDENTIFIED_CREATURE_NAME:
                continue
            if creature.name not in bl_name_set:
                continue
            if creature.id_method == 'OCR':
                continue

            bar_x = creature.game_window_coordinate[0] - self._slot_width // 2
            bar_y = creature.game_window_coordinate[1] - self._slot_width // 2 - 5

            name_y0 = max(0, bar_y - NAME_HEIGHT)
            name_y1 = max(0, bar_y)
            name_x0 = max(0, bar_x - NAME_LEFT_OFFSET)
            name_x1 = min(game_window_image.shape[1], bar_x + NAME_RIGHT_OFFSET)

            if name_y1 <= name_y0 or name_x1 <= name_x0:
                continue
            if name_y1 > game_window_image.shape[0]:
                continue

            name_region = game_window_image[name_y0:name_y1, name_x0:name_x1]
            self._char_atlas_manager.learn_from_creature(name_region, creature.name)

        self._char_atlas_manager.maybe_save()

    def get_closest_creature(self, creatures: List[GameWindowCreature],
                             coordinate: Tuple[int, int, int],
                             debug: bool = False) -> Optional[GameWindowCreature]:
        return get_closest_creature(
            creatures, coordinate, self._get_game_window_walkable, debug
        )

    def has_target_to_creature(self, creatures: List[GameWindowCreature],
                               target_creature: GameWindowCreature,
                               coordinate: Tuple[int, int, int]) -> bool:
        return has_target_to_creature(
            creatures, target_creature, coordinate, self._get_game_window_walkable
        )

    def _bfs_flood_fill(self, walkable: np.ndarray, start_y: int, start_x: int,
                        blocked_slots: set) -> dict:
        return bfs_flood_fill(walkable, start_y, start_x, blocked_slots)

    def _get_game_window_walkable(self, coordinate: Tuple[int, int, int]) -> Optional[np.ndarray]:
        try:
            from src.repositories.radar.config import (
                walkableFloorsSqms, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y
            )

            floor = coordinate[2]
            pixel_x = coordinate[0] - COORDINATE_OFFSET_X
            pixel_y = coordinate[1] - COORDINATE_OFFSET_Y

            y_start = pixel_y - 5
            y_end = pixel_y + 6
            x_start = pixel_x - 7
            x_end = pixel_x + 8

            if y_start < 0 or y_end > walkableFloorsSqms.shape[1]:
                return None
            if x_start < 0 or x_end > walkableFloorsSqms.shape[2]:
                return None
            if floor < 0 or floor >= walkableFloorsSqms.shape[0]:
                return None

            walkable = walkableFloorsSqms[floor, y_start:y_end, x_start:x_end].copy()
            return walkable.astype(np.int32)

        except Exception as e:
            print(f"[GameWindow] Error getting walkable matrix: {e}")
            return None

    def get_target_creature(self, creatures: List[GameWindowCreature]) -> Optional[GameWindowCreature]:
        return get_target_creature(creatures)

    def get_monsters(self, creatures: List[GameWindowCreature]) -> List[GameWindowCreature]:
        return get_monsters(creatures)

    def get_players(self, creatures: List[GameWindowCreature]) -> List[GameWindowCreature]:
        return get_players(creatures)

    def is_trapped_by_creatures(self, creatures: List[GameWindowCreature],
                                coordinate: Tuple[int, int, int]) -> bool:
        return is_trapped_by_creatures(creatures, coordinate)

    def get_different_creatures_by_slots(self, previous: List[GameWindowCreature],
                                         current: List[GameWindowCreature],
                                         slots: List[Tuple[int, int]] = None) -> List[GameWindowCreature]:
        return get_different_creatures_by_slots(previous, current, slots)

    def get_nearest_creatures_count(self, creatures: List[GameWindowCreature]) -> int:
        return get_nearest_creatures_count(creatures)

    def find_depot_locker(self, screenshot: np.ndarray = None) -> Optional[Tuple[int, int, int, int]]:
        if screenshot is None:
            screenshot = self._screen.capture(grayscale=True)

        gw_pos = self.get_game_window_position(screenshot)
        return find_depot_locker(screenshot, gw_pos)

    def set_walkable_sqms(self, walkable_sqms: np.ndarray) -> None:
        self._walkable_sqms = walkable_sqms

    def get_slot_from_coordinate(self, player_coord: Tuple[int, int, int],
                                 target_coord: Tuple[int, int, int]) -> Optional[Tuple[int, int]]:
        return get_slot_from_coordinate(player_coord, target_coord)

    def get_slot_screen_position(self, slot: Tuple[int, int]) -> Optional[Tuple[int, int]]:
        return get_slot_screen_position(slot, self._game_window_position)

    def click_slot(self, slot: Tuple[int, int]) -> bool:
        return click_slot(slot, self._game_window_position)

    def right_click_slot(self, slot: Tuple[int, int]) -> bool:
        return right_click_slot(slot, self._game_window_position)

    def click_coordinate(self, player_coord: Tuple[int, int, int],
                         target_coord: Tuple[int, int, int]) -> bool:
        slot = get_slot_from_coordinate(player_coord, target_coord)
        if slot is None:
            return False
        return click_slot(slot, self._game_window_position)

    def right_click_coordinate(self, player_coord: Tuple[int, int, int],
                               target_coord: Tuple[int, int, int]) -> bool:
        slot = get_slot_from_coordinate(player_coord, target_coord)
        if slot is None:
            return False
        return right_click_slot(slot, self._game_window_position)

    @property
    def template_count(self) -> int:
        return len(self._monster_templates)

    @property
    def uses_farmhash(self) -> bool:
        return FARMHASH_AVAILABLE

    @property
    def is_game_window_detected(self) -> bool:
        return self._game_window_position is not None

    def debug_walkable_matrix(self, coordinate: Tuple[int, int, int],
                              creatures: List[GameWindowCreature] = None) -> None:
        local_walkable = self._get_game_window_walkable(coordinate)
        if local_walkable is None:
            print(f"[DEBUG] No walkable matrix for coordinate {coordinate}")
            return

        player_y, player_x = 5, 7

        print(f"\n[DEBUG] Walkable matrix at {coordinate}")
        print(f"[DEBUG] Matrix shape: {local_walkable.shape}")
        print(f"[DEBUG] Player at slot ({player_x}, {player_y}) = center")
        print()

        creature_map = {}
        if creatures:
            for c in creatures:
                sx, sy = c.slot
                if 0 <= sx < 15 and 0 <= sy < 11:
                    creature_map[(sx, sy)] = c.name[:1].upper()

        print("    ", end="")
        for col in range(15):
            print(f"{col:2}", end="")
        print()

        for row in range(local_walkable.shape[0]):
            print(f"{row:2}: ", end="")
            for col in range(local_walkable.shape[1]):
                walkable = local_walkable[row, col] > 0

                if row == player_y and col == player_x:
                    print(" P", end="")
                elif (col, row) in creature_map:
                    if walkable:
                        print(f" {creature_map[(col, row)]}", end="")
                    else:
                        print(" ?", end="")
                elif walkable:
                    print(" .", end="")
                else:
                    print(" #", end="")
            print()

        print()
        print("Legend: P=Player, .=Walkable, #=Blocked, M/letter=Monster, ?=Creature on blocked tile")
        print()


# Singleton instance
_gamewindow_instance = None


def get_gamewindow_repository() -> GameWindowRepository:
    global _gamewindow_instance
    if _gamewindow_instance is None:
        _gamewindow_instance = GameWindowRepository()
    return _gamewindow_instance


def reset_gamewindow_repository() -> None:
    global _gamewindow_instance
    _gamewindow_instance = None

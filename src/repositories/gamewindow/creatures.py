"""
Creatures - all creature detection logic in standalone functions.

Consolidates bar detection, creature identification, pathfinding
and adds PyTibia features: misalignment correction, direction-aware
detection, 3 name matching strategies, loot detection, nearest count,
isUnderRoof.
"""
import math
from typing import Dict, List, Optional, Set, Tuple
from collections import Counter
from dataclasses import dataclass

import cv2
import numpy as np

from ...core.constants import (
    CONFIDENCE_CREATURE,
    UNIDENTIFIED_CREATURE_NAME,
)
from ...wiki.misalignment import get_misalignment
from .config import (
    BAR_WIDTH, BAR_HEIGHT, BLACK_THRESHOLD, BAR_MIN_DARK_RATIO,
    BAR_MIN_VERTICAL_GAP, BAR_MIN_INTERIOR_CONTRAST,
    NAME_HEIGHT, NAME_LEFT_OFFSET, NAME_RIGHT_OFFSET,
    GRID_WIDTH, GRID_HEIGHT, PLAYER_SLOT_X, PLAYER_SLOT_Y,
    UNDER_ROOF_PIXEL_VALUE, IGNORED_PIXEL_VALUES,
)

try:
    from numba import njit

    @njit(cache=True, fastmath=True)
    def _has_matrix_inside_other(matrix, other):
        for i in range(matrix.shape[0]):
            for j in range(matrix.shape[1]):
                if other[i][j] != 0:
                    continue
                val = matrix[i][j]
                if val == 0:
                    continue
                if val == 113:
                    continue
                if val == 29:
                    continue
                if val == 57:
                    continue
                if val == 91:
                    continue
                if val == 152:
                    continue
                if val == 170:
                    continue
                if val == 192:
                    continue
                return False
        return True

    @njit(cache=True)
    def _bfs_flood_fill_jit(walkable, start_y, start_x,
                            blocked_x, blocked_y, num_blocked):
        height, width = walkable.shape
        distances = np.full((height, width), -1, dtype=np.int32)
        distances[start_y, start_x] = 0

        max_queue = height * width
        queue_y = np.zeros(max_queue, dtype=np.int32)
        queue_x = np.zeros(max_queue, dtype=np.int32)
        queue_dist = np.zeros(max_queue, dtype=np.int32)

        queue_y[0] = start_y
        queue_x[0] = start_x
        queue_dist[0] = 0
        head = 0
        tail = 1

        blocked_lookup = np.zeros((height, width), dtype=np.uint8)
        for i in range(num_blocked):
            bx, by = blocked_x[i], blocked_y[i]
            if 0 <= by < height and 0 <= bx < width:
                blocked_lookup[by, bx] = 1

        dy = np.array([0, 0, 1, -1], dtype=np.int32)
        dx = np.array([1, -1, 0, 0], dtype=np.int32)

        while head < tail:
            y = queue_y[head]
            x = queue_x[head]
            dist = queue_dist[head]
            head += 1

            for d in range(4):
                ny = y + dy[d]
                nx = x + dx[d]

                if ny < 0 or ny >= height or nx < 0 or nx >= width:
                    continue
                if distances[ny, nx] >= 0:
                    continue
                if walkable[ny, nx] <= 0:
                    continue

                new_dist = dist + 1
                distances[ny, nx] = new_dist

                if blocked_lookup[ny, nx] == 1:
                    continue

                queue_y[tail] = ny
                queue_x[tail] = nx
                queue_dist[tail] = new_dist
                tail += 1

        return distances

    # Warm up JIT
    _dummy_walkable = np.ones((11, 15), dtype=np.int32)
    _dummy_blocked_x = np.array([0], dtype=np.int32)
    _dummy_blocked_y = np.array([0], dtype=np.int32)
    _bfs_flood_fill_jit(_dummy_walkable, 5, 7, _dummy_blocked_x, _dummy_blocked_y, 0)

    _dummy_m = np.zeros((3, 3), dtype=np.uint8)
    _dummy_o = np.zeros((3, 3), dtype=np.uint8)
    _has_matrix_inside_other(_dummy_m, _dummy_o)

    NUMBA_AVAILABLE = True
except ImportError:
    NUMBA_AVAILABLE = False


@dataclass
class GameWindowCreature:
    name: str
    creature_type: str
    slot: Tuple[int, int]
    coordinate: Tuple[int, int, int]
    window_coordinate: Tuple[int, int]
    game_window_coordinate: Tuple[int, int]
    is_being_attacked: bool = False
    is_under_roof: bool = False
    hp_percent: float = 100.0
    id_method: str = ""


# ---------------------------------------------------------------------------
# Bar detection
# ---------------------------------------------------------------------------

def get_creatures_bars(image: np.ndarray,
                       max_fallback_bars: int = 1) -> List[Tuple[int, int]]:
    height, width = image.shape
    if height < BAR_HEIGHT or width < BAR_WIDTH:
        return []

    black_mask = (image <= BLACK_THRESHOLD).astype(np.uint8)
    kernel = np.ones(BAR_WIDTH, dtype=np.uint8)
    min_dark = int(BAR_WIDTH * BAR_MIN_DARK_RATIO)
    all_bars = []
    strict_bars = []
    fallback_candidates = []

    for y in range(height - 3):
        row_sum = np.convolve(black_mask[y, :], kernel, mode='valid')
        top_candidates = np.where(row_sum >= min_dark)[0]

        if len(top_candidates) == 0:
            continue

        bottom_sum = np.convolve(black_mask[y + 3, :], kernel, mode='valid')

        for x in top_candidates:
            is_valid, used_fallback, contrast = _is_valid_bar(
                image, x, y, all_bars, bottom_sum, min_dark)
            if not is_valid:
                continue
            all_bars.append((x, y))
            if used_fallback:
                fallback_candidates.append((x, y, contrast))
            else:
                strict_bars.append((x, y))

    needed = max(0, max_fallback_bars - len(strict_bars))
    if fallback_candidates and needed > 0:
        fallback_candidates.sort(key=lambda b: -b[2])
        selected = [(x, y) for x, y, _ in fallback_candidates[:needed]]
    else:
        selected = []

    return strict_bars + selected


def _is_valid_bar(image: np.ndarray, x: int, y: int,
                  existing_bars: List[Tuple[int, int]],
                  bottom_sum: np.ndarray,
                  min_dark: int) -> Tuple[bool, bool, float]:
    if existing_bars and existing_bars[-1][1] == y and x - existing_bars[-1][0] < BAR_WIDTH:
        return False, False, 0.0

    for i in range(len(existing_bars) - 1, -1, -1):
        ex, ey = existing_bars[i]
        if y - ey > BAR_MIN_VERTICAL_GAP:
            break
        if abs(x - ex) < BAR_WIDTH:
            return False, False, 0.0

    if x < len(bottom_sum) and bottom_sum[x] < min_dark:
        return False, False, 0.0

    border_avg = (float(np.mean(image[y, x:x + BAR_WIDTH])) +
                  float(np.mean(image[y + 3, x:x + BAR_WIDTH]))) / 2
    interior_avg = (float(np.mean(image[y + 1, x + 2:x + 22])) +
                    float(np.mean(image[y + 2, x + 2:x + 22]))) / 2
    contrast = interior_avg - border_avg

    if contrast < BAR_MIN_INTERIOR_CONTRAST:
        # Low HP fallback: with <10% HP the bar is mostly empty (dark) so the
        # mean fails. But the leftmost pixels still have the HP color fill
        # (red/yellow/green) while the rest is dark (empty bar).
        # Two conditions: left bright + right dark (distinguishes from terrain).
        # After scanning, callers rank candidates by contrast and pick the best N.
        left_max = max(float(np.max(image[y + 1, x + 1:x + 4])),
                       float(np.max(image[y + 2, x + 1:x + 4])))
        right_avg = (float(np.mean(image[y + 1, x + 8:x + 22])) +
                     float(np.mean(image[y + 2, x + 8:x + 22]))) / 2
        left_bright = left_max - border_avg >= BAR_MIN_INTERIOR_CONTRAST
        right_dark = right_avg <= border_avg + 5
        if not (left_bright and right_dark):
            return False, False, 0.0
        return True, True, contrast

    return True, False, contrast


# ---------------------------------------------------------------------------
# Creature identification
# ---------------------------------------------------------------------------

def has_matrix_inside_other(matrix: np.ndarray, other: np.ndarray) -> bool:
    if NUMBA_AVAILABLE:
        return _has_matrix_inside_other(matrix, other)
    return _has_matrix_inside_other_python(matrix, other)


def _has_matrix_inside_other_python(matrix: np.ndarray, other: np.ndarray) -> bool:
    for i in range(matrix.shape[0]):
        for j in range(matrix.shape[1]):
            if other[i][j] == 0 and matrix[i][j] not in IGNORED_PIXEL_VALUES:
                return False
    return True


def identify_creature(image: np.ndarray, bar_x: int, bar_y: int,
                      battle_list_names: List[str],
                      available_names: Counter,
                      matched_counts: Counter,
                      total_bars: int,
                      monster_templates: Dict[str, np.ndarray],
                      logged_warnings: Set[str],
                      char_atlas_manager=None) -> Tuple[str, str, str]:
    """
    Identify creature at HP bar position.

    Uses 4 strategies:
    1. Trust battlelist (single type, bars <= names)
    2. OCR name reading (hash lookup + char-level OCR)
    3. Template matching with 3 name offset strategies
    4. Fallback / mark as player

    Returns (creature_name, creature_type, id_method).
    """
    name_y0 = max(0, bar_y - NAME_HEIGHT)
    name_y1 = bar_y
    name_x0 = max(0, bar_x - NAME_LEFT_OFFSET)
    name_x1 = min(image.shape[1], bar_x + NAME_RIGHT_OFFSET)
    name_region = image[name_y0:name_y1, name_x0:name_x1]

    def name_available(name):
        return matched_counts[name] < available_names[name]

    available_list = [n for n in battle_list_names if name_available(n)]
    unique_types = set(available_list)
    total_monster_names = sum(available_names.values())

    # Strategy 1: trust battlelist
    if len(unique_types) == 1:
        return available_list[0], 'monster', "BL"

    # Strategy 2: OCR name reading
    if char_atlas_manager is not None and available_list:
        matched = char_atlas_manager.identify_name(name_region, available_list)
        if matched is not None:
            return matched, 'monster', "OCR"

    # Strategy 3: template matching with 3 offsets
    if available_list:
        matched = _match_with_three_strategies(
            name_region, battle_list_names, name_available,
            monster_templates, logged_warnings
        )
        if matched is not None:
            return matched, 'monster', "TM"

    # Strategy 4: fallback if bars <= monster names
    if total_bars <= total_monster_names and available_list:
        return available_list[0], 'monster', "BL"

    return UNIDENTIFIED_CREATURE_NAME, 'player', ""


def _match_with_three_strategies(name_region: np.ndarray,
                                 battle_list_names: List[str],
                                 name_available,
                                 monster_templates: Dict[str, np.ndarray],
                                 logged_warnings: Set[str]) -> Optional[str]:
    """Try 3 name matching strategies (exact, +1 pixel, -1 pixel)."""
    for bl_name in battle_list_names:
        if not name_available(bl_name):
            continue

        template = monster_templates.get(bl_name)
        if template is None:
            if bl_name not in logged_warnings:
                print(f"[GameWindow] WARNING: No template for '{bl_name}'")
                logged_warnings.add(bl_name)
            continue

        # Strategy A: exact position (cv2 template matching)
        score = _get_template_score(name_region, template)
        if score >= CONFIDENCE_CREATURE:
            return bl_name

        # Strategy B: pixel-level comparison with has_matrix_inside_other
        if template.shape[0] <= name_region.shape[0] and template.shape[1] <= name_region.shape[1]:
            crop = name_region[:template.shape[0], :template.shape[1]]
            if has_matrix_inside_other(crop, template):
                return bl_name

            # Strategy C: offset +1 pixel right
            if template.shape[1] + 1 <= name_region.shape[1]:
                crop_right = name_region[:template.shape[0], 1:template.shape[1] + 1]
                trimmed_template = template[:, :template.shape[1] - 1]
                if crop_right.shape[1] >= trimmed_template.shape[1]:
                    crop_right = crop_right[:, :trimmed_template.shape[1]]
                    if has_matrix_inside_other(crop_right, trimmed_template):
                        return bl_name

            # Strategy D: offset -1 pixel left
            if template.shape[1] > 1:
                end = min(template.shape[1] - 1, name_region.shape[1])
                crop_left = name_region[:template.shape[0], :end]
                trimmed_template_left = template[:, 1:1 + end]
                if crop_left.shape[1] >= trimmed_template_left.shape[1]:
                    crop_left = crop_left[:, :trimmed_template_left.shape[1]]
                    if has_matrix_inside_other(crop_left, trimmed_template_left):
                        return bl_name

    return None


def _get_template_score(region: np.ndarray, template: np.ndarray) -> float:
    if template.shape[0] > region.shape[0] or template.shape[1] > region.shape[1]:
        return 0.0
    result = cv2.matchTemplate(region, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, _ = cv2.minMaxLoc(result)
    return max_val


# ---------------------------------------------------------------------------
# Creature creation
# ---------------------------------------------------------------------------

def make_creature(name: str, creature_type: str, id_method: str,
                  bar_x: int, bar_y: int,
                  image: np.ndarray,
                  coordinate: Tuple[int, int, int],
                  slot_width: int,
                  game_window_position: Tuple[int, int, int, int],
                  direction: Optional[str] = None,
                  walked_pixels: int = 0) -> GameWindowCreature:
    """
    Create a GameWindowCreature with misalignment correction,
    direction-aware detection, and isUnderRoof check.
    """
    misalignment = get_misalignment(name)
    dist_to_bar = 19 if slot_width == 64 else 3

    x_coord = bar_x - dist_to_bar + misalignment['x']
    x_slot = max(0, min(14, round(x_coord / slot_width)))

    y_coord = 0 if bar_y <= 14 else bar_y + 5
    y_coord += misalignment['y']
    y_slot = max(0, min(10, round(y_coord / slot_width)))

    slot = (x_slot, y_slot)

    world_coord = (
        coordinate[0] - 7 + x_slot,
        coordinate[1] - 5 + y_slot,
        coordinate[2]
    )

    gw_pos = game_window_position
    half_slot = slot_width / 2
    click_x = gw_pos[0] + min(max(x_coord + half_slot, half_slot), image.shape[1] - half_slot)
    click_y = gw_pos[1] + min(max(y_coord + half_slot, half_slot), image.shape[0] - half_slot)

    window_coord = (int(click_x), int(click_y))
    game_window_coord = (int(x_coord + half_slot), int(y_coord + half_slot))

    is_attacked = _is_creature_attacked(image, bar_x, bar_y, slot_width)
    is_roof = _is_under_roof(image, bar_x, bar_y, slot_width)

    return GameWindowCreature(
        name=name,
        creature_type=creature_type,
        slot=slot,
        coordinate=world_coord,
        window_coordinate=window_coord,
        game_window_coordinate=game_window_coord,
        is_being_attacked=is_attacked,
        is_under_roof=is_roof,
        id_method=id_method
    )


def _is_creature_attacked(image: np.ndarray, bar_x: int, bar_y: int,
                           slot_width: int) -> bool:
    border_x = max(0, bar_x - (19 if slot_width == 64 else 3))
    border_y = bar_y + 5

    # Clip region to image bounds instead of returning False
    region_end_y = min(border_y + slot_width, image.shape[0])
    region_end_x = min(border_x + slot_width, image.shape[1])

    if region_end_y <= border_y or region_end_x <= border_x:
        return False

    region = image[border_y:region_end_y, border_x:region_end_x]
    border_gap = 4 if slot_width == 64 else 2
    region_h, region_w = region.shape

    if region_h < border_gap * 2 or region_w < border_gap * 2:
        return False

    count = 0
    borders_checked = 0

    # Top border
    for p in region[0:border_gap, :].flatten():
        if p == 76 or p == 166:
            count += 1
    borders_checked += 1

    # Bottom border (only if full height)
    if region_h >= slot_width:
        for p in region[-border_gap:, :].flatten():
            if p == 76 or p == 166:
                count += 1
        borders_checked += 1

    # Left border
    for p in region[border_gap:region_h - border_gap, 0:border_gap].flatten():
        if p == 76 or p == 166:
            count += 1
    borders_checked += 1

    # Right border (only if full width)
    if region_w >= slot_width:
        for p in region[border_gap:region_h - border_gap, -border_gap:].flatten():
            if p == 76 or p == 166:
                count += 1
        borders_checked += 1

    # Scale threshold by how many borders we checked (out of 4)
    threshold = int(50 * borders_checked / 4)
    return count > threshold


def _is_under_roof(image: np.ndarray, bar_x: int, bar_y: int,
                   slot_width: int) -> bool:
    check_x = max(0, bar_x - (19 if slot_width == 64 else 3)) + slot_width // 2
    check_y = bar_y + 5 + slot_width // 2

    if check_y >= image.shape[0] or check_x >= image.shape[1]:
        return False

    return image[check_y, check_x] == UNDER_ROOF_PIXEL_VALUE


# ---------------------------------------------------------------------------
# Get creatures pipeline
# ---------------------------------------------------------------------------

def get_creatures(battle_list_names: List[str],
                  coordinate: Tuple[int, int, int],
                  game_window_image: np.ndarray,
                  game_window_position: Tuple[int, int, int, int],
                  slot_width: int,
                  monster_templates: Dict[str, np.ndarray],
                  logged_warnings: Set[str],
                  direction: Optional[str] = None,
                  walked_pixels: int = 0,
                  char_atlas_manager=None) -> List[GameWindowCreature]:
    """Full creature detection pipeline."""
    max_fallback = max(1, len(battle_list_names))
    bars = get_creatures_bars(game_window_image, max_fallback_bars=max_fallback)
    if not bars:
        return []

    center_x = game_window_image.shape[1] / 2
    center_y = game_window_image.shape[0] / 2
    bars_sorted = sorted(
        bars,
        key=lambda b: math.sqrt((b[0] - center_x)**2 + (b[1] - center_y)**2)
    )

    available_names = Counter(battle_list_names)
    matched_counts = Counter()
    total_bars = len(bars_sorted)

    creatures = []
    seen_slots = {}  # slot -> creature (dedup: one creature per grid cell)
    for bar_x, bar_y in bars_sorted:
        name, ctype, method = identify_creature(
            game_window_image, bar_x, bar_y,
            battle_list_names, available_names, matched_counts,
            total_bars, monster_templates, logged_warnings,
            char_atlas_manager
        )

        creature = make_creature(
            name, ctype, method, bar_x, bar_y,
            game_window_image, coordinate, slot_width,
            game_window_position, direction, walked_pixels
        )

        # Dedup: keep one creature per grid slot, prefer identified over unidentified
        slot = creature.slot
        if slot in seen_slots:
            existing = seen_slots[slot]
            # Keep the identified one (monster > player)
            if existing.name != UNIDENTIFIED_CREATURE_NAME:
                continue  # already have an identified creature for this slot
            if creature.name == UNIDENTIFIED_CREATURE_NAME:
                continue  # both unidentified, keep first
            # New creature is identified, replace
            creatures.remove(existing)
            if existing.name != UNIDENTIFIED_CREATURE_NAME:
                matched_counts[existing.name] -= 1

        seen_slots[slot] = creature
        creatures.append(creature)
        if creature.name != UNIDENTIFIED_CREATURE_NAME:
            matched_counts[creature.name] += 1

    return creatures


# ---------------------------------------------------------------------------
# Pathfinding
# ---------------------------------------------------------------------------

def bfs_flood_fill(walkable: np.ndarray, start_y: int, start_x: int,
                   blocked_slots: Set[Tuple[int, int]]) -> Dict[Tuple[int, int], int]:
    if NUMBA_AVAILABLE:
        return _bfs_jit(walkable, start_y, start_x, blocked_slots)
    return _bfs_python(walkable, start_y, start_x, blocked_slots)


def _bfs_jit(walkable, start_y, start_x, blocked_slots):
    if blocked_slots:
        blocked_list = list(blocked_slots)
        blocked_x = np.array([b[0] for b in blocked_list], dtype=np.int32)
        blocked_y = np.array([b[1] for b in blocked_list], dtype=np.int32)
        num_blocked = len(blocked_list)
    else:
        blocked_x = np.array([0], dtype=np.int32)
        blocked_y = np.array([0], dtype=np.int32)
        num_blocked = 0

    dist_matrix = _bfs_flood_fill_jit(
        walkable.astype(np.int32), start_y, start_x,
        blocked_x, blocked_y, num_blocked
    )

    distances = {}
    for y in range(dist_matrix.shape[0]):
        for x in range(dist_matrix.shape[1]):
            if dist_matrix[y, x] >= 0:
                distances[(y, x)] = dist_matrix[y, x]
    return distances


def _bfs_python(walkable, start_y, start_x, blocked_slots):
    from collections import deque

    distances = {(start_y, start_x): 0}
    queue = deque([(start_y, start_x, 0)])
    directions = [(0, 1), (0, -1), (1, 0), (-1, 0)]

    while queue:
        y, x, dist = queue.popleft()
        for dy, dx in directions:
            ny, nx = y + dy, x + dx
            if not (0 <= ny < walkable.shape[0] and 0 <= nx < walkable.shape[1]):
                continue
            if (ny, nx) in distances:
                continue
            if walkable[ny, nx] <= 0:
                continue
            if (nx, ny) in blocked_slots:
                distances[(ny, nx)] = dist + 1
                continue
            distances[(ny, nx)] = dist + 1
            queue.append((ny, nx, dist + 1))

    return distances


def get_closest_creature(creatures: List[GameWindowCreature],
                         coordinate: Tuple[int, int, int],
                         get_walkable_func,
                         debug: bool = False) -> Optional[GameWindowCreature]:
    if not creatures:
        return None

    local_walkable = get_walkable_func(coordinate)
    if local_walkable is None:
        return None

    if debug:
        print(f"[Pathfinding] Checking {len(creatures)} creatures at {coordinate}")

    creature_slots = set()
    for c in creatures:
        sx, sy = c.slot
        if 0 <= sx < GRID_WIDTH and 0 <= sy < GRID_HEIGHT:
            if not (sx == PLAYER_SLOT_X and sy == PLAYER_SLOT_Y):
                creature_slots.add((sx, sy))

    reachable_distances = bfs_flood_fill(
        local_walkable, PLAYER_SLOT_Y, PLAYER_SLOT_X, creature_slots
    )

    if debug:
        print(f"[Pathfinding] BFS found {len(reachable_distances)} reachable tiles")

    reachable_creatures = []
    for creature in creatures:
        slot_x, slot_y = creature.slot

        if not (0 <= slot_x < GRID_WIDTH and 0 <= slot_y < GRID_HEIGHT):
            continue
        if slot_x == PLAYER_SLOT_X and slot_y == PLAYER_SLOT_Y:
            continue

        min_dist = _get_min_distance_to_creature(
            slot_x, slot_y, reachable_distances, local_walkable
        )

        if min_dist >= float('inf'):
            if debug:
                print(f"[Pathfinding] {creature.name}: UNREACHABLE")
            continue

        manhattan = abs(slot_x - PLAYER_SLOT_X) + abs(slot_y - PLAYER_SLOT_Y)
        path_ratio_threshold = manhattan * 2 + 3

        if min_dist > path_ratio_threshold:
            if debug:
                print(f"[Pathfinding] {creature.name}: BLOCKED BY WALL")
            continue

        reachable_creatures.append((min_dist, manhattan, creature))
        if debug:
            print(f"[Pathfinding] {creature.name}: REACHABLE (dist={min_dist})")

    if not reachable_creatures:
        return None

    reachable_creatures.sort(key=lambda x: (x[0], x[1]))
    return reachable_creatures[0][2]


def has_target_to_creature(creatures: List[GameWindowCreature],
                           target_creature: GameWindowCreature,
                           coordinate: Tuple[int, int, int],
                           get_walkable_func) -> bool:
    """Validate that a path exists from the player to the target creature.

    Called each tick during combat to detect when a target moves behind a wall.
    Uses the same BFS + wall heuristic as get_closest_creature.
    """
    if target_creature is None:
        return False

    local_walkable = get_walkable_func(coordinate)
    if local_walkable is None:
        return False

    slot_x, slot_y = target_creature.slot
    if not (0 <= slot_x < GRID_WIDTH and 0 <= slot_y < GRID_HEIGHT):
        return False
    if slot_x == PLAYER_SLOT_X and slot_y == PLAYER_SLOT_Y:
        return False

    creature_slots = set()
    for c in creatures:
        sx, sy = c.slot
        if 0 <= sx < GRID_WIDTH and 0 <= sy < GRID_HEIGHT:
            if not (sx == PLAYER_SLOT_X and sy == PLAYER_SLOT_Y):
                creature_slots.add((sx, sy))

    reachable_distances = bfs_flood_fill(
        local_walkable, PLAYER_SLOT_Y, PLAYER_SLOT_X, creature_slots
    )

    min_dist = _get_min_distance_to_creature(
        slot_x, slot_y, reachable_distances, local_walkable
    )

    if min_dist >= float('inf'):
        return False

    manhattan = abs(slot_x - PLAYER_SLOT_X) + abs(slot_y - PLAYER_SLOT_Y)
    path_ratio_threshold = manhattan * 2 + 3

    return min_dist <= path_ratio_threshold


def _get_min_distance_to_creature(slot_x: int, slot_y: int,
                                  reachable_distances: Dict,
                                  local_walkable: np.ndarray) -> float:
    adjacent_tiles = [
        (slot_y - 1, slot_x),
        (slot_y + 1, slot_x),
        (slot_y, slot_x - 1),
        (slot_y, slot_x + 1),
    ]

    min_dist = float('inf')
    for ay, ax in adjacent_tiles:
        if not (0 <= ay < GRID_HEIGHT and 0 <= ax < GRID_WIDTH):
            continue
        if (ay, ax) in reachable_distances and local_walkable[ay, ax] > 0:
            min_dist = min(min_dist, reachable_distances[(ay, ax)])

    if (slot_y, slot_x) in reachable_distances:
        min_dist = min(min_dist, reachable_distances[(slot_y, slot_x)])

    return min_dist


# ---------------------------------------------------------------------------
# BL→GW attack cross-reference
# ---------------------------------------------------------------------------

def mark_attacked_from_bl(creatures: List[GameWindowCreature],
                           attacked_name: Optional[str],
                           color_gw: Optional[np.ndarray] = None,
                           slot_width: int = 64) -> None:
    """Override GW is_being_attacked using BL attack info.

    Grayscale pixel detection (76/166) fails on capture card (NV12 shifts values).
    R-channel on GW tile borders fails on lava (terrain is also red).
    Solution: BL detects attack reliably via R-channel on icon area (no terrain).
    Then we match the correct GW creature using relative R-excess comparison.
    """
    for c in creatures:
        c.is_being_attacked = False

    if not attacked_name:
        return

    candidates = [c for c in creatures if c.name == attacked_name]
    if not candidates:
        return

    if len(candidates) == 1:
        candidates[0].is_being_attacked = True
        return

    # Multiple same-name candidates: pick by highest R_excess at tile border.
    # The one WITH the attack border always has higher R_excess than without,
    # even on lava terrain (relative comparison, no absolute threshold needed).
    if color_gw is None or len(color_gw.shape) != 3:
        candidates[0].is_being_attacked = True
        return

    best = None
    best_score = -999.0
    for c in candidates:
        score = _get_tile_border_red_excess(color_gw, c, slot_width)
        if score > best_score:
            best_score = score
            best = c

    if best is not None:
        best.is_being_attacked = True


def _get_tile_border_red_excess(color_gw: np.ndarray,
                                 creature: GameWindowCreature,
                                 slot_width: int) -> float:
    """Compute mean R-channel excess at a creature's tile border."""
    gw_coord = creature.game_window_coordinate
    half = slot_width // 2
    border_x = max(0, gw_coord[0] - half)
    border_y = max(0, gw_coord[1] - half)

    region_end_y = min(border_y + slot_width, color_gw.shape[0])
    region_end_x = min(border_x + slot_width, color_gw.shape[1])

    if region_end_y <= border_y or region_end_x <= border_x:
        return -999.0

    region = color_gw[border_y:region_end_y, border_x:region_end_x]
    border_gap = 4 if slot_width == 64 else 2
    rh, rw = region.shape[:2]

    if rh < border_gap * 2 or rw < border_gap * 2:
        return -999.0

    samples = [region[0:border_gap, :].reshape(-1, 3)]
    if rh >= slot_width:
        samples.append(region[-border_gap:, :].reshape(-1, 3))
    samples.append(region[border_gap:rh - border_gap, 0:border_gap].reshape(-1, 3))
    if rw >= slot_width:
        samples.append(region[border_gap:rh - border_gap, -border_gap:].reshape(-1, 3))

    all_s = np.vstack(samples)
    r = all_s[:, 2].astype(np.int16)
    g = all_s[:, 1].astype(np.int16)
    b = all_s[:, 0].astype(np.int16)
    red_excess = r - np.maximum(g, b)
    return float(red_excess.mean())


# ---------------------------------------------------------------------------
# Filtering helpers
# ---------------------------------------------------------------------------

def get_target_creature(creatures: List[GameWindowCreature]) -> Optional[GameWindowCreature]:
    for c in creatures:
        if c.is_being_attacked:
            return c
    return None


def get_creatures_by_type(creatures: List[GameWindowCreature],
                          creature_type: str) -> List[GameWindowCreature]:
    return [c for c in creatures if c.creature_type == creature_type]


def get_monsters(creatures: List[GameWindowCreature]) -> List[GameWindowCreature]:
    return get_creatures_by_type(creatures, 'monster')


def get_players(creatures: List[GameWindowCreature]) -> List[GameWindowCreature]:
    return get_creatures_by_type(creatures, 'player')


# ---------------------------------------------------------------------------
# New features
# ---------------------------------------------------------------------------

def get_different_creatures_by_slots(previous: List[GameWindowCreature],
                                     current: List[GameWindowCreature],
                                     slots: List[Tuple[int, int]] = None) -> List[GameWindowCreature]:
    """Detect killed creatures by comparing previous vs current frame."""
    prev_slots = {c.slot: c for c in previous}
    curr_slots = {c.slot for c in current}

    killed = []
    for slot, creature in prev_slots.items():
        if slots is not None and slot not in slots:
            continue
        if slot not in curr_slots:
            killed.append(creature)

    return killed


def get_nearest_creatures_count(creatures: List[GameWindowCreature]) -> int:
    """Count creatures in 3x3 area around player (adjacent squares)."""
    count = 0
    for c in creatures:
        sx, sy = c.slot
        if abs(sx - PLAYER_SLOT_X) <= 1 and abs(sy - PLAYER_SLOT_Y) <= 1:
            if not (sx == PLAYER_SLOT_X and sy == PLAYER_SLOT_Y):
                count += 1
    return count


def is_trapped_by_creatures(creatures: List[GameWindowCreature],
                            coordinate: Tuple[int, int, int]) -> bool:
    try:
        from src.repositories.radar.config import (
            walkableFloorsSqms, COORDINATE_OFFSET_X, COORDINATE_OFFSET_Y
        )
        from scipy.spatial import distance

        floor = coordinate[2]
        pixel_x = coordinate[0] - COORDINATE_OFFSET_X
        pixel_y = coordinate[1] - COORDINATE_OFFSET_Y

        y_start = pixel_y - 1
        y_end = pixel_y + 2
        x_start = pixel_x - 1
        x_end = pixel_x + 2

        if y_start < 0 or y_end > walkableFloorsSqms.shape[1]:
            return False
        if x_start < 0 or x_end > walkableFloorsSqms.shape[2]:
            return False

        player_box = walkableFloorsSqms[floor, y_start:y_end, x_start:x_end].copy()

        for creature in creatures:
            creature_coord = creature.coordinate if hasattr(creature, 'coordinate') else None
            if creature_coord is None:
                continue

            dist = distance.euclidean(
                (creature_coord[0], creature_coord[1]),
                (coordinate[0], coordinate[1])
            )

            if dist >= 1.42:
                continue

            box_x = creature_coord[0] - coordinate[0] + 1
            box_y = creature_coord[1] - coordinate[1] + 1

            if 0 <= box_x < 3 and 0 <= box_y < 3:
                player_box[box_y, box_x] = 0

        surrounding_positions = [
            (0, 0), (0, 1), (0, 2),
            (1, 0),         (1, 2),
            (2, 0), (2, 1), (2, 2)
        ]

        for y, x in surrounding_positions:
            if player_box[y, x] == 1:
                return False

        return True

    except Exception as e:
        print(f"[GameWindow] Error checking trapped: {e}")
        return False

"""
Skills Core - Read values from skills window.

OPTIMIZED: Uses hash-based lookup for O(1) digit recognition instead of
template matching (10x faster - eliminates 10 template matches per value).
Falls back to template matching only if hash lookup fails.
"""
from typing import Optional, List, Tuple
import cv2
import numpy as np

from .config import images, numbers_hashes, minutes_or_hours_hashes, hashit
from .locators import get_skills_icon_position
from ...core.constants import CONFIDENCE_DIGIT


# Template matching confidence threshold (from constants)
DIGIT_CONFIDENCE = CONFIDENCE_DIGIT

# Cache for digit reading results (hash -> value)
# This prevents repeated template matching on identical regions
_digit_read_cache = {}
_CACHE_MAX_SIZE = 500  # Reduced to allow faster cache turnover


def clear_digit_cache():
    """Clear the digit reading cache. Call this periodically to ensure fresh reads."""
    global _digit_read_cache
    _digit_read_cache = {}

# JIT optimization for NMS (Non-Maximum Suppression)
try:
    from numba import njit

    @njit(cache=True)
    def _nms_jit(matches_digit: np.ndarray, matches_x: np.ndarray,
                 matches_conf: np.ndarray, num_matches: int,
                 min_distance: int) -> Tuple[np.ndarray, np.ndarray, np.ndarray, int]:
        """
        JIT-optimized Non-Maximum Suppression for digit detection.

        Speedup: 2-4x over pure Python version.

        Args:
            matches_digit: Array of detected digit values
            matches_x: Array of x positions
            matches_conf: Array of confidences
            num_matches: Number of valid matches
            min_distance: Minimum distance between detections (4 pixels)

        Returns:
            Tuple of (digits, x_positions, confidences, count)
        """
        if num_matches == 0:
            return matches_digit[:0], matches_x[:0], matches_conf[:0], 0

        # Sort indices by x position
        sorted_indices = np.argsort(matches_x[:num_matches])

        # Result arrays
        result_digit = np.zeros(num_matches, dtype=np.int32)
        result_x = np.zeros(num_matches, dtype=np.int32)
        result_conf = np.zeros(num_matches, dtype=np.float64)
        result_count = 0

        last_kept_x = -999

        i = 0
        while i < num_matches:
            idx = sorted_indices[i]
            current_x = matches_x[idx]

            # If this position is far enough from last kept
            if current_x - last_kept_x >= min_distance:
                # Find all matches within min_distance pixels
                best_idx = idx
                best_conf = matches_conf[idx]

                j = i + 1
                while j < num_matches:
                    next_idx = sorted_indices[j]
                    if matches_x[next_idx] - current_x >= min_distance:
                        break
                    if matches_conf[next_idx] > best_conf:
                        best_conf = matches_conf[next_idx]
                        best_idx = next_idx
                    j += 1

                # Keep the best match in this group
                result_digit[result_count] = matches_digit[best_idx]
                result_x[result_count] = matches_x[best_idx]
                result_conf[result_count] = matches_conf[best_idx]
                result_count += 1
                last_kept_x = matches_x[best_idx]

                i = j
            else:
                i += 1

        return result_digit, result_x, result_conf, result_count

    # Warm up JIT
    _dummy_d = np.array([0, 1], dtype=np.int32)
    _dummy_x = np.array([0, 10], dtype=np.int32)
    _dummy_c = np.array([0.9, 0.8], dtype=np.float64)
    _nms_jit(_dummy_d, _dummy_x, _dummy_c, 2, 4)

    NUMBA_NMS_AVAILABLE = True
except ImportError:
    NUMBA_NMS_AVAILABLE = False


def normalize_for_matching(img: np.ndarray) -> np.ndarray:
    """
    Normalize image for digit matching.

    Converts grayscale to binary where text pixels become white
    and everything else becomes black.
    Supports both screen capture (exact 126/192) and capture card (threshold-based).
    """
    # First try exact match (screen capture — fast path)
    exact = np.logical_or(img == 126, img == 192)
    if np.count_nonzero(exact) > 10:
        return np.where(exact, 255, 0).astype(np.uint8)
    # Fallback: threshold for capture card (text pixels are bright, >150)
    return np.where(img > 150, 255, 0).astype(np.uint8)


def normalize_for_hash(img: np.ndarray) -> np.ndarray:
    """
    Normalize image for hash-based lookup.

    Matches the format used in config.py for hash generation:
    - Text pixels (126, 192) become 192 (matching digit template format)
    - Everything else becomes black (0)
    """
    return np.where(
        np.logical_or(img == 126, img == 192), 192, 0
    ).astype(np.uint8)


def read_number_hash(region: np.ndarray) -> Optional[int]:
    """
    Read a number using O(1) hash lookup.

    OPTIMIZED: Builds hash from extracted digits at expected positions,
    matching the format used in config.py hash generation.

    Args:
        region: Grayscale region (8 pixels tall) containing the number

    Returns:
        Integer value, or None if no hash match
    """
    if region is None or region.shape[0] < 8:
        return None

    # Normalize the region to match digit template format (0/192)
    region_norm = normalize_for_hash(region)

    # Find columns with content
    cols_with_content = np.where(np.any(region_norm > 0, axis=0))[0]
    if len(cols_with_content) == 0:
        return None

    # Get the rightmost content position
    right_edge = cols_with_content[-1] + 1
    left_edge = cols_with_content[0]

    # Calculate content width
    content_width = right_edge - left_edge

    # Build a 22-pixel wide image matching config.py format
    # Digit positions: 0-6 (hundreds), 8-14 (tens), 16-22 (units)
    # Each digit is 6 pixels wide with 2-pixel gaps
    number_img = np.zeros((8, 22), dtype=np.uint8)

    # Extract just the content area
    content = region_norm[:8, left_edge:right_edge]

    # Right-align the content in the 22-pixel image
    # This matches how config.py positions digits (rightmost = units at 16-22)
    # Hash table only covers 0-999 (3 digits = 22px max)
    # If content is wider, skip hash lookup entirely
    if content_width > 22:
        return None

    start_pos = 22 - content_width
    number_img[:, start_pos:22] = content

    # Try hash lookup
    h = hashit(number_img)
    if h in numbers_hashes:
        return numbers_hashes[h]

    # Try with 1-pixel shifts to handle alignment differences
    for shift in [-1, 1, -2, 2]:
        if 0 <= shift + (22 - content_width) and shift + 22 <= 22:
            shifted_img = np.zeros((8, 22), dtype=np.uint8)
            start = max(0, 22 - content_width + shift)
            end = min(22, start + content_width)
            src_start = max(0, -shift)
            src_end = src_start + (end - start)
            if src_end <= content_width:
                shifted_img[:, start:end] = content[:, src_start:src_end]
                h = hashit(shifted_img)
                if h in numbers_hashes:
                    return numbers_hashes[h]

    return None


def read_time_hash(region: np.ndarray) -> Optional[Tuple[int, int]]:
    """
    Read a time value (HH:MM) using O(1) hash lookup.

    OPTIMIZED: Two hash computations instead of 20+ template matches.

    Args:
        region: Grayscale region containing time (HH:MM format)

    Returns:
        Tuple of (hours, minutes), or None if no hash match
    """
    if region is None or region.shape[0] < 8:
        return None

    # Normalize the region
    region_norm = normalize_for_hash(region)

    # Find columns with content
    cols_with_content = np.where(np.any(region_norm > 0, axis=0))[0]
    if len(cols_with_content) == 0:
        return None

    # Find the colon (gap in the middle) - it separates hours from minutes
    # Look for a gap of 2+ pixels (colon width)
    diffs = np.diff(cols_with_content)
    gaps = np.where(diffs > 2)[0]

    if len(gaps) == 0:
        # No colon found, might be just minutes
        return None

    # The colon gap separates hours and minutes
    # Find the largest gap (should be the colon)
    colon_gap_idx = gaps[np.argmax(diffs[gaps])]
    hours_end = cols_with_content[colon_gap_idx]
    minutes_start = cols_with_content[colon_gap_idx + 1]

    # Extract hours region (left of colon)
    hours_region = region_norm[:8, :hours_end + 1]
    # Extract minutes region (right of colon)
    minutes_region = region_norm[:8, minutes_start:]

    hours = None
    minutes = None

    # Try hash lookup for minutes (always 2 digits, 14 pixels wide)
    if minutes_region.shape[1] >= 6:
        # Pad to 14 pixels
        if minutes_region.shape[1] < 14:
            padded = np.zeros((8, 14), dtype=np.uint8)
            padded[:, 14 - minutes_region.shape[1]:] = minutes_region
            minutes_region = padded
        else:
            minutes_region = minutes_region[:, :14]

        h = hashit(minutes_region)
        if h in minutes_or_hours_hashes:
            minutes = minutes_or_hours_hashes[h]

    # Try hash lookup for hours (1-2 digits)
    if hours_region.shape[1] >= 6:
        # Pad to 14 pixels
        if hours_region.shape[1] < 14:
            padded = np.zeros((8, 14), dtype=np.uint8)
            padded[:, 14 - hours_region.shape[1]:] = hours_region
            hours_region = padded
        else:
            hours_region = hours_region[:, :14]

        h = hashit(hours_region)
        if h in minutes_or_hours_hashes:
            hours = minutes_or_hours_hashes[h]

    if minutes is not None:
        return (hours if hours is not None else 0, minutes)

    return None


def match_digit(region: np.ndarray, digit_templates: dict) -> Tuple[int, float]:
    """
    Find the best matching digit in a region using template matching.

    Args:
        region: Normalized grayscale region (8xN pixels)
        digit_templates: Dictionary of {digit: template} where templates are 8x6

    Returns:
        Tuple of (digit, confidence) or (-1, 0.0) if no match
    """
    best_digit = -1
    best_confidence = 0.0

    for digit, template in digit_templates.items():
        if template is None:
            continue

        # Normalize template to match region format
        template_norm = np.where(template > 0, 255, 0).astype(np.uint8)

        if region.shape[1] < template_norm.shape[1]:
            continue

        result = cv2.matchTemplate(region, template_norm, cv2.TM_CCOEFF_NORMED)
        _, max_val, _, _ = cv2.minMaxLoc(result)

        if max_val > best_confidence and max_val >= DIGIT_CONFIDENCE:
            best_digit = digit
            best_confidence = max_val

    return best_digit, best_confidence


def find_all_digits(region: np.ndarray, digit_templates: dict) -> List[Tuple[int, int, float]]:
    """
    Find all digits in a region from right to left.

    Uses Non-Maximum Suppression to handle overlapping detections.
    JIT optimized: Uses Numba-compiled NMS when available (2-4x faster).

    Args:
        region: Normalized grayscale region
        digit_templates: Dictionary of {digit: template}

    Returns:
        List of (digit, x_position, confidence) sorted by x position descending

    OPTIMIZED: NMS changed from O(m²) to O(m log m) using sorted position approach.
    """
    all_matches = []

    for digit, template in digit_templates.items():
        if template is None:
            continue

        # Binary templates (macOS: 0/192) get normalized to 0/255
        # Raw templates (win32: varied values) are used as-is
        unique_vals = len(set(int(v) for v in template.flatten()))
        if unique_vals <= 3:
            template_to_match = np.where(template > 0, 255, 0).astype(np.uint8)
        else:
            template_to_match = template

        if region.shape[1] < template_to_match.shape[1]:
            continue

        result = cv2.matchTemplate(region, template_to_match, cv2.TM_CCOEFF_NORMED)

        # Find all matches above threshold
        locations = np.where(result >= DIGIT_CONFIDENCE)

        for x in locations[1]:
            all_matches.append((digit, x, result[0, x]))

    if not all_matches:
        return []

    # JIT optimized NMS path
    if NUMBA_NMS_AVAILABLE and len(all_matches) > 5:
        # Convert to numpy arrays for JIT
        num_matches = len(all_matches)
        matches_digit = np.array([m[0] for m in all_matches], dtype=np.int32)
        matches_x = np.array([m[1] for m in all_matches], dtype=np.int32)
        matches_conf = np.array([m[2] for m in all_matches], dtype=np.float64)

        # Run JIT NMS
        result_digit, result_x, result_conf, count = _nms_jit(
            matches_digit, matches_x, matches_conf, num_matches, 4
        )

        # Convert back to list and sort by x descending
        found_digits = [
            (int(result_digit[i]), int(result_x[i]), float(result_conf[i]))
            for i in range(count)
        ]
        found_digits.sort(key=lambda d: d[1], reverse=True)
        return found_digits

    # Fallback: Pure Python NMS
    # Step 1: Sort by x position, then by confidence descending for same x
    all_matches.sort(key=lambda m: (m[1], -m[2]))

    # Step 2: Single pass through sorted matches, keeping best in each 4-pixel window
    found_digits = []
    last_kept_x = -999  # Track last kept position

    # Group by x position (within 4 pixels)
    i = 0
    while i < len(all_matches):
        current_x = all_matches[i][1]

        # If this position is far enough from last kept, find best in this group
        if current_x - last_kept_x >= 4:
            # Find all matches within 4 pixels of current_x
            group_end = i
            while group_end < len(all_matches) and all_matches[group_end][1] - current_x < 4:
                group_end += 1

            # Find best confidence in this group
            best = max(all_matches[i:group_end], key=lambda m: m[2])
            found_digits.append(best)
            last_kept_x = best[1]

            i = group_end
        else:
            i += 1

    # Sort by x position descending (rightmost first = units)
    found_digits.sort(key=lambda d: d[1], reverse=True)

    return found_digits


def _are_templates_binary(digit_templates):
    """Check if digit templates are binary (macOS: 0/192) or raw (win32)."""
    sample = next((t for t in digit_templates.values() if t is not None), None)
    if sample is None:
        return True
    return len(set(int(v) for v in sample.flatten())) <= 3


def _prepare_region_for_matching(region, digit_templates):
    """Prepare region for template matching based on template type.

    Binary templates (macOS) need normalized region.
    Raw templates (win32) work directly on raw pixels.
    """
    if _are_templates_binary(digit_templates):
        return normalize_for_matching(region)
    return region


def read_number_from_region(region: np.ndarray) -> int:
    """
    Read a numeric value from a region.

    OPTIMIZED: Uses O(1) hash lookup first, falls back to template matching
    only if hash lookup fails. Results are cached to avoid repeated matching
    on identical regions.

    Args:
        region: Grayscale region containing digits

    Returns:
        Integer value, or 0 if no digits found
    """
    global _digit_read_cache

    if region is None or region.size == 0:
        return 0

    # Compute hash for cache lookup
    region_hash = hashit(region)

    # Check cache first
    if region_hash in _digit_read_cache:
        return _digit_read_cache[region_hash]

    # FAST PATH: Try hash lookup first (O(1))
    result = read_number_hash(region)
    if result is not None:
        # Cache and return
        if len(_digit_read_cache) < _CACHE_MAX_SIZE:
            _digit_read_cache[region_hash] = result
        return result

    # SLOW PATH: Fall back to template matching
    digit_templates = images.get('digits', {})
    match_region = _prepare_region_for_matching(region, digit_templates)

    found = []
    if digit_templates:
        found = find_all_digits(match_region, digit_templates)

    if not found:
        if len(_digit_read_cache) < _CACHE_MAX_SIZE:
            _digit_read_cache[region_hash] = 0
        return 0

    # Build number from digits (rightmost = units)
    value = 0
    multiplier = 1

    for digit, _, _ in found:
        value += digit * multiplier
        multiplier *= 10

    # Cache the result
    if len(_digit_read_cache) < _CACHE_MAX_SIZE:
        _digit_read_cache[region_hash] = value

    return value


def read_time_from_region(region: np.ndarray) -> int:
    """
    Read a time value (HH:MM format) from a region.

    OPTIMIZED: Uses O(1) hash lookup first, falls back to template matching
    only if hash lookup fails. Results are cached to avoid repeated matching.

    Args:
        region: Grayscale region containing time digits

    Returns:
        Time in minutes
    """
    global _digit_read_cache

    if region is None or region.size == 0:
        return 0

    # Compute hash for cache lookup (use different key prefix to distinguish from numbers)
    region_hash = hashit(region) + 1000000000

    # Check cache first
    if region_hash in _digit_read_cache:
        return _digit_read_cache[region_hash]

    # FAST PATH: Try hash lookup first (O(1))
    result = read_time_hash(region)
    if result is not None:
        hours, minutes = result
        value = hours * 100 + minutes
        if len(_digit_read_cache) < _CACHE_MAX_SIZE:
            _digit_read_cache[region_hash] = value
        return value

    # SLOW PATH: Fall back to template matching
    digit_templates = images.get('digits', {})
    match_region = _prepare_region_for_matching(region, digit_templates)

    found = []
    if digit_templates:
        found = find_all_digits(match_region, digit_templates)

    if len(found) < 2:
        if len(_digit_read_cache) < _CACHE_MAX_SIZE:
            _digit_read_cache[region_hash] = 0
        return 0

    # Time format: HH:MM
    # found[0] = rightmost digit (minutes units)
    # found[1] = minutes tens
    # found[2] = hours units (if present)
    # found[3] = hours tens (if present)

    minutes = 0
    hours = 0

    if len(found) >= 1:
        minutes += found[0][0]  # Minutes units
    if len(found) >= 2:
        minutes += found[1][0] * 10  # Minutes tens
    if len(found) >= 3:
        hours += found[2][0]  # Hours units
    if len(found) >= 4:
        hours += found[3][0] * 10  # Hours tens

    value = hours * 100 + minutes

    # Cache the result
    if len(_digit_read_cache) < _CACHE_MAX_SIZE:
        _digit_read_cache[region_hash] = value

    return value


def find_value_region(screenshot: np.ndarray, skills_pos: tuple, skill_name: str) -> Optional[np.ndarray]:
    """
    Find and extract the region containing a skill value.

    Uses the skills panel layout to find where numbers should be.
    This is resolution-independent as it searches within the panel.
    """
    # Skills panel is approximately 170 pixels wide
    panel_width = 170
    panel_x = skills_pos[0]

    # Extract the full skills panel area
    panel_region = screenshot[skills_pos[1]:skills_pos[1] + 200, panel_x:panel_x + panel_width]

    # Find text blocks dynamically to determine y_offsets
    panel_binary = np.where(panel_region > 100, 255, 0).astype(np.uint8)
    text_blocks = []
    in_block = False
    block_start = 0
    for row_y in range(panel_binary.shape[0]):
        if np.count_nonzero(panel_binary[row_y]) > 10:
            if not in_block:
                block_start = row_y
                in_block = True
        else:
            if in_block:
                text_blocks.append(block_start)
                in_block = False

    # Find HP block: first block with y >= 85 that has 6 consecutive blocks after it
    hp_y = None
    for i in range(len(text_blocks) - 6):
        if text_blocks[i] < 85:
            continue
        consecutive = True
        for j in range(i, i + 6):
            if j + 1 >= len(text_blocks):
                consecutive = False
                break
            if text_blocks[j + 1] - text_blocks[j] > 20:
                consecutive = False
                break
        if consecutive:
            hp_y = text_blocks[i]
            # Calculate spacing between consecutive blocks
            spacing = (text_blocks[i + 1] - text_blocks[i])
            # Build y_offsets relative to HP position
            y_offsets = {
                'hp': hp_y,
                'mana': text_blocks[i + 1],
                'soul': text_blocks[i + 2],
                'capacity': text_blocks[i + 3],
                'speed': text_blocks[i + 4],
                'food': text_blocks[i + 5],
                'stamina': text_blocks[i + 6],
            }
            # Level is always block 1 (after title), Experience is block 2
            if len(text_blocks) > 2:
                y_offsets['level'] = text_blocks[1]
                y_offsets['experience'] = text_blocks[2]
            break

    if hp_y is None:
        return None

    if skill_name not in y_offsets or y_offsets.get(skill_name) is None:
        return None

    y = y_offsets[skill_name]

    if y + 8 > panel_region.shape[0]:
        return None

    # Use threshold >150 for finding text columns (works for both platforms:
    # macOS text=192, Windows text=180-240, background<100 in both)
    row = np.where(panel_region[y:y+8, :] > 150, 255, 0).astype(np.uint8)

    # Find where the value digits are (rightmost group of pixels)
    cols_with_pixels = np.where(np.any(row > 0, axis=0))[0]

    if len(cols_with_pixels) == 0:
        return None

    # Find gaps to separate label text from value digits
    # The largest gap is typically between the label and the value
    diffs = np.diff(cols_with_pixels)
    gaps = np.where(diffs > 3)[0]

    if len(gaps) > 0:
        # Find the largest gap (this separates label from value)
        gap_sizes = diffs[gaps]
        largest_gap_idx = gaps[np.argmax(gap_sizes)]
        value_start = cols_with_pixels[largest_gap_idx + 1]
    else:
        # No gaps, use the leftmost pixel
        value_start = cols_with_pixels[0]

    # Add 1 pixel padding to the left to avoid cutting first digit
    value_start = max(0, value_start - 1)

    # Find the end of the value digits: stop at the next large gap
    # after the value starts. This prevents picking up pixels from adjacent content.
    # Max gap between digits within a number is ~3px (inter-digit spacing).
    # Use panel width limit: value digits are within the right 40% of the panel.
    value_cols = cols_with_pixels[cols_with_pixels >= value_start]
    max_value_width = 45  # Max width for a skill value (HH:MM or 4+ digits)
    value_end_limit = value_start + max_value_width
    value_cols = value_cols[value_cols < value_end_limit]
    value_diffs = np.diff(value_cols) if len(value_cols) > 1 else np.array([])
    end_gaps = np.where(value_diffs > 10)[0]
    if len(end_gaps) > 0:
        value_end = value_cols[end_gaps[0]] + 2
    else:
        value_end = value_cols[-1] + 2

    # Extract the value region (only the digit area, not trailing content)
    return panel_region[y:y+8, value_start:value_end]


def get_skill_value(screenshot: np.ndarray, skill_name: str) -> Optional[int]:
    """
    Get a skill value from the skills window.

    This is the main function for reading numeric skill values.
    Works across different resolutions by finding the skills panel
    and extracting values using template matching.

    Args:
        screenshot: Grayscale screenshot
        skill_name: One of 'hp', 'mana', 'capacity', 'speed', 'food', 'stamina'

    Returns:
        Integer value, or None if skills window not found
    """
    skills_pos = get_skills_icon_position(screenshot)
    if skills_pos is None:
        return None

    # Find the value region for this skill
    value_region = find_value_region(screenshot, skills_pos, skill_name)
    if value_region is None:
        return 0

    # Read the value
    if skill_name in ('food', 'stamina'):
        return read_time_from_region(value_region)
    else:
        return read_number_from_region(value_region)


def get_hp(screenshot: np.ndarray) -> Optional[int]:
    """Get HP value from skills window."""
    return get_skill_value(screenshot, 'hp')


def get_mana(screenshot: np.ndarray) -> Optional[int]:
    """Get Mana value from skills window."""
    return get_skill_value(screenshot, 'mana')


def get_capacity(screenshot: np.ndarray) -> Optional[int]:
    """Get Capacity value from skills window."""
    return get_skill_value(screenshot, 'capacity')


def get_speed(screenshot: np.ndarray) -> Optional[int]:
    """Get Speed value from skills window."""
    return get_skill_value(screenshot, 'speed')


def get_food(screenshot: np.ndarray) -> Optional[int]:
    """Get food timer in minutes."""
    return get_skill_value(screenshot, 'food')


def get_stamina(screenshot: np.ndarray) -> Optional[int]:
    """Get Stamina in minutes from skills window."""
    return get_skill_value(screenshot, 'stamina')


def get_experience(screenshot: np.ndarray) -> Optional[int]:
    """Get Experience value from skills window."""
    return get_skill_value(screenshot, 'experience')

"""
Refill Core - NPC trade window detection and interaction.

Based on PyTibia's approach for GUI-based NPC trade automation.
"""
import time
from typing import Optional, Tuple

import cv2
import numpy as np
import pyautogui

from .config import (
    images,
    TRADE_WINDOW_WIDTH,
    TRADE_WINDOW_HEIGHT,
    ITEM_HEIGHT,
    ITEM_START_Y,
    MAX_VISIBLE_ITEMS,
    AMOUNT_INPUT_X,
    AMOUNT_INPUT_Y,
    BUY_BUTTON_X,
    BUY_BUTTON_Y,
)
from ...core.constants import CONFIDENCE_UI_DEFAULT, CONFIDENCE_UI_BUTTON, CONFIDENCE_TRADE_ITEM, JITTER_SIGMA_TYPING
from ...utils.jitter import jitter


def _locate(
    img: np.ndarray,
    template: np.ndarray,
    confidence: float = CONFIDENCE_UI_DEFAULT
) -> Optional[Tuple[int, int, int, int]]:
    """Locate template in image. Returns (x, y, w, h) or None."""
    if template is None or img is None:
        return None
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return None

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    _, max_val, _, max_loc = cv2.minMaxLoc(result)

    if max_val >= confidence:
        return (max_loc[0], max_loc[1], template.shape[1], template.shape[0])
    return None


def _locate_all(
    img: np.ndarray,
    template: np.ndarray,
    confidence: float = CONFIDENCE_UI_DEFAULT
) -> list:
    """Locate all occurrences of template in image."""
    if template is None or img is None:
        return []
    if template.shape[0] > img.shape[0] or template.shape[1] > img.shape[1]:
        return []

    result = cv2.matchTemplate(img, template, cv2.TM_CCOEFF_NORMED)
    locations = np.where(result >= confidence)

    matches = []
    for pt in zip(*locations[::-1]):
        matches.append((pt[0], pt[1], template.shape[1], template.shape[0]))

    return matches


# Cache for trade window position
_trade_window_cache: Optional[Tuple[int, int, int, int]] = None

# Cache for search box position (doesn't change during trade session)
_search_box_cache: Optional[Tuple[int, int]] = None


def get_trade_window_position(screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Find NPC trade window position.

    Args:
        screenshot: Grayscale screenshot

    Returns:
        (x, y, w, h) tuple or None if not found
    """
    global _trade_window_cache

    trade_bar = images['ui'].get('tradeBar')
    if trade_bar is None:
        # No template - try to find by trade window title text
        return None

    # Try cached position first
    if _trade_window_cache is not None:
        x, y, w, h = _trade_window_cache
        region = screenshot[y:y+h, x:x+w]
        if region.shape == trade_bar.shape:
            match = cv2.matchTemplate(region, trade_bar, cv2.TM_CCOEFF_NORMED)
            if cv2.minMaxLoc(match)[1] >= 0.9:
                return _trade_window_cache

    # Search for trade window
    pos = _locate(screenshot, trade_bar, confidence=CONFIDENCE_UI_DEFAULT)
    if pos is not None:
        _trade_window_cache = pos

    return pos


def is_trade_window_open(screenshot: np.ndarray) -> bool:
    """
    Check if NPC trade window is currently open.

    Tries multiple detection methods:
    1. Trade bar template (if configured)
    2. Ok button template (universal across all NPCs)
    """
    # Method 1: Try trade bar
    if get_trade_window_position(screenshot) is not None:
        return True

    # Method 2: Try Ok button (more universal)
    ok_button = images['ui'].get('okButton')
    if ok_button is not None:
        pos = _locate(screenshot, ok_button, confidence=CONFIDENCE_UI_DEFAULT)
        if pos is not None:
            return True

    return False


def _normalize_item_name(name: str) -> str:
    """
    Normalize item name to match template filename.

    Handles both camelCase and spaces:
    - "Great Health Potion" -> "greathealthpotion"
    - "greatHealthPotion" -> "greathealthpotion"
    """
    return name.lower().replace(' ', '').replace('_', '')


def find_item_in_trade(
    screenshot: np.ndarray,
    item_name: str
) -> Optional[Tuple[int, int]]:
    """
    Find item in trade window by name.

    Searches the FULL screenshot for the item template.
    This approach works on all resolutions.

    Args:
        screenshot: Grayscale screenshot
        item_name: Name of the item to find (e.g., "Great Health Potion")

    Returns:
        (x, y) center position of item or None if not found
    """
    # Verify trade window is open
    if not is_trade_window_open(screenshot):
        return None

    # Try to find item template by normalized name
    normalized_name = _normalize_item_name(item_name)
    item_template = None

    # Search through potions with normalized matching
    for template_name, template in images['potions'].items():
        if _normalize_item_name(template_name) == normalized_name:
            item_template = template
            break

    if item_template is None:
        print(f"[Refill] No template found for '{item_name}'")
        return None

    # Search in full screenshot - works on all resolutions
    item_pos = _locate(screenshot, item_template, confidence=CONFIDENCE_UI_BUTTON)
    if item_pos is not None:
        return (
            item_pos[0] + item_pos[2] // 2,
            item_pos[1] + item_pos[3] // 2
        )

    return None


def set_buy_amount(screenshot: np.ndarray, amount: int) -> bool:
    """
    Set the buy amount in trade window.

    Args:
        screenshot: Grayscale screenshot
        amount: Number of items to buy

    Returns:
        True if successful
    """
    trade_pos = get_trade_window_position(screenshot)
    if trade_pos is None:
        return False

    # Click on amount input field
    input_x = trade_pos[0] + AMOUNT_INPUT_X
    input_y = trade_pos[1] + AMOUNT_INPUT_Y

    # Triple-click to select all text
    pyautogui.click(input_x, input_y, clicks=3, interval=jitter(0.05))
    time.sleep(jitter(0.1))

    # Type the amount
    pyautogui.typewrite(str(amount), interval=jitter(0.02, JITTER_SIGMA_TYPING))
    time.sleep(jitter(0.1))

    return True


def click_buy_button(screenshot: np.ndarray) -> bool:
    """
    Click the buy/OK button in trade window using template matching.

    Args:
        screenshot: Grayscale screenshot

    Returns:
        True if successful
    """
    # Try buy button template first
    buy_button = images['ui'].get('buyButton')
    if buy_button is not None:
        pos = _locate(screenshot, buy_button, confidence=CONFIDENCE_UI_BUTTON)
        if pos is not None:
            click_x = pos[0] + pos[2] // 2
            click_y = pos[1] + pos[3] // 2
            pyautogui.click(click_x, click_y)
            return True

    # Fallback: try OK button template
    ok_button = images['ui'].get('okButton')
    if ok_button is not None:
        pos = _locate(screenshot, ok_button, confidence=CONFIDENCE_UI_BUTTON)
        if pos is not None:
            click_x = pos[0] + pos[2] // 2
            click_y = pos[1] + pos[3] // 2
            pyautogui.click(click_x, click_y)
            return True

    # Last fallback: use trade window position + fixed offset
    trade_pos = get_trade_window_position(screenshot)
    if trade_pos is None:
        return False

    button_x = trade_pos[0] + BUY_BUTTON_X
    button_y = trade_pos[1] + BUY_BUTTON_Y
    pyautogui.click(button_x, button_y)

    return True


def buy_item(
    screenshot: np.ndarray,
    item_name: str,
    quantity: int
) -> bool:
    """
    High-level function to buy items from NPC trade window.

    Assumes trade window is already open.

    Args:
        screenshot: Grayscale screenshot
        item_name: Name of item to buy
        quantity: Number of items to buy

    Returns:
        True if successful
    """
    if quantity <= 0:
        return True

    # Find item in trade window
    item_pos = find_item_in_trade(screenshot, item_name)
    if item_pos is None:
        print(f"[Refill] Item '{item_name}' not found in trade window")
        return False

    # Click on item to select it
    pyautogui.click(item_pos[0], item_pos[1])
    time.sleep(jitter(0.2))

    # Set amount
    if not set_buy_amount(screenshot, quantity):
        print(f"[Refill] Failed to set buy amount")
        return False

    # Click buy
    if not click_buy_button(screenshot):
        print(f"[Refill] Failed to click buy button")
        return False

    print(f"[Refill] Bought {quantity}x {item_name}")
    return True


def clear_trade_window_cache() -> None:
    """Clear the trade window position cache."""
    global _trade_window_cache, _trade_bottom_cache, _search_box_cache
    _trade_window_cache = None
    _trade_bottom_cache = None
    _search_box_cache = None


# Cache for trade bottom position
_trade_bottom_cache: Optional[Tuple[int, int, int, int]] = None


def get_trade_bottom_position(screenshot: np.ndarray) -> Optional[Tuple[int, int, int, int]]:
    """
    Find the bottom position of the trade window (using OK button).

    This is used as reference for search box and amount input positions.
    PyTibia approach: find OK button and return position BELOW the button.

    IMPORTANT: The returned Y position is at the BOTTOM of the OK button area
    (OK button top Y + button height + small offset), matching PyTibia's approach.
    This allows using the same offsets as PyTibia for other UI elements.

    Returns:
        (x, y, w, h) where y is below the OK button, or None if not found
    """
    global _trade_bottom_cache

    trade_pos = get_trade_window_position(screenshot)
    if trade_pos is None:
        return None

    ok_button = images['ui'].get('okButton')
    if ok_button is None:
        # Fallback: estimate bottom position based on trade window
        # Trade window is typically ~250 pixels tall
        return (trade_pos[0], trade_pos[1] + 256, TRADE_WINDOW_WIDTH, 2)

    # Search for OK button in trade window area
    trade_region = screenshot[
        trade_pos[1]:trade_pos[1] + 350,
        trade_pos[0]:trade_pos[0] + TRADE_WINDOW_WIDTH
    ]

    button_pos = _locate(trade_region, ok_button, confidence=CONFIDENCE_UI_BUTTON)
    if button_pos is not None:
        # PyTibia returns: (tradeBar_x, tradeBar_y + okButton_y + 26, 174, 2)
        # The X is always from the trade bar, not the OK button
        # The Y is below the OK button (okButton_y + 26)
        abs_pos = (
            trade_pos[0],  # Use trade bar X (like PyTibia)
            trade_pos[1] + button_pos[1] + 26,  # Below the OK button (PyTibia uses +26)
            174,  # PyTibia uses fixed width
            2
        )
        _trade_bottom_cache = abs_pos
        return abs_pos

    return None


def get_search_box_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """
    Find the search box position in the trade window using template matching.

    Uses caching to avoid position changes during a trade session.

    Returns:
        (x, y) center of search box, or None if not found
    """
    global _search_box_cache

    # Use cached position if available (search box doesn't move during trade)
    if _search_box_cache is not None:
        return _search_box_cache

    # Try template matching first
    search_template = images['ui'].get('searchBox')
    if search_template is not None:
        pos = _locate(screenshot, search_template, confidence=CONFIDENCE_UI_BUTTON)
        if pos is not None:
            # Return center of the search box
            result = (pos[0] + pos[2] // 2, pos[1] + pos[3] // 2)
            _search_box_cache = result
            return result

    # Fallback: use offset calculation
    bottom_pos = get_trade_bottom_position(screenshot)
    if bottom_pos is None:
        trade_pos = get_trade_window_position(screenshot)
        if trade_pos is None:
            return None
        result = (trade_pos[0] + 100, trade_pos[1] + 180)
        _search_box_cache = result
        return result

    bx, by = bottom_pos[0], bottom_pos[1]
    result = (bx + 80, by - 75)
    _search_box_cache = result
    return result


def get_amount_input_position(screenshot: np.ndarray) -> Optional[Tuple[int, int]]:
    """
    Find the amount input field position in the trade window using template matching.

    Returns:
        (x, y) center of amount input, or None if not found
    """
    # Try template matching first
    amount_template = images['ui'].get('amountInput')
    if amount_template is not None:
        pos = _locate(screenshot, amount_template, confidence=CONFIDENCE_UI_BUTTON)
        if pos is not None:
            # Return center of the amount input
            return (pos[0] + pos[2] // 2, pos[1] + pos[3] // 2)

    # Fallback: use offset calculation
    bottom_pos = get_trade_bottom_position(screenshot)
    if bottom_pos is None:
        trade_pos = get_trade_window_position(screenshot)
        if trade_pos is None:
            return None
        return (trade_pos[0] + AMOUNT_INPUT_X, trade_pos[1] + AMOUNT_INPUT_Y)

    bx, by = bottom_pos[0], bottom_pos[1]
    return (bx + 115, by - 42)


def find_item_with_search(
    screenshot: np.ndarray,
    item_name: str,
    max_retries: int = 3
) -> Optional[Tuple[int, int]]:
    """
    Find and click item using the search box.

    Uses template matching to find UI elements:
    1. Find and click search box
    2. Clear previous search (triple-click + backspace)
    3. Type item name
    4. Wait for filtering
    5. Locate item by template

    Args:
        screenshot: Grayscale screenshot
        item_name: Name of item to find (e.g., "Strong Mana Potion")
        max_retries: Number of retry attempts

    Returns:
        (x, y) position of item, or None if not found
    """
    from mss import mss

    # Extract search term before loop
    search_term = item_name.lower().replace(' potion', '').strip()
    print(f"[Refill] Searching for '{item_name}' (term: '{search_term}')")

    for attempt in range(max_retries):
        # Get fresh screenshot at start of each attempt
        with mss() as sct:
            screenshot = np.array(sct.grab(sct.monitors[1]))
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)

        # Find search box using template matching
        search_pos = get_search_box_position(screenshot)
        if search_pos is None:
            print(f"[Refill] Search box not found (attempt {attempt + 1}/{max_retries})")
            time.sleep(jitter(0.5))
            continue

        # Double-click on search box to focus and select text
        pyautogui.click(search_pos[0], search_pos[1], clicks=2)
        time.sleep(jitter(0.5))

        # Clear search box
        pyautogui.press('backspace')
        time.sleep(jitter(0.3))

        # Click to position cursor
        pyautogui.click(search_pos[0], search_pos[1])
        time.sleep(jitter(0.5))

        # Type search term using pyautogui
        print(f"[Refill] Typing search term: '{search_term}'")
        pyautogui.write(search_term, interval=jitter(0.05, JITTER_SIGMA_TYPING))
        time.sleep(jitter(1.5))  # Wait for search to filter

        # Capture new screenshot after filtering
        with mss() as sct:
            new_screenshot = np.array(sct.grab(sct.monitors[1]))
            new_screenshot = cv2.cvtColor(new_screenshot, cv2.COLOR_BGRA2GRAY)

        # Try to find item using template matching
        item_pos = find_item_in_trade(new_screenshot, item_name)
        if item_pos is not None:
            print(f"[Refill] Found '{item_name}' at {item_pos}")
            return item_pos

        print(f"[Refill] Item '{item_name}' not found after search (attempt {attempt + 1}/{max_retries})")
        time.sleep(jitter(0.5))

        # Get new screenshot for next attempt
        with mss() as sct:
            screenshot = np.array(sct.grab(sct.monitors[1]))
            screenshot = cv2.cvtColor(screenshot, cv2.COLOR_BGRA2GRAY)

    return None


def clear_search_box(screenshot: np.ndarray) -> bool:
    """
    Clear the search box in the trade window.

    Uses template matching to find search box, then clears it.

    Args:
        screenshot: Grayscale screenshot

    Returns:
        True if successful
    """
    search_pos = get_search_box_position(screenshot)
    if search_pos is None:
        print("[Refill] Could not find search box to clear")
        return False

    # Click on search box to focus
    pyautogui.click(search_pos[0], search_pos[1])
    time.sleep(jitter(0.2))

    # Triple-click to select all text
    pyautogui.click(search_pos[0], search_pos[1], clicks=3, interval=jitter(0.05))
    time.sleep(jitter(0.2))

    # Delete selected text
    pyautogui.press('backspace')
    time.sleep(jitter(0.2))

    print("[Refill] Search box cleared")
    return True


def close_trade_window() -> None:
    """Close the trade window by pressing Escape."""
    pyautogui.press('escape')
    time.sleep(jitter(0.2))
    clear_trade_window_cache()


def buy_item_with_search(
    screenshot: np.ndarray,
    item_name: str,
    quantity: int
) -> bool:
    """
    Buy items using search box approach (PyTibia style).

    Complete flow:
    1. Find item using search box
    2. Click on item
    3. Set quantity
    4. Click buy/OK
    5. Clear search box

    Args:
        screenshot: Grayscale screenshot
        item_name: Name of item to buy
        quantity: Number of items to buy

    Returns:
        True if successful
    """
    from mss import mss

    if quantity <= 0:
        return True

    # Find and click item using search
    item_pos = find_item_with_search(screenshot, item_name)
    if item_pos is None:
        print(f"[Refill] Failed to find '{item_name}' using search")
        return False

    # Click on item
    pyautogui.click(item_pos[0], item_pos[1])
    time.sleep(jitter(0.3))

    # Capture new screenshot for setting amount
    with mss() as sct:
        new_screenshot = np.array(sct.grab(sct.monitors[1]))
        new_screenshot = cv2.cvtColor(new_screenshot, cv2.COLOR_BGRA2GRAY)

    # Set amount - clear field first, then type
    amount_pos = get_amount_input_position(new_screenshot)
    if amount_pos is not None:
        # Click on amount field
        pyautogui.click(amount_pos[0], amount_pos[1])
        time.sleep(jitter(0.1))
        # Select all with Ctrl+A
        pyautogui.hotkey('ctrl', 'a')
        time.sleep(jitter(0.1))
        # Delete selected text
        pyautogui.press('delete')
        time.sleep(jitter(0.1))
        # Type the new amount
        pyautogui.typewrite(str(quantity), interval=jitter(0.02, JITTER_SIGMA_TYPING))
        time.sleep(jitter(0.2))
    else:
        # Fallback to old method
        set_buy_amount(new_screenshot, quantity)

    # Click buy button
    click_buy_button(new_screenshot)
    time.sleep(jitter(0.5))

    # Clear search box for next item
    with mss() as sct:
        final_screenshot = np.array(sct.grab(sct.monitors[1]))
        final_screenshot = cv2.cvtColor(final_screenshot, cv2.COLOR_BGRA2GRAY)

    clear_search_box(final_screenshot)
    time.sleep(jitter(0.3))

    print(f"[Refill] Bought {quantity}x {item_name}")
    return True

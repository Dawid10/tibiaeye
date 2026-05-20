"""Chat repository - loot message detection and parsing.

Pure functions at module level + thin ChatRepository facade.
"""
import re
from typing import Dict, List, Optional, Tuple

import cv2
import numpy as np

from .config import (
    GrayImage, LOOT_OF_PREFIX,
    load_loot_of_template, load_nothing_template, load_tab_templates,
)
from .locators import get_loot_tab_position, get_chat_content_area, get_loot_lines
from .extractors import extract_all_loot_texts
from ...utils.hash import hashit
from ...core.constants import CHAT_MAX_LOOT_LINES


# ============================================
# Pure functions
# ============================================

def normalize_gray_pixels(image: GrayImage) -> GrayImage:
    """Threshold to binary for consistent hashing across screenshots.

    Chat text is light (>100) on dark background (<100).
    Thresholding eliminates sub-pixel rendering variations that cause
    different hashes for the same line between frames.
    """
    _, binary = cv2.threshold(image, 100, 255, cv2.THRESH_BINARY)
    return binary


def detect_new_loot_lines(
    line_hashes: List[int],
    previous_hashes: List[int],
) -> Tuple[List[int], List[int]]:
    """Compare line hashes with previous cache to find new lines.

    Returns:
        (new_line_indices, updated_hashes)
        - new_line_indices: indices into line_hashes that are new
        - updated_hashes: the new hash list to cache for next call
    """
    previous_set = set(previous_hashes)
    new_indices = []
    for i, h in enumerate(line_hashes):
        if h not in previous_set:
            new_indices.append(i)

    # Keep last N hashes for comparison
    updated = line_hashes[-CHAT_MAX_LOOT_LINES:]
    return new_indices, updated


def parse_loot_message(text: str) -> Optional[Dict]:
    """Parse a loot message into structured data.

    Formats:
        "Loot of a demon: a demon horn, 2 platinum coins, a small ruby."
        "Loot of a rat: nothing"
        "Loot of Hellgorak: a boots of haste."

    Returns:
        {'creature': str, 'items': [{'name': str, 'quantity': int}, ...]}
        or None if text doesn't match loot format.
    """
    if not text:
        return None

    # Match "Loot of [a|an] <creature>: <items>" (anywhere in text, timestamp may precede)
    pattern = r'[Ll]oot\s+of\s+(?:an?\s+)?(.+?):\s*(.+)'
    match = re.search(pattern, text)
    if not match:
        return None

    creature = match.group(1).strip()
    items_text = match.group(2).strip()

    # Clean OCR artifacts from chat border/scrollbar
    items_text = re.sub(r'[\[\]|{}]+$', '', items_text).strip()
    items_text = re.sub(r'\s+[\[\]|{})\s]+$', '', items_text).strip()
    # Remove trailing junk after last period (e.g. "meat. [J" -> "meat.")
    period_match = re.search(r'\.\s+\S{1,4}$', items_text)
    if period_match:
        items_text = items_text[:period_match.start() + 1]

    # "nothing" means empty loot
    if items_text.lower() in ('nothing', 'nothing.'):
        return {'creature': creature, 'items': []}

    items = _parse_items(items_text)
    return {'creature': creature, 'items': items}


def _parse_items(items_text: str) -> List[Dict]:
    """Parse comma-separated item list.

    Handles:
        "a demon horn" → quantity=1, name="demon horn"
        "2 platinum coins" → quantity=2, name="platinum coins"
        "an ancient shield" → quantity=1, name="ancient shield"
    """
    # Remove trailing period
    items_text = items_text.rstrip('.')

    raw_items = [item.strip() for item in items_text.split(',')]
    parsed = []

    for raw in raw_items:
        if not raw:
            continue
        item = _parse_single_item(raw)
        if item:
            parsed.append(item)

    return parsed


def _parse_single_item(text: str) -> Optional[Dict]:
    """Parse a single item like '2 platinum coins' or 'a demon horn'."""
    text = text.strip()
    # Clean OCR artifacts from item name
    text = re.sub(r'[\[\]|{}]+$', '', text).strip()
    text = text.rstrip('.')
    if not text:
        return None

    # "a <item>" or "an <item>"
    article_match = re.match(r'^an?\s+(.+)$', text, re.IGNORECASE)
    if article_match:
        return {'name': article_match.group(1).strip(), 'quantity': 1}

    # "<number> <item>"
    quantity_match = re.match(r'^(\d+)\s+(.+)$', text)
    if quantity_match:
        return {
            'name': quantity_match.group(2).strip(),
            'quantity': int(quantity_match.group(1)),
        }

    # Fallback: treat entire text as item name
    return {'name': text, 'quantity': 1}


# ============================================
# ChatRepository facade
# ============================================

def extract_timestamp(text: str) -> str:
    """Extract timestamp prefix from OCR text.

    Tibia chat lines start with HH:MM or HH:MM:SS.
    Example: "13:04:56 Loot of a rotworm: 10 gold coins."
    """
    if not text:
        return ''
    match = re.match(r'(\d{1,2}:\d{2}(?::\d{2})?)', text.strip())
    if match:
        return match.group(1)
    return ''


def _message_key(msg: Dict, timestamp: str = '') -> str:
    """Create a stable dedup key from a parsed loot message.

    Includes timestamp so identical loots at different times are both tracked.
    Key format: "13:04:56|rotworm|gold coins:10|lump of dirt:1"
    """
    items_part = '|'.join(
        f"{i['name']}:{i['quantity']}" for i in sorted(msg.get('items', []), key=lambda x: x['name'])
    )
    return f"{timestamp}|{msg['creature']}|{items_part}"


class ChatRepository:
    """Facade for chat loot message detection. Delegates to pure functions."""

    def __init__(self):
        self._loot_of_template = load_loot_of_template()
        self._nothing_template = load_nothing_template()
        self._tab_templates = load_tab_templates()
        self._seen_text_keys: List[str] = []
        self._previous_hashes: List[int] = []
        self._enabled = self._loot_of_template is not None and len(self._tab_templates) > 0
        if not self._enabled:
            print("[Chat] Loot tracking disabled (missing templates in src/repositories/chat/images/)")

    @property
    def is_enabled(self) -> bool:
        return self._enabled

    def get_new_loot_messages(self, screenshot: GrayImage) -> List[Dict]:
        """Get new loot messages since last call.

        Uses image hashing to skip OCR on lines already seen.
        Only runs Tesseract on genuinely new lines (hash not in cache).

        Returns list of parsed loot dicts:
            [{'creature': str, 'items': [{'name': str, 'quantity': int}]}]
        """
        if not self._enabled:
            return []

        if screenshot is None:
            return []

        tab_pos = get_loot_tab_position(screenshot, self._tab_templates)
        if tab_pos is None:
            return []

        content_area = get_chat_content_area(screenshot, tab_pos)
        if content_area is None:
            return []

        cx, cy, cw, ch = content_area
        chat_image = screenshot[cy:cy + ch, cx:cx + cw]

        loot_lines = get_loot_lines(chat_image, self._loot_of_template)
        if not loot_lines:
            return []

        # Hash each line image to detect new lines without OCR
        line_hashes = []
        for line_image, _bbox in loot_lines:
            normalized = normalize_gray_pixels(line_image)
            line_hashes.append(hashit(normalized))

        new_indices, updated_hashes = detect_new_loot_lines(
            line_hashes, self._previous_hashes)
        self._previous_hashes = updated_hashes

        if not new_indices:
            return []

        # OCR only the new lines
        new_lines = [loot_lines[i] for i in new_indices]
        texts = extract_all_loot_texts(new_lines)

        # Parse and dedup by text content (handles OCR inconsistencies)
        previous_set = set(self._seen_text_keys)
        new_messages = []
        current_keys = list(self._seen_text_keys)

        for text in texts:
            parsed = parse_loot_message(text)
            if not parsed or not parsed['items']:
                continue
            timestamp = extract_timestamp(text)
            key = _message_key(parsed, timestamp)
            current_keys.append(key)
            if key not in previous_set:
                new_messages.append(parsed)

        self._seen_text_keys = current_keys[-CHAT_MAX_LOOT_LINES:]

        return new_messages


# ============================================
# Singleton
# ============================================

_chat_repository = None


def get_chat_repository() -> ChatRepository:
    """Get singleton ChatRepository instance."""
    global _chat_repository
    if _chat_repository is None:
        _chat_repository = ChatRepository()
    return _chat_repository

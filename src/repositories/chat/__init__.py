"""Chat Repository - loot message detection from chat channel."""
from .core import (
    ChatRepository,
    get_chat_repository,
    parse_loot_message,
    detect_new_loot_lines,
    normalize_gray_pixels,
    extract_timestamp,
    _message_key,
)

__all__ = [
    'ChatRepository',
    'get_chat_repository',
    'parse_loot_message',
    'detect_new_loot_lines',
    'normalize_gray_pixels',
    '_message_key',
]

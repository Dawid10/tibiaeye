"""Connection repository - disconnect/login screen detection."""
from .core import (
    is_disconnected,
    is_login_screen,
    is_character_list,
    is_game_loaded,
    get_ok_button_position,
    get_login_button_position,
    get_email_field_position,
    get_password_field_position,
    get_character_row_positions,
    get_enter_game_button_position,
    ConnectionRepository,
)

__all__ = [
    'is_disconnected',
    'is_login_screen',
    'is_character_list',
    'is_game_loaded',
    'get_ok_button_position',
    'get_login_button_position',
    'get_email_field_position',
    'get_password_field_position',
    'get_character_row_positions',
    'get_enter_game_button_position',
    'ConnectionRepository',
]

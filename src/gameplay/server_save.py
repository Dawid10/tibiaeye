"""Server Save - detection and state management for daily server save."""
from datetime import datetime, timedelta, timezone

from ..core.constants import SERVER_SAVE_WINDOW_MINUTES, SERVER_SAVE_RECONNECT_EXTRA_WAIT


# CET = UTC+1 (Tibia servers run on CET)
CET = timezone(timedelta(hours=1))


def _parse_save_time(time_str: str) -> tuple:
    """Parse HH:MM string into (hour, minute)."""
    parts = time_str.strip().split(':')
    return int(parts[0]), int(parts[1])


def get_server_save_state(server_save_time: str, window_minutes: int = SERVER_SAVE_WINDOW_MINUTES) -> str:
    """Get current server save state.

    Returns:
        'normal': no server save activity
        'approaching': within window_minutes before save
        'active': save_time to save_time + 3 min
        'recovering': save_time + 3 min to save_time + 5 min
    """
    hour, minute = _parse_save_time(server_save_time)
    now = datetime.now(CET)
    save_today = now.replace(hour=hour, minute=minute, second=0, microsecond=0)

    diff_seconds = (now - save_today).total_seconds()

    # 'active': 0 to 3 minutes after save time
    if 0 <= diff_seconds < 180:
        return 'active'

    # 'recovering': 3 to 5 minutes after save time
    if 180 <= diff_seconds < 300:
        return 'recovering'

    # 'approaching': within window_minutes before save time
    if -window_minutes * 60 <= diff_seconds < 0:
        return 'approaching'

    return 'normal'


def is_server_save_window(server_save_time: str, window_minutes: int = SERVER_SAVE_WINDOW_MINUTES) -> bool:
    """Check if current time is within the server save window (approaching, active, or recovering)."""
    return get_server_save_state(server_save_time, window_minutes) != 'normal'


def get_reconnect_extra_wait() -> float:
    """Get extra wait time before reconnecting after server save kick."""
    return SERVER_SAVE_RECONNECT_EXTRA_WAIT

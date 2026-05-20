"""Reconnect Detector - state machine for auto-reconnect after disconnect."""
import time
from enum import Enum
from typing import Any, Dict, Optional

import pyautogui

from ..core.constants import (
    RECONNECT_CHECK_FREQUENCY,
    RECONNECT_DELAY_CLICK_OK,
    RECONNECT_DELAY_BEFORE_LOGIN,
    RECONNECT_DELAY_AFTER_LOGIN,
    RECONNECT_DELAY_CHAR_SELECT,
    RECONNECT_DELAY_GAME_LOAD,
    RECONNECT_DELAY_BETWEEN_RETRIES,
    RECONNECT_MAX_RETRIES,
    RECONNECT_TYPEWRITE_INTERVAL,
    RECONNECT_CONSECUTIVE_FAILURES,
    RECONNECT_INPUT_FIELD_OFFSET_X,
    JITTER_SIGMA_TYPING,
)
from ..utils.jitter import jitter
from ..repositories.connection import (
    is_disconnected,
    is_login_screen,
    is_character_list,
    is_game_loaded,
    get_ok_button_position,
    get_login_button_position,
    get_email_field_position,
    get_password_field_position,
    get_enter_game_button_position,
)
from ..utils.alerts import get_alert_system
from ..hardware.patch import use_software_input


class ReconnectState(Enum):
    CONNECTED = "CONNECTED"
    DISCONNECTED = "DISCONNECTED"
    CLICKING_OK = "CLICKING_OK"
    WAITING_LOGIN_SCREEN = "WAITING_LOGIN_SCREEN"
    LOGGING_IN = "LOGGING_IN"
    WAITING_CHARACTER_LIST = "WAITING_CHARACTER_LIST"
    SELECTING_CHARACTER = "SELECTING_CHARACTER"
    WAITING_GAME_LOAD = "WAITING_GAME_LOAD"


class ReconnectDetector:
    """State machine for detecting disconnects and performing auto-reconnect."""

    def __init__(self):
        self._state = ReconnectState.CONNECTED
        self._retry_count = 0
        self._max_retries = RECONNECT_MAX_RETRIES
        self._delay_between_retries = RECONNECT_DELAY_BETWEEN_RETRIES
        self._last_state_change = 0.0
        self._enabled = False
        self._email = ""
        self._password = ""
        self._session_logger = None
        self._telemetry = None
        self._disconnect_time = 0.0
        self._consecutive_failures = 0
        self._screen = None
        self._server_save_mode = False

    def configure(self, reconnect_config: Dict[str, Any]) -> None:
        """Configure reconnect from GUI settings."""
        self._enabled = reconnect_config.get('enabled', False)
        self._email = reconnect_config.get('email', '')
        self._password = reconnect_config.get('password', '')
        self._max_retries = reconnect_config.get('maxRetries', RECONNECT_MAX_RETRIES)
        self._delay_between_retries = reconnect_config.get('delayBetweenRetries', RECONNECT_DELAY_BETWEEN_RETRIES)

    def set_session_logger(self, session_logger) -> None:
        """Set session logger for detailed logging."""
        self._session_logger = session_logger

    def set_telemetry(self, telemetry) -> None:
        """Set telemetry client for reconnect event tracking."""
        self._telemetry = telemetry

    def _track(self, event_type: str, data: dict) -> None:
        """Send reconnect telemetry event if client is available."""
        if self._telemetry is None:
            return
        self._telemetry.track_event(event_type, data)

    @property
    def is_connected(self) -> bool:
        return self._state == ReconnectState.CONNECTED

    @property
    def is_reconnecting(self) -> bool:
        return self._state != ReconnectState.CONNECTED

    @property
    def state(self) -> ReconnectState:
        return self._state

    @property
    def retry_count(self) -> int:
        return self._retry_count

    def set_server_save_mode(self, active: bool) -> None:
        """When True, increase tolerance for frozen screens during server save."""
        self._server_save_mode = active

    def report_middleware_failure(self) -> None:
        """Called when a middleware fails to extract data (secondary detection)."""
        if not self._enabled:
            return
        if self._state != ReconnectState.CONNECTED:
            return
        if self._server_save_mode:
            return
        self._consecutive_failures += 1

    def report_middleware_success(self) -> None:
        """Called when a middleware successfully extracts data."""
        self._consecutive_failures = 0

    def check_and_reconnect(self, context: Dict[str, Any], tick_count: int) -> bool:
        """Check for disconnect and handle reconnect flow.

        Returns True if reconnecting (caller should skip gameplay).
        """
        if not self._enabled:
            return False

        if tick_count % RECONNECT_CHECK_FREQUENCY != 0 and self._state == ReconnectState.CONNECTED:
            return False

        screenshot = context.get('screenshot')
        if screenshot is None:
            return False

        if self._state == ReconnectState.CONNECTED:
            return self._handle_connected(screenshot)

        if self._state == ReconnectState.DISCONNECTED:
            self._handle_disconnected(screenshot)
            return True

        if self._state == ReconnectState.CLICKING_OK:
            self._handle_clicking_ok(screenshot)
            return True

        if self._state == ReconnectState.WAITING_LOGIN_SCREEN:
            self._handle_waiting_login_screen(screenshot)
            return True

        if self._state == ReconnectState.LOGGING_IN:
            self._handle_logging_in(screenshot)
            return True

        if self._state == ReconnectState.WAITING_CHARACTER_LIST:
            self._handle_waiting_character_list(screenshot)
            return True

        if self._state == ReconnectState.SELECTING_CHARACTER:
            self._handle_selecting_character(screenshot)
            return True

        if self._state == ReconnectState.WAITING_GAME_LOAD:
            self._handle_waiting_game_load(screenshot)
            return True

        return False

    def _handle_connected(self, screenshot) -> bool:
        """Check if we got disconnected."""
        if is_disconnected(screenshot):
            self._transition(ReconnectState.DISCONNECTED)
            self._disconnect_time = time.time()
            self._log("Disconnect dialog detected!")
            get_alert_system().alert('warning', "Disconnected! Starting auto-reconnect...")
            self._track("disconnect", {"reason": "disconnect_dialog"})
            return True

        if is_login_screen(screenshot):
            self._transition(ReconnectState.WAITING_LOGIN_SCREEN)
            self._disconnect_time = time.time()
            self._log("Login screen detected! Starting auto-reconnect...")
            get_alert_system().alert('warning', "Login screen detected! Starting auto-reconnect...")
            self._track("disconnect", {"reason": "login_screen"})
            return True

        if is_character_list(screenshot):
            self._transition(ReconnectState.WAITING_CHARACTER_LIST)
            self._disconnect_time = time.time()
            self._log("Character list detected! Selecting character...")
            self._track("disconnect", {"reason": "character_list"})
            return True

        return False

    def _handle_disconnected(self, screenshot) -> None:
        """Click OK on disconnect dialog."""
        if not self._wait_elapsed(RECONNECT_DELAY_CLICK_OK):
            return

        ok_pos = get_ok_button_position(screenshot)
        if ok_pos is None:
            if is_login_screen(screenshot):
                self._transition(ReconnectState.WAITING_LOGIN_SCREEN)
                self._log("Already on login screen, skipping OK click")
                return
            self._retry_or_give_up("OK button not found")
            return

        pyautogui.click(ok_pos[0], ok_pos[1])
        self._log(f"Clicked OK button at {ok_pos}")
        self._transition(ReconnectState.CLICKING_OK)

    def _handle_clicking_ok(self, screenshot) -> None:
        """Wait for login screen after clicking OK."""
        if not self._wait_elapsed(RECONNECT_DELAY_BEFORE_LOGIN):
            return

        if is_login_screen(screenshot):
            self._transition(ReconnectState.WAITING_LOGIN_SCREEN)
            self._log("Login screen appeared")
            return

        if is_disconnected(screenshot):
            self._transition(ReconnectState.DISCONNECTED)
            self._log("Disconnect dialog still visible, retrying OK click")
            return

        self._retry_or_give_up("Login screen did not appear after clicking OK")

    def _verify_login_screen(self, screenshot) -> bool:
        """SAFETY: verify we are on the login screen before typing credentials."""
        if not is_login_screen(screenshot):
            self._log("SAFETY: login screen NOT detected, aborting credential input!", "WARNING")
            return False
        return True

    def _take_fresh_screenshot(self) -> object:
        """Take a fresh screenshot for safety verification."""
        if self._screen is None:
            from ..core import get_screen_capture
            self._screen = get_screen_capture()
        return self._screen.capture(grayscale=True)

    def _handle_waiting_login_screen(self, screenshot) -> None:
        """Type credentials and click login."""
        if not self._wait_elapsed(RECONNECT_DELAY_BEFORE_LOGIN):
            return

        if not self._email or not self._password:
            self._log("Email or password not configured, cannot auto-login")
            self._give_up("Missing credentials")
            return

        # SAFETY: fresh screenshot to confirm we are still on login screen
        fresh = self._take_fresh_screenshot()
        if not self._verify_login_screen(fresh):
            self._transition(ReconnectState.CONNECTED)
            return

        email_pos = get_email_field_position(fresh)
        if email_pos is None:
            self._retry_or_give_up("Email field not found")
            return

        # Switch to software input (pyautogui/Quartz) for the entire login
        # interaction. Arduino HID drops shifted characters (@, *, uppercase)
        # on macOS with non-US input sources.
        with use_software_input():
            self._type_credentials_and_login(fresh, email_pos)

    def _type_credentials_and_login(self, fresh, email_pos) -> None:
        """Type email/password and click login using software input (pyautogui).

        Called inside use_software_input() context so all pyautogui calls
        go through the original OS-level functions, not Arduino HID.
        """
        input_x = email_pos[0] + RECONNECT_INPUT_FIELD_OFFSET_X
        input_y = email_pos[1]
        pyautogui.click(input_x, input_y, clicks=3)
        time.sleep(jitter(0.2))

        fresh = self._take_fresh_screenshot()
        if not self._verify_login_screen(fresh):
            self._transition(ReconnectState.CONNECTED)
            return

        pyautogui.write(self._email, interval=jitter(RECONNECT_TYPEWRITE_INTERVAL, JITTER_SIGMA_TYPING))
        self._log("Typed email")

        time.sleep(jitter(0.3))

        password_pos = get_password_field_position(fresh)
        if password_pos is None:
            pyautogui.press('tab')
            time.sleep(jitter(0.2))
        else:
            pyautogui.click(
                password_pos[0] + RECONNECT_INPUT_FIELD_OFFSET_X,
                password_pos[1],
                clicks=3,
            )
            time.sleep(jitter(0.2))

        fresh = self._take_fresh_screenshot()
        if not self._verify_login_screen(fresh):
            self._transition(ReconnectState.CONNECTED)
            return

        pyautogui.write(self._password, interval=jitter(RECONNECT_TYPEWRITE_INTERVAL, JITTER_SIGMA_TYPING))
        self._log("Typed password")

        time.sleep(jitter(0.3))

        login_pos = get_login_button_position(fresh)
        if login_pos is not None:
            pyautogui.click(login_pos[0], login_pos[1])
            self._log(f"Clicked Login button at {login_pos}")
        else:
            pyautogui.press('enter')
            self._log("Pressed Enter to login (button not found)")

        self._transition(ReconnectState.LOGGING_IN)

    def _handle_logging_in(self, screenshot) -> None:
        """Wait for character list after login."""
        if not self._wait_elapsed(RECONNECT_DELAY_AFTER_LOGIN):
            return

        if is_character_list(screenshot):
            self._transition(ReconnectState.WAITING_CHARACTER_LIST)
            self._log("Character list appeared")
            return

        if is_login_screen(screenshot):
            self._retry_or_give_up("Still on login screen (bad credentials?)")
            return

        if is_disconnected(screenshot):
            self._transition(ReconnectState.DISCONNECTED)
            self._log("Disconnect dialog appeared during login")
            return

        self._retry_or_give_up("Character list did not appear after login")

    def _handle_waiting_character_list(self, screenshot) -> None:
        """Click OK to enter game (first character is already selected)."""
        if not self._wait_elapsed(RECONNECT_DELAY_CHAR_SELECT):
            return

        enter_pos = get_enter_game_button_position(screenshot)
        if enter_pos is None:
            self._retry_or_give_up("Enter Game button not found")
            return

        pyautogui.click(enter_pos[0], enter_pos[1])
        self._log(f"Clicked OK at {enter_pos}")
        self._transition(ReconnectState.SELECTING_CHARACTER)

    def _handle_selecting_character(self, screenshot) -> None:
        """Wait for game to start loading."""
        if not self._wait_elapsed(RECONNECT_DELAY_GAME_LOAD / 2):
            return

        if is_game_loaded(screenshot):
            self._transition(ReconnectState.CONNECTED)
            self._on_reconnected()
            return

        if is_character_list(screenshot):
            self._transition(ReconnectState.WAITING_CHARACTER_LIST)
            self._log("Still on character list, retrying")
            return

        self._transition(ReconnectState.WAITING_GAME_LOAD)

    def _handle_waiting_game_load(self, screenshot) -> None:
        """Wait for game to fully load."""
        if not self._wait_elapsed(RECONNECT_DELAY_GAME_LOAD):
            return

        if is_game_loaded(screenshot):
            self._transition(ReconnectState.CONNECTED)
            self._on_reconnected()
            return

        self._retry_or_give_up("Game did not load after entering")

    def _on_reconnected(self) -> None:
        """Called when successfully reconnected."""
        duration = time.time() - self._disconnect_time if self._disconnect_time > 0 else 0
        self._log(f"Reconnected successfully after {self._retry_count} retries!")
        get_alert_system().alert('alert', "Reconnected successfully!")
        self._track("reconnect_success", {
            "retryCount": self._retry_count,
            "durationSeconds": round(duration, 1),
        })
        self._retry_count = 0
        self._consecutive_failures = 0
        self._disconnect_time = 0.0

    def _transition(self, new_state: ReconnectState) -> None:
        """Transition to a new state."""
        old_state = self._state
        self._state = new_state
        self._last_state_change = time.time()
        self._log(f"State: {old_state.value} -> {new_state.value}")

    def _wait_elapsed(self, delay: float) -> bool:
        """Check if enough time has elapsed since last state change."""
        return time.time() - self._last_state_change >= delay

    def _retry_or_give_up(self, reason: str) -> None:
        """Increment retry count or give up."""
        self._retry_count += 1
        self._log(f"Retry {self._retry_count}/{self._max_retries}: {reason}", "WARNING")
        self._track("reconnect_retry", {
            "retryCount": self._retry_count,
            "reason": reason,
        })

        if self._retry_count >= self._max_retries:
            self._give_up(reason)
            return

        time.sleep(jitter(self._delay_between_retries))
        self._transition(ReconnectState.DISCONNECTED)

    def _give_up(self, reason: str) -> None:
        """Stop trying to reconnect."""
        duration = time.time() - self._disconnect_time if self._disconnect_time > 0 else 0
        self._log(f"Giving up after {self._retry_count} retries: {reason}", "CRITICAL")
        get_alert_system().start_loop_alert(
            'critical',
            f"AUTO-RECONNECT FAILED after {self._retry_count} retries: {reason}"
        )
        self._track("reconnect_failure", {
            "retryCount": self._retry_count,
            "reason": reason,
            "durationSeconds": round(duration, 1),
        })
        self._transition(ReconnectState.CONNECTED)
        self._retry_count = 0
        self._disconnect_time = 0.0
        self._enabled = False

    def _log(self, message: str, level: str = "INFO") -> None:
        """Log reconnect event."""
        print(f"[Reconnect] {message}")
        if self._session_logger is not None:
            self._session_logger._log(f"[Reconnect] {message}", level)

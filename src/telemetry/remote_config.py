import copy
import logging
from threading import Lock
from typing import Optional

logger = logging.getLogger(__name__)


class RemoteConfigManager:
    """
    Thread-safe manager for remote bot config received via API/WebSocket.

    Config flows: Dashboard -> API -> WebSocket -> RemoteConfigManager -> GameLoop
    """

    def __init__(self):
        self._lock = Lock()
        self._config: dict = {}
        self._version: int = 0
        self._has_config: bool = False

    def fetch(self, api_url: str, api_key: str, character_id: str) -> bool:
        """
        Fetch initial config from API on startup.

        Returns True if config was fetched successfully, False otherwise.
        Graceful no-op if request fails.
        """
        try:
            import requests
            response = requests.get(
                f"{api_url}/api/v1/characters/{character_id}/config",
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                timeout=10.0,
            )
            if not response.ok:
                logger.info(f"Remote config fetch failed: HTTP {response.status_code}")
                return False

            data = response.json()
            config = data.get("config", {})
            version = data.get("version", 0)

            if not config:
                return False

            with self._lock:
                self._config = config
                self._version = version
                self._has_config = True

            logger.info(f"Remote config fetched (version {version})")
            return True
        except Exception as e:
            logger.info(f"Remote config fetch failed: {e}")
            return False

    def on_config_updated(self, config: dict, version: int) -> None:
        """
        Callback from WebSocket when dashboard pushes config update.
        Thread-safe.
        """
        with self._lock:
            if version <= self._version:
                return
            self._config = config
            self._version = version
            self._has_config = True
        logger.info(f"Remote config updated (version {version})")

    def get_config(self) -> dict:
        """Return deep copy of current config. Thread-safe."""
        with self._lock:
            return copy.deepcopy(self._config)

    @property
    def version(self) -> int:
        with self._lock:
            return self._version

    @property
    def has_config(self) -> bool:
        with self._lock:
            return self._has_config

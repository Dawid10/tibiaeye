import json
import logging
from threading import Thread, Event
from time import sleep
from typing import Optional, Tuple

logger = logging.getLogger(__name__)

# Tentar importar websocket, mas nao falhar se nao existir
try:
    import websocket
    WEBSOCKET_AVAILABLE = True
except ImportError:
    WEBSOCKET_AVAILABLE = False
    logger.warning("websocket-client not installed. Realtime position disabled.")


class RealtimeClient:
    """
    Cliente WebSocket para enviar posicao em tempo real.

    Envia posicao a cada 500ms (2 updates/segundo).
    Se websocket nao estiver instalado, funciona como no-op.
    """

    def __init__(
        self,
        ws_url: str,
        api_key: str,
        update_interval: float = 0.5,
    ):
        self._ws_url = ws_url
        self._api_key = api_key
        self._update_interval = update_interval

        self._ws = None
        self._thread: Optional[Thread] = None
        self._stop_event = Event()
        self._session_id: Optional[str] = None

        # Ultima posicao conhecida
        self._last_position: Optional[Tuple[int, int, int]] = None
        self._position_changed = Event()
        self._connected = False

        # Status data (HP, mana, bot state)
        self._status_data: Optional[dict] = None
        self._status_changed = Event()

        # Callback for config-updated messages from dashboard
        self._config_callback = None

    def set_config_callback(self, callback):
        """Set callback for config-updated messages from dashboard."""
        self._config_callback = callback

    def send_config_ack(self, version):
        """Send config-ack to confirm reception."""
        if not self._ws or not self._connected or not self._session_id:
            return
        try:
            message = json.dumps({
                "type": "config-ack",
                "sessionId": self._session_id,
                "version": version,
            })
            self._ws.send(message)
        except Exception as e:
            logger.debug(f"Failed to send config-ack: {e}")

    def start(self, session_id: str) -> None:
        """Inicia conexao WebSocket."""
        if not WEBSOCKET_AVAILABLE:
            logger.warning("WebSocket not available, skipping realtime")
            return

        self._session_id = session_id
        self._stop_event.clear()

        self._thread = Thread(target=self._run, daemon=True, name="RealtimeClient")
        self._thread.start()

    def stop(self) -> None:
        """Para conexao WebSocket."""
        self._stop_event.set()
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
        if self._thread:
            self._thread.join(timeout=5)
        self._connected = False

    def update_position(self, x: int, y: int, z: int) -> None:
        """
        Atualiza posicao atual. Non-blocking, O(1).

        Chamado pelo game loop a cada tick.
        """
        new_position = (x, y, z)
        if new_position != self._last_position:
            self._last_position = new_position
            self._position_changed.set()

    def update_status(
        self,
        hp_percent: float,
        mana_percent: float,
        bot_state: str,
        target_creature: Optional[str] = None,
        current_task: Optional[str] = None,
        experience: Optional[int] = None,
        level: Optional[int] = None,
        is_stuck: bool = False,
        speed: Optional[int] = None,
        stamina: Optional[int] = None,
        capacity: Optional[int] = None,
    ) -> None:
        """Atualiza status do bot. Non-blocking."""
        self._status_data = {
            "hpPercent": hp_percent,
            "manaPercent": mana_percent,
            "botState": bot_state,
            "targetCreature": target_creature,
            "currentTask": current_task,
            "isStuck": is_stuck,
        }
        if experience is not None:
            self._status_data["experience"] = experience
        if level is not None:
            self._status_data["level"] = level
        if speed is not None:
            self._status_data["speed"] = speed
        if stamina is not None:
            self._status_data["stamina"] = stamina
        if capacity is not None:
            self._status_data["capacity"] = capacity
        self._status_changed.set()

    def _run(self) -> None:
        """Loop principal do WebSocket."""
        while not self._stop_event.is_set():
            try:
                self._connect()
            except Exception as e:
                logger.warning(f"WebSocket error: {e}")
                sleep(5)  # Retry apos 5s

    def _connect(self) -> None:
        """Conecta ao WebSocket."""
        if not WEBSOCKET_AVAILABLE:
            return

        # Close previous WebSocket before reconnecting
        if self._ws:
            try:
                self._ws.close()
            except Exception:
                pass
            self._ws = None

        url = f"{self._ws_url}?token={self._api_key}&session={self._session_id}"

        self._ws = websocket.WebSocketApp(
            url,
            on_open=self._on_open,
            on_close=self._on_close,
            on_error=self._on_error,
            on_message=self._on_message,
        )

        # Roda em thread separada
        ws_thread = Thread(target=self._ws.run_forever, daemon=True)
        ws_thread.start()

        # Loop de envio de posicao e status
        while not self._stop_event.is_set() and self._ws.sock:
            self._position_changed.wait(timeout=self._update_interval)
            if self._position_changed.is_set():
                self._send_position()
                self._position_changed.clear()
            if self._status_changed.is_set():
                self._send_status()
                self._status_changed.clear()

    def _send_position(self) -> None:
        """Envia posicao atual via WebSocket."""
        if not self._ws or not self._last_position or not self._connected:
            return

        try:
            from datetime import datetime, timezone
            message = json.dumps({
                "type": "position",
                "sessionId": self._session_id,
                "x": self._last_position[0],
                "y": self._last_position[1],
                "z": self._last_position[2],
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._ws.send(message)
        except Exception as e:
            logger.debug(f"Failed to send position: {e}")

    def _send_status(self) -> None:
        """Envia status do bot via WebSocket."""
        if not self._ws or not self._status_data or not self._connected:
            return

        try:
            from datetime import datetime, timezone
            message = json.dumps({
                "type": "status",
                "sessionId": self._session_id,
                **self._status_data,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            })
            self._ws.send(message)
        except Exception as e:
            logger.debug(f"Failed to send status: {e}")

    def _on_message(self, ws, message):
        """Handle incoming WebSocket messages."""
        try:
            data = json.loads(message)
            msg_type = data.get("type")
            if msg_type == "config-updated" and self._config_callback:
                config = data.get("config", {})
                version = data.get("version", 0)
                self._config_callback(config, version)
        except Exception as e:
            logger.debug(f"Failed to parse WS message: {e}")

    def _on_open(self, ws) -> None:
        print("[Telemetry] WebSocket connected")
        self._connected = True

    def _on_close(self, ws, close_status, close_msg) -> None:
        print(f"[Telemetry] WebSocket closed: {close_status}")
        self._connected = False

    def _on_error(self, ws, error) -> None:
        print(f"[Telemetry] WebSocket error: {error}")
        self._connected = False

    @property
    def is_connected(self) -> bool:
        return self._connected

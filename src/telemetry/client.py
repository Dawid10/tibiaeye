import os
import sys
import signal
import atexit
import logging
import threading
from typing import Optional, Tuple
import requests

from .buffer import EventBuffer, TelemetryEvent
from .worker import TelemetryWorker
from .realtime import RealtimeClient
from .remote_config import RemoteConfigManager

logger = logging.getLogger(__name__)


class TelemetryClient:
    """
    Cliente de telemetria para o bot.

    Uso:
        telemetry = TelemetryClient()
        telemetry.start_session(character_id="uuid", hunt_location="Oramond")

        # Durante o jogo (non-blocking, ~1us cada)
        telemetry.track_kill("Demon", experience=6000, position=(1000, 1000, 7))
        telemetry.track_loot("Demon Horn", quantity=1, value=5000)
        telemetry.track_experience(experience=100000000, level=500)
        telemetry.update_position(1000, 1000, 7)

        # Ao finalizar
        telemetry.end_session()
    """

    def __init__(
        self,
        api_url: Optional[str] = None,
        api_key: Optional[str] = None,
        ws_url: Optional[str] = None,
        flush_interval: float = 5.0,
        enabled: Optional[bool] = None,
    ):
        self._api_url = api_url or os.getenv("TELEMETRY_API_URL", "http://localhost:3333")
        self._api_key = api_key or os.getenv("TELEMETRY_API_KEY", "")
        self._ws_url = ws_url or os.getenv("TELEMETRY_WS_URL", "ws://localhost:3333/ws")
        self._flush_interval = flush_interval

        # Se enabled nao for especificado, verifica env var e API key
        if enabled is None:
            env_enabled = os.getenv("TELEMETRY_ENABLED", "true").lower() == "true"
            enabled = env_enabled and bool(self._api_key)
        self._enabled = enabled

        self._buffer: Optional[EventBuffer[TelemetryEvent]] = None
        self._worker: Optional[TelemetryWorker] = None
        self._realtime: Optional[RealtimeClient] = None
        self._session_id: Optional[str] = None
        self._ending = False
        self._original_sigterm = None
        self._remote_config: Optional[RemoteConfigManager] = None

        if not self._enabled:
            logger.info("Telemetry disabled (no API key configured)")

    @property
    def is_enabled(self) -> bool:
        """Retorna se telemetria esta habilitada."""
        return self._enabled

    @property
    def session_id(self) -> Optional[str]:
        """Retorna ID da sessao atual."""
        return self._session_id

    @property
    def remote_config(self) -> Optional[RemoteConfigManager]:
        """Remote config manager for dashboard-pushed config."""
        return self._remote_config

    @property
    def realtime(self) -> Optional[RealtimeClient]:
        """Realtime WebSocket client."""
        return self._realtime

    def start_session(
        self,
        character_id: str,
        hunt_location: Optional[str] = None,
        initial_level: Optional[int] = None,
        initial_experience: Optional[int] = None,
        route_id: Optional[str] = None,
    ) -> str:
        """
        Inicia uma nova sessao de telemetria.

        Args:
            character_id: UUID do character cadastrado no sistema
            hunt_location: Local da hunt (opcional)
            initial_level: Level inicial (opcional)
            initial_experience: XP inicial (opcional)
            route_id: UUID da rota vinculada (opcional)

        Returns:
            ID da sessao criada (ou string vazia se desabilitado)
        """
        if not self._enabled:
            return ""

        # Cria sessao na API e obtem o ID
        self._session_id = self._create_session_on_api(
            character_id=character_id,
            hunt_location=hunt_location,
            initial_level=initial_level,
            initial_experience=initial_experience,
            route_id=route_id,
        )

        if not self._session_id:
            print("[Telemetry] Failed to create session - telemetry disabled for this session")
            return ""

        self._buffer = EventBuffer(max_size=10_000)

        # Worker para eventos em batch
        self._worker = TelemetryWorker(
            buffer=self._buffer,
            api_url=self._api_url,
            api_key=self._api_key,
            session_id=self._session_id,
            flush_interval=self._flush_interval,
        )

        # Cliente realtime para posicao
        self._realtime = RealtimeClient(
            ws_url=self._ws_url,
            api_key=self._api_key,
            update_interval=0.5,
        )

        self._worker.start()
        self._realtime.start(self._session_id)

        # Remote config manager
        self._remote_config = RemoteConfigManager()
        self._remote_config.fetch(self._api_url, self._api_key, character_id)
        self._realtime.set_config_callback(self._remote_config.on_config_updated)

        self._register_cleanup_handlers()

        print(f"[Telemetry] Session started: {self._session_id}")
        return self._session_id

    def _create_session_on_api(
        self,
        character_id: str,
        hunt_location: Optional[str] = None,
        initial_level: Optional[int] = None,
        initial_experience: Optional[int] = None,
        route_id: Optional[str] = None,
    ) -> Optional[str]:
        """
        Cria sessao na API e retorna o ID.

        Returns:
            Session ID ou None se falhou
        """
        try:
            body = {"characterId": character_id}
            if hunt_location:
                body["huntLocation"] = hunt_location
            if initial_level is not None:
                body["initialLevel"] = initial_level
            if initial_experience is not None:
                body["initialExperience"] = str(initial_experience)
            if route_id:
                body["routeId"] = route_id

            response = requests.post(
                f"{self._api_url}/api/v1/sessions",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json=body,
                timeout=10.0,
            )
            if not response.ok:
                try:
                    error_data = response.json()
                    print(f"[Telemetry] Failed to create session: {error_data.get('message', response.status_code)}")
                except Exception:
                    print(f"[Telemetry] Failed to create session: HTTP {response.status_code}")
                return None

            data = response.json()
            return data.get("id")
        except requests.RequestException as e:
            print(f"[Telemetry] Failed to create session: {e}")
            return None

    def _register_cleanup_handlers(self) -> None:
        """Register atexit and SIGTERM handlers to close session on exit."""
        atexit.register(self._cleanup_on_exit)
        try:
            self._original_sigterm = signal.getsignal(signal.SIGTERM)
            signal.signal(signal.SIGTERM, self._handle_sigterm)
        except ValueError:
            self._original_sigterm = None

    def _unregister_cleanup_handlers(self) -> None:
        """Unregister cleanup handlers after session ends normally."""
        atexit.unregister(self._cleanup_on_exit)
        if self._original_sigterm is not None:
            try:
                signal.signal(signal.SIGTERM, self._original_sigterm)
            except ValueError:
                pass
            self._original_sigterm = None

    def _cleanup_on_exit(self) -> None:
        """Called by atexit — close session without final level/xp."""
        self.end_session()

    def _handle_sigterm(self, signum, frame) -> None:
        """Called on SIGTERM — close session then exit."""
        self.end_session()
        sys.exit(0)

    def end_session(
        self,
        final_level: Optional[int] = None,
        final_experience: Optional[int] = None,
    ) -> None:
        """
        Finaliza a sessao atual.

        Args:
            final_level: Level final (opcional)
            final_experience: XP final (opcional)
        """
        if self._ending:
            return
        if not self._enabled or not self._worker:
            return

        self._ending = True

        # Flush pending events before closing session
        self._worker.stop()

        # Update session on API BEFORE closing WebSocket.
        # The server's WS close handler only auto-completes ACTIVE sessions.
        # If session is PAUSED, the close handler is a no-op, so we must
        # PATCH to "completed" first — otherwise the dashboard receives
        # "session-ended" while the DB still says "paused".
        self._end_session_on_api(final_level, final_experience)

        if self._realtime:
            self._realtime.stop()

        self._unregister_cleanup_handlers()

        logger.info(f"Telemetry session ended: {self._session_id}")

        self._session_id = None
        self._buffer = None
        self._worker = None
        self._realtime = None
        self._remote_config = None
        self._ending = False

    def update_session_status(self, status: str) -> None:
        """
        Atualiza status da sessao na API (paused/active).

        When pausing: flushes pending events, pauses worker, then PATCHes API.
        When resuming: PATCHes API first, then resumes worker.

        Args:
            status: "paused" ou "active"
        """
        if not self._enabled or not self._session_id:
            return

        # Pause worker before changing status to avoid "Session is not active" errors
        if status == "paused" and self._worker:
            self._worker.pause()

        session_id = self._session_id
        api_url = self._api_url
        api_key = self._api_key
        worker = self._worker

        def _patch():
            try:
                requests.patch(
                    f"{api_url}/api/v1/sessions/{session_id}",
                    headers={
                        "Authorization": f"Bearer {api_key}",
                        "Content-Type": "application/json",
                    },
                    json={"status": status},
                    timeout=5.0,
                )
                logger.info(f"Session status updated to: {status}")
            except requests.RequestException as e:
                logger.warning(f"Failed to update session status: {e}")

            # Resume worker after API confirms session is active again
            if status == "active" and worker:
                worker.resume()

        threading.Thread(target=_patch, daemon=True).start()

    def _end_session_on_api(
        self,
        final_level: Optional[int] = None,
        final_experience: Optional[int] = None,
    ) -> None:
        """Atualiza sessao na API para status completed."""
        if not self._session_id:
            return

        try:
            requests.patch(
                f"{self._api_url}/api/v1/sessions/{self._session_id}",
                headers={
                    "Authorization": f"Bearer {self._api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "status": "completed",
                    "finalLevel": final_level,
                    "finalExperience": final_experience,
                },
                timeout=10.0,
            )
        except requests.RequestException as e:
            logger.warning(f"Failed to end session on API: {e}")

    # =========================================
    # Metodos de Tracking (Non-blocking)
    # =========================================

    def track_kill(
        self,
        creature_name: str,
        experience: Optional[int] = None,
        position: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        """
        Registra kill de criatura.

        Performance: ~1us (non-blocking)
        """
        if not self._enabled:
            return

        data = {"creatureName": creature_name}

        if experience is not None:
            data["experienceGained"] = experience

        if position is not None:
            data["positionX"] = position[0]
            data["positionY"] = position[1]
            data["positionZ"] = position[2]

        self._enqueue(TelemetryEvent(event_type="kill", data=data))

    def track_loot(
        self,
        item_name: str,
        quantity: int = 1,
        value: Optional[int] = None,
        creature_name: Optional[str] = None,
    ) -> None:
        """
        Registra loot coletado.

        Performance: ~1us (non-blocking)
        """
        if not self._enabled:
            return

        data = {
            "itemName": item_name,
            "quantity": quantity,
        }

        if value is not None:
            data["estimatedValue"] = value

        if creature_name is not None:
            data["creatureName"] = creature_name

        self._enqueue(TelemetryEvent(event_type="loot", data=data))

    def track_experience(self, experience: int, level: int) -> None:
        """
        Registra snapshot de experiencia (para calcular XP/h).

        Performance: ~1us (non-blocking)

        Recomendado chamar a cada 1-5 minutos.
        """
        if not self._enabled:
            return

        self._enqueue(TelemetryEvent(
            event_type="experience",
            data={
                "experience": str(experience),
                "level": level,
            }
        ))

    def track_event(self, event_type: str, data: Optional[dict] = None) -> None:
        """
        Registra evento generico.

        Performance: ~1us (non-blocking)
        """
        if not self._enabled:
            return

        self._enqueue(TelemetryEvent(
            event_type=event_type,
            data=data or {},
        ))

    def track_death(
        self,
        killer: Optional[str] = None,
        position: Optional[Tuple[int, int, int]] = None
    ) -> None:
        """Registra morte do personagem."""
        data = {}
        if killer:
            data["killer"] = killer
        if position:
            data["positionX"] = position[0]
            data["positionY"] = position[1]
            data["positionZ"] = position[2]

        self.track_event("death", data)

    def track_level_up(self, new_level: int) -> None:
        """Registra level up."""
        self.track_event("level_up", {"newLevel": new_level})

    def track_refill(
        self,
        potions_bought: Optional[int] = None,
        gold_spent: Optional[int] = None
    ) -> None:
        """Registra refill de supplies."""
        data = {}
        if potions_bought:
            data["potionsBought"] = potions_bought
        if gold_spent:
            data["goldSpent"] = gold_spent

        self.track_event("refill", data)

    def track_attack_start(
        self,
        creature_name: str,
        position: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        """Registra inicio de ataque a uma criatura."""
        data = {"creatureName": creature_name}
        if position:
            data["positionX"] = position[0]
            data["positionY"] = position[1]
            data["positionZ"] = position[2]

        self.track_event("attack_start", data)

    def track_waypoint_reached(
        self,
        waypoint_index: int,
        waypoint_type: Optional[str] = None,
        position: Optional[Tuple[int, int, int]] = None,
        route_name: Optional[str] = None,
        total_waypoints: Optional[int] = None,
    ) -> None:
        """Registra chegada a um waypoint."""
        data = {"waypointIndex": waypoint_index}
        if waypoint_type:
            data["waypointType"] = waypoint_type
        if position:
            data["positionX"] = position[0]
            data["positionY"] = position[1]
            data["positionZ"] = position[2]
        if route_name:
            data["routeName"] = route_name
        if total_waypoints is not None:
            data["totalWaypoints"] = total_waypoints

        self.track_event("waypoint_reached", data)

    def track_warning(
        self,
        message: str,
        level: str = "warning",
        position: Optional[Tuple[int, int, int]] = None,
    ) -> None:
        """Registra warning/error no timeline (stuck, recovery, etc)."""
        data = {"message": message, "level": level}
        if position:
            data["positionX"] = position[0]
            data["positionY"] = position[1]
            data["positionZ"] = position[2]

        self.track_event("warning", data)

    def update_position(self, x: int, y: int, z: int) -> None:
        """
        Atualiza posicao para live tracking.

        Deve ser chamado a cada tick do game loop.
        Performance: ~0.1us (non-blocking)
        """
        if self._realtime:
            self._realtime.update_position(x, y, z)

    def update_status(
        self,
        hp_percent: float,
        mana_percent: float,
        bot_state: str,
        target_creature: str = None,
        current_task: str = None,
        experience: int = None,
        level: int = None,
        is_stuck: bool = False,
        speed: Optional[int] = None,
        stamina: Optional[int] = None,
        capacity: Optional[int] = None,
    ) -> None:
        """Atualiza status do bot para live dashboard."""
        if self._realtime:
            self._realtime.update_status(
                hp_percent=hp_percent,
                mana_percent=mana_percent,
                bot_state=bot_state,
                target_creature=target_creature,
                current_task=current_task,
                experience=experience,
                level=level,
                is_stuck=is_stuck,
                speed=speed,
                stamina=stamina,
                capacity=capacity,
            )

    # =========================================
    # Metodos Internos
    # =========================================

    def _enqueue(self, event: TelemetryEvent) -> None:
        """Adiciona evento ao buffer (thread-safe, O(1))."""
        if self._buffer is not None:
            self._buffer.append(event)

    @property
    def stats(self) -> dict:
        """Retorna estatisticas de telemetria."""
        if not self._worker:
            return {"enabled": False}

        stats = self._worker.stats
        stats["enabled"] = True
        stats["session_id"] = self._session_id
        stats["realtime_connected"] = self._realtime.is_connected if self._realtime else False
        return stats

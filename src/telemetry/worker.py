import logging
from threading import Thread, Event
from typing import Optional
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from .buffer import EventBuffer, TelemetryEvent

logger = logging.getLogger(__name__)


class TelemetryWorker:
    """
    Background worker que envia eventos para a API.

    - Roda em thread separada (nao bloqueia game loop)
    - Flush periodico (configuravel)
    - Retry automatico com exponential backoff
    - Graceful shutdown com flush final
    """

    def __init__(
        self,
        buffer: EventBuffer[TelemetryEvent],
        api_url: str,
        api_key: str,
        session_id: str,
        flush_interval: float = 5.0,
        max_batch_size: int = 500,
        request_timeout: float = 10.0,
    ):
        self._buffer = buffer
        self._api_url = api_url
        self._api_key = api_key
        self._session_id = session_id
        self._flush_interval = flush_interval
        self._max_batch_size = max_batch_size
        self._request_timeout = request_timeout

        self._stop_event = Event()
        self._paused = False
        self._thread: Optional[Thread] = None
        self._http_session: Optional[requests.Session] = None

        # Metricas
        self._events_sent = 0
        self._events_failed = 0
        self._batches_sent = 0

    def start(self) -> None:
        """Inicia o worker em background thread."""
        if self._thread is not None:
            return

        self._stop_event.clear()
        self._http_session = self._create_http_session()
        self._thread = Thread(target=self._run, daemon=True, name="TelemetryWorker")
        self._thread.start()
        logger.info("TelemetryWorker started")

    def stop(self, timeout: float = 10.0) -> None:
        """
        Para o worker e faz flush final.

        Args:
            timeout: Tempo maximo para aguardar flush final
        """
        if self._thread is None:
            return

        logger.info("TelemetryWorker stopping...")
        self._stop_event.set()
        self._thread.join(timeout=timeout)

        # Flush final (sincrono)
        self._flush()

        if self._http_session:
            self._http_session.close()

        self._thread = None
        logger.info(
            f"TelemetryWorker stopped. "
            f"Sent: {self._events_sent}, Failed: {self._events_failed}"
        )

    def _create_http_session(self) -> requests.Session:
        """Cria sessao HTTP com retry automatico."""
        session = requests.Session()

        retry_strategy = Retry(
            total=3,
            backoff_factor=1,  # 1s, 2s, 4s
            status_forcelist=[429, 500, 502, 503, 504],
            allowed_methods=["POST"],
        )

        adapter = HTTPAdapter(max_retries=retry_strategy)
        session.mount("http://", adapter)
        session.mount("https://", adapter)

        session.headers.update({
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        })

        return session

    def pause(self) -> None:
        """Pause flushing (flush remaining events first)."""
        self._flush()
        self._paused = True

    def resume(self) -> None:
        """Resume flushing."""
        self._paused = False

    def _run(self) -> None:
        """Loop principal do worker."""
        while not self._stop_event.is_set():
            self._stop_event.wait(timeout=self._flush_interval)
            if self._paused:
                continue
            self._flush()

    def _flush(self) -> None:
        """Envia todos os eventos do buffer para a API."""
        events = self._buffer.drain()
        if not events:
            return

        # Divide em batches se necessario
        for i in range(0, len(events), self._max_batch_size):
            batch = events[i:i + self._max_batch_size]
            self._send_batch(batch)

    def _send_batch(self, events: list[TelemetryEvent]) -> bool:
        """
        Envia batch de eventos para a API.

        Returns:
            True se sucesso, False se falhou
        """
        if not self._http_session:
            return False

        payload = {
            "sessionId": self._session_id,
            "events": [
                {
                    "type": event.event_type,
                    **event.data,
                    "timestamp": event.timestamp,
                }
                for event in events
            ]
        }

        try:
            response = self._http_session.post(
                f"{self._api_url}/api/v1/events/batch",
                json=payload,
                timeout=self._request_timeout,
            )

            if not response.ok:
                self._events_failed += len(events)
                try:
                    error_data = response.json()
                    print(f"[Telemetry] Failed to send batch: {error_data}")
                except Exception:
                    print(f"[Telemetry] Failed to send batch: HTTP {response.status_code}")
                return False

            self._events_sent += len(events)
            self._batches_sent += 1
            return True

        except requests.RequestException as e:
            self._events_failed += len(events)
            print(f"[Telemetry] Failed to send batch ({len(events)} events dropped): {e}")
            return False

    @property
    def stats(self) -> dict:
        """Retorna estatisticas do worker."""
        return {
            "events_sent": self._events_sent,
            "events_failed": self._events_failed,
            "batches_sent": self._batches_sent,
            "buffer_size": len(self._buffer),
            "buffer_dropped": self._buffer.dropped_count,
        }

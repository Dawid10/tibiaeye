from collections import deque
from threading import Lock
from typing import Generic, TypeVar
from dataclasses import dataclass, field
from datetime import datetime, timezone

T = TypeVar('T')


@dataclass
class TelemetryEvent:
    """Evento de telemetria com timestamp."""
    event_type: str
    data: dict
    timestamp: str = field(default_factory=lambda: datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")[:-3] + "Z")


class EventBuffer(Generic[T]):
    """
    Buffer thread-safe para eventos de telemetria.

    - Append e O(1) e non-blocking
    - Drain retorna todos os eventos e limpa o buffer
    - Limite maximo previne memory leak se API estiver offline
    """

    def __init__(self, max_size: int = 10_000):
        self._buffer: deque[T] = deque(maxlen=max_size)
        self._lock = Lock()
        self._dropped_count = 0

    def append(self, item: T) -> bool:
        """
        Adiciona item ao buffer. Thread-safe, O(1).

        Returns:
            True se adicionado, False se buffer cheio (item mais antigo descartado)
        """
        with self._lock:
            was_full = len(self._buffer) == self._buffer.maxlen
            self._buffer.append(item)
            if was_full:
                self._dropped_count += 1
            return not was_full

    def drain(self) -> list[T]:
        """
        Remove e retorna todos os itens do buffer. Thread-safe.

        Returns:
            Lista com todos os itens (buffer fica vazio)
        """
        with self._lock:
            items = list(self._buffer)
            self._buffer.clear()
            return items

    def __len__(self) -> int:
        with self._lock:
            return len(self._buffer)

    @property
    def dropped_count(self) -> int:
        """Quantidade de eventos descartados por buffer cheio."""
        with self._lock:
            return self._dropped_count

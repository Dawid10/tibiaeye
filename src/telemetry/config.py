from dataclasses import dataclass
import os


@dataclass
class TelemetryConfig:
    """Configuracao do sistema de telemetria."""

    # API
    api_url: str = "http://localhost:3333"
    api_key: str = ""
    ws_url: str = "ws://localhost:3333/ws"

    # Worker
    flush_interval: float = 5.0      # Segundos entre flushes
    max_batch_size: int = 500        # Maximo de eventos por batch
    request_timeout: float = 10.0    # Timeout de request HTTP

    # Buffer
    buffer_max_size: int = 10_000    # Maximo de eventos no buffer

    # Feature flags
    enabled: bool = True
    track_kills: bool = True
    track_loot: bool = True
    track_experience: bool = True
    track_position: bool = True
    experience_interval: float = 60.0  # Segundos entre snapshots de XP

    @classmethod
    def from_env(cls) -> "TelemetryConfig":
        """Cria config a partir de variaveis de ambiente."""
        return cls(
            api_url=os.getenv("TELEMETRY_API_URL", "http://localhost:3333"),
            api_key=os.getenv("TELEMETRY_API_KEY", ""),
            ws_url=os.getenv("TELEMETRY_WS_URL", "ws://localhost:3333/ws"),
            enabled=os.getenv("TELEMETRY_ENABLED", "true").lower() == "true",
            flush_interval=float(os.getenv("TELEMETRY_FLUSH_INTERVAL", "5.0")),
        )

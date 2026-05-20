import pytest
from unittest.mock import Mock, patch
from src.telemetry.client import TelemetryClient


def test_client_disabled_without_api_key():
    client = TelemetryClient(api_key="")

    assert client.is_enabled == False
    assert client.start_session("Test") == ""


def test_client_tracks_kill():
    with patch.object(TelemetryClient, '_enqueue') as mock_enqueue:
        client = TelemetryClient(api_key="test-key")
        client._enabled = True
        client._buffer = Mock()

        client.track_kill("Demon", experience=6000)

        assert mock_enqueue.called


def test_client_graceful_when_disabled():
    client = TelemetryClient(enabled=False)

    # Nao deve dar erro mesmo desabilitado
    client.track_kill("Demon")
    client.track_loot("Demon Horn")
    client.track_experience(1000000, 100)
    client.update_position(1000, 1000, 7)
    client.end_session()

import pytest
from unittest.mock import patch, Mock, MagicMock
from src.telemetry.buffer import EventBuffer, TelemetryEvent
from src.telemetry.worker import TelemetryWorker


class TestTelemetryWorker:
    def _make_worker(self, buffer=None):
        buf = buffer or EventBuffer(max_size=1000)
        return TelemetryWorker(
            buffer=buf,
            api_url="http://test:4000",
            api_key="test-key",
            session_id="session-123",
            flush_interval=0.1,
        ), buf

    def test_start_stop(self):
        worker, _ = self._make_worker()
        worker.start()
        assert worker._thread is not None
        worker.stop(timeout=2.0)
        assert worker._thread is None

    def test_stats_initial(self):
        worker, _ = self._make_worker()
        stats = worker.stats
        assert stats["events_sent"] == 0
        assert stats["events_failed"] == 0
        assert stats["batches_sent"] == 0

    @patch("src.telemetry.worker.requests.Session")
    def test_send_batch_success(self, mock_session_cls):
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response
        mock_session_cls.return_value = mock_session

        worker, buf = self._make_worker()
        worker._http_session = mock_session

        events = [TelemetryEvent("kill", {"creatureName": "Demon"})]
        result = worker._send_batch(events)

        assert result is True
        assert worker._events_sent == 1
        assert worker._batches_sent == 1

    @patch("src.telemetry.worker.requests.Session")
    def test_send_batch_failure_requeues(self, mock_session_cls):
        import requests

        mock_session = MagicMock()
        mock_session.post.side_effect = requests.ConnectionError("fail")
        mock_session_cls.return_value = mock_session

        buf = EventBuffer(max_size=1000)
        worker, buf = self._make_worker(buffer=buf)
        worker._http_session = mock_session

        events = [TelemetryEvent("kill", {"creatureName": "Demon"})]
        result = worker._send_batch(events)

        assert result is False
        assert worker._events_failed == 1
        # Events are dropped after retry exhaustion (HTTP adapter handles retries)
        assert len(buf) == 0

    def test_flush_empty_buffer(self):
        worker, buf = self._make_worker()
        worker._http_session = MagicMock()

        # Should not error on empty buffer
        worker._flush()
        assert worker._batches_sent == 0

    def test_flush_drains_buffer(self):
        mock_session = MagicMock()
        mock_response = Mock()
        mock_response.raise_for_status = Mock()
        mock_session.post.return_value = mock_response

        buf = EventBuffer(max_size=1000)
        buf.append(TelemetryEvent("kill", {}))
        buf.append(TelemetryEvent("loot", {}))

        worker, _ = self._make_worker(buffer=buf)
        worker._http_session = mock_session

        worker._flush()

        assert len(buf) == 0
        assert worker._events_sent == 2

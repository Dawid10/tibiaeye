import pytest
from src.telemetry.buffer import EventBuffer, TelemetryEvent


def test_buffer_append():
    buffer = EventBuffer(max_size=3)

    assert buffer.append(TelemetryEvent("test", {})) == True
    assert buffer.append(TelemetryEvent("test", {})) == True
    assert buffer.append(TelemetryEvent("test", {})) == True

    assert len(buffer) == 3


def test_buffer_overflow():
    buffer = EventBuffer(max_size=2)

    buffer.append(TelemetryEvent("test1", {}))
    buffer.append(TelemetryEvent("test2", {}))
    buffer.append(TelemetryEvent("test3", {}))  # Descarta test1

    assert len(buffer) == 2
    assert buffer.dropped_count == 1


def test_buffer_drain():
    buffer = EventBuffer()

    buffer.append(TelemetryEvent("test1", {}))
    buffer.append(TelemetryEvent("test2", {}))

    events = buffer.drain()

    assert len(events) == 2
    assert len(buffer) == 0


def test_buffer_thread_safety():
    import threading

    buffer = EventBuffer(max_size=10000)

    def append_events():
        for i in range(1000):
            buffer.append(TelemetryEvent(f"test{i}", {}))

    threads = [threading.Thread(target=append_events) for _ in range(10)]

    for t in threads:
        t.start()

    for t in threads:
        t.join()

    assert len(buffer) == 10000

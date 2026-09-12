from __future__ import annotations

import time

from edge.config import load_config
from edge.fusion.engine import FusionEngine
from edge.fusion.events import EventType
from edge.perception.onnx_runner import InferenceResult


def test_perclos_fires_drowsiness(tmp_path):
    cfg = load_config("edge/config/dev_sim.yaml")
    engine = FusionEngine(cfg)
    ts = time.monotonic()
    driver_open = InferenceResult("driver", ts, [], {"ear": 0.3, "eyes_closed": 0.0})
    fired = []
    for _ in range(30):
        ts += 0.2
        closed = InferenceResult("driver", ts, [], {"ear": 0.15, "eyes_closed": 1.0})
        fired.extend(engine.process(closed, None))
    types = {e.event_type for e in fired}
    assert EventType.DROWSINESS in types


def test_hard_brake_from_speed():
    cfg = load_config("edge/config/dev_sim.yaml")
    engine = FusionEngine(cfg)
    from edge.sensors.can_j1939 import VehicleSample
    from edge.sensors.gateway_client import TelemetryState

    ts = time.monotonic()
    engine.update_telemetry(
        TelemetryState(vehicle=VehicleSample(ts, speed_kmh=80, wheel_speed_kmh=80))
    )
    engine.process(None, None)
    ts += 1.0
    engine.update_telemetry(
        TelemetryState(vehicle=VehicleSample(ts, speed_kmh=20, wheel_speed_kmh=20))
    )
    fired = engine.process(None, None)
    assert any(e.event_type == EventType.HARD_BRAKE for e in fired)


def test_session_score_penalizes():
    from edge.fusion.engine import FiredEvent
    from edge.scoring.session_score import SessionScore

    s = SessionScore("test")
    ev = FiredEvent("1", "test", 0.0, EventType.PHONE_USE, 4, 0.0, {})
    s.apply_event(ev)
    assert s.score < 100.0

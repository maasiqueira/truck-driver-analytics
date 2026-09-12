from __future__ import annotations

import logging
import time
import uuid
from dataclasses import dataclass, field

from edge.config import AppConfig
from edge.fusion.correlator import FusionContext, amplify_severity
from edge.fusion.events import EVENT_SEVERITY, EventType
from edge.fusion.state_machines import PerclosTracker, PhoneConfirmMachine, StateMachine
from edge.perception.onnx_runner import InferenceResult
from edge.sensors.gateway_client import TelemetryState
from edge.sensors.imu_beagley import BeagleYImuReader, ImuSample, KinematicsEstimator

log = logging.getLogger(__name__)


@dataclass
class FiredEvent:
    event_id: str
    session_id: str
    timestamp_mono: float
    event_type: EventType
    severity: int
    duration_s: float
    metadata: dict = field(default_factory=dict)


class FusionEngine:
    def __init__(self, cfg: AppConfig, session_id: str | None = None):
        self.cfg = cfg
        self.session_id = session_id or str(uuid.uuid4())
        th = cfg.thresholds
        self.perclos = PerclosTracker(
            th.get("perclos_window_s", 60),
            th.get("perclos_ratio", 0.15),
            th.get("perclos_duration_s", 4.0),
        )
        self.phone = PhoneConfirmMachine(
            th.get("phone_window_s", 3.0),
            int(th.get("phone_confirm_windows", 2)),
        )
        self.distraction = StateMachine("distraction")
        self.lane = StateMachine("lane")
        self.ctx = FusionContext()
        self.kinematics = KinematicsEstimator()
        self.imu = BeagleYImuReader(on_sample=self._on_imu)
        self._telemetry = TelemetryState()
        self._last_imu: ImuSample | None = None

    def start(self) -> None:
        self.imu.start()

    def stop(self) -> None:
        self.imu.stop()

    def _on_imu(self, sample: ImuSample) -> None:
        self._last_imu = sample

    def update_telemetry(self, state: TelemetryState) -> None:
        self._telemetry = state

    def process(
        self,
        driver: InferenceResult | None,
        road: InferenceResult | None,
    ) -> list[FiredEvent]:
        ts = time.monotonic()
        if driver:
            ts = driver.timestamp_mono
        elif road:
            ts = road.timestamp_mono
        fired: list[FiredEvent] = []

        if driver:
            fired.extend(self._process_driver(driver, ts))
        if road:
            fired.extend(self._process_road(road, ts))
        fired.extend(self._process_vehicle(ts))
        return fired

    def _process_driver(self, res: InferenceResult, ts: float) -> list[FiredEvent]:
        out: list[FiredEvent] = []
        m = res.metrics
        ear_th = self.cfg.thresholds.get("ear_closed", 0.21)
        eyes_closed = m.get("ear", 1.0) < ear_th
        if self.perclos.tick(ts, eyes_closed):
            self.ctx.drowsiness_active = True
            sev = amplify_severity(EVENT_SEVERITY[EventType.DROWSINESS], self.ctx, EventType.DROWSINESS)
            out.append(self._fire(EventType.DROWSINESS, ts, sev, {"ear": m.get("ear")}))

        yaw = abs(m.get("head_yaw_approx", 0.0))
        pitch = abs(m.get("head_pitch_approx", 0.0))
        distracted = (
            yaw > self.cfg.thresholds.get("distraction_yaw_deg", 35)
            or pitch > self.cfg.thresholds.get("distraction_pitch_deg", 25)
        )
        if distracted:
            if not self.distraction.active:
                self.distraction.begin(ts, yaw=yaw, pitch=pitch)
            self.ctx.distraction_active = True
        elif self.distraction.active:
            dur = ts - self.distraction.started_mono
            if dur >= self.cfg.thresholds.get("distraction_duration_s", 2.5):
                sev = amplify_severity(EVENT_SEVERITY[EventType.DISTRACTION], self.ctx, EventType.DISTRACTION)
                out.append(self._fire(EventType.DISTRACTION, ts, sev, {"duration_s": dur, **self.distraction.metadata}))
            self.distraction.end()
            self.ctx.distraction_active = False

        phone = any(d.get("label") == "cell_phone" for d in res.detections)
        if self.phone.tick(ts, phone):
            sev = EVENT_SEVERITY[EventType.PHONE_USE]
            out.append(self._fire(EventType.PHONE_USE, ts, sev, {"confirmed": True}))
        return out

    def _process_road(self, res: InferenceResult, ts: float) -> list[FiredEvent]:
        out: list[FiredEvent] = []
        offset = abs(res.metrics.get("lane_offset_ratio", 0.0))
        if offset > self.cfg.thresholds.get("lane_departure_offset_ratio", 0.12):
            if not self.lane.active:
                self.lane.begin(ts, offset=offset)
            self.ctx.lane_departure_active = True
        elif self.lane.active:
            dur = ts - self.lane.started_mono
            sev = amplify_severity(EVENT_SEVERITY[EventType.LANE_DEPARTURE], self.ctx, EventType.LANE_DEPARTURE)
            out.append(self._fire(EventType.LANE_DEPARTURE, ts, sev, {"duration_s": dur, **self.lane.metadata}))
            self.lane.end()
            self.ctx.lane_departure_active = False

        ttc = res.metrics.get("lead_ttc_s", float("inf"))
        if ttc < self.cfg.thresholds.get("tailgate_ttc_s", 2.0):
            sev = EVENT_SEVERITY[EventType.TAILGATING]
            out.append(self._fire(EventType.TAILGATING, ts, sev, {"ttc_s": ttc}))
        return out

    def _process_vehicle(self, ts: float) -> list[FiredEvent]:
        out: list[FiredEvent] = []
        speed_m_s = None
        v = self._telemetry.vehicle
        g = self._telemetry.gnss
        if v and v.wheel_speed_kmh is not None:
            speed_m_s = v.wheel_speed_kmh / 3.6
        elif g and g.speed_kmh is not None:
            speed_m_s = g.speed_kmh / 3.6

        if speed_m_s is not None:
            accel = self.kinematics.ingest_speed(ts, speed_m_s)
            if accel is not None and accel < -self.cfg.thresholds.get("hard_brake_m_s2", 4.5):
                out.append(
                    self._fire(
                        EventType.HARD_BRAKE,
                        ts,
                        EVENT_SEVERITY[EventType.HARD_BRAKE],
                        {"decel_m_s2": accel},
                    )
                )

        if self._last_imu and speed_m_s:
            lat = KinematicsEstimator.lateral_from_imu(self._last_imu, speed_m_s)
            if self._last_imu.yaw_rate_deg_s > self.cfg.thresholds.get("hard_turn_yaw_rate_deg_s", 25):
                out.append(
                    self._fire(
                        EventType.HARD_TURN,
                        ts,
                        EVENT_SEVERITY[EventType.HARD_TURN],
                        {"yaw_rate_deg_s": self._last_imu.yaw_rate_deg_s, "lateral_m_s2": lat},
                    )
                )
        return out

    def _fire(
        self,
        event_type: EventType,
        ts: float,
        severity: int,
        metadata: dict,
    ) -> FiredEvent:
        return FiredEvent(
            event_id=str(uuid.uuid4()),
            session_id=self.session_id,
            timestamp_mono=ts,
            event_type=event_type,
            severity=severity,
            duration_s=float(metadata.get("duration_s", 0.0)),
            metadata=metadata,
        )

    def current_speed_kmh(self) -> float:
        v = self._telemetry.vehicle
        if v and v.speed_kmh is not None:
            return v.speed_kmh
        g = self._telemetry.gnss
        if g:
            return g.speed_kmh
        return 0.0

from __future__ import annotations

import json
import logging
import math
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class ImuSample:
    timestamp_mono: float
    accel_m_s2: tuple[float, float, float]
    gyro_deg_s: tuple[float, float, float]
    yaw_rate_deg_s: float
    source: str = "beagley_imu"


class ImuSimulator:
    """Placeholder when sysfs/IIO not available (dev)."""

    def __init__(self, on_sample: Callable[[ImuSample], None] | None = None):
        self.on_sample = on_sample
        self._stop = threading.Event()
        self.last: ImuSample | None = None

    def start(self) -> None:
        threading.Thread(target=self._run, daemon=True).start()

    def stop(self) -> None:
        self._stop.set()

    def _run(self) -> None:
        while not self._stop.is_set():
            s = ImuSample(
                timestamp_mono=time.monotonic(),
                accel_m_s2=(0.0, 0.0, 9.81),
                gyro_deg_s=(0.0, 0.0, 0.0),
                yaw_rate_deg_s=0.0,
            )
            self.last = s
            if self.on_sample:
                self.on_sample(s)
            time.sleep(0.05)


class BeagleYImuReader:
    """
    BeagleY-AI onboard IMU.
    On target: read from IIO (e.g. /sys/bus/iio/devices/iio:device0/) or vendor HAL.
    """

    def __init__(
        self,
        iio_accel: str | None = None,
        iio_gyro: str | None = None,
        on_sample: Callable[[ImuSample], None] | None = None,
    ):
        self.iio_accel = Path(iio_accel) if iio_accel else None
        self.iio_gyro = Path(iio_gyro) if iio_gyro else None
        self.on_sample = on_sample
        self._stop = threading.Event()
        self.last: ImuSample | None = None

    def start(self) -> None:
        if self.iio_accel and self.iio_accel.exists():
            threading.Thread(target=self._run_iio, daemon=True).start()
        else:
            log.info("IMU IIO path not found; using simulator")
            ImuSimulator(self.on_sample).start()

    def stop(self) -> None:
        self._stop.set()

    def _run_iio(self) -> None:
        while not self._stop.is_set():
            try:
                raw = (self.iio_accel / "in_accel_x_raw").read_text().strip()
                ax = float(raw) * 0.001
                ay = float((self.iio_accel / "in_accel_y_raw").read_text()) * 0.001
                az = float((self.iio_accel / "in_accel_z_raw").read_text()) * 0.001
                gz = 0.0
                if self.iio_gyro and (self.iio_gyro / "in_anglvel_z_raw").exists():
                    gz = float((self.iio_gyro / "in_anglvel_z_raw").read_text()) * 0.001
                sample = ImuSample(
                    timestamp_mono=time.monotonic(),
                    accel_m_s2=(ax, ay, az),
                    gyro_deg_s=(0.0, 0.0, gz),
                    yaw_rate_deg_s=gz,
                )
                self.last = sample
                if self.on_sample:
                    self.on_sample(sample)
            except Exception:
                log.exception("IMU read error")
            time.sleep(0.02)


@dataclass
class KinematicsEstimator:
    """Derive longitudinal/lateral dynamics from CAN, GPS, or IMU fallback."""

    history: list[tuple[float, float]] = field(default_factory=list)
    max_history: int = 50

    def ingest_speed(self, timestamp_mono: float, speed_m_s: float) -> float | None:
        self.history.append((timestamp_mono, speed_m_s))
        if len(self.history) > self.max_history:
            self.history.pop(0)
        if len(self.history) < 2:
            return None
        t0, v0 = self.history[-2]
        t1, v1 = self.history[-1]
        dt = t1 - t0
        if dt <= 0:
            return None
        return (v1 - v0) / dt

    @staticmethod
    def lateral_from_imu(imu: ImuSample, speed_m_s: float) -> float:
        yaw_r = math.radians(imu.yaw_rate_deg_s)
        return abs(speed_m_s * yaw_r)


def load_gateway_json(line: bytes) -> dict | None:
    try:
        return json.loads(line.decode("utf-8"))
    except json.JSONDecodeError:
        return None

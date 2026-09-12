from __future__ import annotations

import json
import logging
import socket
import threading
import time
from dataclasses import dataclass, field
from typing import Any, Callable

from edge.sensors.can_j1939 import VehicleSample
from edge.sensors.gps_nmea import GnssSample
from edge.sensors.imu_beagley import ImuSample

log = logging.getLogger(__name__)


@dataclass
class TelemetryState:
    vehicle: VehicleSample | None = None
    gnss: GnssSample | None = None
    imu: ImuSample | None = None


class GatewayClient:
    """BeagleY-AI client: receive CAN/GPS from STM32MP157 over USB3 TCP bridge."""

    def __init__(
        self,
        host: str,
        port: int,
        reconnect_s: float = 5.0,
        on_update: Callable[[TelemetryState], None] | None = None,
    ):
        self.host = host
        self.port = port
        self.reconnect_s = reconnect_s
        self.on_update = on_update
        self.state = TelemetryState()
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        buf = b""
        while not self._stop.is_set():
            try:
                with socket.create_connection((self.host, self.port), timeout=5.0) as sock:
                    sock.settimeout(1.0)
                    log.info("gateway connected %s:%s", self.host, self.port)
                    while not self._stop.is_set():
                        chunk = sock.recv(4096)
                        if not chunk:
                            break
                        buf += chunk
                        while b"\n" in buf:
                            line, buf = buf.split(b"\n", 1)
                            self._handle_line(line)
            except OSError:
                log.debug("gateway reconnect in %.0fs", self.reconnect_s)
                time.sleep(self.reconnect_s)

    def _handle_line(self, line: bytes) -> None:
        try:
            msg = json.loads(line.decode("utf-8"))
        except json.JSONDecodeError:
            return
        kind = msg.get("type")
        ts = time.monotonic()
        if kind == "vehicle":
            self.state.vehicle = VehicleSample(
                timestamp_mono=ts,
                speed_kmh=msg.get("speed_kmh"),
                wheel_speed_kmh=msg.get("wheel_speed_kmh"),
                brake_active=msg.get("brake_active"),
                throttle_pct=msg.get("throttle_pct"),
                source="gateway_can",
            )
        elif kind == "gnss":
            self.state.gnss = GnssSample(
                timestamp_mono=ts,
                lat=float(msg.get("lat", 0)),
                lon=float(msg.get("lon", 0)),
                speed_kmh=float(msg.get("speed_kmh", 0)),
                heading_deg=float(msg.get("heading_deg", 0)),
                fix_quality=int(msg.get("fix_quality", 0)),
                source="gateway_gps",
            )
        if self.on_update:
            self.on_update(self.state)

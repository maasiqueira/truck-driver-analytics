from __future__ import annotations

import logging
import struct
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class VehicleSample:
    timestamp_mono: float
    speed_kmh: float | None = None
    wheel_speed_kmh: float | None = None
    brake_active: bool | None = None
    throttle_pct: float | None = None
    source: str = "can"


class J1939Decoder:
    """Minimal J1939 decode for wheel-based speed (PGN 65265 / 0xFEF1)."""

    def __init__(self, wheel_speed_pgn: int = 0xFEF1):
        self.wheel_speed_pgn = wheel_speed_pgn
        self._last: VehicleSample | None = None

    def on_frame(self, can_id: int, data: bytes) -> VehicleSample | None:
        pgn = (can_id >> 8) & 0x3FFFF
        if pgn != self.wheel_speed_pgn or len(data) < 8:
            return None
        speed_raw = struct.unpack_from("<H", data, 1)[0]
        if speed_raw >= 0xFEFF:
            return None
        speed_kmh = speed_raw / 256.0
        sample = VehicleSample(
            timestamp_mono=time.monotonic(),
            speed_kmh=speed_kmh,
            wheel_speed_kmh=speed_kmh,
            source="can_j1939",
        )
        self._last = sample
        return sample

    @property
    def last(self) -> VehicleSample | None:
        return self._last


class CanBusReader:
    def __init__(
        self,
        interface: str = "can0",
        bustype: str = "socketcan",
        bitrate: int = 250000,
        wheel_speed_pgn: int = 0xFEF1,
        on_sample: Callable[[VehicleSample], None] | None = None,
    ):
        self.interface = interface
        self.bustype = bustype
        self.bitrate = bitrate
        self.decoder = J1939Decoder(wheel_speed_pgn)
        self.on_sample = on_sample
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
        try:
            import can
        except ImportError:
            log.warning("python-can not installed; CAN reader idle")
            return
        try:
            bus = can.interface.Bus(channel=self.interface, bustype=self.bustype)
        except Exception:
            log.exception("CAN bus open failed")
            return
        try:
            while not self._stop.is_set():
                msg = bus.recv(timeout=0.5)
                if msg is None:
                    continue
                sample = self.decoder.on_frame(msg.arbitration_id, bytes(msg.data))
                if sample and self.on_sample:
                    self.on_sample(sample)
        finally:
            bus.shutdown()

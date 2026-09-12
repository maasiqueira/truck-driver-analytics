from __future__ import annotations

import logging
import math
import threading
import time
from dataclasses import dataclass
from typing import Callable

log = logging.getLogger(__name__)


@dataclass
class GnssSample:
    timestamp_mono: float
    lat: float
    lon: float
    speed_kmh: float
    heading_deg: float
    fix_quality: int
    source: str = "gps"


class GpsNmeaReader:
    def __init__(
        self,
        port: str = "/dev/ttyUSB0",
        baud: int = 9600,
        on_sample: Callable[[GnssSample], None] | None = None,
    ):
        self.port = port
        self.baud = baud
        self.on_sample = on_sample
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self.last: GnssSample | None = None

    def start(self) -> None:
        self._thread = threading.Thread(target=self._run, daemon=True)
        self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread:
            self._thread.join(timeout=2.0)

    def _run(self) -> None:
        try:
            import serial
            import pynmea2
        except ImportError:
            log.warning("pyserial/pynmea2 missing; GPS reader idle")
            return
        try:
            ser = serial.Serial(self.port, self.baud, timeout=1.0)
        except Exception:
            log.exception("GPS serial open failed")
            return
        try:
            while not self._stop.is_set():
                line = ser.readline().decode("ascii", errors="ignore").strip()
                if not line.startswith("$"):
                    continue
                try:
                    msg = pynmea2.parse(line)
                except pynmea2.ParseError:
                    continue
                sample = self._from_msg(msg)
                if sample:
                    self.last = sample
                    if self.on_sample:
                        self.on_sample(sample)
        finally:
            ser.close()

    @staticmethod
    def _from_msg(msg) -> GnssSample | None:
        import pynmea2

        if isinstance(msg, pynmea2.RMC) and msg.status == "A":
            speed_kmh = float(msg.spd_over_grnd) * 1.852
            return GnssSample(
                timestamp_mono=time.monotonic(),
                lat=float(msg.latitude),
                lon=float(msg.longitude),
                speed_kmh=speed_kmh,
                heading_deg=float(msg.true_course or 0.0),
                fix_quality=1,
            )
        if isinstance(msg, pynmea2.GGA) and msg.gps_qual:
            return GnssSample(
                timestamp_mono=time.monotonic(),
                lat=float(msg.latitude),
                lon=float(msg.longitude),
                speed_kmh=0.0,
                heading_deg=0.0,
                fix_quality=int(msg.gps_qual),
            )
        return None


def haversine_m(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    r = 6371000.0
    p1, p2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dl = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(p1) * math.cos(p2) * math.sin(dl / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))

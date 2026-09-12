from __future__ import annotations

import logging
import queue
import threading
import time
from dataclasses import dataclass

import numpy as np

from edge.capture.pipeline import build_capture, CapturedFrame
from edge.config import AppConfig

log = logging.getLogger(__name__)


@dataclass
class FramePacket:
    timestamp_mono: float
    driver: np.ndarray | None
    road: np.ndarray | None


class DualCameraCapture:
    """Async dual-stream capture with bounded queues (drop stale)."""

    def __init__(self, cfg: AppConfig):
        self.cfg = cfg
        self._driver_q: queue.Queue[CapturedFrame] = queue.Queue(maxsize=cfg.queue_size)
        self._road_q: queue.Queue[CapturedFrame] = queue.Queue(maxsize=cfg.queue_size)
        self._stop = threading.Event()
        self._threads: list[threading.Thread] = []

    def _worker(self, stream: str, q: queue.Queue[CapturedFrame]) -> None:
        cam = self.cfg.cameras.get(stream)
        if cam is None:
            log.error("missing camera config: %s", stream)
            return
        cap = build_capture(stream, cam, self.cfg)
        target_fps = float(self.cfg.cameras.get(stream, cam).fps)
        try:
            cap.open()
            while not self._stop.is_set():
                frame = cap.read()
                if frame is None:
                    time.sleep(0.005)
                    continue
                if self.cfg.drop_stale:
                    while not q.empty():
                        try:
                            q.get_nowait()
                        except queue.Empty:
                            break
                try:
                    q.put_nowait(frame)
                except queue.Full:
                    pass
                time.sleep(max(0.0, 1.0 / target_fps - 0.001))
        except Exception:
            log.exception("capture worker failed: %s", stream)
        finally:
            cap.close()

    def start(self) -> None:
        for stream, q in (("driver", self._driver_q), ("road", self._road_q)):
            t = threading.Thread(target=self._worker, args=(stream, q), daemon=True)
            t.start()
            self._threads.append(t)

    def stop(self) -> None:
        self._stop.set()
        for t in self._threads:
            t.join(timeout=2.0)

    def poll_pair(self, timeout: float = 0.5) -> FramePacket | None:
        driver = self._get_latest(self._driver_q, timeout)
        road = self._get_latest(self._road_q, timeout)
        if driver is None and road is None:
            return None
        ts = max(
            driver.timestamp_mono if driver else 0.0,
            road.timestamp_mono if road else 0.0,
        )
        offset = self.cfg.sync_offset_ms / 1000.0
        if driver and road:
            ts = (driver.timestamp_mono + road.timestamp_mono - offset) / 2.0
        return FramePacket(
            timestamp_mono=ts,
            driver=driver.bgr if driver else None,
            road=road.bgr if road else None,
        )

    @staticmethod
    def _get_latest(q: queue.Queue[CapturedFrame], timeout: float) -> CapturedFrame | None:
        deadline = time.monotonic() + timeout
        latest: CapturedFrame | None = None
        while time.monotonic() < deadline:
            try:
                latest = q.get(timeout=0.05)
            except queue.Empty:
                if latest is not None:
                    break
        return latest

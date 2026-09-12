from __future__ import annotations

import threading
import time
from collections import deque
from dataclasses import dataclass

import numpy as np


@dataclass
class RingFrame:
    timestamp_mono: float
    stream: str
    bgr: np.ndarray


class RingBuffer:
    def __init__(self, max_seconds: float, target_fps: float = 15.0):
        self.max_frames = int(max_seconds * target_fps) + 1
        self._driver: deque[RingFrame] = deque(maxlen=self.max_frames)
        self._road: deque[RingFrame] = deque(maxlen=self.max_frames)
        self._lock = threading.Lock()

    def push(self, stream: str, timestamp_mono: float, bgr: np.ndarray) -> None:
        frame = RingFrame(timestamp_mono, stream, bgr.copy())
        with self._lock:
            if stream == "driver":
                self._driver.append(frame)
            else:
                self._road.append(frame)

    def slice(
        self,
        stream: str,
        center_ts: float,
        pre_s: float,
        post_s: float,
    ) -> list[RingFrame]:
        lo = center_ts - pre_s
        hi = center_ts + post_s
        with self._lock:
            buf = self._driver if stream == "driver" else self._road
            return [f for f in buf if lo <= f.timestamp_mono <= hi]

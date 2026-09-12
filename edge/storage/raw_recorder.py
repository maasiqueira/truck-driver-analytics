from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass
from pathlib import Path

import cv2
import numpy as np

log = logging.getLogger(__name__)


@dataclass
class RecordingConfig:
    enabled: bool = True
    video_subdir: str = "videos"
    segment_s: float = 900.0
    codec: str = "mp4v"
    fps: float = 15.0


class RawVideoRecorder:
    """Grava streams driver/road no microSD com rotação por segmento."""

    def __init__(
        self,
        base_dir: Path,
        session_id: str,
        cfg: RecordingConfig,
    ):
        self.base_dir = base_dir / cfg.video_subdir / session_id
        self.cfg = cfg
        self.session_id = session_id
        self._writers: dict[str, cv2.VideoWriter] = {}
        self._segment_start = time.monotonic()
        self._segment_idx = 0
        self._lock = threading.Lock()
        self._shape: tuple[int, int] | None = None

    def start(self) -> None:
        if not self.cfg.enabled:
            return
        self.base_dir.mkdir(parents=True, exist_ok=True)
        log.info("raw recording dir %s segment_s=%.0f", self.base_dir, self.cfg.segment_s)

    def _open_writer(self, stream: str, frame: np.ndarray) -> cv2.VideoWriter:
        h, w = frame.shape[:2]
        self._shape = (w, h)
        fourcc = cv2.VideoWriter_fourcc(*self.cfg.codec[:4].ljust(4, "0"))
        path = self.base_dir / f"{stream}_seg{self._segment_idx:04d}.mp4"
        writer = cv2.VideoWriter(str(path), fourcc, self.cfg.fps, (w, h))
        if not writer.isOpened():
            raise RuntimeError(f"VideoWriter failed: {path}")
        log.info("recording %s -> %s", stream, path)
        return writer

    def _maybe_rotate(self) -> None:
        if time.monotonic() - self._segment_start < self.cfg.segment_s:
            return
        for w in self._writers.values():
            w.release()
        self._writers.clear()
        self._segment_start = time.monotonic()
        self._segment_idx += 1

    def write(self, stream: str, frame: np.ndarray) -> None:
        if not self.cfg.enabled:
            return
        with self._lock:
            self._maybe_rotate()
            if stream not in self._writers:
                self._writers[stream] = self._open_writer(stream, frame)
            self._writers[stream].write(frame)

    def stop(self) -> None:
        with self._lock:
            for w in self._writers.values():
                w.release()
            self._writers.clear()

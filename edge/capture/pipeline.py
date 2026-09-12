from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from typing import Iterator

import cv2
import numpy as np

from edge.config import AppConfig, CameraConfig

log = logging.getLogger(__name__)


@dataclass
class CapturedFrame:
    stream: str
    timestamp_mono: float
    bgr: np.ndarray


class GStreamerCapture:
    """OpenCV appsink over a GStreamer pipeline (IMX219 / V3Link on BeagleY)."""

    def __init__(self, stream: str, pipeline: str):
        self.stream = stream
        self.pipeline = pipeline.strip()
        self._cap: cv2.VideoCapture | None = None

    def open(self) -> None:
        self._cap = cv2.VideoCapture(self.pipeline, cv2.CAP_GSTREAMER)
        if not self._cap.isOpened():
            raise RuntimeError(f"GStreamer open failed for {self.stream}: {self.pipeline[:80]}...")

    def read(self) -> CapturedFrame | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            return None
        return CapturedFrame(self.stream, time.monotonic(), frame)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


class OpenCVCapture:
    """File or V4L2 device via OpenCV."""

    def __init__(self, stream: str, cam: CameraConfig):
        self.stream = stream
        self.cam = cam
        self._cap: cv2.VideoCapture | None = None

    def _source(self) -> int | str:
        if self.cam.source == "file" and self.cam.path:
            return self.cam.path
        if self.cam.device:
            return self.cam.device
        return 0

    def open(self) -> None:
        src = self._source()
        if isinstance(src, str) and src.isdigit():
            src = int(src)
        self._cap = cv2.VideoCapture(src)
        if self.cam.width and self.cam.height:
            self._cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.cam.width)
            self._cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.cam.height)
        if not self._cap.isOpened():
            raise RuntimeError(f"OpenCV open failed for {self.stream}: {src}")

    def read(self) -> CapturedFrame | None:
        if self._cap is None:
            return None
        ok, frame = self._cap.read()
        if not ok or frame is None:
            if self.cam.source == "file":
                self._cap.set(cv2.CAP_PROP_POS_FRAMES, 0)
                ok, frame = self._cap.read()
                if not ok:
                    return None
            else:
                return None
        return CapturedFrame(self.stream, time.monotonic(), frame)

    def close(self) -> None:
        if self._cap is not None:
            self._cap.release()
            self._cap = None


def build_capture(
    stream: str,
    cam: CameraConfig,
    cfg: AppConfig,
) -> GStreamerCapture | OpenCVCapture:
    if cfg.capture_backend == "gstreamer" and cam.source == "v4l2":
        pipeline = cfg.driver_pipeline if stream == "driver" else cfg.road_pipeline
        if pipeline:
            return GStreamerCapture(stream, pipeline)
    return OpenCVCapture(stream, cam)


def iterate_stream(
    cap: GStreamerCapture | OpenCVCapture,
    max_fps: float | None = None,
) -> Iterator[CapturedFrame]:
    cap.open()
    min_interval = 1.0 / max_fps if max_fps else 0.0
    last = 0.0
    try:
        while True:
            frame = cap.read()
            if frame is None:
                time.sleep(0.01)
                continue
            if min_interval:
                now = time.monotonic()
                elapsed = now - last
                if elapsed < min_interval:
                    time.sleep(min_interval - elapsed)
                last = time.monotonic()
            yield frame
    finally:
        cap.close()

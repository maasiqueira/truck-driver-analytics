from __future__ import annotations

import logging
from pathlib import Path

import cv2
import numpy as np

from edge.storage.ring_buffer import RingFrame

log = logging.getLogger(__name__)


class ClipExporter:
    def __init__(self, clips_dir: Path, clip_max_s: float = 30.0):
        self.clips_dir = clips_dir
        self.clip_max_s = clip_max_s
        self.clips_dir.mkdir(parents=True, exist_ok=True)

    def export_side_by_side(
        self,
        event_id: str,
        driver_frames: list[RingFrame],
        road_frames: list[RingFrame],
        fps: float = 10.0,
    ) -> str | None:
        if not driver_frames and not road_frames:
            return None
        n = max(len(driver_frames), len(road_frames))
        if n == 0:
            return None
        max_n = int(self.clip_max_s * fps)
        n = min(n, max_n)

        def pick(frames: list[RingFrame], i: int) -> RingFrame | None:
            if not frames:
                return None
            return frames[min(i, len(frames) - 1)]

        h, w = 360, 640
        out_path = self.clips_dir / f"{event_id}.mp4"
        writer = cv2.VideoWriter(
            str(out_path),
            cv2.VideoWriter_fourcc(*"mp4v"),
            fps,
            (w * 2, h),
        )
        try:
            for i in range(n):
                d = pick(driver_frames, i)
                r = pick(road_frames, i)
                left = cv2.resize(d.bgr, (w, h)) if d else np.zeros((h, w, 3), dtype=np.uint8)
                right = cv2.resize(r.bgr, (w, h)) if r else np.zeros((h, w, 3), dtype=np.uint8)
                writer.write(cv2.hconcat([left, right]))
        finally:
            writer.release()
        return str(out_path)

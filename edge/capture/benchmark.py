from __future__ import annotations

import argparse
import logging
import statistics
import time

from edge.capture.dual_camera import DualCameraCapture
from edge.config import load_config

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Benchmark dual IMX219/V3Link capture")
    parser.add_argument("--config", default="edge/config/default.yaml")
    parser.add_argument("--duration", type=float, default=30.0)
    args = parser.parse_args()

    cfg = load_config(args.config)
    cap = DualCameraCapture(cfg)
    cap.start()

    intervals: list[float] = []
    driver_ok = 0
    road_ok = 0
    t0 = time.monotonic()
    last = t0
    try:
        while time.monotonic() - t0 < args.duration:
            pkt = cap.poll_pair(timeout=0.2)
            if pkt is None:
                continue
            now = time.monotonic()
            intervals.append(now - last)
            last = now
            if pkt.driver is not None:
                driver_ok += 1
            if pkt.road is not None:
                road_ok += 1
    finally:
        cap.stop()

    elapsed = time.monotonic() - t0
    fps = len(intervals) / elapsed if elapsed else 0.0
    log.info("duration=%.1fs pairs=%d effective_fps=%.2f", elapsed, len(intervals), fps)
    log.info("driver_frames=%d road_frames=%d", driver_ok, road_ok)
    if intervals:
        log.info(
            "interval_ms mean=%.1f p95=%.1f",
            statistics.mean(intervals) * 1000,
            sorted(intervals)[int(len(intervals) * 0.95)] * 1000,
        )
    log.info(
        "GPU: run `tegrastats` on Jetson or monitor AM67A DSP load via SoC tools on BeagleY"
    )


if __name__ == "__main__":
    main()

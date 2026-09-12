"""Benchmark perception FPS (dev machine or BeagleY)."""

from __future__ import annotations

import argparse
import logging
import time

import cv2
import numpy as np

from edge.perception.dms import DmsRunner
from edge.perception.road import RoadRunner

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--frames", type=int, default=200)
    args = parser.parse_args()

    dms = DmsRunner()
    road = RoadRunner()
    dummy = np.zeros((720, 1280, 3), dtype=np.uint8)
    cv2.rectangle(dummy, (400, 200), (900, 600), (128, 128, 128), -1)

    for name, fn in (("dms", lambda: dms.process(dummy, time.monotonic())), ("road", lambda: road.process(dummy, time.monotonic()))):
        t0 = time.monotonic()
        for _ in range(args.frames):
            fn()
        elapsed = time.monotonic() - t0
        log.info("%s fps=%.2f", name, args.frames / elapsed)


if __name__ == "__main__":
    main()

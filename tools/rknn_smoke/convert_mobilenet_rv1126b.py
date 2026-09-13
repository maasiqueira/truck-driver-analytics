"""Convert MobileNet v1 TFLite to RV1126B RKNN (FP16, no calibration). Run on Linux x86_64 with Toolkit2."""

from __future__ import annotations

import sys
from pathlib import Path

from rknn.api import RKNN

WORKDIR = Path(__file__).resolve().parent
TFLITE = WORKDIR / "mobilenet_v1_1.0_224.tflite"
OUT = WORKDIR / "mobilenet_v1_rv1126b.rknn"


def main() -> int:
    if not TFLITE.is_file():
        print(f"Missing {TFLITE}; download TFLite first.", file=sys.stderr)
        return 1

    rknn = RKNN(verbose=True)
    print("--> config rv1126b")
    rknn.config(
        mean_values=[128, 128, 128],
        std_values=[128, 128, 128],
        target_platform="rv1126b",
    )
    print("--> load tflite")
    if rknn.load_tflite(model=str(TFLITE)) != 0:
        return 2
    print("--> build fp")
    if rknn.build(do_quantization=False) != 0:
        return 3
    print("--> export")
    if rknn.export_rknn(str(OUT)) != 0:
        return 4
    rknn.release()
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

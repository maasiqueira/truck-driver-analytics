"""Convert YOLOv5n ONNX to RV1126B RKNN (FP16). Requires yolov5n.onnx in same directory."""

from __future__ import annotations

import sys
from pathlib import Path

from rknn.api import RKNN

WORKDIR = Path(__file__).resolve().parent
ONNX = WORKDIR / "yolov5n.onnx"
OUT = WORKDIR / "yolov5n_rv1126b_fp.rknn"


def main() -> int:
    if not ONNX.is_file():
        print(f"Missing {ONNX}", file=sys.stderr)
        return 1

    rknn = RKNN(verbose=True)
    rknn.config(
        mean_values=[[0, 0, 0]],
        std_values=[[255, 255, 255]],
        target_platform="rv1126b",
    )
    if rknn.load_onnx(model=str(ONNX)) != 0:
        return 2
    if rknn.build(do_quantization=False) != 0:
        return 3
    if rknn.export_rknn(str(OUT)) != 0:
        return 4
    rknn.release()
    print(f"Wrote {OUT} ({OUT.stat().st_size} bytes)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

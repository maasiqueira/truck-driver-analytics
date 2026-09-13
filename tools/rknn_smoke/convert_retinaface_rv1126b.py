"""Convert RetinaFace mobile320 ONNX to RV1126B RKNN (FP16)."""

from __future__ import annotations

import sys
from pathlib import Path

from rknn.api import RKNN

WORKDIR = Path(__file__).resolve().parent
ONNX = WORKDIR / "RetinaFace_mobile320.onnx"
OUT = WORKDIR / "RetinaFace_mobile320_rv1126b_fp.rknn"


def main() -> int:
    if not ONNX.is_file():
        print(f"Missing {ONNX}", file=sys.stderr)
        return 1
    rknn = RKNN(verbose=True)
    rknn.config(
        mean_values=[[104, 117, 123]],
        std_values=[[1, 1, 1]],
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

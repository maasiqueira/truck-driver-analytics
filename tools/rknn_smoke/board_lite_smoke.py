"""Minimal RKNN Lite2 smoke test on RV1126B (load + init_runtime + one inference)."""

from __future__ import annotations

import argparse
import sys
from pathlib import Path

import numpy as np
from rknnlite.api import RKNNLite


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--model",
        type=Path,
        default=Path(__file__).resolve().parent / "yolov5n_rv1126b_fp.rknn",
    )
    parser.add_argument("--size", type=int, default=640, help="Input H=W for random tensor")
    args = parser.parse_args()
    model = args.model.resolve()
    if not model.is_file():
        print(f"Model not found: {model}", file=sys.stderr)
        return 1

    lite = RKNNLite(verbose=True)
    print("--> load_rknn")
    if lite.load_rknn(str(model)) != 0:
        return 2
    print("--> init_runtime")
    if lite.init_runtime() != 0:
        return 3
    s = args.size
    inp = np.random.randint(0, 255, (1, s, s, 3), dtype=np.uint8)
    print("--> inference")
    outs = lite.inference(inputs=[inp], data_format=["nhwc"])
    arr = outs[0]
    print(f"OK output shape={arr.shape} dtype={arr.dtype} min={float(arr.min()):.4f} max={float(arr.max()):.4f}")
    lite.release()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

from __future__ import annotations

import argparse
from pathlib import Path

from ultralytics import YOLO


def export_yolo_onnx(out_dir: str = "models/weights", size: str = "n") -> None:
    Path(out_dir).mkdir(parents=True, exist_ok=True)
    model = YOLO(f"yolov8{size}.pt")
    path = model.export(format="onnx", imgsz=640, simplify=True)
    dest = Path(out_dir) / f"yolov8{size}.onnx"
    Path(path).replace(dest)
    print(f"exported {dest}")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--size", default="n", choices=["n", "s"])
    parser.add_argument("--out", default="models/weights")
    args = parser.parse_args()
    export_yolo_onnx(args.out, args.size)


if __name__ == "__main__":
    main()

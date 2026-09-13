from __future__ import annotations

import logging
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from edge.perception.onnx_runner import InferenceResult

log = logging.getLogger(__name__)


def resolve_road_backend(
    backend: str,
    rknn_path: str,
) -> str:
    """Return 'rknn', 'ultralytics', or 'none'."""
    b = (backend or "auto").lower()
    rknn_file = Path(rknn_path)
    if b == "rknn" or (b == "auto" and rknn_file.is_file()):
        try:
            import rknnlite  # noqa: F401

            return "rknn"
        except ImportError:
            if b == "rknn":
                log.warning("road_backend=rknn but rknnlite missing")
    if b in ("ultralytics", "yolo", "auto"):
        return "ultralytics"
    return "none"


@dataclass
class RoadRunner:
    input_size: int = 640
    model_path: str = "models/weights/yolov8n.onnx"
    rknn_model_path: str = "models/weights/yolov5n_rv1126b_fp.rknn"
    road_backend: str = "auto"
    conf_thresh: float = 0.25
    vehicle_classes: tuple[int, ...] = (2, 3, 5, 7)  # car, motorcycle, bus, truck
    lane_departure_offset_ratio: float = 0.12
    _backend: str = field(init=False, default="none")
    _rknn: Any = field(init=False, default=None, repr=False)
    rknn_detector: Any = field(default=None, repr=False)

    def __post_init__(self) -> None:
        self._backend = resolve_road_backend(self.road_backend, self.rknn_model_path)
        if self._backend == "rknn":
            if self.rknn_detector is not None:
                self._rknn = self.rknn_detector
            else:
                from edge.perception.yolov5_rknn import Yolov5RknnDetector

                self._rknn = Yolov5RknnDetector(
                    self.rknn_model_path,
                    input_size=self.input_size,
                    conf_thresh=self.conf_thresh,
                )
            log.info("Road perception backend: rknn (%s)", self.rknn_model_path)
        elif self._backend == "ultralytics":
            log.info("Road perception backend: ultralytics (%s)", self.model_path)
        else:
            log.info("Road perception backend: none (lane proxy only)")

    def process(self, bgr: np.ndarray, timestamp_mono: float) -> InferenceResult:
        h, w = bgr.shape[:2]
        detections = self._detect_vehicles(bgr)
        metrics = self._lane_metrics(bgr, w, h)
        lead = self._lead_vehicle(detections, w, h)
        if lead:
            metrics["lead_ttc_s"] = lead.get("ttc_s", float("inf"))
            metrics["lead_distance_proxy"] = lead.get("distance_proxy", 0.0)
        return InferenceResult(
            stream="road",
            timestamp_mono=timestamp_mono,
            detections=detections,
            metrics=metrics,
            raw={"lead": lead},
        )

    def _detect_vehicles(self, bgr: np.ndarray) -> list[dict[str, Any]]:
        if self._backend == "rknn" and self._rknn is not None:
            return self._rknn.detect_vehicles(bgr, self.vehicle_classes)
        if self._backend != "ultralytics":
            return []
        try:
            from ultralytics import YOLO

            if not Path(self.model_path).exists():
                return []
            model = YOLO(self.model_path)
            results = model.predict(bgr, imgsz=self.input_size, verbose=False)
            out: list[dict[str, Any]] = []
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    if cls not in self.vehicle_classes:
                        continue
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    out.append(
                        {
                            "label": "vehicle",
                            "class_id": cls,
                            "confidence": conf,
                            "bbox": [x1, y1, x2, y2],
                        }
                    )
            return out
        except Exception:
            return []

    def _lane_metrics(self, bgr: np.ndarray, w: int, h: int) -> dict[str, float]:
        gray = cv2.cvtColor(bgr, cv2.COLOR_BGR2GRAY)
        roi = gray[int(h * 0.55) :, :]
        edges = cv2.Canny(roi, 50, 150)
        col_sum = edges.sum(axis=0).astype(np.float32)
        if col_sum.max() <= 0:
            return {"lane_offset_ratio": 0.0}
        left_mass = col_sum[: w // 2].sum()
        right_mass = col_sum[w // 2 :].sum()
        total = left_mass + right_mass
        balance = (right_mass - left_mass) / total if total else 0.0
        return {"lane_offset_ratio": float(balance)}

    def _lead_vehicle(
        self, detections: list[dict[str, Any]], w: int, h: int
    ) -> dict[str, Any] | None:
        center_x = w / 2
        best = None
        best_score = -1.0
        for d in detections:
            x1, y1, x2, y2 = d["bbox"]
            cx = (x1 + x2) / 2
            if abs(cx - center_x) > w * 0.25:
                continue
            box_h = y2 - y1
            score = box_h / h
            if score > best_score:
                best_score = score
                focal_proxy = 800.0
                distance_proxy = (focal_proxy * 1.5) / max(box_h, 1.0)
                ttc_s = distance_proxy / max(10.0, 1.0)
                best = {
                    "bbox": d["bbox"],
                    "distance_proxy": distance_proxy,
                    "ttc_s": ttc_s,
                }
        return best

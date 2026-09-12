from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import cv2
import numpy as np

from edge.perception.onnx_runner import InferenceResult


@dataclass
class RoadRunner:
    input_size: int = 640
    model_path: str = "models/weights/yolov8n.onnx"
    vehicle_classes: tuple[int, ...] = (2, 3, 5, 7)  # car, motorcycle, bus, truck
    lane_departure_offset_ratio: float = 0.12

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
        try:
            from ultralytics import YOLO
            from pathlib import Path

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

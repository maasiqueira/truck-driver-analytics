from __future__ import annotations

import logging
import math
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from edge.perception.onnx_runner import InferenceResult, OnnxRunner

log = logging.getLogger(__name__)

FACE_MODEL_URL = (
    "https://storage.googleapis.com/mediapipe-models/face_landmarker/"
    "face_landmarker/float16/1/face_landmarker.task"
)
DEFAULT_FACE_MODEL = Path("models/weights/face_landmarker.task")

try:
    import mediapipe as mp
except ImportError:
    mp = None


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def eye_aspect_ratio(landmarks: list[tuple[float, float]], indices: tuple[int, ...]) -> float:
    p = [landmarks[i] for i in indices]
    vertical = _dist(p[1], p[5]) + _dist(p[2], p[4])
    horizontal = _dist(p[0], p[3]) * 2.0
    return vertical / horizontal if horizontal > 1e-6 else 0.0


LEFT_EYE = (33, 160, 158, 133, 153, 144)
RIGHT_EYE = (362, 385, 387, 263, 373, 380)
MOUTH = (13, 14, 78, 308)


def mouth_aspect_ratio(landmarks: list[tuple[float, float]]) -> float:
    top, bottom, left, right = (landmarks[i] for i in MOUTH)
    vertical = _dist(top, bottom)
    horizontal = _dist(left, right)
    return vertical / horizontal if horizontal > 1e-6 else 0.0


def ensure_face_model(path: Path = DEFAULT_FACE_MODEL) -> Path | None:
    if path.exists():
        return path
    path.parent.mkdir(parents=True, exist_ok=True)
    try:
        log.info("downloading face landmarker model to %s", path)
        urllib.request.urlretrieve(FACE_MODEL_URL, path)
        return path
    except OSError:
        log.warning("could not download face landmarker model")
        return None


class _LegacyFaceMesh:
    def __init__(self) -> None:
        self._mesh = mp.solutions.face_mesh.FaceMesh(
            max_num_faces=1,
            refine_landmarks=True,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5,
        )

    def process(self, rgb: np.ndarray, w: int, h: int) -> list[tuple[float, float]] | None:
        res = self._mesh.process(rgb)
        if not res.multi_face_landmarks:
            return None
        lm = res.multi_face_landmarks[0]
        return [(p.x * w, p.y * h) for p in lm.landmark]


class _TasksFaceLandmarker:
    def __init__(self, model_path: Path) -> None:
        from mediapipe.tasks import python
        from mediapipe.tasks.python import vision

        options = vision.FaceLandmarkerOptions(
            base_options=python.BaseOptions(model_asset_path=str(model_path)),
            running_mode=vision.RunningMode.IMAGE,
            num_faces=1,
        )
        self._landmarker = vision.FaceLandmarker.create_from_options(options)

    def process(self, rgb: np.ndarray, w: int, h: int) -> list[tuple[float, float]] | None:
        mp_image = mp.Image(image_format=mp.ImageFormat.SRGB, data=rgb)
        result = self._landmarker.detect(mp_image)
        if not result.face_landmarks:
            return None
        lm = result.face_landmarks[0]
        return [(p.x * w, p.y * h) for p in lm]


def _create_face_backend() -> _LegacyFaceMesh | _TasksFaceLandmarker | None:
    if mp is None:
        return None
    if hasattr(mp, "solutions"):
        return _LegacyFaceMesh()
    model = ensure_face_model()
    if model is None:
        return None
    return _TasksFaceLandmarker(model)


@dataclass
class DmsRunner:
    ear_threshold: float = 0.21
    phone_runner: OnnxRunner | None = None

    def __post_init__(self) -> None:
        self._face = _create_face_backend()

    def process(self, bgr: np.ndarray, timestamp_mono: float) -> InferenceResult:
        h, w = bgr.shape[:2]
        metrics: dict[str, float] = {}
        detections: list[dict[str, Any]] = []
        rgb = cv2.cvtColor(bgr, cv2.COLOR_BGR2RGB)

        if self._face is not None:
            pts = self._face.process(rgb, w, h)
            if pts:
                ear_l = eye_aspect_ratio(pts, LEFT_EYE)
                ear_r = eye_aspect_ratio(pts, RIGHT_EYE)
                ear = (ear_l + ear_r) / 2.0
                mar = mouth_aspect_ratio(pts)
                metrics["ear"] = ear
                metrics["mar"] = mar
                metrics["eyes_closed"] = 1.0 if ear < self.ear_threshold else 0.0
                nose = pts[1]
                metrics["head_yaw_approx"] = (nose[0] / w - 0.5) * 90.0
                metrics["head_pitch_approx"] = (nose[1] / h - 0.45) * 90.0

        if self.phone_runner and self.phone_runner.ready:
            detections.extend(self._detect_phones_yolo(bgr))

        return InferenceResult(
            stream="driver",
            timestamp_mono=timestamp_mono,
            detections=detections,
            metrics=metrics,
        )

    def _detect_phones_yolo(self, bgr: np.ndarray) -> list[dict[str, Any]]:
        try:
            from ultralytics import YOLO

            model_path = str(self.phone_runner.model_path)
            model = YOLO(model_path)
            results = model.predict(bgr, verbose=False, classes=[67])
            out: list[dict[str, Any]] = []
            for r in results:
                for box in r.boxes:
                    cls = int(box.cls[0])
                    conf = float(box.conf[0])
                    x1, y1, x2, y2 = box.xyxy[0].tolist()
                    out.append(
                        {
                            "label": "cell_phone",
                            "class_id": cls,
                            "confidence": conf,
                            "bbox": [x1, y1, x2, y2],
                        }
                    )
            return out
        except Exception:
            return []

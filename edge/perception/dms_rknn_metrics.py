"""DMS metrics from RetinaFace 5-point landmarks (proxy EAR/MAR/pose)."""

from __future__ import annotations

import math

import numpy as np

from edge.perception.retinaface_rknn import RetinaFaceResult


def _dist(a: tuple[float, float], b: tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def metrics_from_retinaface(res: RetinaFaceResult, frame_w: int, frame_h: int) -> dict[str, float]:
    """
    Landmarks: right eye, left eye, nose, right mouth, left mouth (RetinaFace order).
    ear/mar are geometry proxies — recalibrate thresholds vs MediaPipe EAR on vehicle data.
    """
    lm = res.landmarks.reshape(5, 2)
    right_eye = tuple(lm[0].tolist())
    left_eye = tuple(lm[1].tolist())
    nose = tuple(lm[2].tolist())
    right_mouth = tuple(lm[3].tolist())
    left_mouth = tuple(lm[4].tolist())

    inter_eye = _dist(left_eye, right_eye)
    eye_mid = ((right_eye[0] + left_eye[0]) / 2, (right_eye[1] + left_eye[1]) / 2)
    mouth_mid = ((right_mouth[0] + left_mouth[0]) / 2, (right_mouth[1] + left_mouth[1]) / 2)
    mouth_w = _dist(right_mouth, left_mouth)

    ear_proxy = _dist(eye_mid, mouth_mid) / max(inter_eye, 1e-3)
    mar = _dist(nose, mouth_mid) / max(mouth_w, 1e-3)

    yaw = ((nose[0] - eye_mid[0]) / max(inter_eye, 1e-3)) * 45.0
    pitch = ((nose[1] - eye_mid[1]) / max(inter_eye, 1e-3)) * 45.0

    face_h = max(float(res.box[3] - res.box[1]), 1.0)
    metrics = {
        "ear": float(ear_proxy),
        "mar": float(mar),
        "head_yaw_approx": float(yaw),
        "head_pitch_approx": float(pitch),
        "face_score": float(res.score),
        "face_detected": 1.0,
        "inter_eye_px": float(inter_eye),
        "face_h_px": face_h,
    }
    return metrics

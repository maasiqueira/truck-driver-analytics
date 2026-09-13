"""RetinaFace decode + NMS (320x320), from airockchip rknn_model_zoo."""

from __future__ import annotations

from math import ceil
from itertools import product

import numpy as np


def prior_box_320() -> np.ndarray:
    image_size = (320, 320)
    anchors: list[float] = []
    min_sizes = [[16, 32], [64, 128], [256, 512]]
    steps = [8, 16, 32]
    feature_maps = [[ceil(image_size[0] / step), ceil(image_size[1] / step)] for step in steps]
    for k, f in enumerate(feature_maps):
        for i, j in product(range(f[0]), range(f[1])):
            for min_size in min_sizes[k]:
                s_kx = min_size / image_size[1]
                s_ky = min_size / image_size[0]
                for cy in [y * steps[k] / image_size[0] for y in [i + 0.5]]:
                    for cx in [x * steps[k] / image_size[1] for x in [j + 0.5]]:
                        anchors.extend([cx, cy, s_kx, s_ky])
    return np.array(anchors, dtype=np.float32).reshape(-1, 4)


_PRIORS_320 = prior_box_320()


def _box_decode(loc: np.ndarray, priors: np.ndarray) -> np.ndarray:
    variances = (0.1, 0.2)
    boxes = np.concatenate(
        (
            priors[:, :2] + loc[:, :2] * variances[0] * priors[:, 2:],
            priors[:, 2:] * np.exp(loc[:, 2:] * variances[1]),
        ),
        axis=1,
    )
    boxes[:, :2] -= boxes[:, 2:] / 2
    boxes[:, 2:] += boxes[:, :2]
    return boxes


def _decode_landm(pre: np.ndarray, priors: np.ndarray) -> np.ndarray:
    variances = (0.1, 0.2)
    parts = []
    for i in range(0, 10, 2):
        parts.append(priors[:, :2] + pre[:, i : i + 2] * variances[0] * priors[:, 2:])
    return np.concatenate(parts, axis=1)


def _nms(dets: np.ndarray, thresh: float) -> list[int]:
    x1, y1, x2, y2, scores = dets[:, 0], dets[:, 1], dets[:, 2], dets[:, 3], dets[:, 4]
    areas = (x2 - x1 + 1) * (y2 - y1 + 1)
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x2[i], x2[order[1:]])
        yy2 = np.minimum(y2[i], y2[order[1:]])
        w = np.maximum(0.0, xx2 - xx1 + 1)
        h = np.maximum(0.0, yy2 - yy1 + 1)
        inter = w * h
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= thresh)[0]]
    return keep


def postprocess_retinaface(
    loc: np.ndarray,
    conf: np.ndarray,
    landm: np.ndarray,
    *,
    img_w: int,
    img_h: int,
    model_size: int = 320,
    aspect_ratio: float,
    offset_x: float,
    offset_y: float,
    score_thresh: float = 0.5,
    nms_thresh: float = 0.5,
) -> tuple[np.ndarray | None, np.ndarray | None, float]:
    """Return best face (box xyxy, landmarks x5y, score)."""
    priors = _PRIORS_320
    loc = loc.squeeze(0)
    conf = conf.squeeze(0)
    landm = landm.squeeze(0)

    boxes = _box_decode(loc, priors)
    scale = np.array([model_size, model_size, model_size, model_size], dtype=np.float32)
    boxes = boxes * scale
    boxes[:, 0::2] = np.clip((boxes[:, 0::2] - offset_x) / aspect_ratio, 0, img_w)
    boxes[:, 1::2] = np.clip((boxes[:, 1::2] - offset_y) / aspect_ratio, 0, img_h)

    scores = conf[:, 1]
    landmarks = _decode_landm(landm, priors)
    lm_scale = np.tile([model_size, model_size], 5).astype(np.float32)
    landmarks = landmarks * lm_scale
    landmarks[:, 0::2] = np.clip((landmarks[:, 0::2] - offset_x) / aspect_ratio, 0, img_w)
    landmarks[:, 1::2] = np.clip((landmarks[:, 1::2] - offset_y) / aspect_ratio, 0, img_h)

    inds = np.where(scores > 0.02)[0]
    if inds.size == 0:
        return None, None, 0.0
    boxes, landmarks, scores = boxes[inds], landmarks[inds], scores[inds]
    order = scores.argsort()[::-1]
    boxes, landmarks, scores = boxes[order], landmarks[order], scores[order]

    dets = np.hstack((boxes, scores[:, np.newaxis])).astype(np.float32)
    keep = _nms(dets, nms_thresh)
    if not keep:
        return None, None, 0.0
    dets = dets[keep]
    landmarks = landmarks[keep]
    best = int(np.argmax(dets[:, 4]))
    score = float(dets[best, 4])
    if score < score_thresh:
        return None, None, score
    return dets[best, :4], landmarks[best], score

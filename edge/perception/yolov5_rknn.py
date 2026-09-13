"""YOLOv5 on Rockchip NPU via RKNN Toolkit Lite2."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from edge.perception.yolov5_postprocess import post_process

log = logging.getLogger(__name__)


@dataclass
class _LetterBoxMeta:
    origin_h: int
    origin_w: int
    ratio: float
    dw: float
    dh: float


def _letterbox(im: np.ndarray, new_shape: tuple[int, int], pad_color: tuple[int, int, int] = (0, 0, 0)) -> tuple[np.ndarray, _LetterBoxMeta]:
    h, w = im.shape[:2]
    r = min(new_shape[0] / h, new_shape[1] / w)
    new_unpad = (int(round(w * r)), int(round(h * r)))
    dw, dh = new_shape[1] - new_unpad[0], new_shape[0] - new_unpad[1]
    dw /= 2
    dh /= 2
    if (w, h) != new_unpad:
        im = cv2.resize(im, new_unpad, interpolation=cv2.INTER_LINEAR)
    top, bottom = int(round(dh - 0.1)), int(round(dh + 0.1))
    left, right = int(round(dw - 0.1)), int(round(dw + 0.1))
    im = cv2.copyMakeBorder(im, top, bottom, left, right, cv2.BORDER_CONSTANT, value=pad_color)
    meta = _LetterBoxMeta(origin_h=h, origin_w=w, ratio=r, dw=dw, dh=dh)
    return im, meta


def _map_boxes_to_original(boxes: np.ndarray, meta: _LetterBoxMeta) -> np.ndarray:
    out = boxes.copy()
    out[:, 0] = np.clip((out[:, 0] - meta.dw) / meta.ratio, 0, meta.origin_w)
    out[:, 1] = np.clip((out[:, 1] - meta.dh) / meta.ratio, 0, meta.origin_h)
    out[:, 2] = np.clip((out[:, 2] - meta.dw) / meta.ratio, 0, meta.origin_w)
    out[:, 3] = np.clip((out[:, 3] - meta.dh) / meta.ratio, 0, meta.origin_h)
    return out


class Yolov5RknnDetector:
    def __init__(
        self,
        model_path: str | Path,
        input_size: int = 640,
        conf_thresh: float = 0.25,
        nms_thresh: float = 0.45,
    ) -> None:
        self.model_path = Path(model_path)
        self.input_size = input_size
        self.conf_thresh = conf_thresh
        self.nms_thresh = nms_thresh
        self._lite: Any = None
        self._warned_rknpu = False

    @property
    def ready(self) -> bool:
        return self.model_path.is_file()

    def _ensure_runtime(self) -> bool:
        if self._lite is not None:
            return True
        if not self.model_path.is_file():
            log.warning("RKNN model missing: %s", self.model_path)
            return False
        try:
            from rknnlite.api import RKNNLite
        except ImportError:
            log.warning("rknn-toolkit-lite2 not installed")
            return False

        if not self._warned_rknpu and not os.access("/dev/rknpu", os.R_OK | os.W_OK):
            log.warning("/dev/rknpu not accessible; run: sudo chmod 666 /dev/rknpu")
            self._warned_rknpu = True

        lite = RKNNLite(verbose=False)
        if lite.load_rknn(str(self.model_path)) != 0:
            log.error("load_rknn failed: %s", self.model_path)
            return False
        if lite.init_runtime() != 0:
            log.error("RKNN init_runtime failed")
            return False
        self._lite = lite
        log.info("RKNN road model loaded: %s", self.model_path)
        return True

    def detect_classes(
        self,
        bgr: np.ndarray,
        class_ids: tuple[int, ...],
        labels: dict[int, str] | None = None,
    ) -> list[dict[str, Any]]:
        labels = labels or {}
        if not self._ensure_runtime():
            return []

        img, meta = _letterbox(bgr, (self.input_size, self.input_size))
        rgb = cv2.cvtColor(img, cv2.COLOR_BGR2RGB)
        inp = np.expand_dims(rgb, 0)
        outputs = self._lite.inference(inputs=[inp], data_format=["nhwc"])
        if not outputs:
            return []

        boxes, classes, scores = post_process(
            [np.array(o) for o in outputs],
            img_size=(self.input_size, self.input_size),
            obj_thresh=self.conf_thresh,
            nms_thresh=self.nms_thresh,
        )
        if boxes is None:
            return []

        boxes = _map_boxes_to_original(boxes, meta)
        out: list[dict[str, Any]] = []
        for box, cls_id, score in zip(boxes, classes, scores):
            cid = int(cls_id)
            if cid not in class_ids:
                continue
            x1, y1, x2, y2 = box.tolist()
            out.append(
                {
                    "label": labels.get(cid, f"class_{cid}"),
                    "class_id": cid,
                    "confidence": float(score),
                    "bbox": [x1, y1, x2, y2],
                }
            )
        return out

    def detect_vehicles(
        self,
        bgr: np.ndarray,
        vehicle_classes: tuple[int, ...],
    ) -> list[dict[str, Any]]:
        return self.detect_classes(
            bgr,
            vehicle_classes,
            labels={2: "vehicle", 3: "vehicle", 5: "vehicle", 7: "vehicle"},
        )

    def release(self) -> None:
        if self._lite is not None:
            self._lite.release()
            self._lite = None

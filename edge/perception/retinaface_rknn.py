"""RetinaFace on RV1126B via RKNN Lite2."""

from __future__ import annotations

import logging
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import cv2
import numpy as np

from edge.perception.retinaface_postprocess import postprocess_retinaface

log = logging.getLogger(__name__)


def letterbox_retinaface(
    image: np.ndarray,
    size: tuple[int, int],
    bg_color: int = 114,
) -> tuple[np.ndarray, float, float, float]:
    tw, th = size
    ih, iw = image.shape[:2]
    aspect = min(tw / iw, th / ih)
    nw, nh = int(iw * aspect), int(ih * aspect)
    resized = cv2.resize(image, (nw, nh), interpolation=cv2.INTER_AREA)
    canvas = np.ones((th, tw, 3), dtype=np.uint8) * bg_color
    ox = (tw - nw) // 2
    oy = (th - nh) // 2
    canvas[oy : oy + nh, ox : ox + nw] = resized
    return canvas, aspect, float(ox), float(oy)


@dataclass
class RetinaFaceResult:
    box: np.ndarray
    landmarks: np.ndarray
    score: float


class RetinaFaceRknn:
    def __init__(self, model_path: str | Path, input_size: int = 320, score_thresh: float = 0.5) -> None:
        self.model_path = Path(model_path)
        self.input_size = input_size
        self.score_thresh = score_thresh
        self._lite: Any = None

    @property
    def ready(self) -> bool:
        return self.model_path.is_file()

    def _ensure_runtime(self) -> bool:
        if self._lite is not None:
            return True
        if not self.model_path.is_file():
            return False
        try:
            from rknnlite.api import RKNNLite
        except ImportError:
            log.warning("rknnlite not installed")
            return False
        if not os.access("/dev/rknpu", os.R_OK | os.W_OK):
            log.warning("/dev/rknpu not accessible")
        lite = RKNNLite(verbose=False)
        if lite.load_rknn(str(self.model_path)) != 0:
            return False
        if lite.init_runtime() != 0:
            return False
        self._lite = lite
        log.info("RetinaFace RKNN loaded: %s", self.model_path)
        return True

    def detect(self, bgr: np.ndarray) -> RetinaFaceResult | None:
        if not self._ensure_runtime():
            return None
        h, w = bgr.shape[:2]
        lb, aspect, ox, oy = letterbox_retinaface(bgr, (self.input_size, self.input_size))
        rgb = lb[..., ::-1]
        inp = np.expand_dims(rgb, 0)
        outputs = self._lite.inference(inputs=[inp], data_format=["nhwc"])
        if not outputs or len(outputs) < 3:
            return None
        loc, conf, landm = outputs[0], outputs[1], outputs[2]
        box, lms, score = postprocess_retinaface(
            np.array(loc),
            np.array(conf),
            np.array(landm),
            img_w=w,
            img_h=h,
            model_size=self.input_size,
            aspect_ratio=aspect,
            offset_x=ox,
            offset_y=oy,
            score_thresh=self.score_thresh,
        )
        if box is None or lms is None:
            return None
        return RetinaFaceResult(box=box, landmarks=lms, score=score)

    def release(self) -> None:
        if self._lite is not None:
            self._lite.release()
            self._lite = None

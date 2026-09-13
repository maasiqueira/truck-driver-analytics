"""YOLOv5 decode + NMS (aligned with airockchip rknn_model_zoo examples/yolov5)."""

from __future__ import annotations

import numpy as np

# Default YOLOv5 anchors (anchors_yolov5.txt)
YOLOV5_ANCHORS = np.array(
    [
        [10, 13],
        [16, 30],
        [33, 23],
        [30, 61],
        [62, 45],
        [59, 119],
        [116, 90],
        [156, 198],
        [373, 326],
    ],
    dtype=np.float32,
).reshape(3, 3, 2)


def filter_boxes(
    boxes: np.ndarray,
    box_confidences: np.ndarray,
    box_class_probs: np.ndarray,
    obj_thresh: float,
) -> tuple[np.ndarray, np.ndarray, np.ndarray]:
    box_confidences = box_confidences.reshape(-1)
    class_max_score = np.max(box_class_probs, axis=-1)
    classes = np.argmax(box_class_probs, axis=-1)
    scores = class_max_score * box_confidences
    keep = np.where(scores >= obj_thresh)[0]
    return boxes[keep], classes[keep], scores[keep]


def nms_boxes(boxes: np.ndarray, scores: np.ndarray, nms_thresh: float) -> np.ndarray:
    x1 = boxes[:, 0]
    y1 = boxes[:, 1]
    w = boxes[:, 2] - boxes[:, 0]
    h = boxes[:, 3] - boxes[:, 1]
    areas = w * h
    order = scores.argsort()[::-1]
    keep: list[int] = []
    while order.size > 0:
        i = int(order[0])
        keep.append(i)
        xx1 = np.maximum(x1[i], x1[order[1:]])
        yy1 = np.maximum(y1[i], y1[order[1:]])
        xx2 = np.minimum(x1[i] + w[i], x1[order[1:]] + w[order[1:]])
        yy2 = np.minimum(y1[i] + h[i], y1[order[1:]] + h[order[1:]])
        inter = np.maximum(0.0, xx2 - xx1 + 0.00001) * np.maximum(0.0, yy2 - yy1 + 0.00001)
        ovr = inter / (areas[i] + areas[order[1:]] - inter)
        order = order[np.where(ovr <= nms_thresh)[0] + 1]
    return np.array(keep, dtype=np.int64)


def _box_process(position: np.ndarray, anchors: list[list[float]], img_size: tuple[int, int]) -> np.ndarray:
    grid_h, grid_w = position.shape[2:4]
    col, row = np.meshgrid(np.arange(0, grid_w), np.arange(0, grid_h))
    col = col.reshape(1, 1, grid_h, grid_w)
    row = row.reshape(1, 1, grid_h, grid_w)
    grid = np.concatenate((col, row), axis=1)
    stride = np.array([img_size[1] // grid_h, img_size[0] // grid_w], dtype=np.float32).reshape(1, 2, 1, 1)

    col = np.repeat(col, len(anchors), axis=0)
    row = np.repeat(row, len(anchors), axis=0)
    grid = np.concatenate((col, row), axis=1)
    anc = np.array(anchors, dtype=np.float32).reshape(len(anchors), 2, 1, 1)

    box_xy = position[:, :2, :, :] * 2 - 0.5
    box_wh = np.power(position[:, 2:4, :, :] * 2, 2) * anc
    box_xy += grid
    box_xy *= stride
    box = np.concatenate((box_xy, box_wh), axis=1)

    xyxy = np.copy(box)
    xyxy[:, 0, :, :] = box[:, 0, :, :] - box[:, 2, :, :] / 2
    xyxy[:, 1, :, :] = box[:, 1, :, :] - box[:, 3, :, :] / 2
    xyxy[:, 2, :, :] = box[:, 0, :, :] + box[:, 2, :, :] / 2
    xyxy[:, 3, :, :] = box[:, 1, :, :] + box[:, 3, :, :] / 2
    return xyxy


def _sp_flatten(x: np.ndarray) -> np.ndarray:
    ch = x.shape[1]
    return x.transpose(0, 2, 3, 1).reshape(-1, ch)


def post_process(
    input_data: list[np.ndarray],
    *,
    img_size: tuple[int, int] = (640, 640),
    obj_thresh: float = 0.25,
    nms_thresh: float = 0.45,
    anchors: np.ndarray | None = None,
) -> tuple[np.ndarray | None, np.ndarray | None, np.ndarray | None]:
    if anchors is None:
        anchors = YOLOV5_ANCHORS
    anchor_list = anchors.reshape(3, 3, 2).tolist()

    reshaped = [
        arr.reshape([len(anchor_list[0]), -1] + list(arr.shape[-2:])).astype(np.float32) for arr in input_data
    ]

    boxes_list, scores_list, cls_list = [], [], []
    for i, tensor in enumerate(reshaped):
        boxes_list.append(_box_process(tensor[:, :4, :, :], anchor_list[i], img_size))
        scores_list.append(tensor[:, 4:5, :, :])
        cls_list.append(tensor[:, 5:, :, :])

    boxes = np.concatenate([_sp_flatten(b) for b in boxes_list])
    classes_conf = np.concatenate([_sp_flatten(c) for c in cls_list])
    scores = np.concatenate([_sp_flatten(s) for s in scores_list])

    boxes, classes, scores = filter_boxes(boxes, scores, classes_conf, obj_thresh)
    if boxes.size == 0:
        return None, None, None

    nboxes, nclasses, nscores = [], [], []
    for c in set(classes.tolist()):
        inds = np.where(classes == c)
        b, cl, s = boxes[inds], classes[inds], scores[inds]
        keep = nms_boxes(b, s, nms_thresh)
        if keep.size:
            nboxes.append(b[keep])
            nclasses.append(cl[keep])
            nscores.append(s[keep])

    if not nboxes:
        return None, None, None
    return np.concatenate(nboxes), np.concatenate(nclasses), np.concatenate(nscores)

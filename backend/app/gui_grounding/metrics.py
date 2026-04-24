"""GUI grounding metrics."""

from __future__ import annotations

from app.gui_grounding.baseline import GroundingLabel, GroundingPrediction


def point_in_box(point: tuple[float, float], bbox: tuple[float, float, float, float]) -> bool:
    x, y = point
    x1, y1, x2, y2 = bbox
    return x1 <= x <= x2 and y1 <= y <= y2


def bbox_iou(
    predicted: tuple[float, float, float, float],
    target: tuple[float, float, float, float],
) -> float:
    px1, py1, px2, py2 = predicted
    tx1, ty1, tx2, ty2 = target

    ix1 = max(px1, tx1)
    iy1 = max(py1, ty1)
    ix2 = min(px2, tx2)
    iy2 = min(py2, ty2)
    inter_w = max(0.0, ix2 - ix1)
    inter_h = max(0.0, iy2 - iy1)
    intersection = inter_w * inter_h
    pred_area = max(0.0, px2 - px1) * max(0.0, py2 - py1)
    target_area = max(0.0, tx2 - tx1) * max(0.0, ty2 - ty1)
    union = pred_area + target_area - intersection
    return intersection / union if union > 0 else 0.0


def gui_action_accuracy(
    predictions: list[GroundingPrediction],
    labels: list[GroundingLabel],
    *,
    iou_threshold: float = 0.5,
) -> float:
    if not labels:
        return 0.0
    hits = 0
    for prediction, label in zip(predictions, labels, strict=False):
        selector_hit = bool(prediction.selector and prediction.selector == label.selector)
        id_hit = bool(prediction.candidate_id and prediction.candidate_id == label.candidate_id)
        point_hit = bool(prediction.point and point_in_box(prediction.point, label.bbox))
        iou_hit = bool(prediction.bbox and bbox_iou(prediction.bbox, label.bbox) >= iou_threshold)
        if selector_hit or id_hit or point_hit or iou_hit:
            hits += 1
    return hits / len(labels)

from __future__ import annotations

import argparse
import json
from pathlib import Path

import yaml


def main() -> None:
    parser = argparse.ArgumentParser(description="Review labeled events vs detections")
    parser.add_argument("--labels", required=True, help="JSONL with ground truth events")
    parser.add_argument("--predictions", required=True, help="JSONL model/session events")
    args = parser.parse_args()

    labels = [json.loads(l) for l in Path(args.labels).read_text(encoding="utf-8").splitlines() if l.strip()]
    preds = [json.loads(l) for l in Path(args.predictions).read_text(encoding="utf-8").splitlines() if l.strip()]

    label_types = {x["type"] for x in labels}
    pred_types = {x["type"] for x in preds}
    tp = len(label_types & pred_types)
    fp = len(pred_types - label_types)
    fn = len(label_types - pred_types)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    print(json.dumps({"tp_types": tp, "precision_proxy": precision, "recall_proxy": recall}, indent=2))


if __name__ == "__main__":
    main()

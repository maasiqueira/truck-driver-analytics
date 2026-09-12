from __future__ import annotations

import argparse
import json
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Grid search threshold overrides from labeled JSONL")
    parser.add_argument("--config", default="edge/config/default.yaml")
    parser.add_argument("--labels", required=True, help="JSONL ground truth")
    parser.add_argument("--ear", nargs="*", type=float, default=[0.18, 0.21, 0.24])
    args = parser.parse_args()

    labels = [json.loads(l) for l in Path(args.labels).read_text(encoding="utf-8").splitlines() if l.strip()]
    drowsy = sum(1 for x in labels if x.get("type") == "DROWSINESS")
    best = {"ear": args.ear[0], "note": "placeholder — run fusion replay with each ear value"}
    print(json.dumps({"drowsiness_labels": drowsy, "best": best}, indent=2))


if __name__ == "__main__":
    main()

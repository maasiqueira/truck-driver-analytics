"""Diagnose face detection and EAR on a driver cabin video."""

from __future__ import annotations

import argparse
import json
import statistics
from pathlib import Path

import cv2
import numpy as np

from edge.perception.dms import DmsRunner, ensure_face_model


def analyze(path: Path, sample_every: int = 5, ear_threshold: float = 0.21, out_dir: Path | None = None) -> dict:
    cap = cv2.VideoCapture(str(path))
    if not cap.isOpened():
        raise RuntimeError(f"cannot open {path}")

    fps = cap.get(cv2.CAP_PROP_FPS) or 15.0
    total = int(cap.get(cv2.CAP_PROP_FRAME_COUNT))
    w = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    h = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))

    dms = DmsRunner(ear_threshold=ear_threshold)
    if dms._face is None:
        raise RuntimeError("face backend unavailable — run ensure_face_model() first")

    ears: list[float] = []
    mars: list[float] = []
    yaws: list[float] = []
    pitches: list[float] = []
    face_detected_frames = 0
    eyes_closed_frames = 0
    sampled = 0
    timeline: list[dict] = []

    if out_dir:
        out_dir.mkdir(parents=True, exist_ok=True)

    frame_idx = 0
    while True:
        ok, bgr = cap.read()
        if not ok:
            break
        if frame_idx % sample_every != 0:
            frame_idx += 1
            continue

        t_s = frame_idx / fps
        res = dms.process(bgr, t_s)
        sampled += 1
        m = res.metrics
        has_face = "ear" in m
        if has_face:
            face_detected_frames += 1
            ears.append(m["ear"])
            mars.append(m["mar"])
            yaws.append(m.get("head_yaw_approx", 0.0))
            pitches.append(m.get("head_pitch_approx", 0.0))
            if m.get("eyes_closed", 0) >= 1.0:
                eyes_closed_frames += 1

        timeline.append(
            {
                "frame": frame_idx,
                "t_s": round(t_s, 2),
                "face": has_face,
                "ear": round(m.get("ear", -1), 4) if has_face else None,
                "eyes_closed": bool(m.get("eyes_closed")) if has_face else None,
                "yaw": round(m.get("head_yaw_approx", 0), 1) if has_face else None,
                "pitch": round(m.get("head_pitch_approx", 0), 1) if has_face else None,
            }
        )

        # Save annotated samples: first face, min EAR, max EAR, no-face example
        if out_dir and has_face:
            annotated = bgr.copy()
            ear_val = m["ear"]
            color = (0, 0, 255) if ear_val < ear_threshold else (0, 200, 0)
            cv2.putText(
                annotated,
                f"t={t_s:.1f}s EAR={ear_val:.3f} yaw={m.get('head_yaw_approx',0):.0f}",
                (10, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.7,
                color,
                2,
            )
            tag = None
            if face_detected_frames == 1:
                tag = "first_face"
            elif ear_val == min(ears):
                tag = "min_ear"
            elif ear_val == max(ears):
                tag = "max_ear"
            if tag:
                cv2.imwrite(str(out_dir / f"{tag}_f{frame_idx}.jpg"), annotated)

        frame_idx += 1

    cap.release()

    # Find longest no-face gap
    max_gap_s = 0.0
    gap_start = None
    for entry in timeline:
        if not entry["face"]:
            if gap_start is None:
                gap_start = entry["t_s"]
        else:
            if gap_start is not None:
                max_gap_s = max(max_gap_s, entry["t_s"] - gap_start)
                gap_start = None

    # PERCLOS-like on sampled frames
    perclos = eyes_closed_frames / face_detected_frames if face_detected_frames else 0.0

    summary = {
        "video": str(path),
        "resolution": f"{w}x{h}",
        "fps": round(fps, 2),
        "total_frames": total,
        "duration_s": round(total / fps, 1),
        "sample_every": sample_every,
        "sampled_frames": sampled,
        "face_detection_rate": round(face_detected_frames / sampled, 3) if sampled else 0.0,
        "face_detected_count": face_detected_frames,
        "ear_threshold": ear_threshold,
        "eyes_closed_rate_on_face": round(perclos, 3),
        "ear": _stats(ears),
        "mar": _stats(mars),
        "head_yaw_approx": _stats(yaws),
        "head_pitch_approx": _stats(pitches),
        "max_no_face_gap_s": round(max_gap_s, 1),
        "timeline_sample": timeline[:: max(1, len(timeline) // 20)][:20],
    }
    return summary


def _stats(values: list[float]) -> dict | None:
    if not values:
        return None
    return {
        "min": round(min(values), 4),
        "max": round(max(values), 4),
        "mean": round(statistics.mean(values), 4),
        "p10": round(sorted(values)[int(len(values) * 0.1)], 4),
        "p90": round(sorted(values)[int(len(values) * 0.9)], 4),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--video", default="data/samples/driver2.mp4")
    parser.add_argument("--sample-every", type=int, default=3, help="analyze every Nth frame")
    parser.add_argument("--ear-threshold", type=float, default=0.21)
    parser.add_argument("--out", default="data/runtime/driver2_analysis")
    args = parser.parse_args()

    ensure_face_model()
    out_dir = Path(args.out)
    summary = analyze(
        Path(args.video),
        sample_every=args.sample_every,
        ear_threshold=args.ear_threshold,
        out_dir=out_dir,
    )
    report_path = out_dir / "report.json"
    report_path.write_text(json.dumps(summary, indent=2), encoding="utf-8")
    print(json.dumps(summary, indent=2))
    print(f"\nreport -> {report_path}")
    print(f"sample frames -> {out_dir}/")


if __name__ == "__main__":
    main()

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass
class CameraConfig:
    source: str
    device: str | None = None
    path: str | None = None
    width: int = 1280
    height: int = 720
    fps: int = 15


@dataclass
class AppConfig:
    raw: dict[str, Any]
    platform: str
    cameras: dict[str, CameraConfig]
    sync_offset_ms: int = 0
    queue_size: int = 4
    drop_stale: bool = True
    capture_backend: str = "gstreamer"
    driver_pipeline: str = ""
    road_pipeline: str = ""
    inference: dict[str, Any] = field(default_factory=dict)
    thresholds: dict[str, float] = field(default_factory=dict)
    gateway: dict[str, Any] = field(default_factory=dict)
    storage: dict[str, Any] = field(default_factory=dict)
    sync: dict[str, Any] = field(default_factory=dict)
    privacy: dict[str, Any] = field(default_factory=dict)
    recording: dict[str, Any] = field(default_factory=dict)
    analysis_log: dict[str, Any] = field(default_factory=dict)


def load_config(path: str | Path) -> AppConfig:
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)

    cam_root = raw.get("cameras", {})
    cameras: dict[str, CameraConfig] = {}
    for name, c in cam_root.items():
        if name in ("sync_offset_ms", "queue_size", "drop_stale"):
            continue
        if not isinstance(c, dict):
            continue
        cameras[name] = CameraConfig(
            source=c.get("source", "v4l2"),
            device=c.get("device"),
            path=c.get("path"),
            width=int(c.get("width", 1280)),
            height=int(c.get("height", 720)),
            fps=int(c.get("fps", 15)),
        )

    cap = raw.get("capture", {})
    return AppConfig(
        raw=raw,
        platform=raw.get("platform", "unknown"),
        cameras=cameras,
        sync_offset_ms=int(cam_root.get("sync_offset_ms", 0)),
        queue_size=int(cam_root.get("queue_size", 4)),
        drop_stale=bool(cam_root.get("drop_stale", True)),
        capture_backend=cap.get("backend", "gstreamer"),
        driver_pipeline=cap.get("driver_pipeline", ""),
        road_pipeline=cap.get("road_pipeline", ""),
        inference=raw.get("inference", {}),
        thresholds={k: float(v) for k, v in raw.get("thresholds", {}).items()},
        gateway=raw.get("gateway", {}),
        storage=raw.get("storage", {}),
        sync=raw.get("sync", {}),
        privacy=raw.get("privacy", {}),
        recording=raw.get("recording", {}),
        analysis_log=raw.get("analysis_log", {}),
    )

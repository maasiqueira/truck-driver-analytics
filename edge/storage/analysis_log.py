from __future__ import annotations

import json
import logging
import threading
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

log = logging.getLogger(__name__)


@dataclass
class AnalysisLogConfig:
    enabled: bool = True
    subdir: str = "analysis"
    flush_interval_s: float = 1.0


@dataclass
class AnalysisLogWriter:
    base_dir: Path
    session_id: str
    cfg: AnalysisLogConfig
    _path: Path | None = field(default=None, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)
    _buffer: list[dict[str, Any]] = field(default_factory=list, init=False)
    _last_flush: float = field(default=0.0, init=False)

    def start(self) -> None:
        if not self.cfg.enabled:
            return
        out = self.base_dir / self.cfg.subdir
        out.mkdir(parents=True, exist_ok=True)
        self._path = out / f"{self.session_id}.jsonl"
        log.info("analysis log %s", self._path)

    def append(
        self,
        timestamp_mono: float,
        driver_metrics: dict[str, float] | None,
        road_metrics: dict[str, float] | None,
        events: list[str] | None = None,
        extra: dict[str, Any] | None = None,
    ) -> None:
        if not self.cfg.enabled or self._path is None:
            return
        row: dict[str, Any] = {
            "ts_mono": timestamp_mono,
            "driver": driver_metrics,
            "road": road_metrics,
        }
        if events:
            row["events"] = events
        if extra:
            row.update(extra)
        with self._lock:
            self._buffer.append(row)
            now = time.monotonic()
            if now - self._last_flush >= self.cfg.flush_interval_s:
                self._flush_unlocked()
                self._last_flush = now

    def _flush_unlocked(self) -> None:
        if not self._buffer or self._path is None:
            return
        with open(self._path, "a", encoding="utf-8") as f:
            for row in self._buffer:
                f.write(json.dumps(row, separators=(",", ":")) + "\n")
        self._buffer.clear()

    def stop(self) -> None:
        with self._lock:
            self._flush_unlocked()

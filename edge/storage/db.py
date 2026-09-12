from __future__ import annotations

import json
import sqlite3
import threading
import time
from dataclasses import dataclass
from pathlib import Path

from edge.fusion.engine import FiredEvent


SCHEMA = """
CREATE TABLE IF NOT EXISTS sessions (
  session_id TEXT PRIMARY KEY,
  started_at REAL,
  ended_at REAL,
  score REAL,
  report_json TEXT
);
CREATE TABLE IF NOT EXISTS events (
  event_id TEXT PRIMARY KEY,
  session_id TEXT,
  ts REAL,
  type TEXT,
  severity INTEGER,
  duration_s REAL,
  metadata_json TEXT,
  clip_path TEXT
);
CREATE TABLE IF NOT EXISTS sync_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  payload_json TEXT,
  created_at REAL,
  synced INTEGER DEFAULT 0
);
"""


@dataclass
class EventStore:
    db_path: Path
    _lock: threading.Lock = threading.Lock()

    def __post_init__(self) -> None:
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        with self._connect() as conn:
            conn.executescript(SCHEMA)

    def _connect(self) -> sqlite3.Connection:
        return sqlite3.connect(self.db_path, check_same_thread=False)

    def start_session(self, session_id: str) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "INSERT OR REPLACE INTO sessions(session_id, started_at, score) VALUES (?, ?, ?)",
                (session_id, time.time(), 100.0),
            )

    def insert_event(self, ev: FiredEvent, clip_path: str | None = None) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                """INSERT INTO events(event_id, session_id, ts, type, severity, duration_s, metadata_json, clip_path)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    ev.event_id,
                    ev.session_id,
                    ev.timestamp_mono,
                    ev.event_type.value,
                    ev.severity,
                    ev.duration_s,
                    json.dumps(ev.metadata),
                    clip_path,
                ),
            )
            conn.execute(
                "INSERT INTO sync_queue(payload_json, created_at) VALUES (?, ?)",
                (
                    json.dumps(
                        {
                            "event_id": ev.event_id,
                            "session_id": ev.session_id,
                            "type": ev.event_type.value,
                            "severity": ev.severity,
                            "metadata": ev.metadata,
                            "clip_path": clip_path,
                        }
                    ),
                    time.time(),
                ),
            )

    def finish_session(self, session_id: str, report: dict) -> None:
        with self._lock, self._connect() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at=?, score=?, report_json=? WHERE session_id=?",
                (time.time(), report.get("score"), json.dumps(report), session_id),
            )

    def pending_sync(self, limit: int = 50) -> list[dict]:
        with self._lock, self._connect() as conn:
            rows = conn.execute(
                "SELECT id, payload_json FROM sync_queue WHERE synced=0 ORDER BY id LIMIT ?",
                (limit,),
            ).fetchall()
        return [{"id": r[0], "payload": json.loads(r[1])} for r in rows]

    def mark_synced(self, ids: list[int]) -> None:
        if not ids:
            return
        with self._lock, self._connect() as conn:
            conn.executemany("UPDATE sync_queue SET synced=1 WHERE id=?", [(i,) for i in ids])

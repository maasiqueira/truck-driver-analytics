from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


def main() -> None:
    parser = argparse.ArgumentParser(description="Replay session events from SQLite")
    parser.add_argument("--db", required=True)
    parser.add_argument("--session-id", required=True)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    rows = conn.execute(
        "SELECT ts, type, severity, metadata_json, clip_path FROM events WHERE session_id=? ORDER BY ts",
        (args.session_id,),
    ).fetchall()
    for ts, typ, sev, meta, clip in rows:
        print(
            json.dumps(
                {
                    "ts": ts,
                    "type": typ,
                    "severity": sev,
                    "metadata": json.loads(meta or "{}"),
                    "clip_path": clip,
                }
            )
        )


if __name__ == "__main__":
    main()

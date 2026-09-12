from __future__ import annotations

import argparse
import json
import sqlite3
from pathlib import Path


MVP_CRITERIA = [
    "dual_camera_runtime",
    "drowsiness_detection",
    "distraction_detection",
    "phone_use_confirmed",
    "lane_departure",
    "tailgating",
    "hard_brake_or_turn",
    "event_clip_export",
    "session_report_export",
]


def main() -> None:
    parser = argparse.ArgumentParser(description="MVP acceptance checklist from SQLite session")
    parser.add_argument("--db", required=True)
    parser.add_argument("--session-id", required=True)
    parser.add_argument("--runtime-hours", type=float, default=0.0)
    args = parser.parse_args()

    conn = sqlite3.connect(args.db)
    types = {
        row[0]
        for row in conn.execute(
            "SELECT DISTINCT type FROM events WHERE session_id=?", (args.session_id,)
        ).fetchall()
    }
    report_path = Path(args.db).parent / "reports" / f"{args.session_id}.json"
    checks = {
        "dual_camera_runtime": args.runtime_hours >= 8.0,
        "drowsiness_detection": "DROWSINESS" in types,
        "distraction_detection": "DISTRACTION" in types,
        "phone_use_confirmed": "PHONE_USE" in types,
        "lane_departure": "LANE_DEPARTURE" in types,
        "tailgating": "TAILGATING" in types,
        "hard_brake_or_turn": bool(types & {"HARD_BRAKE", "HARD_TURN"}),
        "event_clip_export": any(
            row[0]
            for row in conn.execute(
                "SELECT clip_path FROM events WHERE session_id=? AND clip_path IS NOT NULL",
                (args.session_id,),
            ).fetchall()
        ),
        "session_report_export": report_path.exists(),
    }
    passed = sum(1 for k in MVP_CRITERIA if checks.get(k))
    print(json.dumps({"checks": checks, "passed": passed, "total": len(MVP_CRITERIA)}, indent=2))


if __name__ == "__main__":
    main()

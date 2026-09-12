from __future__ import annotations

import argparse
import csv
import json
import logging
import signal
import sys
import time
from pathlib import Path

from edge.capture.dual_camera import DualCameraCapture
from edge.config import load_config
from edge.fusion.engine import FusionEngine
from edge.perception.dms import DmsRunner
from edge.perception.onnx_runner import OnnxRunner
from edge.perception.road import RoadRunner
from edge.scoring.session_score import SessionScore
from edge.sensors.gateway_client import GatewayClient
from edge.storage.analysis_log import AnalysisLogConfig, AnalysisLogWriter
from edge.storage.clip_exporter import ClipExporter
from edge.storage.db import EventStore
from edge.storage.raw_recorder import RawVideoRecorder, RecordingConfig
from edge.storage.ring_buffer import RingBuffer
from edge.storage.sd_layout import resolve_data_dir
from edge.sync.uplink import OtaManager, SyncWorker

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
log = logging.getLogger("tda.main")


def main() -> None:
    parser = argparse.ArgumentParser(description="Truck driver analytics edge runtime")
    parser.add_argument("--config", default="edge/config/default.yaml")
    parser.add_argument("--max-seconds", type=float, default=0.0, help="0 = run until SIGINT")
    args = parser.parse_args()

    cfg = load_config(args.config)
    storage = cfg.storage
    data_dir = resolve_data_dir(str(storage.get("data_dir", "./data/runtime")))
    log.info("using data_dir=%s platform=%s", data_dir, cfg.platform)
    store = EventStore(data_dir / storage.get("sqlite", "events.db"))

    inf = cfg.inference
    phone_onnx = OnnxRunner(inf.get("road_yolo", "models/weights/yolov8n.onnx"))
    dms = DmsRunner(
        ear_threshold=cfg.thresholds.get("ear_closed", 0.21),
        phone_runner=phone_onnx if phone_onnx.ready else None,
    )
    road = RoadRunner(
        input_size=int(inf.get("road_input_size", 640)),
        model_path=inf.get("road_yolo", "models/weights/yolov8n.onnx"),
        lane_departure_offset_ratio=cfg.thresholds.get("lane_departure_offset_ratio", 0.12),
    )

    fusion = FusionEngine(cfg)
    fusion.start()
    score = SessionScore(session_id=fusion.session_id)
    store.start_session(fusion.session_id)

    ring = RingBuffer(
        float(storage.get("ring_buffer_s", 120)),
        target_fps=float(inf.get("target_fps_driver", 12)),
    )
    clips = ClipExporter(
        data_dir / "clips",
        clip_max_s=float(storage.get("clip_max_s", 30)),
    )

    rec_cfg_raw = cfg.recording
    rec_cfg = RecordingConfig(
        enabled=bool(rec_cfg_raw.get("enabled", False)),
        video_subdir=str(rec_cfg_raw.get("video_subdir", "videos")),
        segment_s=float(rec_cfg_raw.get("segment_s", 900)),
        codec=str(rec_cfg_raw.get("codec", "mp4v")),
        fps=float(cfg.cameras["driver"].fps if "driver" in cfg.cameras else 15),
    )
    raw_recorder = RawVideoRecorder(data_dir, fusion.session_id, rec_cfg)
    raw_recorder.start()

    al_raw = cfg.analysis_log
    analysis_log = AnalysisLogWriter(
        data_dir,
        fusion.session_id,
        AnalysisLogConfig(
            enabled=bool(al_raw.get("enabled", False)),
            subdir=str(al_raw.get("subdir", "analysis")),
            flush_interval_s=float(al_raw.get("flush_interval_s", 1.0)),
        ),
    )
    analysis_log.start()

    gateway: GatewayClient | None = None
    if cfg.gateway.get("enabled"):
        gateway = GatewayClient(
            host=str(cfg.gateway.get("host", "192.168.7.1")),
            port=int(cfg.gateway.get("port", 8765)),
            reconnect_s=float(cfg.gateway.get("reconnect_s", 5)),
            on_update=lambda st: fusion.update_telemetry(st),
        )
        gateway.start()

    sync_worker: SyncWorker | None = None
    if cfg.sync.get("enabled"):
        sync_worker = SyncWorker(
            store,
            str(cfg.sync.get("api_base")),
            str(cfg.sync.get("device_id")),
            interval_s=float(cfg.sync.get("interval_s", 60)),
            batch_size=int(cfg.sync.get("batch_size", 50)),
        )
        sync_worker.start()

    if cfg.sync.get("enabled"):
        try:
            OtaManager(Path("models/weights"), str(cfg.sync.get("api_base")), str(cfg.sync.get("device_id"))).check_and_apply("0.1.0")
        except Exception:
            log.debug("OTA skipped (offline or dev)")

    capture = DualCameraCapture(cfg)
    capture.start()

    stop = False

    def _sig(_s, _f):
        nonlocal stop
        stop = True

    signal.signal(signal.SIGINT, _sig)
    if hasattr(signal, "SIGTERM"):
        signal.signal(signal.SIGTERM, _sig)

    t0 = time.monotonic()
    session_t0 = time.time()
    log.info("session %s platform=%s", fusion.session_id, cfg.platform)

    try:
        while not stop:
            if args.max_seconds and (time.monotonic() - t0) >= args.max_seconds:
                break
            pkt = capture.poll_pair(timeout=0.3)
            if pkt is None:
                continue

            speed = fusion.current_speed_kmh()
            pause_cabin = (
                cfg.privacy.get("pause_cabin_when_ignition_off")
                and speed < float(cfg.privacy.get("cabin_min_speed_kmh", 5))
            )

            driver_res = None
            road_res = None
            if pkt.driver is not None and not pause_cabin:
                ring.push("driver", pkt.timestamp_mono, pkt.driver)
                raw_recorder.write("driver", pkt.driver)
                driver_res = dms.process(pkt.driver, pkt.timestamp_mono)
            if pkt.road is not None:
                ring.push("road", pkt.timestamp_mono, pkt.road)
                raw_recorder.write("road", pkt.road)
                road_res = road.process(pkt.road, pkt.timestamp_mono)

            fired = fusion.process(driver_res, road_res)
            analysis_log.append(
                pkt.timestamp_mono,
                driver_res.metrics if driver_res else None,
                road_res.metrics if road_res else None,
                events=[e.event_type.value for e in fired],
                extra={"speed_kmh": fusion.current_speed_kmh()},
            )

            for ev in fired:
                score.apply_event(ev)
                pre = float(storage.get("clip_pre_s", 5))
                post = float(storage.get("clip_post_s", 10))
                d_slice = ring.slice("driver", ev.timestamp_mono, pre, post)
                r_slice = ring.slice("road", ev.timestamp_mono, pre, post)
                clip_path = clips.export_side_by_side(ev.event_id, d_slice, r_slice)
                store.insert_event(ev, clip_path)
                log.info("event %s sev=%s %s", ev.event_type.value, ev.severity, ev.metadata)

            score.duration_s = time.time() - session_t0
    finally:
        capture.stop()
        raw_recorder.stop()
        analysis_log.stop()
        fusion.stop()
        if gateway:
            gateway.stop()
        if sync_worker:
            sync_worker.stop()
        report = score.to_report()
        store.finish_session(fusion.session_id, report)
        export_session_report(data_dir, fusion.session_id, report)
        log.info("session finished score=%.1f", report["score"])


def export_session_report(data_dir: Path, session_id: str, report: dict) -> None:
    out = data_dir / "reports"
    out.mkdir(parents=True, exist_ok=True)
    json_path = out / f"{session_id}.json"
    csv_path = out / f"{session_id}.csv"
    json_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    with open(csv_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)
        w.writerow(["event_type", "severity", "penalty", "timestamp_mono"])
        for p in report.get("penalties", []):
            w.writerow([p.get("event_type"), p.get("severity"), p.get("penalty"), p.get("timestamp_mono")])


if __name__ == "__main__":
    main()

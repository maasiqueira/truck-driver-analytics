from __future__ import annotations

import argparse
import json
import logging
import socket
import threading
import time
from pathlib import Path

import yaml

from edge.sensors.can_j1939 import CanBusReader, VehicleSample
from edge.sensors.gps_nmea import GnssNmeaReader, GnssSample

logging.basicConfig(level=logging.INFO)
log = logging.getLogger(__name__)


class GatewayService:
    def __init__(self, cfg: dict):
        self.host = cfg["listen"]["host"]
        self.port = int(cfg["listen"]["port"])
        can = cfg.get("can", {})
        gps = cfg.get("gps", {})
        self._clients: list[socket.socket] = []
        self._lock = threading.Lock()
        self._latest_vehicle: VehicleSample | None = None
        self._latest_gnss: GnssSample | None = None

        def on_vehicle(v: VehicleSample) -> None:
            self._latest_vehicle = v
            self._broadcast(
                {
                    "type": "vehicle",
                    "speed_kmh": v.speed_kmh,
                    "wheel_speed_kmh": v.wheel_speed_kmh,
                    "brake_active": v.brake_active,
                    "throttle_pct": v.throttle_pct,
                }
            )

        def on_gnss(g: GnssSample) -> None:
            self._latest_gnss = g
            self._broadcast(
                {
                    "type": "gnss",
                    "lat": g.lat,
                    "lon": g.lon,
                    "speed_kmh": g.speed_kmh,
                    "heading_deg": g.heading_deg,
                    "fix_quality": g.fix_quality,
                }
            )

        self._can = CanBusReader(
            interface=can.get("interface", "can0"),
            bustype=can.get("bustype", "socketcan"),
            bitrate=int(can.get("bitrate", 250000)),
            wheel_speed_pgn=int(can.get("j1939", {}).get("wheel_speed_pgn", 0xFEF1)),
            on_sample=on_vehicle,
        )
        self._gps = GpsNmeaReader(
            port=gps.get("port", "/dev/ttyUSB0"),
            baud=int(gps.get("baud", 9600)),
            on_sample=on_gnss,
        )

    def _broadcast(self, payload: dict) -> None:
        line = (json.dumps(payload, separators=(",", ":")) + "\n").encode("utf-8")
        with self._lock:
            dead: list[socket.socket] = []
            for c in self._clients:
                try:
                    c.sendall(line)
                except OSError:
                    dead.append(c)
            for c in dead:
                self._clients.remove(c)

    def _accept_loop(self) -> None:
        srv = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        srv.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        srv.bind((self.host, self.port))
        srv.listen(8)
        log.info("gateway listening on %s:%s", self.host, self.port)
        while True:
            conn, addr = srv.accept()
            log.info("client %s", addr)
            with self._lock:
                self._clients.append(conn)
            if self._latest_vehicle:
                v = self._latest_vehicle
                self._broadcast(
                    {
                        "type": "vehicle",
                        "speed_kmh": v.speed_kmh,
                        "wheel_speed_kmh": v.wheel_speed_kmh,
                        "brake_active": v.brake_active,
                        "throttle_pct": v.throttle_pct,
                    }
                )

    def run(self) -> None:
        self._can.start()
        self._gps.start()
        self._accept_loop()


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", default="edge/config/gateway_stm32.yaml")
    args = parser.parse_args()
    with open(args.config, encoding="utf-8") as f:
        cfg = yaml.safe_load(f)
    GatewayService(cfg).run()


if __name__ == "__main__":
    main()

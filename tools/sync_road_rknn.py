"""Sync RKNN road integration files to EAI board (no full tarball)."""

from __future__ import annotations

import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parents[1]
REMOTE = "/home/nano/truck-driver-analytics"
FILES = [
    "edge/main.py",
    "edge/perception/road.py",
    "edge/perception/dms.py",
    "edge/perception/yolov5_rknn.py",
    "edge/perception/yolov5_postprocess.py",
    "edge/perception/retinaface_rknn.py",
    "edge/perception/retinaface_postprocess.py",
    "edge/perception/dms_rknn_metrics.py",
    "edge/config/eai_nano_tb.yaml",
    "models/weights/yolov5n_rv1126b_fp.rknn",
    "models/weights/RetinaFace_mobile320_rv1126b_fp.rknn",
]


def main() -> None:
    password = os.environ.get("TDA_SSH_PASSWORD", "123456")
    host = os.environ.get("TDA_SSH_HOST", "192.168.15.87")
    user = os.environ.get("TDA_SSH_USER", "nano")

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(host, username=user, password=password, timeout=30)
    sftp = client.open_sftp()
    for rel in FILES:
        local = ROOT / rel
        if not local.is_file():
            print(f"missing local: {local}", file=sys.stderr)
            sys.exit(1)
        remote = f"{REMOTE}/{rel.replace(chr(92), '/')}"
        remote_dir = str(Path(remote).parent).replace(chr(92), "/")
        client.exec_command(f"mkdir -p {remote_dir}")
        print(f"put {rel}")
        sftp.put(str(local), remote)
    sftp.close()

    cmd = (
        f"echo '{password}' | sudo -S chmod 666 /dev/rknpu 2>/dev/null; "
        f"cd {REMOTE} && source .venv/bin/activate && "
        f"python3 -c \"from edge.perception.dms import DmsRunner; from edge.perception.road import RoadRunner; "
        f"import numpy as np; img=np.zeros((480,640,3),np.uint8); "
        f"d=DmsRunner(dms_backend='rknn'); m=d.process(img,0.0); "
        f"print('dms_ok metrics_keys', len(m.metrics)); "
        f"r=RoadRunner(road_backend='rknn'); print('vehicles', len(r._detect_vehicles(img)))\""
    )
    _, stdout, stderr = client.exec_command(cmd, timeout=120)
    print(stdout.read().decode())
    err = stderr.read().decode()
    if err.strip():
        print(err, file=sys.stderr)
    client.close()


if __name__ == "__main__":
    main()

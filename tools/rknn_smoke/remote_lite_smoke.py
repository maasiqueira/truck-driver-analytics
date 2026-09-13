"""Copy Lite2 wheel + RKNN model to EAI board, pip install, run board_lite_smoke.py."""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

import paramiko

ROOT = Path(__file__).resolve().parent
REPO = ROOT.parents[1]
DEFAULT_WHEEL = ROOT / "wheels" / (
    "rknn_toolkit_lite2-2.3.2-cp310-cp310-manylinux_2_17_aarch64.manylinux2014_aarch64.whl"
)
REMOTE_DIR = "/home/nano/truck-driver-analytics/tools/rknn_smoke"
VENV = "/home/nano/truck-driver-analytics/.venv"


def run_ssh(client: paramiko.SSHClient, cmd: str) -> tuple[int, str, str]:
    _, stdout, stderr = client.exec_command(cmd, timeout=600)
    out = stdout.read().decode(errors="replace")
    err = stderr.read().decode(errors="replace")
    code = stdout.channel.recv_exit_status()
    return code, out, err


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.15.87")
    parser.add_argument("--user", default="nano")
    parser.add_argument("--password", default=os.environ.get("TDA_SSH_PASSWORD", "123456"))
    parser.add_argument("--wheel", type=Path, default=DEFAULT_WHEEL)
    parser.add_argument(
        "--model",
        type=Path,
        default=ROOT / "yolov5n_rv1126b_fp.rknn",
    )
    args = parser.parse_args()

    if not args.wheel.is_file():
        print(f"Wheel missing: {args.wheel}", file=sys.stderr)
        sys.exit(1)
    if not args.model.is_file():
        print(f"RKNN model missing: {args.model}", file=sys.stderr)
        sys.exit(1)

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)
    sftp = client.open_sftp()
    try:
        run_ssh(client, f"mkdir -p {REMOTE_DIR}")
        remote_wheel = f"{REMOTE_DIR}/{args.wheel.name}"
        remote_model = f"{REMOTE_DIR}/{args.model.name}"
        remote_script = f"{REMOTE_DIR}/board_lite_smoke.py"
        print(f"upload wheel -> {remote_wheel}")
        sftp.put(str(args.wheel), remote_wheel)
        print(f"upload model -> {remote_model}")
        sftp.put(str(args.model), remote_model)
        print(f"upload script -> {remote_script}")
        sftp.put(str(ROOT / "board_lite_smoke.py"), remote_script)
    finally:
        sftp.close()

    # /dev/rknpu is often root-only on Armbian; Lite2 needs read/write access.
    fix_perms = (
        f"echo '{args.password}' | sudo -S chmod 666 /dev/rknpu 2>/dev/null || true; "
    )
    pip_cmd = (
        f"set -e; {fix_perms} source {VENV}/bin/activate; "
        f"pip install -U pip; "
        f"pip install '{REMOTE_DIR}/{args.wheel.name}'; "
        f"python3 -c \"from rknnlite.api import RKNNLite; print('import OK')\"; "
        f"python3 {REMOTE_DIR}/board_lite_smoke.py --model {REMOTE_DIR}/{args.model.name} --size 640"
    )
    print("running on board...")
    code, out, err = run_ssh(client, pip_cmd)
    print(out)
    if err.strip():
        print(err, file=sys.stderr)
    client.close()
    if code != 0:
        sys.exit(code)
    print("Smoke test passed.")


if __name__ == "__main__":
    main()

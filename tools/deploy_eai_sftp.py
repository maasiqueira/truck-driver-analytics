"""Deploy truck-driver-analytics to EAI-Nano-TB via SFTP (paramiko)."""

from __future__ import annotations

import argparse
import os
import sys
import tarfile
import tempfile
from pathlib import Path

import paramiko

EXCLUDE_DIRS = {
    ".venv",
    "__pycache__",
    ".pytest_cache",
    "truck_driver_analytics.egg-info",
    "data/runtime",
    ".git",
    ".cursor",
    "Rockchip",
    "tools/rknn_smoke",
}
EXCLUDE_SUFFIX = {".pyc", ".mp4", ".db"}


def should_add(path: Path, root: Path) -> bool:
    rel = path.relative_to(root)
    if any(part in EXCLUDE_DIRS for part in rel.parts):
        return False
    if path.suffix in EXCLUDE_SUFFIX:
        return False
    return True


def make_tar(project_root: Path) -> Path:
    tmp = tempfile.NamedTemporaryFile(suffix=".tar.gz", delete=False)
    tmp.close()
    with tarfile.open(tmp.name, "w:gz") as tar:
        for path in project_root.rglob("*"):
            if path.is_file() and should_add(path, project_root):
                tar.add(path, arcname=path.relative_to(project_root).as_posix())
    return Path(tmp.name)


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--host", default="192.168.15.87")
    parser.add_argument("--user", default="nano")
    parser.add_argument("--password", default=os.environ.get("TDA_SSH_PASSWORD", ""))
    parser.add_argument("--project-root", default=".")
    args = parser.parse_args()
    if not args.password:
        print("Set TDA_SSH_PASSWORD or pass --password", file=sys.stderr)
        sys.exit(1)

    root = Path(args.project_root).resolve()
    tarball = make_tar(root)
    remote_tar = f"/home/{args.user}/truck-driver-analytics.tgz"
    remote_dir = f"/home/{args.user}/truck-driver-analytics"

    client = paramiko.SSHClient()
    client.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    client.connect(args.host, username=args.user, password=args.password, timeout=30)
    sftp = client.open_sftp()
    print(f"upload {tarball} -> {remote_tar}")
    sftp.put(str(tarball), remote_tar)
    sftp.close()
    tarball.unlink(missing_ok=True)

    commands = f"""
set -e
mkdir -p {remote_dir}
tar -xzf {remote_tar} -C {remote_dir}
rm -f {remote_tar}
mkdir -p /home/nano/tda-data
cd {remote_dir}
python3 -m venv .venv
. .venv/bin/activate
pip install -U pip wheel
pip install -e ".[embedded]"
echo 'Deploy finished.'
"""
    stdin, stdout, stderr = client.exec_command(commands, get_pty=True)
    stdout.channel.recv_exit_status()
    out = stdout.read().decode("utf-8", "replace")
    err = stderr.read().decode("utf-8", "replace")
    sys.stdout.buffer.write(out.encode("utf-8", errors="replace"))
    if err:
        sys.stderr.buffer.write(err.encode("utf-8", errors="replace"))
    client.close()


if __name__ == "__main__":
    main()

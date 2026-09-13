import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
pw = os.environ.get("TDA_SSH_PASSWORD", "123456")
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.15.87", username="nano", password=pw, timeout=15)

cmds = [
    "cd ~/truck-driver-analytics && . .venv/bin/activate && "
    "tda-benchmark-capture --config edge/config/eai_nano_tb.yaml --duration 20 2>&1",
    "find ~/tda-data -type f 2>/dev/null | wc -l",
    "find ~/tda-data -type f 2>/dev/null | head -25",
    "du -sh ~/tda-data ~/tda-data/videos 2>/dev/null",
    "ls -lt ~/tda-data/reports/ 2>/dev/null | head -5",
    "wc -l ~/tda-data/analysis/*.jsonl 2>/dev/null",
    "python3 -c \"import sqlite3; c=sqlite3.connect('/home/nano/tda-data/events.db'); "
    "print(c.execute('select type, count(1) from events group by type').fetchall())\" 2>/dev/null",
    "systemctl is-active tda-eai-nano 2>/dev/null || echo service_not_enabled",
    "pip show mediapipe 2>/dev/null | head -1 || echo no_mediapipe",
]
for cmd in cmds:
    print("\n========", cmd[:85], "========")
    _, stdout, _ = c.exec_command(cmd, timeout=180)
    print(stdout.read().decode("utf-8", "replace"))
c.close()

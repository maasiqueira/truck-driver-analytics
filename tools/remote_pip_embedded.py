import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
pw = os.environ["TDA_SSH_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.15.87", username="nano", password=pw, timeout=30)
cmd = "cd /home/nano/truck-driver-analytics && . .venv/bin/activate && pip install -e '.[embedded]'"
stdin, stdout, stderr = c.exec_command(cmd, get_pty=True, timeout=900)
print(stdout.read().decode("utf-8", "replace"))
print(stderr.read().decode("utf-8", "replace"), file=sys.stderr)
print("exit", stdout.channel.recv_exit_status())
c.close()

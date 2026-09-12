import os
import paramiko
import sys

sys.stdout.reconfigure(encoding="utf-8", errors="replace")
pw = os.environ["TDA_SSH_PASSWORD"]
c = paramiko.SSHClient()
c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
c.connect("192.168.15.87", username="nano", password=pw, timeout=30)
cmds = [
    "gst-launch-1.0 -e v4l2src device=/dev/video23 num-buffers=5 ! fakesink 2>&1 | tail -6",
    "gst-launch-1.0 -e v4l2src device=/dev/video23 num-buffers=5 ! "
    "'video/x-raw,format=NV12,width=1920,height=1080' ! fakesink 2>&1 | tail -8",
    "cd /home/nano/truck-driver-analytics && . .venv/bin/activate && python3 -c \"import cv2; "
    "c=cv2.VideoCapture('/dev/video23'); print('opencv', c.isOpened()); "
    "ok,f=c.read(); print('read', ok, None if f is None else f.shape)\"",
]
for cmd in cmds:
    print(">>>", cmd[:100])
    _, stdout, _ = c.exec_command(cmd, timeout=90)
    print(stdout.read().decode("utf-8", "replace"))
c.close()

#!/usr/bin/env bash
set -euo pipefail

DRIVER=${TDA_DRIVER_DEV:-/dev/video23}
ROAD=${TDA_ROAD_DEV:-/dev/video31}

echo "=== v4l2 devices ==="
v4l2-ctl --list-devices || true

for dev in "$DRIVER" "$ROAD"; do
  echo ""
  echo "=== $dev formats ==="
  v4l2-ctl -d "$dev" --list-formats-ext || echo "missing $dev"
done

echo ""
echo "=== one frame test (GStreamer) ==="
gst-launch-1.0 -e v4l2src device="$DRIVER" num-buffers=30 ! fakesink sync=false || true

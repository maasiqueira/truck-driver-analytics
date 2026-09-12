#!/usr/bin/env bash
# Montar partição do cartão (mmcblk1p2) em /mnt/microsd — revisar lsblk antes.
set -euo pipefail
DEV=${TDA_SD_PART:-/dev/mmcblk1p2}
MNT=${TDA_SD_MOUNT:-/mnt/microsd}

sudo mkdir -p "$MNT"
if mountpoint -q "$MNT"; then
  echo "already mounted: $MNT"
  exit 0
fi
sudo mount "$DEV" "$MNT"
sudo mkdir -p "$MNT/tda"
sudo chown -R nano:nano "$MNT/tda"
echo "OK: use storage.data_dir: $MNT/tda in eai_nano_tb.yaml"

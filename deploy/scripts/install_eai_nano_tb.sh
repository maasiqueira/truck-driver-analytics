#!/usr/bin/env bash
# Executar NA placa como usuário nano (não root).
set -euo pipefail

REPO="${1:-$HOME/truck-driver-analytics}"
CFG="${TDA_CONFIG:-$REPO/edge/config/eai_nano_tb.yaml}"

cd "$REPO"
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip wheel
pip install -e ".[embedded]"

mkdir -p /mnt/microsd/tda 2>/dev/null || true
export TDA_DATA_DIR="${TDA_DATA_DIR:-/mnt/microsd/tda}"

echo "Install OK. Test:"
echo "  source $REPO/.venv/bin/activate"
echo "  tda-benchmark-capture --config $CFG --duration 15"
echo "  tda-run --config $CFG --max-seconds 60"

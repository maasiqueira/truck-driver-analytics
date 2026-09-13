# EASY EAI-Nano-TB (RV1126B + IMX415)

Placa **EAI-Nano-TB**, Linux **Armbian**, SoC **Rockchip RV1126B**, duas **EAI-CAM-IMX415** (MIPI-CSI), display MIPI-DSI (preview opcional).

| Stream | Device | Papel |
|--------|--------|--------|
| Cabine (DMS) | `/dev/video23` | Motorista |
| Estrada (ADAS) | `/dev/video31` | Via à frente |

Config principal: [`edge/config/eai_nano_tb.yaml`](../edge/config/eai_nano_tb.yaml)

## Estrutura no microSD

Tudo sob `storage.data_dir` (padrão `/mnt/microsd/tda`):

```
/mnt/microsd/tda/
  events.db              # eventos + fila sync
  videos/<session_id>/   # gravação bruta segmentada
    driver_seg0000.mp4
    road_seg0000.mp4
  analysis/<session_id>.jsonl   # métricas DMS/ADAS em tempo real
  clips/                 # clipes por evento
  reports/               # JSON/CSV da sessão
```

## 1. Preparar microSD na placa

SSH (senha interativa no seu PC):

```bash
ssh nano@192.168.15.87
```

Identificar montagem:

```bash
lsblk -f
df -h
```

Criar ponto de montagem persistente (exemplo — ajuste a partição):

```bash
sudo mkdir -p /mnt/microsd
# Se o cartão monta em /media/nano/XXXX, pode usar symlink:
# sudo ln -sf /media/nano/XXXX /mnt/microsd
sudo mkdir -p /mnt/microsd/tda
sudo chown -R nano:nano /mnt/microsd/tda
```

Opcional `/etc/fstab` para montar boot (cuidado com `nofail`).

## 2. Dependências (Armbian)

```bash
sudo apt update
sudo apt install -y python3 python3-venv python3-pip \
  gstreamer1.0-tools gstreamer1.0-plugins-base gstreamer1.0-plugins-good \
  v4l-utils libopencv-dev
```

## 3. Clonar do GitHub (maasiqueira)

```bash
cd ~
git clone https://github.com/maasiqueira/truck-driver-analytics.git
cd truck-driver-analytics
python3 -m venv .venv
source .venv/bin/activate
pip install -U pip
pip install -e ".[embedded]"
```

> **RV1126B:** não instale `mediapipe` nesta placa (binário exige LSE). Use `dms_backend: rknn` com RetinaFace (ver abaixo).

**RKNN (NPU):** instale `rknn-toolkit-lite2` 2.3.2 (wheel aarch64 cp310) no venv. Copie os `.rknn` para `models/weights/` (não versionados no git; gere com `tools/rknn_smoke/`):

- Estrada: `yolov5n_rv1126b_fp.rknn` + `road_backend: rknn`
- Cabine: `RetinaFace_mobile320_rv1126b_fp.rknn` + `dms_backend: rknn` (EAR/MAR são *proxies* geométricos — ajuste `thresholds.ear_closed` no veículo)
- Celular: `dms_phone_via_rknn: true` (reutiliza o mesmo YOLOv5n)

Se `init_runtime` falhar: `sudo chmod 666 /dev/rknpu` (ou udev permanente). Sync rápido: `python tools/sync_road_rknn.py`.

Modelos:

```bash
python models/export/onnx_export.py --size n
# Face landmarker baixa automaticamente no primeiro run (MediaPipe Tasks)
```

## 4. Validar câmeras

```bash
bash deploy/scripts/probe_eai_cameras.sh
tda-benchmark-capture --config edge/config/eai_nano_tb.yaml --duration 30
```

Se GStreamer falhar, liste formatos:

```bash
v4l2-ctl -d /dev/video23 --list-formats-ext
v4l2-ctl -d /dev/video31 --list-formats-ext
```

Ajuste `width`, `height`, `framerate` e `format` em `eai_nano_tb.yaml`.

## 5. Rodar avaliação embarcada

```bash
export TDA_CONFIG=$HOME/truck-driver-analytics/edge/config/eai_nano_tb.yaml
tda-run --config "$TDA_CONFIG"
```

Teste 2 minutos:

```bash
tda-run --config edge/config/eai_nano_tb.yaml --max-seconds 120
```

## 6. Serviço systemd

```bash
sudo cp deploy/systemd/tda-eai-nano.service /etc/systemd/system/
sudo sed -i "s|/opt/truck-driver-analytics|$HOME/truck-driver-analytics|g" /etc/systemd/system/tda-eai-nano.service
sudo systemctl daemon-reload
sudo systemctl enable --now tda-eai-nano
journalctl -u tda-eai-nano -f
```

## 7. Performance RV1126

- IMX415 @ 1080p15 em **duas** câmeras + DMS/ADAS exige CPU; se necessário:
  - Reduza para 1280×720 @ 15 fps
  - `target_fps_driver` / `target_fps_road`: 6–8
  - Use NPU Rockchip (RKNN) numa fase posterior — ONNX CPU é o MVP
- Display DSI: deixe `display.enabled: false` até precisar de preview (evita competir com banda MIPI)

## 8. Veículo

- Alimentação 12/24 V regulada; evite gravar com cartão quase cheio
- Fixe cabine/estrada; recalibre `sync_offset_ms` se necessário
- Copie dados do SD via `rsync` ou leitor no PC:

```bash
rsync -av nano@192.168.15.87:/mnt/microsd/tda/ ./backup_td/
```

## Troubleshooting

| Problema | Ação |
|----------|------|
| `/dev/video23` vazio | `media-ctl -p`, cabo CSI, driver IMX415 |
| Gravação cai em `./data/runtime` | SD não gravável — ver logs `using data_dir=` |
| FPS baixo | Resolução, skip inferência alternada driver/road |
| MediaPipe pesado | Reduzir FPS DMS; considerar RKNN |

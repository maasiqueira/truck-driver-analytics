# Truck Driver Analytics (MVP)

Sistema embarcado de avaliação de comportamento do motorista (DMS + ADAS leve) com **duas câmeras**, inferência em tempo real, eventos, clipes e gravação em **microSD**.

Plataformas documentadas:

| Plataforma | Doc |
|------------|-----|
| **EASY EAI-Nano-TB** (RV1126B, IMX415, Armbian) | [docs/eai_nano_tb.md](docs/eai_nano_tb.md) |
| BeagleY-AI + STM32MP157 (CAN/GPS/4G) | [docs/hardware_bom.md](docs/hardware_bom.md) |
| Dev PC (vídeos) | `edge/config/dev_sim.yaml` |

GitHub: [maasiqueira/truck-driver-analytics](https://github.com/maasiqueira/truck-driver-analytics) — ver [docs/github_maasiqueira.md](docs/github_maasiqueira.md).

## Topologia de hardware

```
[2× IMX219 V3Link] ──► BeagleY-AI (AM67A) ──USB3──► STM32MP157
                              │                         ├── CAN (J1939)
                              └── IMU integrado           ├── USB2 → GPS
                                                          └── Modem 4G
```

| Papel | Placa | Funções |
|-------|--------|---------|
| Visão + IA | BeagleY-AI | Captura dual sincronizada, DMS/ADAS, fusão, score, SQLite, clipes |
| Conectividade + veículo | STM32MP157 | CAN J1939, GPS NMEA, uplink 4G, bridge USB para telemetria |

## Quick start (dev / bancada)

```bash
python -m venv .venv
source .venv/bin/activate   # Windows: .venv\Scripts\activate
pip install -e ".[dev,can,gps]"

# Vídeos de teste (sem câmeras)
tda-run --config edge/config/dev_sim.yaml

# EAI-Nano-TB (RV1126B, /dev/video23 + /dev/video31, microSD)
tda-run --config edge/config/eai_nano_tb.yaml

# Benchmark de captura (GStreamer)
tda-benchmark-capture --config edge/config/eai_nano_tb.yaml

# Gateway (rodar na STM32MP157)
tda-gateway --config edge/config/gateway_stm32.yaml
```

Documentação: [docs/architecture.md](docs/architecture.md), [docs/hardware_bom.md](docs/hardware_bom.md).

# Catálogo de eventos

| Tipo | Descrição | Severidade base | Evidência |
|------|-----------|-----------------|-----------|
| DROWSINESS | PERCLOS / olhos fechados prolongado | 5 | EAR, vídeo cabine |
| DISTRACTION | Cabeça/olhar fora da via | 3 | yaw/pitch approx |
| PHONE_USE | Celular confirmado (janelas temporais) | 4 | YOLO + confirmação |
| LANE_DEPARTURE | Desvio de faixa (proxy bordas) | 4 | lane_offset_ratio |
| TAILGATING | TTC abaixo do limiar | 4 | lead vehicle bbox |
| HARD_BRAKE | Desaceleração CAN/GPS | 3 | m/s² |
| HARD_TURN | Yaw rate IMU | 3 | deg/s |
| NO_SEATBELT | Reservado pós-MVP | 2 | — |

## Fusão multimodal

- `LANE_DEPARTURE` + `DISTRACTION` ativa → severidade +1 (cap 5).
- `DROWSINESS` + desvio de faixa → severidade +2.

## Retenção sugerida (LGPD)

- Clipes de vídeo: 30 dias.
- Metadados de eventos: 12 meses.
- Consentimento do motorista e base legal documentada pela transportadora.

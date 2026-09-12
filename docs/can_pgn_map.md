# Mapa J1939 (veículo teste)

Documentar PGNs observados no caminhão de teste. Valores default no código referem-se a **Wheel-Based Vehicle Speed** (PGN 65265 / 0xFEF1).

| PGN (hex) | Nome | SPN | Unidade | Notas |
|-----------|------|-----|---------|-------|
| 0xFEF1 | EEC1 / Wheel speed | 84 | km/h (1/256) | Default em `gateway_stm32.yaml` |
| | Brake switch | | | A mapear no sniff |
| | Accelerator pedal | | | A mapear no sniff |

## Sniff (Linux / STM32)

```bash
candump can0 -t a | tee logs/can_sniff.log
```

Atualizar `edge/config/gateway_stm32.yaml` → `can.j1939.*` após identificar IDs corretos do fabricante.

## Fallback

Se CAN não expuser velocidade:

- Usar GPS (`GpsNmeaReader`) para derivar desaceleração.
- Usar IMU BeagleY para yaw rate e aceleração lateral.

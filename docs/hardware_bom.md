# BOM e interfaces — MVP

## Diagrama do usuário

```
[2 × Câmeras IMX219]
        |
[Arducam IMX219 V3Link Kit]
        |
[BeagleY-AI (AM67A)] ── IMU onboard
        |
     USB 3.0
        |
[Placa STM32MP157]
   |        |         |
  CAN    USB 3.0    USB 2.0 → GPS
              |
         Modem 4G
```

## BeagleY-AI (AM67A)

- **Função:** visão, inferência, fusão, armazenamento local, cliente de sync.
- **Câmeras:** V3Link termina no BeagleY (CSI/USB conforme carrier); duas IMX219 sincronizadas.
- **IMU:** leitura via IIO — configurar paths em produção (`/sys/bus/iio/devices/...`).
- **Inferência:** exportar YOLO para ONNX; compilar artifacts **TIDL** para C7x/MMA quando disponível no SDK BeagleY.
- **Serviços:** `tda-run`, `tda-benchmark-capture`.

## STM32MP157

- **Função:** CAN J1939, GPS, modem 4G, bridge TCP para BeagleY.
- **CAN:** SocketCAN `can0`, 250 kbit/s típico em caminhão.
- **GPS:** adaptador USB serial `/dev/ttyUSB0` (ajustar udev).
- **Rede:** modem gerenciado pelo NetworkManager; BeagleY usa rota default via STM32 se necessário.
- **Serviço:** `tda-gateway`.

## Bancada de desenvolvimento

- PC Windows/Linux com `edge/config/dev_sim.yaml` e vídeos em `data/samples/`.
- Gateway pode rodar em WSL/Linux com CAN simulado (`vcan0`).

## Checklist de bring-up

1. Validar ambas câmeras 1280×720@15 fps (`tda-benchmark-capture`).
2. Subir gateway na STM32; ping/TCP do BeagleY.
3. Sniff CAN e preencher [`can_pgn_map.md`](can_pgn_map.md).
4. Gravar sessão 1 h; revisar eventos com `tools/replay/replay_session.py`.
5. Teste rodoviário 8 h + `tools/field_test/acceptance_report.py`.

# Klipper-Infinity-Flow

**Integrazione Infinity Flow S1+ con Klipper per IdeaFormer IR3 V2**

Native Ricerca — Progetto R&D 3D Printing

---

## Panoramica

Questo progetto collega i sensori hardware dell'Infinity Flow S1+ (automatic filament reloader) direttamente al firmware Klipper, trasformandoli in sensori di filament runout intelligenti con gestione dello swap automatico.

L'S1+ è un dispositivo proprietario basato su ESP32-S3 che normalmente comunica solo con il cloud FlowQ. Questa integrazione bypassa il cloud e legge i segnali dei microswitches in parallelo, senza modificare il firmware dell'S1+ né invalidare la garanzia.

## Architettura

```
S1+ Gearbox Switches ──┬── S1+ PCB (funzionamento invariato)
                        │
                        └── ESP32 Bridge (ESPHome)
                               │
                               ├── MQTT → Moonraker → Klipper extras module
                               │                        ├── Pause print
                               │                        ├── Swap detection
                               │                        └── Status reporting
                               │
                               └── MQTT → Home Assistant (opzionale)
```

## Hardware

- 1x ESP32 DevKit (~€5-8)
- 2x cavi dupont F-F (segnali switch)
- 1x cavo dupont per GND comune
- Opzionale: SCT-013 current transformer (motor sensing)

### Wiring (tap parallelo — non invasivo)

```
S1+ Gearbox A Switch ──┬──→ S1+ PCB (pin originale)
                        └──→ ESP32 GPIO32 (pull-up interno)

S1+ Gearbox B Switch ──┬──→ S1+ PCB (pin originale)
                        └──→ ESP32 GPIO33 (pull-up interno)

S1+ GND ────────────────┬──→ S1+ PCB GND
                         └──→ ESP32 GND
```

I microswitches dell'S1+ sono ball-actuated. Il segnale è digitale ON/OFF, 3.3V-compatibile. Se il livello logico è 5V, servono divisori resistivi.

## Installazione

```bash
git clone <repo> ~/klipper-infinity-flow
cd ~/klipper-infinity-flow
./install.sh
```

Lo script installa:
- `infinity_flow.py` in `~/klipper/klippy/extras/`
- `infinity_flow.py` in `~/moonraker/moonraker/components/`
- `paho-mqtt` per Moonraker
- Mosquitto MQTT broker

Poi:
1. Aggiungi `[infinity_flow]` a `printer.cfg` (vedi `docs/config_snippets.cfg`)
2. Aggiungi `[infinity_flow]` a `moonraker.conf`
3. Flash ESPHome: `cd esphome && esphome run infinity_flow_bridge.yaml`
4. Wiring fisico
5. `sudo systemctl restart klipper moonraker`

## Comandi GCode

| Comando | Descrizione |
|---------|-------------|
| `QUERY_FILAMENT_SENSOR SENSOR=infinity_flow` | Stato sensore |
| `SET_FILAMENT_SENSOR SENSOR=infinity_flow ENABLE=1/0` | On/Off |
| `INFINITY_FLOW_STATUS` | Report dettagliato |
| `INFINITY_FLOW_UPDATE SIDE=A STATE=present/runout` | Update manuale |

## API Moonraker

- `GET /server/infinity_flow/status` — stato MQTT e sensori
- `POST /server/infinity_flow/enable` — abilita/disabilita

## Logica di funzionamento

### Modalità `all_empty` (default)

1. Side A esaurisce → S1+ avvia swap → modulo logga "swap in progress"
2. Grace period 30s → attende completamento swap
3. Side B ha filamento → swap riuscito, stampa continua
4. Entrambi vuoti dopo grace → **PAUSA** + `runout_gcode`

## Struttura progetto

```
klipper-infinity-flow/
├── install.sh
├── README.md
├── esphome/
│   └── infinity_flow_bridge.yaml
├── klipper_module/
│   └── infinity_flow.py
├── moonraker_component/
│   └── infinity_flow.py
├── docs/
│   └── config_snippets.cfg
└── hardware/
    └── (case STL, wiring photos)
```

## Roadmap

- [x] ESPHome bridge config
- [x] Klipper extras module
- [x] Moonraker MQTT component
- [x] Install script
- [ ] Wiring fisico + test
- [ ] Case stampato 3D per bridge ESP32
- [ ] BLE reverse engineering (GATT scan con nRF Connect)
- [ ] FlowQ traffic analysis (mitmproxy)
- [ ] KlipperScreen panel (NativeUI theme)

## Licenza

GNU GPLv3

# Klipper Infinity Flow S1+

Klipper integration for the **Infinity Flow S1+** automatic filament reloader.

Turns your S1+ into native Klipper filament runout sensors — visible in Fluidd, Mainsail, and KlipperScreen — with automatic pause logic when both spools run out.

**No extra hardware required.** This integration connects directly to the FlowQ cloud API that your S1+ already uses.

---

## How it works

```
Infinity Flow S1+
    ↓ (Wi-Fi, unchanged — S1+ works as normal)
FlowQ Cloud  (infinityflow3d.com)
    ↓ (WebSocket — this integration)
Moonraker component
    ↓ (GCode command)
Klipper extras module
    ↓ (virtual filament sensors)
Fluidd / Mainsail / KlipperScreen
```

The integration reads filament state from the FlowQ cloud in real time and mirrors it into Klipper as standard filament runout sensors. Your S1+ hardware and its own firmware are completely unchanged.

---

## Requirements

- Klipper + Moonraker (any printer)
- Infinity Flow S1+ connected to your Wi-Fi and FlowQ account
- Python packages: `aiohttp`, `websockets` (installed automatically)

---

## Quick Install

```bash
cd ~
git clone https://github.com/tommasobbianchi/klipper-infinity-flow
cd klipper-infinity-flow
./install.sh
```

The installer copies the Klipper module and Moonraker component, installs Python dependencies, and (if KlipperScreen is present) installs the status panel.

---

## Setup

### 1. Get your FlowQ token

```bash
python3 ~/klipper-infinity-flow/flowq_setup_token.py
```

This logs in with your FlowQ account and outputs the token to paste in the next step. If your account uses Google sign-in, see the alternative method below.

<details>
<summary>Alternative: extract token from browser</summary>

1. Open **flowq.infinityflow3d.com** and log in
2. Press `F12` → Application tab → Local Storage → `https://flowq.infinityflow3d.com`
3. Find `refresh_token` and copy its value

</details>

### 2. Add to `moonraker.conf`

```ini
[infinity_flow]
refresh_token: YOUR_TOKEN_HERE
# s1plus_id is auto-detected — only needed if you have multiple S1+ devices
```

### 3. Add to `printer.cfg`

No dummy pins needed. Virtual sensors are registered automatically.

```ini
[infinity_flow]
extruder: extruder
pause_mode: all_empty
swap_grace_period: 30
runout_gcode:
    M117 Filament exhausted — pausing
    PAUSE
```

### 4. Restart

```bash
sudo systemctl restart moonraker klipper
```

---

## Dashboard visibility

After restart, two filament sensors appear automatically in Fluidd and Mainsail:

- **infinity_flow_a** — Slot A
- **infinity_flow_b** — Slot B

In KlipperScreen: tap **Infinity Flow** from the main menu — shows live slot status (color-coded to match the S1+ LEDs: green=feeding, blue=standby, red=empty).

---

## Configuration reference

All options with defaults:

**`printer.cfg`**

| Key | Default | Description |
|-----|---------|-------------|
| `extruder` | `extruder` | Extruder name (change for multi-extruder setups) |
| `pause_mode` | `all_empty` | `all_empty` = pause when both slots empty; `any_empty` = pause on first runout |
| `swap_grace_period` | `30` | Seconds to wait for S1+ spool swap before triggering pause |
| `event_delay` | `3.0` | Minimum seconds between consecutive events (anti-bounce) |
| `slot_a_sensor` | `infinity_flow_a` | Name for Slot A virtual sensor |
| `slot_b_sensor` | `infinity_flow_b` | Name for Slot B virtual sensor |
| `runout_gcode` | PAUSE | GCode to run when all filament exhausted |
| `swap_gcode` | *(none)* | GCode to run when S1+ starts a spool swap |
| `insert_gcode` | *(none)* | GCode to run when filament is inserted (outside print) |
| `enabled` | `True` | Enable/disable sensor monitoring |

**`moonraker.conf`**

| Key | Default | Description |
|-----|---------|-------------|
| `refresh_token` | *(required)* | FlowQ account token |
| `s1plus_id` | auto-detected | Device UUID (only needed with multiple S1+ devices) |
| `poll_interval` | `10` | REST polling interval in seconds (WebSocket fallback) |
| `slot_a_sensor` | `infinity_flow_a` | Must match `slot_a_sensor` in `printer.cfg` if changed |
| `slot_b_sensor` | `infinity_flow_b` | Must match `slot_b_sensor` in `printer.cfg` if changed |

---

## GCode commands

| Command | Description |
|---------|-------------|
| `QUERY_FILAMENT_SENSOR SENSOR=infinity_flow` | Brief status |
| `SET_FILAMENT_SENSOR SENSOR=infinity_flow ENABLE=1` | Enable monitoring |
| `SET_FILAMENT_SENSOR SENSOR=infinity_flow ENABLE=0` | Disable monitoring |
| `INFINITY_FLOW_STATUS` | Detailed status report |
| `INFINITY_FLOW_UPDATE SIDE=A STATE=present` | Manual state override |

---

## Moonraker API

| Endpoint | Description |
|----------|-------------|
| `GET /server/infinity_flow/status` | JSON sensor state |
| `GET /server/infinity_flow/setup` | HTML setup guide (open in browser) |

---

## Token renewal

FlowQ tokens expire after ~7 days. The KlipperScreen panel and the setup page (`http://printer-ip:7125/server/infinity_flow/setup`) show the expiry date with a warning.

To renew:

```bash
python3 ~/klipper-infinity-flow/flowq_setup_token.py
# Copy the new refresh_token into moonraker.conf
sudo systemctl restart moonraker
```

---

## Troubleshooting

**Sensors don't appear in Fluidd/Mainsail**
→ Check Klipper logs: `tail -f /tmp/klippy.log | grep -i infinity`
→ Make sure `[infinity_flow]` is in `printer.cfg` and Klipper was restarted

**WebSocket not connecting / sensors always show unknown**
→ Check Moonraker logs: `tail -f /tmp/moonraker.log | grep -i infinity`
→ Token may be expired — check the setup page and renew if needed
→ Make sure your printer can reach the internet (test: `ping api.infinityflow3d.com`)

**KlipperScreen panel not visible**
→ Make sure `[menu __main infinity_flow]` is in `KlipperScreen.conf`
→ Restart KlipperScreen: `sudo systemctl restart KlipperScreen`

**Login fails in flowq_setup_token.py**
→ If your FlowQ account uses Google sign-in, you need to set a password first:
   flowq.infinityflow3d.com → Settings → Security → Set password
→ Or use the browser token extraction method (see Setup step 1)

---

## License

GNU GPLv3

# Moonraker component for Infinity Flow S1+ via FlowQ Cloud API
#
# Connects directly to the FlowQ WebSocket for real-time filament
# state updates from the S1+ device. No additional hardware required.
#
# State mapping (confirmed from FlowQ JS bundle + live API data):
#   "loaded"   → filament present, ready (green indicator)
#   "active"   → filament feeding actively (green indicator, S1+ LED: green)
#   "sleep"    → slot sleeping, filament present (blue indicator, S1+ LED: blue)
#   "unloaded" → no filament / runout (red indicator, S1+ LED: red)
#   anything else → treated as runout
#
# Configuration in moonraker.conf:
#
#   [infinity_flow]
#   # FlowQ credentials — get refresh_token via setup script or browser:
#   #   Run: python3 infinity_flow_setup.py
#   #   Or: open flowq.infinityflow3d.com, F12 > Application > Local Storage
#   #       copy "refresh_token" value here
#   refresh_token: YOUR_REFRESH_TOKEN_HERE
#
#   # Optional: specific S1+ device ID (default: first/only device)
#   #s1plus_id: your-device-uuid
#
#   # Polling interval in seconds when WS is unavailable (default: 5)
#   #poll_interval: 5
#
#   # Slot names matching [filament_switch_sensor] in printer.cfg
#   #slot_a_sensor: infinity_flow_a
#   #slot_b_sensor: infinity_flow_b
#
# In printer.cfg:
#   [filament_switch_sensor infinity_flow_a]
#   pause_on_runout: True
#   switch_pin: ^!PC0  # dummy pin — state managed by this component
#
#   [filament_switch_sensor infinity_flow_b]
#   pause_on_runout: True
#   switch_pin: ^!PC1  # dummy pin

from __future__ import annotations
import asyncio
import base64
import datetime
import json
import logging
import time
from typing import TYPE_CHECKING, Any, Dict, Optional, List

if TYPE_CHECKING:
    from moonraker.confighelper import ConfigHelper
    from moonraker.components.klippy_connection import KlippyConnection

try:
    import aiohttp
    HAS_AIOHTTP = True
except ImportError:
    HAS_AIOHTTP = False

try:
    import websockets
    HAS_WEBSOCKETS = True
except ImportError:
    HAS_WEBSOCKETS = False

FLOWQ_API = "https://api.infinityflow3d.com/api"
FLOWQ_WS = "wss://ws.infinityflow3d.com/ws"  # /ws path, ?token= query param

# States that indicate filament is present (confirmed from live API)
PRESENT_STATES = {"loaded", "active", "sleep"}

_STATE_LABEL = {
    "loaded":   "Ready",
    "active":   "Feeding",
    "sleep":    "Sleep",
    "unloaded": "Empty",
}
_STATE_COLOR = {
    "loaded":   "#4CAF50",   # green
    "active":   "#4CAF50",   # green  (S1+ LED: green when feeding)
    "sleep":    "#2196F3",   # blue   (S1+ LED: blue when standby)
    "unloaded": "#F44336",   # red    (S1+ LED: red when empty)
}

_SETUP_HTML = """\
<!DOCTYPE html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Infinity Flow S1+ — Klipper Setup</title>
  <style>
    *{{box-sizing:border-box}}
    body{{font-family:system-ui,-apple-system,sans-serif;max-width:700px;
          margin:0 auto;padding:16px 12px;background:#121212;color:#e0e0e0}}
    h1{{color:#4CAF50;font-size:1.4em;margin-bottom:2px}}
    .sub{{color:#888;font-size:.88em;margin-bottom:20px}}
    h2{{color:#81D4FA;font-size:1.0em;margin:22px 0 8px;
        text-transform:uppercase;letter-spacing:.05em}}
    pre{{background:#1a1a1a;border:1px solid #2e2e2e;border-radius:8px;
         padding:12px 14px;overflow-x:auto;font-size:.86em;margin:0;
         white-space:pre-wrap;word-break:break-all;line-height:1.5}}
    .slots{{display:flex;gap:10px;margin-bottom:14px;flex-wrap:wrap}}
    .slot{{flex:1;min-width:90px;text-align:center;background:#1a1a1a;
           border:1px solid #2e2e2e;border-radius:10px;padding:10px 8px}}
    .slot .name{{font-size:.75em;color:#888;margin-bottom:5px;
                 text-transform:uppercase;letter-spacing:.06em}}
    .slot .val{{font-weight:600;font-size:1.0em}}
    .info-row{{display:flex;gap:10px;align-items:center;
               background:#1a1a1a;border:1px solid #2e2e2e;
               border-radius:10px;padding:10px 14px;margin-bottom:10px;
               font-size:.9em}}
    .info-row .lbl{{color:#888;min-width:80px}}
    .ok{{color:#4CAF50}} .warn-c{{color:#FF9800}} .err{{color:#F44336}}
    .notice{{background:#1a2a00;border:1px solid #558B2F;border-radius:8px;
             padding:10px 14px;font-size:.88em;margin-bottom:10px}}
    .warn-box{{background:#2a1800;border:1px solid #FF6D00;border-radius:8px;
               padding:10px 14px;font-size:.88em;margin-bottom:10px}}
    .step{{counter-increment:steps;background:#1a1a1a;border:1px solid #2e2e2e;
           border-radius:10px;padding:12px 14px;margin-bottom:10px}}
    .step-title{{font-weight:600;margin-bottom:8px;color:#e0e0e0}}
    .step-title::before{{content:counter(steps)". ";color:#81D4FA}}
    ol.steps{{counter-reset:steps;list-style:none;padding:0;margin:0}}
    .copy-wrap{{position:relative;margin-top:8px}}
    .copy-btn{{position:absolute;top:7px;right:7px;background:#252525;
               border:1px solid #444;color:#bbb;padding:3px 10px;
               border-radius:5px;cursor:pointer;font-size:.78em}}
    .copy-btn:active{{background:#4CAF50;color:#fff;border-color:#4CAF50}}
    .reveal-btn{{background:none;border:1px solid #444;color:#81D4FA;
                 padding:3px 10px;border-radius:5px;cursor:pointer;
                 font-size:.8em;margin-left:8px}}
    .token-masked{{font-family:monospace;font-size:.85em;
                   color:#aaa;word-break:break-all}}
    details summary{{cursor:pointer;color:#81D4FA;font-size:.88em;
                     margin-top:10px;user-select:none}}
    code{{background:#252525;padding:1px 5px;border-radius:3px;
          font-size:.9em}}
    footer{{margin-top:32px;font-size:.78em;color:#444;text-align:center;
            border-top:1px solid #1e1e1e;padding-top:12px}}
    @media(max-width:400px){{.slots{{flex-direction:column}}}}
  </style>
</head>
<body>
  <h1>&#x267B; Infinity Flow S1+</h1>
  <div class="sub">Klipper Integration &mdash; Setup &amp; Status</div>

  <!-- ── Live Status ─────────────────────────────────────────── -->
  <h2>Live Status</h2>
  <div class="slots">
    <div class="slot">
      <div class="name">Slot A</div>
      <div class="val" style="color:{color_a}">{label_a}</div>
    </div>
    <div class="slot">
      <div class="name">Slot B</div>
      <div class="val" style="color:{color_b}">{label_b}</div>
    </div>
    <div class="slot">
      <div class="name">FlowQ Cloud</div>
      <div class="val" style="color:{color_ws}">{label_ws}</div>
    </div>
  </div>

  <!-- ── Token Info ──────────────────────────────────────────── -->
  <h2>Token</h2>
  {token_section}

  <!-- ── Setup Guide ────────────────────────────────────────── -->
  <h2>Setup Guide</h2>
  <div class="notice">
    This integration connects to the <strong>FlowQ cloud API</strong> &mdash;
    no hardware modifications or extra devices needed.
    You only need your FlowQ account credentials.
  </div>

  <ol class="steps">
    <li class="step">
      <div class="step-title">Install the integration</div>
      <div class="copy-wrap">
        <button class="copy-btn" onclick="cp('s1')">Copy</button>
        <pre id="s1">cd ~ && git clone https://github.com/tommasobbianchi/klipper-infinity-flow
cd klipper-infinity-flow && ./install.sh</pre>
      </div>
    </li>

    <li class="step">
      <div class="step-title">Get your FlowQ refresh token</div>
      <p style="font-size:.88em;margin:0 0 8px">
        Run the setup script &mdash; it logs in with your FlowQ account
        and prints the token to paste in the next step:
      </p>
      <div class="copy-wrap">
        <button class="copy-btn" onclick="cp('s2')">Copy</button>
        <pre id="s2">python3 ~/klipper-infinity-flow/flowq_setup_token.py</pre>
      </div>
      <details>
        <summary>Alternative: extract token from browser</summary>
        <ol style="font-size:.85em;padding-left:20px;margin:8px 0 0">
          <li>Open <strong>flowq.infinityflow3d.com</strong> and log in</li>
          <li>Press <kbd>F12</kbd> &rarr; Application tab &rarr; Local Storage
              &rarr; <code>https://flowq.infinityflow3d.com</code></li>
          <li>Find <code>refresh_token</code> and copy its value</li>
        </ol>
      </details>
    </li>

    <li class="step">
      <div class="step-title">Add to <code>moonraker.conf</code></div>
      <div class="copy-wrap">
        <button class="copy-btn" onclick="cp('s3')">Copy</button>
        <pre id="s3">[infinity_flow]
refresh_token: YOUR_REFRESH_TOKEN_HERE
# s1plus_id is auto-detected — only needed if you have multiple S1+ devices
#s1plus_id: your-device-uuid</pre>
      </div>
    </li>

    <li class="step">
      <div class="step-title">Add to <code>printer.cfg</code></div>
      <p style="font-size:.88em;margin:0 0 8px">
        No dummy pins needed &mdash; sensors are registered automatically.
      </p>
      <div class="copy-wrap">
        <button class="copy-btn" onclick="cp('s4')">Copy</button>
        <pre id="s4">[infinity_flow]
extruder: extruder
pause_mode: all_empty
swap_grace_period: 30
runout_gcode:
    M117 Filament exhausted &mdash; pausing
    PAUSE</pre>
      </div>
    </li>

    <li class="step">
      <div class="step-title">Restart services</div>
      <div class="copy-wrap">
        <button class="copy-btn" onclick="cp('s5')">Copy</button>
        <pre id="s5">sudo systemctl restart moonraker klipper</pre>
      </div>
    </li>
  </ol>

  <footer>
    Served by Moonraker &bull; Infinity Flow Klipper Component
  </footer>

  <script>
    function cp(id) {{
      var el = document.getElementById(id);
      navigator.clipboard.writeText(el.innerText)
        .then(() => {{ var b = event.target;
                       b.textContent = 'Copied!';
                       setTimeout(() => b.textContent = 'Copy', 1400); }})
        .catch(() => {{ el.select && el.select(); }});
    }}
    function loadToken() {{
      fetch('/server/infinity_flow/token')
        .then(r => r.json())
        .then(d => {{
          var t = (d.result || d).token || '';
          if (!t) {{ alert('Token unavailable'); return; }}
          document.getElementById('tok-val').textContent = t;
          document.getElementById('tok-val').style.display = 'block';
          document.getElementById('tok-copy').style.display = 'inline';
          document.getElementById('tok-reveal').style.display = 'none';
        }})
        .catch(() => alert('Could not fetch token — make sure you are on the local network'));
    }}
  </script>
</body>
</html>
"""

# Token info HTML fragments injected into _SETUP_HTML
_TOKEN_OK = """\
  <div class="info-row">
    <span class="lbl">Status</span>
    <span class="ok">&#x2713; Configured</span>
  </div>
  <div class="info-row {expiry_cls}">
    <span class="lbl">Expires</span>
    <span>{expiry}</span>
    {renew_hint}
  </div>
  <details>
    <summary>Show token (for migration to another printer)</summary>
    <div style="margin-top:8px">
      <div style="font-size:.8em;color:#888;margin-bottom:6px">
        Keep this private. Only share if moving to a new printer.
        Your token starts with: <code>{token_preview}</code>
      </div>
      <div class="copy-wrap" id="tok-wrap">
        <button class="copy-btn" id="tok-copy" style="display:none"
                onclick="cp('tok-val')">Copy</button>
        <pre id="tok-val" style="display:none"></pre>
        <button onclick="loadToken()" id="tok-reveal"
                style="background:#252525;border:1px solid #444;color:#81D4FA;
                       padding:5px 14px;border-radius:6px;cursor:pointer;
                       font-size:.85em">
          &#x1F513; Reveal full token
        </button>
      </div>
    </div>
  </details>"""

_TOKEN_MISSING = """\
  <div class="warn-box">
    &#x26A0; No token configured yet &mdash; follow the Setup Guide below.
  </div>"""


class InfinityFlowCloud:
    """Moonraker component bridging S1+ via FlowQ Cloud WebSocket."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.name = config.get_name()

        if not HAS_AIOHTTP:
            raise config.error(
                "aiohttp package required. "
                "Install with: pip install aiohttp")
        if not HAS_WEBSOCKETS:
            raise config.error(
                "websockets package required. "
                "Install with: pip install websockets")

        self.refresh_token: str = config.get("refresh_token", "")
        if not self.refresh_token:
            raise config.error(
                "[infinity_flow] requires 'refresh_token'. "
                "Get it by running: python3 flowq_setup_token.py")

        self.s1plus_id: Optional[str] = config.get("s1plus_id", None)
        self.poll_interval: int = config.getint("poll_interval", 10)
        self.slot_a_sensor: str = config.get(
            "slot_a_sensor", "infinity_flow_a")
        self.slot_b_sensor: str = config.get(
            "slot_b_sensor", "infinity_flow_b")

        self._access_token: Optional[str] = None
        self._token_expiry: float = 0.0

        # Current states
        self.state_a: Optional[str] = None
        self.state_b: Optional[str] = None
        self.online: bool = False
        self.ws_connected: bool = False

        self._ws_task: Optional[asyncio.Task] = None
        self._poll_task: Optional[asyncio.Task] = None

        self.server.register_event_handler(
            "server:klippy_ready", self._on_klippy_ready)
        self.server.register_event_handler(
            "server:klippy_shutdown", self._on_klippy_shutdown)

        self.server.register_endpoint(
            "/server/infinity_flow/status",
            ["GET"], self._handle_status_request)

        self.server.register_endpoint(
            "/server/infinity_flow/setup",
            ["GET"], self._handle_setup_request,
            wrap_result=False,
            content_type="text/html; charset=UTF-8",
            auth_required=False,
        )

        self.server.register_endpoint(
            "/server/infinity_flow/token",
            ["GET"], self._handle_token_request,
            auth_required=True,
        )

        # Explicit notify_name to avoid collision with Klipper's generic events
        self.server.register_notification(
            "infinity_flow:state_changed",
            notify_name="infinity_flow_state_changed")

        logging.info(
            "InfinityFlowCloud: Initialized (sensor_a=%s, sensor_b=%s)",
            self.slot_a_sensor, self.slot_b_sensor)

    # ------------------------------------------------------------------ #
    # Lifecycle
    # ------------------------------------------------------------------ #

    async def _on_klippy_ready(self) -> None:
        # Initial state fetch via REST, then start WS
        try:
            await self._refresh_access_token()
            await self._fetch_initial_state()
        except Exception as e:
            logging.error("InfinityFlowCloud: Startup error: %s", e)

        self._ws_task = asyncio.create_task(self._ws_loop())

    async def _on_klippy_shutdown(self) -> None:
        if self._ws_task:
            self._ws_task.cancel()
        if self._poll_task:
            self._poll_task.cancel()
        self.ws_connected = False

    # ------------------------------------------------------------------ #
    # Auth
    # ------------------------------------------------------------------ #

    async def _refresh_access_token(self) -> str:
        """Exchange refresh_token for a fresh access_token."""
        async with aiohttp.ClientSession() as session:
            async with session.post(
                f"{FLOWQ_API}/v1/identity/token/refresh",
                json={"refresh_token": self.refresh_token},
                headers={
                    "Content-Type": "application/json",
                    "Origin": "https://flowq.infinityflow3d.com",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    body = await resp.text()
                    raise RuntimeError(
                        f"Token refresh failed {resp.status}: {body}")
                data = await resp.json()
                self._access_token = data["access_token"]
                # Tokens typically expire in 1h; refresh 5 min early
                self._token_expiry = time.time() + 3300
                logging.info("InfinityFlowCloud: Access token refreshed")
                return self._access_token  # type: ignore

    async def _get_valid_token(self) -> str:
        if not self._access_token or time.time() > self._token_expiry:
            await self._refresh_access_token()
        return self._access_token  # type: ignore

    async def _get_ws_token(self) -> str:
        """Get a short-lived token specifically for WS auth."""
        token = await self._get_valid_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{FLOWQ_API}/v1/identity/ws/token",
                headers={
                    "Authorization": f"Bearer {token}",
                    "Origin": "https://flowq.infinityflow3d.com",
                },
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status == 200:
                    data = await resp.json()
                    return data.get("token") or token
                return token  # Fall back to access token

    # ------------------------------------------------------------------ #
    # REST — initial state fetch
    # ------------------------------------------------------------------ #

    async def _fetch_initial_state(self) -> None:
        token = await self._get_valid_token()
        async with aiohttp.ClientSession() as session:
            async with session.get(
                f"{FLOWQ_API}/v1/s1plus/devices",
                headers={"Authorization": f"Bearer {token}"},
                timeout=aiohttp.ClientTimeout(total=10),
            ) as resp:
                if resp.status != 200:
                    logging.warning(
                        "InfinityFlowCloud: /v1/s1plus/devices returned %d",
                        resp.status)
                    return
                devices: List[Dict[str, Any]] = await resp.json()

        if not devices:
            logging.warning("InfinityFlowCloud: No S1+ devices found")
            return

        # Pick device by ID or use first
        device = next(
            (d for d in devices if d["id"] == self.s1plus_id),
            devices[0]
        ) if self.s1plus_id else devices[0]

        if not self.s1plus_id:
            self.s1plus_id = device["id"]
            logging.info(
                "InfinityFlowCloud: Using S1+ device id=%s name=%s",
                device["id"], device.get("name", "?"))

        self.online = device.get("online", False)
        self._apply_state("A", device.get("state_a"))
        self._apply_state("B", device.get("state_b"))
        logging.info(
            "InfinityFlowCloud: Initial state — A=%s B=%s online=%s",
            self.state_a, self.state_b, self.online)

    # ------------------------------------------------------------------ #
    # WebSocket loop
    # ------------------------------------------------------------------ #

    async def _ws_loop(self) -> None:
        """Reconnecting WebSocket loop."""
        from urllib.parse import quote
        retry_delay = 5
        while True:
            try:
                ws_token = await self._get_ws_token()
                # WS auth via query param (confirmed from JS bundle)
                ws_url = f"{FLOWQ_WS}?token={quote(ws_token)}"
                async for ws in websockets.connect(
                    ws_url,
                    ping_interval=None,
                    max_size=2 ** 20,
                ):
                    self.ws_connected = True
                    retry_delay = 5
                    logging.info("InfinityFlowCloud: WebSocket connected")
                    try:
                        await self._ws_session(ws)
                    except websockets.ConnectionClosed as e:
                        self.ws_connected = False
                        logging.warning(
                            "InfinityFlowCloud: WS closed: %s", e)
            except asyncio.CancelledError:
                return
            except Exception as e:
                self.ws_connected = False
                logging.error(
                    "InfinityFlowCloud: WS error: %s, retry in %ds",
                    e, retry_delay)
                await asyncio.sleep(retry_delay)
                retry_delay = min(retry_delay * 2, 60)

    async def _ws_session(self, ws) -> None:
        """Handle a single WebSocket session."""
        hb_task = asyncio.create_task(self._heartbeat(ws))
        try:
            async for raw in ws:
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    continue
                await self._handle_ws_message(msg)
        finally:
            hb_task.cancel()

    async def _heartbeat(self, ws) -> None:
        while True:
            await asyncio.sleep(25)
            try:
                await ws.send(json.dumps({"type": "ping"}))
            except Exception:
                return

    async def _handle_ws_message(
            self, msg: Dict[str, Any]) -> None:
        resource = msg.get("resource")
        if resource != "State":
            return

        device_id = msg.get("id")
        if self.s1plus_id and device_id != self.s1plus_id:
            return  # Not our device

        patch = msg.get("patch")
        if not isinstance(patch, list) or len(patch) < 2:
            return

        state_a = patch[0].get("state") if patch[0] else None
        state_b = patch[1].get("state") if patch[1] else None

        self._apply_state("A", state_a)
        self._apply_state("B", state_b)

    # ------------------------------------------------------------------ #
    # State application
    # ------------------------------------------------------------------ #

    def _apply_state(self, side: str, state: Optional[str]) -> None:
        """Apply a new slot state, send GCode if changed."""
        if side == "A":
            prev = self.state_a
            self.state_a = state
        else:
            prev = self.state_b
            self.state_b = state

        if state == prev:
            return

        is_present = state in PRESENT_STATES
        logging.info(
            "InfinityFlowCloud: Slot %s state changed: %s → %s (%s)",
            side, prev, state,
            "PRESENT" if is_present else "RUNOUT")

        self._send_filament_state(side, is_present)
        asyncio.ensure_future(
            self._notify_state_change(side, state, is_present))

    def _send_filament_state(self, side: str, present: bool) -> None:
        gcode = (
            f"INFINITY_FLOW_UPDATE SIDE={side} "
            f"STATE={'present' if present else 'runout'}"
        )
        try:
            klippy_apis = self.server.lookup_component("klippy_apis")
            asyncio.ensure_future(klippy_apis.run_gcode(gcode, default=None))
            logging.debug(
                "InfinityFlowCloud: Sent GCode: %s", gcode)
        except Exception as e:
            logging.error(
                "InfinityFlowCloud: GCode error: %s", e)

    async def _notify_state_change(
            self, side: str, state: Optional[str],
            present: bool) -> None:
        self.server.send_event(
            "infinity_flow:state_changed",
            {"side": side, "state": state, "present": present})

    # ------------------------------------------------------------------ #
    # HTTP endpoints
    # ------------------------------------------------------------------ #

    async def _handle_status_request(
            self, web_request) -> Dict[str, Any]:
        return {
            "ws_connected": self.ws_connected,
            "s1plus_online": self.online,
            "s1plus_id": self.s1plus_id,
            "slot_a": {
                "state": self.state_a,
                "present": self.state_a in PRESENT_STATES,
                "sensor": self.slot_a_sensor,
            },
            "slot_b": {
                "state": self.state_b,
                "present": self.state_b in PRESENT_STATES,
                "sensor": self.slot_b_sensor,
            },
        }

    async def _handle_setup_request(self, web_request) -> str:
        """Serve a mobile-friendly HTML setup / status page."""
        expiry = self._decode_token_expiry(self.refresh_token)

        # Build token section — never embed full token in HTML source
        try:
            parts = self.refresh_token.split(".")
            payload = parts[1] + "=" * (-len(parts[1]) % 4)
            exp = json.loads(base64.urlsafe_b64decode(payload)).get("exp", 0)
            days_left = (exp - time.time()) / 86400
            if days_left < 0:
                expiry_cls = "err"
                renew_hint = (
                    "<span style='color:#F44336;font-size:.85em'>"
                    "&#x26A0; <strong>EXPIRED</strong> — renew now</span>")
            elif days_left < 7:
                expiry_cls = "warn-c"
                renew_hint = (
                    "<span style='color:#FF9800;font-size:.85em'>"
                    "&nbsp;&#x26A0; renew soon</span>")
            else:
                expiry_cls = "ok"
                renew_hint = ""
        except Exception:
            expiry_cls = "ok"
            renew_hint = ""

        # Show only a short prefix — full token retrieved via JS fetch
        token_preview = self.refresh_token[:16] + "…" if self.refresh_token else ""
        token_section = _TOKEN_OK.format(
            expiry=expiry,
            expiry_cls=expiry_cls,
            renew_hint=renew_hint,
            token_preview=token_preview,
        )

        def sl(state):
            return _STATE_LABEL.get(state or "", "Unknown")

        def sc(state):
            return _STATE_COLOR.get(state or "", "#9E9E9E")

        return _SETUP_HTML.format(
            label_a=sl(self.state_a),
            color_a=sc(self.state_a),
            label_b=sl(self.state_b),
            color_b=sc(self.state_b),
            label_ws="Connected" if self.ws_connected else "Disconnected",
            color_ws="#4CAF50" if self.ws_connected else "#F44336",
            token_section=token_section,
        )

    async def _handle_token_request(
            self, web_request) -> Dict[str, Any]:
        """Return the refresh_token — requires authentication."""
        return {
            "token": self.refresh_token,
            "expires": self._decode_token_expiry(self.refresh_token),
        }

    @staticmethod
    def _decode_token_expiry(token: str) -> str:
        """Decode JWT payload (no signature verification) to get exp date."""
        try:
            parts = token.split(".")
            if len(parts) < 2:
                return "unknown"
            payload = parts[1]
            # Add padding
            payload += "=" * (-len(payload) % 4)
            data = json.loads(base64.urlsafe_b64decode(payload))
            exp = data.get("exp")
            if exp:
                dt = datetime.datetime.utcfromtimestamp(exp)
                return dt.strftime("%Y-%m-%d %H:%M UTC")
        except Exception:
            pass
        return "unknown"


def load_component(config: ConfigHelper) -> InfinityFlowCloud:
    return InfinityFlowCloud(config)

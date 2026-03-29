import io
import json
import logging
import threading
import urllib.request

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GdkPixbuf, GLib, Pango

from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("klipperscreen")

_STATE_LABEL = {
    "loaded":   "Ready",
    "active":   "Feeding",
    "sleep":    "Sleep",
    "unloaded": "Empty",
}
_STATE_COLOR = {
    "loaded":   "#4CAF50",
    "active":   "#8BC34A",
    "sleep":    "#2196F3",
    "unloaded": "#F44336",
}


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        title = title or "Infinity Flow"
        super().__init__(screen, title)

        main = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=10, margin=12,
        )

        # ── Slot status row ─────────────────────────────────────
        slot_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=12, halign=Gtk.Align.CENTER,
        )
        self.labels["slot_a"] = self._make_slot_box("A")
        self.labels["slot_b"] = self._make_slot_box("B")
        slot_row.pack_start(self.labels["slot_a"], False, False, 0)
        slot_row.pack_start(self.labels["slot_b"], False, False, 0)
        main.pack_start(slot_row, False, False, 0)

        # ── WS status badge ─────────────────────────────────────
        self.labels["ws"] = Gtk.Label(halign=Gtk.Align.CENTER)
        self.labels["ws"].set_markup(
            "<small><span foreground='#9E9E9E'>● Connecting…</span></small>")
        main.pack_start(self.labels["ws"], False, False, 0)

        # ── QR code ─────────────────────────────────────────────
        self.labels["qr"] = Gtk.Image()
        qr_box = Gtk.Box(halign=Gtk.Align.CENTER)
        qr_box.pack_start(self.labels["qr"], False, False, 0)
        main.pack_start(qr_box, True, True, 0)

        hint = Gtk.Label(halign=Gtk.Align.CENTER)
        hint.set_markup(
            "<small>Scan to open setup page on your phone</small>")
        hint.set_line_wrap(True)
        main.pack_start(hint, False, False, 0)

        # ── URL label (fallback) ─────────────────────────────────
        self.labels["url"] = Gtk.Label(halign=Gtk.Align.CENTER)
        self.labels["url"].set_markup(
            f"<small><tt>{self._setup_url()}</tt></small>")
        self.labels["url"].set_line_wrap(True)
        self.labels["url"].set_selectable(True)
        main.pack_start(self.labels["url"], False, False, 4)

        self.content.add(main)

        # Fetch status + generate QR immediately (don't wait for activate())
        threading.Thread(target=self._fetch_status, daemon=True).start()
        threading.Thread(target=self._generate_qr, daemon=True).start()

    # ── helpers ─────────────────────────────────────────────────

    def _moonraker_base(self) -> str:
        host = getattr(self._screen._ws, "host", "localhost")
        port = getattr(self._screen._ws, "port", 7125)
        ssl = getattr(self._screen._ws, "ssl", False)
        scheme = "https" if ssl else "http"
        return f"{scheme}://{host}:{port}"

    def _setup_url(self) -> str:
        return f"{self._moonraker_base()}/server/infinity_flow/setup"

    def _make_slot_box(self, side: str) -> Gtk.Box:
        box = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=4, halign=Gtk.Align.CENTER,
            width_request=110,
        )
        lbl_title = Gtk.Label()
        lbl_title.set_markup(f"<b>Slot {side}</b>")
        lbl_state = Gtk.Label()
        lbl_state.set_markup(
            "<span foreground='#9E9E9E'>—</span>")
        box.pack_start(lbl_title, False, False, 0)
        box.pack_start(lbl_state, False, False, 0)
        box._state_lbl = lbl_state
        return box

    def _set_slot(self, side: str, state):
        key = f"slot_{side.lower()}"
        if key not in self.labels:
            return
        label = _STATE_LABEL.get(state or "", "Unknown")
        color = _STATE_COLOR.get(state or "", "#9E9E9E")
        self.labels[key]._state_lbl.set_markup(
            f"<span foreground='{color}'><b>{label}</b></span>")

    # ── QR generation ────────────────────────────────────────────

    def _generate_qr(self):
        try:
            import qrcode
            url = self._setup_url()
            qr = qrcode.QRCode(
                error_correction=qrcode.constants.ERROR_CORRECT_L,
                box_size=6,
                border=2,
            )
            qr.add_data(url)
            qr.make(fit=True)
            img = qr.make_image(fill_color="black", back_color="white")

            buf = io.BytesIO()
            img.save(buf, format="PNG")
            buf.seek(0)
            raw = buf.read()

            loader = GdkPixbuf.PixbufLoader.new_with_type("png")
            loader.write(raw)
            loader.close()
            pb = loader.get_pixbuf()
            pb = pb.scale_simple(200, 200, GdkPixbuf.InterpType.NEAREST)
            GLib.idle_add(self.labels["qr"].set_from_pixbuf, pb)
        except Exception as e:
            logger.warning("InfinityFlow panel: QR generation failed: %s", e)

    # ── Status fetch ─────────────────────────────────────────────

    def _fetch_status(self):
        try:
            url = f"{self._moonraker_base()}/server/infinity_flow/status"
            with urllib.request.urlopen(url, timeout=3) as resp:
                data = json.loads(resp.read())
            result = data.get("result", data)
            GLib.idle_add(self._apply_status, result)
        except Exception as e:
            logger.debug("InfinityFlow panel: status fetch failed: %s", e)

    def _apply_status(self, data):
        ws_ok = data.get("ws_connected", False)
        self.labels["ws"].set_markup(
            "<small><span foreground='#4CAF50'>● WS connected</span></small>"
            if ws_ok else
            "<small><span foreground='#F44336'>● WS disconnected</span></small>"
        )
        self._set_slot("a", (data.get("slot_a") or {}).get("state"))
        self._set_slot("b", (data.get("slot_b") or {}).get("state"))
        return False

    # ── KlipperScreen lifecycle ──────────────────────────────────

    def activate(self):
        threading.Thread(target=self._fetch_status, daemon=True).start()

    def process_update(self, action, data):
        if action == "notify_infinity_flow_state_changed":
            side = (data.get("side") or "").lower()
            state = data.get("state")
            if side in ("a", "b"):
                GLib.idle_add(self._set_slot, side, state)

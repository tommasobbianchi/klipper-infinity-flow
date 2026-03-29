import json
import logging
import threading
import urllib.request

import gi
gi.require_version("Gtk", "3.0")
from gi.repository import Gtk, GLib

from ks_includes.screen_panel import ScreenPanel

logger = logging.getLogger("klipperscreen")

# raw_state → (display_label, card_bg, fg_text, dot_color)
_STATE = {
    "loaded":   ("Ready",   "#C5E1A5", "#1B5E20", "#388E3C"),
    "active":   ("Feeding", "#80DEEA", "#006064", "#00838F"),
    "sleep":    ("Standby", "#FFF59D", "#7F3B00", "#E65100"),
    "unloaded": ("Empty",   "#F48FB1", "#880E4F", "#C62828"),
}
_UNKNOWN = ("—", "#ECEFF1", "#546E7A", "#78909C")


class Panel(ScreenPanel):
    def __init__(self, screen, title):
        super().__init__(screen, title or "Infinity Flow")
        self._timer = None
        self._cards = {}  # side → {"prov": CssProvider, "dot": Label, "state": Label}

        outer = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=0,
            margin_top=6,
            margin_bottom=8,
            margin_start=10,
            margin_end=10,
        )

        # ── Title row ────────────────────────────────────────────
        hdr = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=8,
            halign=Gtk.Align.CENTER,
            margin_bottom=8,
        )
        title_lbl = Gtk.Label()
        title_lbl.set_markup("<b><span size='x-large'>Infinity Flow S1+</span></b>")
        self.labels["ws"] = Gtk.Label()
        self._set_ws(False)
        hdr.pack_start(title_lbl, False, False, 0)
        hdr.pack_start(self.labels["ws"], False, False, 6)
        outer.pack_start(hdr, False, False, 0)

        # ── Slot cards row ───────────────────────────────────────
        cards_row = Gtk.Box(
            orientation=Gtk.Orientation.HORIZONTAL,
            spacing=10,
            homogeneous=True,
        )
        for side in ("A", "B"):
            cards_row.pack_start(self._build_card(side), True, True, 0)
        outer.pack_start(cards_row, True, True, 0)

        # ── Refresh button ───────────────────────────────────────
        btn_box = Gtk.Box(halign=Gtk.Align.CENTER, margin_top=8)
        btn = Gtk.Button(label="  ↻  Refresh  ")
        btn.connect("clicked", lambda _: threading.Thread(
            target=self._fetch, daemon=True).start())
        btn_box.pack_start(btn, False, False, 0)
        outer.pack_start(btn_box, False, False, 0)

        self.content.add(outer)
        threading.Thread(target=self._fetch, daemon=True).start()

    # ── Card builder ─────────────────────────────────────────────

    def _build_card(self, side: str):
        ev = Gtk.EventBox()
        prov = Gtk.CssProvider()
        _, bg, fg, dot = _UNKNOWN
        prov.load_from_data(self._card_css(bg).encode())
        ev.get_style_context().add_provider(prov, Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION)

        inner = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL,
            spacing=6,
            margin=18,
            halign=Gtk.Align.CENTER,
            valign=Gtk.Align.CENTER,
        )

        lbl_side = Gtk.Label()
        lbl_side.set_markup(f"<b><span size='xx-large'>Slot {side}</span></b>")

        lbl_dot = Gtk.Label()
        lbl_dot.set_markup(f"<span foreground='{dot}' size='56000'>●</span>")

        lbl_state = Gtk.Label()
        lbl_state.set_markup(
            f"<b><span foreground='{fg}' size='x-large'>—</span></b>")

        inner.pack_start(lbl_side, False, False, 0)
        inner.pack_start(lbl_dot, True, True, 0)
        inner.pack_start(lbl_state, False, False, 0)
        ev.add(inner)

        self._cards[side] = {"prov": prov, "dot": lbl_dot, "state": lbl_state}
        return ev

    @staticmethod
    def _card_css(bg: str) -> str:
        return f"* {{ background-color: {bg}; border-radius: 14px; }}"

    # ── State setters ─────────────────────────────────────────────

    def _set_slot(self, side: str, raw_state):
        c = self._cards.get(side)
        if not c:
            return
        label_txt, bg, fg, dot = _STATE.get(raw_state, _UNKNOWN)
        c["prov"].load_from_data(self._card_css(bg).encode())
        c["dot"].set_markup(
            f"<span foreground='{dot}' size='56000'>●</span>")
        c["state"].set_markup(
            f"<b><span foreground='{fg}' size='x-large'>{label_txt}</span></b>")

    def _set_ws(self, connected: bool):
        self.labels["ws"].set_markup(
            "<span foreground='#388E3C' size='large'>●</span>"
            if connected else
            "<span foreground='#C62828' size='large'>●</span>"
        )

    # ── API fetch ─────────────────────────────────────────────────

    def _fetch(self):
        try:
            with urllib.request.urlopen(
                "http://localhost:7125/server/infinity_flow/status", timeout=4
            ) as r:
                data = json.loads(r.read()).get("result", {})
            GLib.idle_add(self._apply, data)
        except Exception as e:
            logger.debug("InfinityFlow panel: %s", e)

    def _apply(self, data):
        self._set_ws(data.get("ws_connected", False))
        for side in ("A", "B"):
            slot = (data.get(f"slot_{side.lower()}") or {})
            self._set_slot(side, slot.get("state"))
        return False

    # ── Lifecycle ─────────────────────────────────────────────────

    def activate(self):
        threading.Thread(target=self._fetch, daemon=True).start()
        self._timer = GLib.timeout_add_seconds(5, self._tick)

    def deactivate(self):
        if self._timer:
            GLib.source_remove(self._timer)
            self._timer = None

    def _tick(self):
        threading.Thread(target=self._fetch, daemon=True).start()
        return True

    def process_update(self, action, data):
        if action == "notify_infinity_flow_state_changed":
            side = (data.get("side") or "").upper()
            state = data.get("state")
            if side in ("A", "B"):
                GLib.idle_add(self._set_slot, side, state)

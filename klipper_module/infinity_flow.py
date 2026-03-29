# Infinity Flow S1+ Integration Module for Klipper
#
# Copyright (C) 2026 Native Ricerca (Tommy Bianchi)
# License: GNU GPLv3
#
# Integrates the Infinity Flow S1+ automatic filament reloader with
# Klipper via the FlowQ cloud WebSocket API.
#
# Architecture:
#   FlowQ cloud WebSocket
#       → Moonraker component (infinity_flow.py)
#           → INFINITY_FLOW_UPDATE gcode
#               → This module (sensor state + pause logic)
#
# The module self-registers virtual filament sensors via
# printer.add_object() — no [filament_switch_sensor] blocks or
# dummy GPIO pins are required in printer.cfg.
#
# Minimal printer.cfg config:
#
#   [infinity_flow]
#   extruder: extruder
#   pause_mode: all_empty       # pause only when BOTH sides empty
#   swap_grace_period: 30       # seconds to wait during spool swap
#   runout_gcode:
#       M117 Filament exhausted — pausing
#       PAUSE
#
# Optional printer.cfg config:
#
#   slot_a_sensor: infinity_flow_a   # name shown in Fluidd / Mainsail
#   slot_b_sensor: infinity_flow_b
#   pause_mode: any_empty            # pause as soon as either side empties
#   swap_gcode:
#       M117 S1+ switching spool...
#   insert_gcode:
#       M117 New spool loaded
#   event_delay: 3.0                 # min seconds between events
#   enabled: True
#
# GCode commands:
#   QUERY_FILAMENT_SENSOR SENSOR=infinity_flow  — brief status
#   SET_FILAMENT_SENSOR SENSOR=infinity_flow ENABLE=1/0
#   INFINITY_FLOW_STATUS                        — detailed status
#   INFINITY_FLOW_UPDATE SIDE=A STATE=present   — called by Moonraker component

import logging
import threading

SWAP_GRACE_DEFAULT = 30.0
CHECK_INTERVAL = 1.0


class VirtualFilamentSensor:
    """
    Registered as 'filament_switch_sensor <name>' via printer.add_object()
    so that Mainsail, Fluidd, and KlipperScreen show it as a native
    filament sensor widget — no physical GPIO pin required.
    """

    def __init__(self, sensor_name: str):
        self.sensor_name = sensor_name
        self.filament_detected: bool = True
        self.enabled: bool = True

    def set_filament_detected(self, present: bool) -> None:
        self.filament_detected = present

    def get_status(self, eventtime):
        return {
            "filament_detected": self.filament_detected,
            "enabled": self.enabled,
        }


class InfinityFlowSensor:
    """
    Klipper extras module for Infinity Flow S1+.

    Receives state updates via the INFINITY_FLOW_UPDATE gcode command
    (sent by the Moonraker infinity_flow component) and manages two
    virtual filament sensors + pause/resume logic.
    """

    def __init__(self, config):
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')

        # Config
        sensor_a_name = config.get('slot_a_sensor', 'infinity_flow_a')
        sensor_b_name = config.get('slot_b_sensor', 'infinity_flow_b')
        self.extruder_name = config.get('extruder', 'extruder')
        self.pause_mode = config.get('pause_mode', 'all_empty')
        if self.pause_mode not in ('all_empty', 'any_empty'):
            raise config.error(
                "pause_mode must be 'all_empty' or 'any_empty', "
                "got: '%s'" % self.pause_mode)
        self.swap_grace = config.getfloat(
            'swap_grace_period', SWAP_GRACE_DEFAULT, minval=0.)
        self.sensor_enabled = config.getboolean('enabled', True)
        # event_delay: minimum seconds between consecutive runout/swap events
        self.event_delay = config.getfloat('event_delay', 3., minval=0.)

        # GCode templates
        gcode_macro = self.printer.load_object(config, 'gcode_macro')

        runout_default = 'M117 S1+ All filament exhausted!\nPAUSE'
        self.runout_gcode = gcode_macro.load_template(
            config, 'runout_gcode',
            config.get('runout_gcode', runout_default))

        self.swap_gcode = None
        if config.get('swap_gcode', None) is not None:
            self.swap_gcode = gcode_macro.load_template(config, 'swap_gcode')

        self.insert_gcode = None
        if config.get('insert_gcode', None) is not None:
            self.insert_gcode = gcode_macro.load_template(
                config, 'insert_gcode')

        # Self-register virtual filament sensors — no dummy pins needed
        self.vsensor_a = VirtualFilamentSensor(sensor_a_name)
        self.vsensor_b = VirtualFilamentSensor(sensor_b_name)
        self.printer.add_object(
            'filament_switch_sensor ' + sensor_a_name, self.vsensor_a)
        self.printer.add_object(
            'filament_switch_sensor ' + sensor_b_name, self.vsensor_b)

        # Internal state
        self.side_a_present = True
        self.side_b_present = True
        self.motor_active = False
        self.swap_in_progress = False
        self.swap_start_time = 0.
        self.min_event_systime = self.reactor.NEVER
        self._lock = threading.Lock()

        self.printer.load_object(config, 'pause_resume')
        self.printer.register_event_handler(
            "klippy:ready", self._handle_ready)
        self.printer.register_event_handler(
            "klippy:shutdown", self._handle_shutdown)

        self.gcode.register_mux_command(
            "QUERY_FILAMENT_SENSOR", "SENSOR", "infinity_flow",
            self.cmd_QUERY_FILAMENT_SENSOR,
            desc="Query Infinity Flow S1+ sensor status")
        self.gcode.register_mux_command(
            "SET_FILAMENT_SENSOR", "SENSOR", "infinity_flow",
            self.cmd_SET_FILAMENT_SENSOR,
            desc="Enable/disable Infinity Flow S1+ sensor")
        self.gcode.register_command(
            "INFINITY_FLOW_STATUS",
            self.cmd_INFINITY_FLOW_STATUS,
            desc="Detailed Infinity Flow S1+ status report")
        self.gcode.register_command(
            "INFINITY_FLOW_UPDATE",
            self.cmd_INFINITY_FLOW_UPDATE,
            desc="Update S1+ sensor state (called by Moonraker component)")

        self._check_timer = None
        logging.info(
            "InfinityFlow: Initialized — pause_mode=%s grace=%.1fs",
            self.pause_mode, self.swap_grace)

    # ── Lifecycle ───────────────────────────────────────────────

    def _handle_ready(self):
        self.min_event_systime = self.reactor.monotonic() + 2.
        self._check_timer = self.reactor.register_timer(
            self._check_callback,
            self.reactor.monotonic() + CHECK_INTERVAL)
        logging.info("InfinityFlow: Ready")

    def _handle_shutdown(self):
        if self._check_timer is not None:
            self.reactor.unregister_timer(self._check_timer)

    # ── Periodic check ──────────────────────────────────────────

    def _check_callback(self, eventtime):
        if not self.sensor_enabled:
            return eventtime + CHECK_INTERVAL

        with self._lock:
            a = self.side_a_present
            b = self.side_b_present
            swapping = self.swap_in_progress

        if swapping and (eventtime - self.swap_start_time) > self.swap_grace:
            if not a and not b:
                self.swap_in_progress = False
                logging.warning("InfinityFlow: Swap grace expired, both sides empty")
                self._trigger_runout(eventtime)
            elif a or b:
                self.swap_in_progress = False
                logging.info("InfinityFlow: Swap completed — A=%s B=%s", a, b)

        return eventtime + CHECK_INTERVAL

    # ── State updates ───────────────────────────────────────────

    def update_side(self, side, is_present, eventtime=None):
        if eventtime is None:
            eventtime = self.reactor.monotonic()

        with self._lock:
            old_a = self.side_a_present
            old_b = self.side_b_present

            if side.upper() == 'A':
                self.side_a_present = is_present
                self.vsensor_a.set_filament_detected(is_present)
                old = old_a
            elif side.upper() == 'B':
                self.side_b_present = is_present
                self.vsensor_b.set_filament_detected(is_present)
                old = old_b
            elif side.upper() == 'MOTOR':
                self.motor_active = is_present
                return
            else:
                return

            new_a = self.side_a_present
            new_b = self.side_b_present

        if is_present and not old:
            logging.info("InfinityFlow: Side %s INSERTED", side)
            self._trigger_insert(eventtime)
        elif not is_present and old:
            logging.info("InfinityFlow: Side %s RUNOUT", side)
            if new_a or new_b:
                self.swap_in_progress = True
                self.swap_start_time = eventtime
                logging.info("InfinityFlow: Swap started, other side available")
                self._trigger_swap(eventtime)
            else:
                if self.pause_mode == 'any_empty':
                    self._trigger_runout(eventtime)
                else:
                    self.swap_in_progress = True
                    self.swap_start_time = eventtime
                    logging.warning(
                        "InfinityFlow: Both sides empty — %.1fs grace",
                        self.swap_grace)

    # ── Event triggers ──────────────────────────────────────────

    def _trigger_runout(self, eventtime):
        if eventtime < self.min_event_systime or not self.sensor_enabled:
            return
        idle_timeout = self.printer.lookup_object("idle_timeout")
        if idle_timeout.get_status(
                self.reactor.monotonic())["state"] != "Printing":
            return

        self.min_event_systime = self.reactor.NEVER
        logging.warning("InfinityFlow: RUNOUT — pausing print")

        def _do(eventtime):
            self.printer.lookup_object('pause_resume').send_pause_command()
            self.reactor.pause(eventtime + 0.5)
            try:
                self.gcode.run_script(self.runout_gcode.render() + "\nM400")
            except Exception:
                logging.exception("InfinityFlow: runout_gcode error")
            self.min_event_systime = self.reactor.monotonic() + self.event_delay

        self.reactor.register_callback(_do)

    def _trigger_swap(self, eventtime):
        if self.swap_gcode is None:
            return
        if eventtime < self.min_event_systime or not self.sensor_enabled:
            return
        self.min_event_systime = self.reactor.NEVER

        def _do(eventtime):
            try:
                self.gcode.run_script(self.swap_gcode.render() + "\nM400")
            except Exception:
                logging.exception("InfinityFlow: swap_gcode error")
            self.min_event_systime = self.reactor.monotonic() + self.event_delay

        self.reactor.register_callback(_do)

    def _trigger_insert(self, eventtime):
        if self.insert_gcode is None:
            return
        if eventtime < self.min_event_systime or not self.sensor_enabled:
            return
        idle_timeout = self.printer.lookup_object("idle_timeout")
        if idle_timeout.get_status(
                self.reactor.monotonic())["state"] == "Printing":
            return
        self.min_event_systime = self.reactor.NEVER

        def _do(eventtime):
            try:
                self.gcode.run_script(self.insert_gcode.render() + "\nM400")
            except Exception:
                logging.exception("InfinityFlow: insert_gcode error")
            self.min_event_systime = self.reactor.monotonic() + self.event_delay

        self.reactor.register_callback(_do)

    # ── GCode commands ──────────────────────────────────────────

    def cmd_QUERY_FILAMENT_SENSOR(self, gcmd):
        with self._lock:
            a, b = self.side_a_present, self.side_b_present
            swapping = self.swap_in_progress
        parts = [
            "Side A: %s" % ("present" if a else "EMPTY"),
            "Side B: %s" % ("present" if b else "EMPTY"),
        ]
        if swapping:
            parts.append("swap in progress")
        gcmd.respond_info(
            "InfinityFlow S1+: filament %s [%s]" %
            ("detected" if (a or b) else "NOT detected", " | ".join(parts)))

    def cmd_SET_FILAMENT_SENSOR(self, gcmd):
        self.sensor_enabled = bool(gcmd.get_int("ENABLE", 1))
        gcmd.respond_info(
            "InfinityFlow S1+ sensor %s" %
            ("enabled" if self.sensor_enabled else "disabled"))

    def cmd_INFINITY_FLOW_STATUS(self, gcmd):
        with self._lock:
            a, b = self.side_a_present, self.side_b_present
            motor = self.motor_active
            swapping = self.swap_in_progress
        now = self.reactor.monotonic()
        grace_remaining = max(0., self.swap_grace -
                              (now - self.swap_start_time)) if swapping else 0.
        gcmd.respond_info("\n".join([
            "=== Infinity Flow S1+ Status ===",
            "Side A: %s" % ("PRESENT" if a else "EMPTY"),
            "Side B: %s" % ("PRESENT" if b else "EMPTY"),
            "Motor: %s" % ("ACTIVE" if motor else "idle"),
            "Swap in progress: %s" % ("YES (%.1fs left)" % grace_remaining
                                      if swapping else "no"),
            "Sensor enabled: %s" % ("YES" if self.sensor_enabled else "NO"),
            "Pause mode: %s" % self.pause_mode,
        ]))

    def cmd_INFINITY_FLOW_UPDATE(self, gcmd):
        side = gcmd.get("SIDE", "A").upper()
        state = gcmd.get("STATE", "present").lower()
        if side not in ('A', 'B', 'MOTOR'):
            gcmd.respond_info("Error: SIDE must be A, B, or MOTOR")
            return
        is_present = state in ('present', 'active', 'loaded', 'sleep',
                               '1', 'true', 'on')
        self.update_side(side, is_present)
        gcmd.respond_info(
            "InfinityFlow: Side %s → %s" %
            (side, "present" if is_present else "empty"))

    # ── Klipper status ──────────────────────────────────────────

    def get_status(self, eventtime):
        with self._lock:
            return {
                "filament_detected": bool(
                    self.side_a_present or self.side_b_present),
                "enabled": bool(self.sensor_enabled),
                "side_a": bool(self.side_a_present),
                "side_b": bool(self.side_b_present),
                "motor_active": bool(self.motor_active),
                "swap_in_progress": bool(self.swap_in_progress),
                "pause_mode": self.pause_mode,
            }


def load_config(config):
    return InfinityFlowSensor(config)

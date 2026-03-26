# Infinity Flow S1+ Integration Module for Klipper
#
# Copyright (C) 2026 Native Ricerca (Tommy Bianchi)
#
# This module integrates the Infinity Flow S1+ automatic filament
# reloader with Klipper via an ESPHome MQTT bridge.
#
# Architecture:
#   S1+ runout switches -> GPIO parallel tap -> ESP32 (ESPHome)
#   -> MQTT -> Moonraker MQTT client -> This Klipper module
#
# The module creates virtual filament sensors that:
#   1. Track filament presence on each S1+ side (A/B)
#   2. Detect when a spool swap is in progress
#   3. Pause the print only when ALL filament is exhausted
#   4. Provide status via QUERY_FILAMENT_SENSOR
#   5. Integrate with KlipperScreen / Fluidd / Mainsail dashboards
#
# Config example in printer.cfg:
#
#   [infinity_flow]
#   mqtt_topic_prefix: infinity_flow
#   extruder: extruder
#   pause_mode: all_empty
#   swap_grace_period: 30
#   runout_gcode:
#       M117 All filament exhausted!
#       PAUSE
#   swap_gcode:
#       M117 S1+ switching to next spool...
#   insert_gcode:
#       M117 New spool loaded on S1+
#   enabled: True
#
# This file may be distributed under the terms of the GNU GPLv3 license.

import logging
import json
import threading

SWAP_GRACE_DEFAULT = 30.0
CHECK_INTERVAL = 1.0


class InfinityFlowSensor:
    """Virtual filament sensor backed by S1+ MQTT data."""

    def __init__(self, config):
        self.name = config.get_name().split()[-1] if ' ' in config.get_name() else 'default'
        self.printer = config.get_printer()
        self.reactor = self.printer.get_reactor()
        self.gcode = self.printer.lookup_object('gcode')

        # Config
        self.mqtt_prefix = config.get('mqtt_topic_prefix', 'infinity_flow')
        self.extruder_name = config.get('extruder', 'extruder')
        self.pause_mode = config.get('pause_mode', 'all_empty')
        self.swap_grace = config.getfloat(
            'swap_grace_period', SWAP_GRACE_DEFAULT, minval=0.)
        self.sensor_enabled = config.getboolean('enabled', True)

        # GCode templates
        gcode_macro = self.printer.load_object(config, 'gcode_macro')
        self.runout_gcode = None
        self.swap_gcode = None
        self.insert_gcode = None

        if config.get('runout_gcode', None) is not None:
            self.runout_gcode = gcode_macro.load_template(
                config, 'runout_gcode', '')
        else:
            self.runout_gcode = gcode_macro.load_template(
                config, 'runout_gcode',
                'M117 S1+ All filament exhausted!\nPAUSE')

        if config.get('swap_gcode', None) is not None:
            self.swap_gcode = gcode_macro.load_template(
                config, 'swap_gcode')

        if config.get('insert_gcode', None) is not None:
            self.insert_gcode = gcode_macro.load_template(
                config, 'insert_gcode')

        # Internal state
        self.side_a_present = True
        self.side_b_present = True
        self.motor_active = False
        self.swap_in_progress = False
        self.swap_start_time = 0.
        self.last_runout_time = 0.
        self.min_event_systime = self.reactor.NEVER
        self.event_delay = config.getfloat('event_delay', 3., minval=0.)

        self._mqtt_lock = threading.Lock()

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
            desc="Detailed Infinity Flow S1+ status")
        self.gcode.register_command(
            "INFINITY_FLOW_UPDATE",
            self.cmd_INFINITY_FLOW_UPDATE,
            desc="Update S1+ sensor state (called by Moonraker MQTT)")

        self._check_timer = None
        logging.info("InfinityFlow: Module initialized, prefix=%s, "
                     "pause_mode=%s, grace=%.1fs",
                     self.mqtt_prefix, self.pause_mode, self.swap_grace)

    def _handle_ready(self):
        self.min_event_systime = self.reactor.monotonic() + 2.
        self._check_timer = self.reactor.register_timer(
            self._check_callback,
            self.reactor.monotonic() + CHECK_INTERVAL)
        logging.info("InfinityFlow: Ready, monitoring active")

    def _handle_shutdown(self):
        if self._check_timer is not None:
            self.reactor.unregister_timer(self._check_timer)

    def _check_callback(self, eventtime):
        """Periodic check for swap timeout and state consistency."""
        if not self.sensor_enabled:
            return eventtime + CHECK_INTERVAL

        with self._mqtt_lock:
            a = self.side_a_present
            b = self.side_b_present
            swapping = self.swap_in_progress

        if swapping and (eventtime - self.swap_start_time) > self.swap_grace:
            if not a and not b:
                self.swap_in_progress = False
                logging.warning(
                    "InfinityFlow: Swap grace expired, both sides empty!")
                self._trigger_runout(eventtime)
            elif a or b:
                self.swap_in_progress = False
                logging.info(
                    "InfinityFlow: Swap completed successfully, "
                    "A=%s B=%s", a, b)

        return eventtime + CHECK_INTERVAL

    def update_side(self, side, is_present, eventtime=None):
        """Update filament presence for a given side."""
        if eventtime is None:
            eventtime = self.reactor.monotonic()

        with self._mqtt_lock:
            old_a = self.side_a_present
            old_b = self.side_b_present

            if side.upper() == 'A':
                self.side_a_present = is_present
            elif side.upper() == 'B':
                self.side_b_present = is_present
            elif side.upper() == 'MOTOR':
                self.motor_active = is_present
                return

            new_a = self.side_a_present
            new_b = self.side_b_present

        if is_present and not (old_a if side.upper() == 'A' else old_b):
            logging.info("InfinityFlow: Side %s filament INSERTED", side)
            self._trigger_insert(eventtime)
        elif not is_present and (old_a if side.upper() == 'A' else old_b):
            logging.info("InfinityFlow: Side %s filament RUNOUT", side)
            if new_a or new_b:
                self.swap_in_progress = True
                self.swap_start_time = eventtime
                logging.info("InfinityFlow: S1+ swap in progress, other side available")
                self._trigger_swap(eventtime)
            else:
                if self.pause_mode == 'any_empty':
                    self._trigger_runout(eventtime)
                else:
                    self.swap_in_progress = True
                    self.swap_start_time = eventtime
                    logging.warning(
                        "InfinityFlow: Both sides empty, starting %.1fs grace period",
                        self.swap_grace)

    def _trigger_runout(self, eventtime):
        if eventtime < self.min_event_systime or not self.sensor_enabled:
            return
        idle_timeout = self.printer.lookup_object("idle_timeout")
        is_printing = idle_timeout.get_status(
            self.reactor.monotonic())["state"] == "Printing"
        if not is_printing:
            return

        self.min_event_systime = self.reactor.NEVER
        logging.warning("InfinityFlow: RUNOUT confirmed - pausing print")

        def _do_runout(eventtime):
            pause_resume = self.printer.lookup_object('pause_resume')
            pause_resume.send_pause_command()
            self.reactor.pause(eventtime + 0.5)
            if self.runout_gcode:
                try:
                    self.gcode.run_script(
                        self.runout_gcode.render() + "\nM400")
                except Exception:
                    logging.exception("InfinityFlow: runout_gcode error")
            self.min_event_systime = (
                self.reactor.monotonic() + self.event_delay)

        self.reactor.register_callback(_do_runout)

    def _trigger_swap(self, eventtime):
        if self.swap_gcode is None:
            return
        if eventtime < self.min_event_systime or not self.sensor_enabled:
            return
        self.min_event_systime = self.reactor.NEVER

        def _do_swap(eventtime):
            try:
                self.gcode.run_script(
                    self.swap_gcode.render() + "\nM400")
            except Exception:
                logging.exception("InfinityFlow: swap_gcode error")
            self.min_event_systime = (
                self.reactor.monotonic() + self.event_delay)

        self.reactor.register_callback(_do_swap)

    def _trigger_insert(self, eventtime):
        if self.insert_gcode is None:
            return
        if eventtime < self.min_event_systime or not self.sensor_enabled:
            return
        idle_timeout = self.printer.lookup_object("idle_timeout")
        is_printing = idle_timeout.get_status(
            self.reactor.monotonic())["state"] == "Printing"
        if is_printing:
            return

        self.min_event_systime = self.reactor.NEVER

        def _do_insert(eventtime):
            try:
                self.gcode.run_script(
                    self.insert_gcode.render() + "\nM400")
            except Exception:
                logging.exception("InfinityFlow: insert_gcode error")
            self.min_event_systime = (
                self.reactor.monotonic() + self.event_delay)

        self.reactor.register_callback(_do_insert)

    def cmd_QUERY_FILAMENT_SENSOR(self, gcmd):
        with self._mqtt_lock:
            a = self.side_a_present
            b = self.side_b_present
            motor = self.motor_active
            swapping = self.swap_in_progress

        any_present = a or b
        status_parts = []
        status_parts.append("Side A: %s" % ("present" if a else "EMPTY"))
        status_parts.append("Side B: %s" % ("present" if b else "EMPTY"))
        if swapping:
            status_parts.append("Swap in progress")
        if motor:
            status_parts.append("Motor active")

        msg = ("InfinityFlow S1+: filament %s [%s]" %
               ("detected" if any_present else "NOT detected",
                " | ".join(status_parts)))
        gcmd.respond_info(msg)

    def cmd_SET_FILAMENT_SENSOR(self, gcmd):
        self.sensor_enabled = bool(gcmd.get_int("ENABLE", 1))
        gcmd.respond_info(
            "InfinityFlow S1+ sensor %s" %
            ("enabled" if self.sensor_enabled else "disabled"))

    def cmd_INFINITY_FLOW_STATUS(self, gcmd):
        with self._mqtt_lock:
            a = self.side_a_present
            b = self.side_b_present
            motor = self.motor_active
            swapping = self.swap_in_progress

        now = self.reactor.monotonic()
        grace_remaining = 0.
        if swapping:
            elapsed = now - self.swap_start_time
            grace_remaining = max(0., self.swap_grace - elapsed)

        lines = [
            "=== Infinity Flow S1+ Status ===",
            "Side A: %s" % ("PRESENT" if a else "EMPTY"),
            "Side B: %s" % ("PRESENT" if b else "EMPTY"),
            "Motor: %s" % ("ACTIVE" if motor else "idle"),
            "Swap in progress: %s" % ("YES" if swapping else "no"),
            "Grace remaining: %.1fs" % grace_remaining,
            "Sensor enabled: %s" % ("YES" if self.sensor_enabled else "NO"),
            "Pause mode: %s" % self.pause_mode,
            "MQTT prefix: %s" % self.mqtt_prefix,
        ]
        gcmd.respond_info("\n".join(lines))

    def cmd_INFINITY_FLOW_UPDATE(self, gcmd):
        side = gcmd.get("SIDE", "A").upper()
        state = gcmd.get("STATE", "present").lower()

        if side not in ('A', 'B', 'MOTOR'):
            gcmd.respond_info("Error: SIDE must be A, B, or MOTOR")
            return

        is_present = state in ('present', 'active', '1', 'true', 'on')
        self.update_side(side, is_present)
        gcmd.respond_info(
            "InfinityFlow: Side %s updated to %s" %
            (side, "present" if is_present else "empty"))

    def get_status(self, eventtime):
        with self._mqtt_lock:
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


def load_config_prefix(config):
    return InfinityFlowSensor(config)

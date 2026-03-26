# Moonraker component for Infinity Flow S1+ MQTT bridge
#
# Subscribes to MQTT topics published by the ESPHome bridge
# and forwards state changes to Klipper's infinity_flow module.
#
# Configuration in moonraker.conf:
#
#   [infinity_flow]
#   mqtt_broker: localhost
#   mqtt_port: 1883
#   mqtt_topic_prefix: infinity_flow
#   #mqtt_user: user
#   #mqtt_password: password
#
# Requires: paho-mqtt (pip install paho-mqtt)

from __future__ import annotations
import logging
import asyncio
from typing import TYPE_CHECKING, Any, Dict, Optional

if TYPE_CHECKING:
    from moonraker.confighelper import ConfigHelper
    from moonraker.components.klippy_connection import KlippyConnection

try:
    import paho.mqtt.client as mqtt
    HAS_PAHO = True
except ImportError:
    HAS_PAHO = False


class InfinityFlowMQTT:
    """Moonraker component bridging S1+ MQTT data to Klipper."""

    def __init__(self, config: ConfigHelper) -> None:
        self.server = config.get_server()
        self.name = config.get_name()

        if not HAS_PAHO:
            raise config.error(
                "paho-mqtt package required. "
                "Install with: pip install paho-mqtt")

        self.broker = config.get("mqtt_broker", "localhost")
        self.port = config.getint("mqtt_port", 1883)
        self.prefix = config.get("mqtt_topic_prefix", "infinity_flow")
        self.mqtt_user = config.get("mqtt_user", None)
        self.mqtt_password = config.get("mqtt_password", None)

        self.connected = False
        self.side_a_state: Optional[str] = None
        self.side_b_state: Optional[str] = None
        self.motor_state: Optional[str] = None

        self.mqtt_client = mqtt.Client(
            client_id="moonraker_infinity_flow",
            protocol=mqtt.MQTTv311)

        if self.mqtt_user:
            self.mqtt_client.username_pw_set(
                self.mqtt_user, self.mqtt_password)

        self.mqtt_client.on_connect = self._on_connect
        self.mqtt_client.on_message = self._on_message
        self.mqtt_client.on_disconnect = self._on_disconnect

        self.server.register_event_handler(
            "server:klippy_ready", self._on_klippy_ready)
        self.server.register_event_handler(
            "server:klippy_shutdown", self._on_klippy_shutdown)

        self.server.register_endpoint(
            "/server/infinity_flow/status",
            ["GET"], self._handle_status_request)
        self.server.register_endpoint(
            "/server/infinity_flow/enable",
            ["POST"], self._handle_enable_request)

        self.server.register_notification("infinity_flow:state_changed")

        logging.info(
            "InfinityFlowMQTT: Initialized, broker=%s:%d, prefix=%s",
            self.broker, self.port, self.prefix)

    async def _on_klippy_ready(self) -> None:
        try:
            self.mqtt_client.connect_async(self.broker, self.port, 60)
            self.mqtt_client.loop_start()
            logging.info("InfinityFlowMQTT: MQTT loop started")
        except Exception as e:
            logging.error(
                "InfinityFlowMQTT: Failed to connect to MQTT: %s", e)

    async def _on_klippy_shutdown(self) -> None:
        self.mqtt_client.loop_stop()
        self.mqtt_client.disconnect()
        self.connected = False
        logging.info("InfinityFlowMQTT: Disconnected")

    def _on_connect(self, client, userdata, flags, rc) -> None:
        if rc == 0:
            self.connected = True
            logging.info("InfinityFlowMQTT: Connected to MQTT broker")
            topics = [
                (f"{self.prefix}/sensor/side_a/state", 1),
                (f"{self.prefix}/sensor/side_b/state", 1),
                (f"{self.prefix}/motor/state", 1),
                (f"{self.prefix}/status", 1),
            ]
            client.subscribe(topics)
            logging.info(
                "InfinityFlowMQTT: Subscribed to %d topics", len(topics))
        else:
            logging.error(
                "InfinityFlowMQTT: Connection failed, rc=%d", rc)

    def _on_disconnect(self, client, userdata, rc) -> None:
        self.connected = False
        if rc != 0:
            logging.warning(
                "InfinityFlowMQTT: Unexpected disconnect, rc=%d", rc)

    def _on_message(self, client, userdata, msg) -> None:
        topic = msg.topic
        payload = msg.payload.decode('utf-8', errors='replace').strip()

        logging.debug(
            "InfinityFlowMQTT: Received %s = %s", topic, payload)

        side = None
        state = None

        if topic == f"{self.prefix}/sensor/side_a/state":
            side = "A"
            state = payload
            self.side_a_state = payload
        elif topic == f"{self.prefix}/sensor/side_b/state":
            side = "B"
            state = payload
            self.side_b_state = payload
        elif topic == f"{self.prefix}/motor/state":
            side = "MOTOR"
            state = payload
            self.motor_state = payload
        elif topic == f"{self.prefix}/status":
            logging.info(
                "InfinityFlowMQTT: S1+ status = %s", payload)
            return

        if side and state:
            self._send_to_klipper(side, state)
            asyncio.ensure_future(
                self._notify_state_change(side, state))

    def _send_to_klipper(self, side: str, state: str) -> None:
        gcode = f"INFINITY_FLOW_UPDATE SIDE={side} STATE={state}"
        try:
            klippy: KlippyConnection = (
                self.server.lookup_component("klippy_connection"))
            if klippy.is_connected():
                asyncio.ensure_future(klippy.run_gcode(gcode))
                logging.debug(
                    "InfinityFlowMQTT: Sent to Klipper: %s", gcode)
            else:
                logging.warning(
                    "InfinityFlowMQTT: Klipper not connected, "
                    "cannot send: %s", gcode)
        except Exception as e:
            logging.error(
                "InfinityFlowMQTT: Error sending to Klipper: %s", e)

    async def _notify_state_change(
            self, side: str, state: str) -> None:
        self.server.send_event(
            "infinity_flow:state_changed",
            {"side": side, "state": state})

    async def _handle_status_request(
            self, web_request) -> Dict[str, Any]:
        return {
            "mqtt_connected": self.connected,
            "broker": f"{self.broker}:{self.port}",
            "side_a": self.side_a_state or "unknown",
            "side_b": self.side_b_state or "unknown",
            "motor": self.motor_state or "unknown",
        }

    async def _handle_enable_request(
            self, web_request) -> Dict[str, Any]:
        enable = web_request.get_boolean("enable", True)
        gcode = f"SET_FILAMENT_SENSOR SENSOR=infinity_flow ENABLE={'1' if enable else '0'}"
        klippy = self.server.lookup_component("klippy_connection")
        if klippy.is_connected():
            await klippy.run_gcode(gcode)
        return {"enabled": enable}


def load_component(config: ConfigHelper) -> InfinityFlowMQTT:
    return InfinityFlowMQTT(config)

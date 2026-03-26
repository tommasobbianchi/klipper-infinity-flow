#!/bin/bash
# install.sh — Infinity Flow S1+ Klipper Integration Installer
# Run on the Klipper host (e.g., IdeaFormer IR3 V2's Raspberry Pi / SBC)
#
# Usage: ./install.sh [--uninstall]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
MOONRAKER_DIR="${MOONRAKER_DIR:-$HOME/moonraker}"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_info()  { echo -e "${GREEN}[INFO]${NC} $1"; }
log_warn()  { echo -e "${YELLOW}[WARN]${NC} $1"; }
log_error() { echo -e "${RED}[ERROR]${NC} $1"; }

install() {
    log_info "=== Infinity Flow S1+ Klipper Integration Installer ==="
    echo ""

    # 1. Check prerequisites
    if [ ! -d "$KLIPPER_DIR/klippy/extras" ]; then
        log_error "Klipper not found at $KLIPPER_DIR"
        log_info "Set KLIPPER_DIR env var if Klipper is elsewhere"
        exit 1
    fi
    log_info "Klipper found at $KLIPPER_DIR"

    if [ ! -d "$MOONRAKER_DIR/moonraker/components" ]; then
        log_error "Moonraker not found at $MOONRAKER_DIR"
        log_info "Set MOONRAKER_DIR env var if Moonraker is elsewhere"
        exit 1
    fi
    log_info "Moonraker found at $MOONRAKER_DIR"

    # 2. Install Klipper module
    log_info "Installing Klipper extras module..."
    cp "$SCRIPT_DIR/klipper_module/infinity_flow.py" \
       "$KLIPPER_DIR/klippy/extras/infinity_flow.py"
    log_info "  -> $KLIPPER_DIR/klippy/extras/infinity_flow.py"

    # 3. Install Moonraker component
    log_info "Installing Moonraker component..."
    cp "$SCRIPT_DIR/moonraker_component/infinity_flow.py" \
       "$MOONRAKER_DIR/moonraker/components/infinity_flow.py"
    log_info "  -> $MOONRAKER_DIR/moonraker/components/infinity_flow.py"

    # 4. Install paho-mqtt for Moonraker
    log_info "Installing paho-mqtt..."
    pip install paho-mqtt --quiet 2>/dev/null || \
    pip install paho-mqtt --break-system-packages --quiet 2>/dev/null || \
    log_warn "Could not install paho-mqtt automatically. Install manually."

    # 5. Install MQTT broker (mosquitto)
    if ! command -v mosquitto &> /dev/null; then
        log_info "Installing Mosquitto MQTT broker..."
        sudo apt-get update -qq
        sudo apt-get install -y -qq mosquitto mosquitto-clients
        sudo systemctl enable mosquitto
        sudo systemctl start mosquitto
        log_info "Mosquitto installed and running"
    else
        log_info "Mosquitto already installed"
    fi

    # 6. Remind about configuration
    echo ""
    log_info "=== Installation complete! ==="
    echo ""
    log_warn "Next steps:"
    echo "  1. Add [infinity_flow] section to your printer.cfg"
    echo "     (see docs/printer_cfg_snippet.cfg for example)"
    echo ""
    echo "  2. Add [infinity_flow] section to your moonraker.conf"
    echo "     (see docs/printer_cfg_snippet.cfg for example)"
    echo ""
    echo "  3. Flash the ESPHome bridge to your ESP32:"
    echo "     cd esphome && esphome run infinity_flow_bridge.yaml"
    echo ""
    echo "  4. Wire the ESP32 to the S1+ runout switches (see README)"
    echo ""
    echo "  5. Restart Klipper and Moonraker:"
    echo "     sudo systemctl restart klipper moonraker"
    echo ""
}

uninstall() {
    log_info "=== Uninstalling Infinity Flow S1+ Integration ==="

    if [ -f "$KLIPPER_DIR/klippy/extras/infinity_flow.py" ]; then
        rm "$KLIPPER_DIR/klippy/extras/infinity_flow.py"
        log_info "Removed Klipper module"
    fi

    if [ -f "$MOONRAKER_DIR/moonraker/components/infinity_flow.py" ]; then
        rm "$MOONRAKER_DIR/moonraker/components/infinity_flow.py"
        log_info "Removed Moonraker component"
    fi

    log_info "Uninstall complete. Remove [infinity_flow] from printer.cfg and moonraker.conf manually."
    log_warn "Mosquitto and paho-mqtt were NOT removed."
}

if [ "$1" = "--uninstall" ]; then
    uninstall
else
    install
fi

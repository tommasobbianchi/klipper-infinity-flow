#!/bin/bash
# install.sh — Infinity Flow S1+ Klipper Integration Installer
#
# Installs the Klipper extras module, Moonraker component, and
# (optionally) the KlipperScreen panel for the Infinity Flow S1+
# automatic filament reloader integration.
#
# Requires: Python 3.9+, Klipper, Moonraker
# Does NOT require: extra hardware, ESPHome, MQTT, dummy GPIO pins
#
# Usage:
#   ./install.sh             # install
#   ./install.sh --uninstall # remove

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
KLIPPER_DIR="${KLIPPER_DIR:-$HOME/klipper}"
MOONRAKER_DIR="${MOONRAKER_DIR:-$HOME/moonraker}"
KLIPPERSCREEN_DIR="${KLIPPERSCREEN_DIR:-$HOME/KlipperScreen}"

RED='\033[0;31m'; GREEN='\033[0;32m'
YELLOW='\033[1;33m'; CYAN='\033[0;36m'; NC='\033[0m'

info()  { echo -e "${GREEN}[✓]${NC} $1"; }
warn()  { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[✗]${NC} $1"; }
step()  { echo -e "${CYAN}[→]${NC} $1"; }

install() {
    echo ""
    echo -e "${GREEN}╔══════════════════════════════════════════════╗${NC}"
    echo -e "${GREEN}║   Infinity Flow S1+ — Klipper Integration    ║${NC}"
    echo -e "${GREEN}╚══════════════════════════════════════════════╝${NC}"
    echo ""

    # ── Prerequisites ─────────────────────────────────────────
    if [ ! -d "$KLIPPER_DIR/klippy/extras" ]; then
        error "Klipper not found at $KLIPPER_DIR"
        warn  "Set KLIPPER_DIR if Klipper is elsewhere: KLIPPER_DIR=/path ./install.sh"
        exit 1
    fi
    info "Klipper found at $KLIPPER_DIR"

    if [ ! -d "$MOONRAKER_DIR/moonraker/components" ]; then
        error "Moonraker not found at $MOONRAKER_DIR"
        warn  "Set MOONRAKER_DIR if Moonraker is elsewhere: MOONRAKER_DIR=/path ./install.sh"
        exit 1
    fi
    info "Moonraker found at $MOONRAKER_DIR"

    # ── Klipper extras module ─────────────────────────────────
    step "Installing Klipper extras module..."
    cp "$SCRIPT_DIR/klipper_module/infinity_flow.py" \
       "$KLIPPER_DIR/klippy/extras/infinity_flow.py"
    info "  $KLIPPER_DIR/klippy/extras/infinity_flow.py"

    # ── Moonraker component ───────────────────────────────────
    step "Installing Moonraker component..."
    cp "$SCRIPT_DIR/moonraker_component/infinity_flow.py" \
       "$MOONRAKER_DIR/moonraker/components/infinity_flow.py"
    info "  $MOONRAKER_DIR/moonraker/components/infinity_flow.py"

    # ── Python dependencies for Moonraker ─────────────────────
    step "Installing Python dependencies (aiohttp, websockets)..."
    _pip_install() {
        pip install "$@" --quiet 2>/dev/null || \
        pip install "$@" --break-system-packages --quiet 2>/dev/null || \
        pip3 install "$@" --break-system-packages --quiet 2>/dev/null || \
        { warn "Could not auto-install $*. Install manually."; return 0; }
    }
    _pip_install aiohttp
    _pip_install websockets
    info "  aiohttp, websockets installed"

    # ── KlipperScreen panel (optional) ────────────────────────
    if [ -d "$KLIPPERSCREEN_DIR/panels" ]; then
        step "Installing KlipperScreen panel..."
        cp "$SCRIPT_DIR/klipperscreen/panel.py" \
           "$KLIPPERSCREEN_DIR/panels/infinity_flow.py"
        info "  $KLIPPERSCREEN_DIR/panels/infinity_flow.py"

        # Add menu entry to KlipperScreen.conf if not already present
        KS_CONF="${PRINTER_DATA_DIR:-$HOME/printer_data}/config/KlipperScreen.conf"
        if [ -f "$KS_CONF" ]; then
            if ! grep -q "infinity_flow" "$KS_CONF" 2>/dev/null; then
                echo "" >> "$KS_CONF"
                echo "[menu __main infinity_flow]" >> "$KS_CONF"
                echo "name: Infinity Flow" >> "$KS_CONF"
                echo "icon: filament" >> "$KS_CONF"
                echo "panel: infinity_flow" >> "$KS_CONF"
                info "  Added 'Infinity Flow' to KlipperScreen main menu"
            else
                info "  KlipperScreen menu entry already present"
            fi
        else
            warn "  KlipperScreen.conf not found — add menu entry manually:"
            echo "    [menu __main infinity_flow]"
            echo "    name: Infinity Flow"
            echo "    icon: filament"
            echo "    panel: infinity_flow"
        fi
    else
        warn "KlipperScreen not found — skipping panel install"
        warn "  Install panel manually: copy klipperscreen/panel.py to"
        warn "  $KLIPPERSCREEN_DIR/panels/infinity_flow.py"
    fi

    # ── Done ───────────────────────────────────────────────────
    echo ""
    info "═══════════════════════════════════════"
    info "Installation complete!"
    info "═══════════════════════════════════════"
    echo ""
    echo "  Run the configurator to finish setup:"
    echo ""
    echo "      python3 $(realpath "$SCRIPT_DIR")/configure.py"
    echo ""
    echo "  It will guide you through:"
    echo "    - Getting your FlowQ token"
    echo "    - Writing printer.cfg and moonraker.conf"
    echo "    - Restarting services"
    echo ""
}

uninstall() {
    echo ""
    step "Uninstalling Infinity Flow S1+ integration..."

    local removed=0
    if [ -f "$KLIPPER_DIR/klippy/extras/infinity_flow.py" ]; then
        rm "$KLIPPER_DIR/klippy/extras/infinity_flow.py"
        info "Removed Klipper module"
        ((removed++)) || true
    fi
    if [ -f "$MOONRAKER_DIR/moonraker/components/infinity_flow.py" ]; then
        rm "$MOONRAKER_DIR/moonraker/components/infinity_flow.py"
        info "Removed Moonraker component"
        ((removed++)) || true
    fi
    if [ -f "$KLIPPERSCREEN_DIR/panels/infinity_flow.py" ]; then
        rm "$KLIPPERSCREEN_DIR/panels/infinity_flow.py"
        info "Removed KlipperScreen panel"
        ((removed++)) || true
    fi

    if [ $removed -eq 0 ]; then
        warn "Nothing to remove (files not found)"
    else
        info "Uninstall complete."
        warn "Remove [infinity_flow] sections from printer.cfg and moonraker.conf manually."
        warn "Then restart: sudo systemctl restart moonraker klipper"
    fi
    echo ""
}

case "${1:-}" in
    --uninstall) uninstall ;;
    *)           install   ;;
esac

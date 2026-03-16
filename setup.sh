#!/usr/bin/env bash
# =============================================================================
# ADS-B Visual Tracker — Raspberry Pi 3B Setup Script
# =============================================================================
# Run once after cloning the repository:
#   chmod +x setup.sh && sudo ./setup.sh
#
# What this does:
#   1. Installs system packages (Python, RTL-SDR drivers, dump1090)
#   2. Creates a Python virtualenv and installs Python dependencies
#   3. Installs a systemd service so the app starts on boot
#   4. Optionally configures Chromium to auto-launch in kiosk mode
# =============================================================================

set -e

REPO_DIR="$(cd "$(dirname "$0")" && pwd)"
APP_USER="${SUDO_USER:-pi}"
VENV_DIR="$REPO_DIR/venv"
SERVICE_NAME="adsb-tracker"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------
info()  { echo -e "\033[1;34m[INFO]\033[0m  $*"; }
ok()    { echo -e "\033[1;32m[ OK ]\033[0m  $*"; }
warn()  { echo -e "\033[1;33m[WARN]\033[0m  $*"; }
die()   { echo -e "\033[1;31m[ERR ]\033[0m  $*" >&2; exit 1; }

# ---------------------------------------------------------------------------
# Must be run as root
# ---------------------------------------------------------------------------
[[ $EUID -eq 0 ]] || die "Run this script with sudo."

info "Setting up ADS-B Visual Tracker in: $REPO_DIR"
info "App will run as user: $APP_USER"

# ---------------------------------------------------------------------------
# 1. System packages
# ---------------------------------------------------------------------------
info "Updating package lists…"
apt-get update -qq

info "Installing system dependencies…"
apt-get install -y --no-install-recommends \
    python3 \
    python3-pip \
    python3-venv \
    libusb-1.0-0 \
    rtl-sdr \
    udev

# Add udev rule so RTL-SDR is accessible without root
if ! grep -q "rtl_sdr" /etc/udev/rules.d/20-rtlsdr.rules 2>/dev/null; then
    info "Adding udev rule for RTL-SDR…"
    cat > /etc/udev/rules.d/20-rtlsdr.rules <<'EOF'
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2838", GROUP="plugdev", MODE="0666"
SUBSYSTEM=="usb", ATTRS{idVendor}=="0bda", ATTRS{idProduct}=="2832", GROUP="plugdev", MODE="0666"
EOF
    udevadm control --reload-rules
fi

# ---------------------------------------------------------------------------
# 2. dump1090 (FlightAware fork) — optional, skip if not wanted
# ---------------------------------------------------------------------------
read -r -p "Install dump1090-fa for live RTL-SDR reception? [y/N] " INSTALL_D1090
if [[ "$INSTALL_D1090" =~ ^[Yy]$ ]]; then
    info "Installing dump1090-fa…"
    # Add FlightAware PiAware repository
    if ! dpkg -s dump1090-fa &>/dev/null; then
        curl -sSL https://flightaware.com/adsb/piaware/install | bash -s -- --no-piaware || true
        apt-get install -y dump1090-fa || warn "dump1090-fa not found; install manually."
    else
        ok "dump1090-fa already installed."
    fi
fi

# ---------------------------------------------------------------------------
# 3. Python virtualenv + dependencies
# ---------------------------------------------------------------------------
info "Creating Python virtualenv in $VENV_DIR…"
sudo -u "$APP_USER" python3 -m venv "$VENV_DIR"

info "Installing Python dependencies…"
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install --upgrade pip -q
sudo -u "$APP_USER" "$VENV_DIR/bin/pip" install -r "$REPO_DIR/requirements.txt" -q
ok "Python dependencies installed."

info "Downloading frontend vendor assets (Leaflet, Socket.IO)…"
sudo -u "$APP_USER" "$VENV_DIR/bin/python" "$REPO_DIR/download_vendor.py" || \
    warn "Vendor download failed — will retry on first app launch."

# ---------------------------------------------------------------------------
# 4. systemd service
# ---------------------------------------------------------------------------
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"
info "Installing systemd service: $SERVICE_FILE"

cat > "$SERVICE_FILE" <<EOF
[Unit]
Description=ADS-B Visual Tracker
After=network.target

[Service]
Type=simple
User=$APP_USER
WorkingDirectory=$REPO_DIR
ExecStart=$VENV_DIR/bin/python main.py
Restart=on-failure
RestartSec=5
Environment=ADSB_PORT=5000

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
systemctl enable "$SERVICE_NAME"
systemctl start "$SERVICE_NAME"
ok "Service $SERVICE_NAME enabled and started."

# ---------------------------------------------------------------------------
# 5. Chromium kiosk mode (optional)
# ---------------------------------------------------------------------------
read -r -p "Configure Chromium to auto-launch in kiosk mode on boot? [y/N] " KIOSK
if [[ "$KIOSK" =~ ^[Yy]$ ]]; then
    AUTOSTART_DIR="/home/$APP_USER/.config/autostart"
    mkdir -p "$AUTOSTART_DIR"
    cat > "$AUTOSTART_DIR/adsb-kiosk.desktop" <<EOF
[Desktop Entry]
Type=Application
Name=ADS-B Kiosk
Exec=bash -c 'sleep 5 && chromium-browser --kiosk --noerrdialogs --disable-infobars --no-first-run http://localhost:5000'
Hidden=false
X-GNOME-Autostart-enabled=true
EOF
    chown "$APP_USER:$APP_USER" "$AUTOSTART_DIR/adsb-kiosk.desktop"
    ok "Chromium kiosk autostart configured."
fi

# ---------------------------------------------------------------------------
# Done
# ---------------------------------------------------------------------------
IP=$(hostname -I | awk '{print $1}')
echo ""
echo "========================================================"
ok "Setup complete!"
echo ""
echo "  App URL    :  http://localhost:5000"
echo "  Network URL:  http://${IP}:5000"
echo ""
echo "  Service    :  sudo systemctl {start|stop|status} $SERVICE_NAME"
echo "  Logs       :  sudo journalctl -u $SERVICE_NAME -f"
echo ""
echo "  Pre-cache tiles for offline use:"
echo "    $VENV_DIR/bin/python cache_tiles.py --from-config"
echo "========================================================"

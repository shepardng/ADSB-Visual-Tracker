# ADS-B Visual Tracker

A real-time aircraft tracking application for **Raspberry Pi 3B** that projects a live map of aircraft overhead onto your ceiling via an HDMI projector.

Ingests ADS-B transponder data from a USB RTL-SDR dongle (via [dump1090](https://github.com/flightaware/dump1090)) or the free [OpenSky Network](https://opensky-network.org/) REST API, filters by a configurable geographic area, and renders aircraft on an interactive Leaflet.js map served from a local Flask web server.

---

## Features

- **Live aircraft map** with callsign, altitude, speed, heading, and trail
- **Two data sources**: RTL-SDR via dump1090 (local) or OpenSky Network (API)
- **Configuration UI** — all settings adjustable via a web browser
- **Presentation mode** — full-screen dark map with a single keypress (`P`)
- **Ceiling projection** — vertical flip and/or 180° rotation for projector alignment
- **Offline tile cache** — pre-download map tiles for your local area
- **Geographic filter** — only show aircraft within a configurable radius

---

## Requirements

| Hardware | |
|---|---|
| Raspberry Pi 3B (or newer) | Runs the Python server |
| RTL-SDR USB dongle | *Optional* — for live local ADS-B reception |
| HDMI projector | Pointed at ceiling for presentation mode |

| Software | |
|---|---|
| Raspberry Pi OS (Bullseye / Bookworm) | |
| Python 3.9+ | |
| dump1090-fa | *Optional* — RTL-SDR decoder |

---

## Quick Start

### 1. Clone and set up

```bash
git clone <repo-url> ADSB-Visual-Tracker
cd ADSB-Visual-Tracker
chmod +x setup.sh
sudo ./setup.sh
```

The setup script installs system packages, creates a Python virtualenv, installs a systemd service, and optionally configures Chromium kiosk autostart.

### 2. Manual start (without setup.sh)

```bash
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt

python main.py
```

Open `http://localhost:5000` in a browser.

### 3. Configure

Click **⚙ Config** in the header (or press `C`).

Key settings:
- **Location** — your latitude, longitude, and radius (km) for aircraft filtering
- **Data Source** — choose OpenSky (API, no hardware) or dump1090 (RTL-SDR dongle)
- **Ceiling Projection** — enable flip/rotation to correct for your projector mount

Click **Save Settings**.

### 4. Enter presentation mode

Press `P` (or click **▶ Present**) to enter full-screen dark mode. The map fills the entire screen — aim your projector at the ceiling.

Press `P` or `Esc` to exit.

---

## Data Sources

### OpenSky Network (default)

No hardware required. The app queries the [OpenSky Network public API](https://opensky-network.org/apidoc/) every 10 seconds.

- Anonymous access: ~10 requests/minute rate limit
- Create a free account at [opensky-network.org](https://opensky-network.org/) for higher limits
- Enter your credentials in the Config panel under **Data Source**

### dump1090 / RTL-SDR

For live, low-latency local reception:

1. Install dump1090-fa (the setup script can do this)
2. Plug in your RTL-SDR dongle
3. Start dump1090: `sudo systemctl start dump1090-fa`
4. In Config, switch **Source** to `dump1090 (RTL-SDR)`
5. Set host `localhost` and port `8080`

---

## Offline Tile Cache

Pre-download map tiles so the map works without internet:

```bash
# Using settings from config.json
python cache_tiles.py --from-config

# Or specify area manually
python cache_tiles.py --lat 40.7128 --lon -74.0060 --radius 150 --theme dark
```

Tiles are stored in `~/.adsb-tracker/tiles/` and served by the local Flask server.

---

## Ceiling Projection Setup

In the **Config panel → Ceiling Projection** section:

| Projector position | Setting |
|---|---|
| Sitting on a table pointing up at the ceiling | Enable **Flip vertically** |
| Mounted upside-down from the ceiling | Enable **Rotate 180°** |
| Mounted upside-down AND sideways | Enable both |

---

## Keyboard Shortcuts

| Key | Action |
|---|---|
| `P` | Toggle presentation mode |
| `Esc` | Exit presentation mode |
| `C` | Open/close config panel |
| `R` | Re-center map on home coordinates |

---

## Project Structure

```
ADSB-Visual-Tracker/
├── main.py                     # Entry point
├── cache_tiles.py              # Offline tile pre-caching utility
├── config.json                 # Persistent configuration (auto-created)
├── requirements.txt
├── setup.sh                    # Raspberry Pi setup script
└── app/
    ├── config_manager.py       # Load/save config.json
    ├── adsb/
    │   ├── aircraft_store.py   # Thread-safe in-memory aircraft state
    │   ├── dump1090_client.py  # RTL-SDR via dump1090 JSON API
    │   ├── opensky_client.py   # OpenSky Network REST API client
    │   └── data_manager.py     # Background data polling + WebSocket push
    └── web/
        ├── routes.py           # REST API + tile proxy
        ├── socketio_events.py  # WebSocket event handlers
        └── static/
            ├── index.html
            ├── css/style.css
            └── js/
                ├── main.js         # App init, keyboard shortcuts, mode switching
                ├── map.js          # Leaflet map, aircraft markers, trails
                ├── socket.js       # Socket.IO client
                └── config_panel.js # Config form UI
```

---

## Service Management

```bash
sudo systemctl status adsb-tracker      # Check status
sudo systemctl restart adsb-tracker     # Restart after config changes
sudo journalctl -u adsb-tracker -f      # Live logs
```

---

## Configuration Reference

All settings are in `config.json` (or the Config panel UI):

```json
{
  "location": {
    "latitude":   40.7128,
    "longitude":  -74.0060,
    "radius_km":  150
  },
  "data_source": {
    "type":                    "opensky",
    "dump1090_host":           "localhost",
    "dump1090_port":           8080,
    "opensky_username":        "",
    "opensky_password":        "",
    "poll_interval_seconds":   10
  },
  "display": {
    "theme":                  "dark",
    "show_trails":            true,
    "trail_length":           10,
    "show_labels":            true,
    "label_fields":           ["callsign", "altitude", "speed"],
    "ceiling_flip_vertical":  false,
    "ceiling_rotate_180":     false,
    "zoom_level":             9
  },
  "filters": {
    "min_altitude_ft":        0,
    "max_altitude_ft":        60000,
    "show_ground_vehicles":   false
  }
}
```

---

## License

MIT

import json
import os
import math
from threading import Lock

CONFIG_PATH = os.path.join(os.path.dirname(os.path.dirname(__file__)), 'config.json')

DEFAULT_CONFIG = {
    "location": {
        "latitude": 40.7128,
        "longitude": -74.0060,
        "radius_km": 150
    },
    "data_source": {
        "type": "opensky",
        "dump1090_host": "localhost",
        "dump1090_port": 8080,
        "opensky_client_id": "",
        "opensky_client_secret": "",
        "opensky_username": "",
        "opensky_password": "",
        "poll_interval_seconds": 10
    },
    "integrations": {
        "skylink_api_key": ""
    },
    "display": {
        "theme": "dark",
        "show_trails": True,
        "trail_length": 10,
        "show_labels": True,
        "label_fields": ["callsign", "altitude", "speed"],
        "ceiling_flip_vertical": False,
        "ceiling_rotate_180": False,
        "zoom_level": 9
    },
    "filters": {
        "min_altitude_ft": 0,
        "max_altitude_ft": 60000,
        "show_ground_vehicles": False
    }
}

_lock = Lock()
_config = None


def _deep_merge(base, override):
    """Recursively merge override into base, returning a new merged dict."""
    result = dict(base)
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config():
    global _config
    with _lock:
        if os.path.exists(CONFIG_PATH):
            with open(CONFIG_PATH, 'r') as f:
                stored = json.load(f)
            _config = _deep_merge(DEFAULT_CONFIG, stored)
        else:
            _config = _deep_merge({}, DEFAULT_CONFIG)
        return dict(_config)


def get_config():
    global _config
    with _lock:
        if _config is None:
            load_config()
        return dict(_config)


def save_config(updates):
    global _config
    with _lock:
        if _config is None:
            load_config()
        _config = _deep_merge(_config, updates)
        tmp = CONFIG_PATH + '.tmp'
        with open(tmp, 'w') as f:
            json.dump(_config, f, indent=2)
        os.replace(tmp, CONFIG_PATH)
        return dict(_config)


def get_bounding_box():
    """Return (lat_min, lat_max, lon_min, lon_max) from configured center + radius."""
    cfg = get_config()
    lat = cfg['location']['latitude']
    lon = cfg['location']['longitude']
    r_km = cfg['location']['radius_km']

    lat_delta = r_km / 111.32
    lon_delta = r_km / (111.32 * math.cos(math.radians(lat)))

    return (lat - lat_delta, lat + lat_delta, lon - lon_delta, lon + lon_delta)

import requests
import logging
import time

logger = logging.getLogger(__name__)

OPENSKY_URL = "https://opensky-network.org/api/states/all"

# OpenSky state vector column order
_COLUMNS = [
    'icao24', 'callsign', 'origin_country', 'time_position',
    'last_contact', 'longitude', 'latitude', 'baro_altitude',
    'on_ground', 'velocity', 'true_track', 'vertical_rate',
    'sensors', 'geo_altitude', 'squawk', 'spi', 'position_source'
]

# Anonymous rate limit: 10 requests/minute (one every 6s minimum)
_MIN_INTERVAL_ANON = 10
_MIN_INTERVAL_AUTH = 6
_last_fetch_time = 0


def fetch_aircraft(lat_min, lat_max, lon_min, lon_max,
                   username='', password='', timeout=15):
    """
    Fetch aircraft within bounding box from OpenSky Network.
    Returns list of dicts in internal format, or None if rate-limited or error.
    """
    global _last_fetch_time

    min_interval = _MIN_INTERVAL_AUTH if username else _MIN_INTERVAL_ANON
    elapsed = time.time() - _last_fetch_time
    if elapsed < min_interval:
        logger.debug("OpenSky rate limit: %.1fs remaining", min_interval - elapsed)
        return None

    params = {
        'lamin': round(lat_min, 4),
        'lamax': round(lat_max, 4),
        'lomin': round(lon_min, 4),
        'lomax': round(lon_max, 4),
    }
    auth = (username, password) if username else None

    try:
        resp = requests.get(OPENSKY_URL, params=params, auth=auth, timeout=timeout)
        resp.raise_for_status()
        _last_fetch_time = time.time()

        data = resp.json()
        states = data.get('states') or []
        return [ac for ac in (_parse_state(s) for s in states) if ac is not None]

    except requests.RequestException as e:
        logger.warning("OpenSky fetch failed: %s", e)
        return None


def _parse_state(state):
    if len(state) < len(_COLUMNS):
        return None

    s = dict(zip(_COLUMNS, state))

    lat = s.get('latitude')
    lon = s.get('longitude')
    if lat is None or lon is None:
        return None

    alt_m = s.get('baro_altitude') or s.get('geo_altitude')
    alt_ft = round(alt_m * 3.28084) if alt_m is not None else None

    speed_ms = s.get('velocity')
    speed_kts = round(speed_ms * 1.94384) if speed_ms is not None else None

    vert_ms = s.get('vertical_rate')
    vert_fpm = round(vert_ms * 196.85) if vert_ms is not None else None

    return {
        'icao': (s.get('icao24') or '').upper(),
        'callsign': (s.get('callsign') or '').strip() or None,
        'latitude': lat,
        'longitude': lon,
        'altitude_ft': 0 if s.get('on_ground') else alt_ft,
        'speed_kts': speed_kts,
        'heading_deg': s.get('true_track'),
        'vertical_rate_fpm': vert_fpm,
        'squawk': s.get('squawk'),
    }

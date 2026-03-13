import requests
import logging

logger = logging.getLogger(__name__)


def fetch_aircraft(host, port, timeout=5):
    """
    Fetch aircraft list from dump1090's JSON API.
    Returns list of dicts in internal format, or None on connection failure.
    """
    url = f"http://{host}:{port}/data/aircraft.json"
    try:
        resp = requests.get(url, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        aircraft_list = data.get('aircraft', [])
        return [_parse(a) for a in aircraft_list if _has_position(a)]
    except requests.RequestException as e:
        logger.warning("dump1090 fetch failed (%s): %s", url, e)
        return None


def _has_position(a):
    return 'lat' in a and 'lon' in a


def _parse(a):
    alt = a.get('altitude')
    if alt == 'ground':
        alt = 0

    return {
        'icao': a.get('hex', '').upper(),
        'callsign': (a.get('flight') or '').strip() or None,
        'latitude': a.get('lat'),
        'longitude': a.get('lon'),
        'altitude_ft': int(alt) if alt is not None else None,
        'speed_kts': a.get('speed'),
        'heading_deg': a.get('track'),
        'vertical_rate_fpm': a.get('vert_rate'),
        'squawk': a.get('squawk'),
    }

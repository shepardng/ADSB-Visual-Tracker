import requests
import logging
import time
import threading

logger = logging.getLogger(__name__)

OPENSKY_URL = "https://opensky-network.org/api/states/all"
OPENSKY_TOKEN_URL = (
    "https://auth.opensky-network.org/auth/realms/opensky-network"
    "/protocol/openid-connect/token"
)
_OPENSKY_CLIENT_ID = "opensky-api"

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

# OAuth 2.0 token cache
_token_lock = threading.Lock()
_access_token = None
_token_expiry = 0.0
_refresh_token = None
_token_username = None   # track which user owns the cached token


def _clear_token():
    global _access_token, _token_expiry, _refresh_token, _token_username
    _access_token = None
    _token_expiry = 0.0
    _refresh_token = None
    _token_username = None


def _get_token(username, password, client_id='', client_secret=''):
    """Return a valid OAuth 2.0 bearer token, refreshing or re-authenticating as needed.

    Prefers Client Credentials grant when client_id and client_secret are provided.
    Falls back to Resource Owner Password Credentials grant when only username/password are set.
    """
    global _access_token, _token_expiry, _refresh_token, _token_username

    now = time.time()
    cache_key = client_id or username

    with _token_lock:
        # Discard cached token if the identity changed
        if _token_username != cache_key:
            _clear_token()

        # Return cached token if still valid (30 s safety margin)
        if _access_token and now < _token_expiry - 30:
            return _access_token

        # --- Client Credentials grant (preferred when client_id+secret available) ---
        if client_id and client_secret:
            # Try refresh token first if we have one
            if _refresh_token:
                try:
                    resp = requests.post(OPENSKY_TOKEN_URL, data={
                        'client_id': client_id,
                        'client_secret': client_secret,
                        'grant_type': 'refresh_token',
                        'refresh_token': _refresh_token,
                    }, timeout=10)
                    if resp.ok:
                        td = resp.json()
                        _access_token = td['access_token']
                        _token_expiry = now + td.get('expires_in', 300)
                        _refresh_token = td.get('refresh_token', _refresh_token)
                        _token_username = cache_key
                        logger.debug("OpenSky OAuth token refreshed (client credentials)")
                        return _access_token
                    logger.debug("Token refresh rejected (%s), re-authenticating", resp.status_code)
                except requests.RequestException as e:
                    logger.warning("Token refresh error: %s", e)
                _refresh_token = None

            resp = requests.post(OPENSKY_TOKEN_URL, data={
                'client_id': client_id,
                'client_secret': client_secret,
                'grant_type': 'client_credentials',
            }, timeout=10)
            resp.raise_for_status()
            td = resp.json()
            _access_token = td['access_token']
            _token_expiry = now + td.get('expires_in', 300)
            _refresh_token = td.get('refresh_token')
            _token_username = cache_key
            logger.info("OpenSky OAuth token acquired via client credentials (id='%s')", client_id)
            return _access_token

        # --- Resource Owner Password Credentials grant (legacy fallback) ---
        if _refresh_token:
            try:
                resp = requests.post(OPENSKY_TOKEN_URL, data={
                    'client_id': _OPENSKY_CLIENT_ID,
                    'grant_type': 'refresh_token',
                    'refresh_token': _refresh_token,
                }, timeout=10)
                if resp.ok:
                    td = resp.json()
                    _access_token = td['access_token']
                    _token_expiry = now + td.get('expires_in', 300)
                    _refresh_token = td.get('refresh_token', _refresh_token)
                    _token_username = cache_key
                    logger.debug("OpenSky OAuth token refreshed")
                    return _access_token
                logger.debug("Token refresh rejected (%s), re-authenticating", resp.status_code)
            except requests.RequestException as e:
                logger.warning("Token refresh error: %s", e)
            _refresh_token = None

        resp = requests.post(OPENSKY_TOKEN_URL, data={
            'client_id': _OPENSKY_CLIENT_ID,
            'grant_type': 'password',
            'username': username,
            'password': password,
        }, timeout=10)
        resp.raise_for_status()
        td = resp.json()
        _access_token = td['access_token']
        _token_expiry = now + td.get('expires_in', 300)
        _refresh_token = td.get('refresh_token')
        _token_username = cache_key
        logger.info("OpenSky OAuth token acquired for user '%s'", username)
        return _access_token


def fetch_aircraft(lat_min, lat_max, lon_min, lon_max,
                   username='', password='',
                   client_id='', client_secret='',
                   timeout=15):
    """
    Fetch aircraft within bounding box from OpenSky Network.
    Authenticated requests use OAuth 2.0 bearer tokens.
    Prefers Client Credentials grant (client_id + client_secret) when available,
    falls back to ROPC grant (username + password).
    Returns list of dicts in internal format, or None if rate-limited or error.
    """
    global _last_fetch_time

    is_authenticated = bool(client_id and client_secret) or bool(username)
    min_interval = _MIN_INTERVAL_AUTH if is_authenticated else _MIN_INTERVAL_ANON
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

    if is_authenticated:
        try:
            token = _get_token(username, password, client_id, client_secret)
            headers = {'Authorization': f'Bearer {token}'}
        except requests.RequestException as e:
            logger.warning("OpenSky OAuth token fetch failed: %s", e)
            return None
    else:
        headers = {}

    try:
        resp = requests.get(OPENSKY_URL, params=params, headers=headers, timeout=timeout)
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

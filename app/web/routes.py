import os
import threading
import logging

import requests as req_lib
from flask import Blueprint, jsonify, request, send_from_directory

from ..config_manager import get_config, save_config, load_config
from ..adsb.aircraft_store import store
from ..adsb import data_manager

logger = logging.getLogger(__name__)

api_bp = Blueprint('api', __name__)

STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')
TILE_CACHE_DIR = os.path.join(os.path.expanduser('~'), '.adsb-tracker', 'tiles')

_TILE_CDN = {
    'dark': 'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    'light': 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
}

_tile_cache_thread = None
_tile_cache_progress = {'status': 'idle', 'fetched': 0, 'total': 0, 'error': None}


# ---------------------------------------------------------------------------
# HTML shell
# ---------------------------------------------------------------------------

@api_bp.route('/')
def index():
    return send_from_directory(STATIC_DIR, 'index.html')


# ---------------------------------------------------------------------------
# Aircraft & status
# ---------------------------------------------------------------------------

@api_bp.route('/api/aircraft')
def get_aircraft():
    cfg = get_config()
    aircraft = store.get_filtered(cfg)
    return jsonify({'aircraft': aircraft, 'count': len(aircraft)})


@api_bp.route('/api/status')
def get_status():
    return jsonify(data_manager.get_status())


# ---------------------------------------------------------------------------
# Configuration
# ---------------------------------------------------------------------------

@api_bp.route('/api/config', methods=['GET'])
def get_config_route():
    return jsonify(get_config())


@api_bp.route('/api/config', methods=['POST'])
def update_config():
    data = request.get_json(force=True, silent=True)
    if not data:
        return jsonify({'error': 'Invalid or missing JSON body'}), 400
    updated = save_config(data)
    return jsonify(updated)


# ---------------------------------------------------------------------------
# Tile proxy with local cache
# ---------------------------------------------------------------------------

@api_bp.route('/tiles/<int:z>/<int:x>/<int:y>.png')
def serve_tile(z, x, y):
    """Serve a locally cached tile; fetch from CDN on cache miss."""
    cfg = get_config()
    theme = cfg['display'].get('theme', 'dark')
    theme_key = 'dark' if theme == 'dark' else 'light'

    tile_dir = os.path.join(TILE_CACHE_DIR, theme_key, str(z), str(x))
    tile_file = f'{y}.png'
    tile_path = os.path.join(tile_dir, tile_file)

    if os.path.exists(tile_path):
        return send_from_directory(tile_dir, tile_file,
                                   max_age=86400,
                                   mimetype='image/png')

    # Cache miss — fetch from CDN
    cdn_url = _TILE_CDN[theme_key].replace('{z}', str(z)).replace('{x}', str(x)).replace('{y}', str(y))
    try:
        resp = req_lib.get(cdn_url, timeout=8,
                           headers={'User-Agent': 'ADSB-Visual-Tracker/1.0'})
        if resp.status_code == 200:
            os.makedirs(tile_dir, exist_ok=True)
            with open(tile_path, 'wb') as f:
                f.write(resp.content)
            return send_from_directory(tile_dir, tile_file,
                                       max_age=86400,
                                       mimetype='image/png')
    except Exception as e:
        logger.warning("Tile fetch failed z=%s x=%s y=%s: %s", z, x, y, e)

    return '', 404


# ---------------------------------------------------------------------------
# Tile pre-caching
# ---------------------------------------------------------------------------

@api_bp.route('/api/cache-tiles', methods=['POST'])
def start_tile_cache():
    """Trigger background tile pre-caching for the configured area."""
    global _tile_cache_thread, _tile_cache_progress

    if _tile_cache_thread and _tile_cache_thread.is_alive():
        return jsonify({'status': 'already_running',
                        'progress': _tile_cache_progress}), 409

    cfg = get_config()
    lat = cfg['location']['latitude']
    lon = cfg['location']['longitude']
    radius_km = cfg['location']['radius_km']
    theme = cfg['display'].get('theme', 'dark')

    _tile_cache_progress = {'status': 'running', 'fetched': 0, 'total': 0, 'error': None}

    def _run():
        try:
            _cache_tiles_bg(lat, lon, radius_km, theme)
            _tile_cache_progress['status'] = 'done'
        except Exception as e:
            _tile_cache_progress['status'] = 'error'
            _tile_cache_progress['error'] = str(e)

    _tile_cache_thread = threading.Thread(target=_run, daemon=True, name='tile-cache')
    _tile_cache_thread.start()
    return jsonify({'status': 'started'})


@api_bp.route('/api/cache-tiles/status')
def tile_cache_status():
    return jsonify(_tile_cache_progress)


def _cache_tiles_bg(lat, lon, radius_km, theme, zoom_min=6, zoom_max=12):
    import math

    cdn = _TILE_CDN['dark' if theme == 'dark' else 'light']
    theme_key = 'dark' if theme == 'dark' else 'light'

    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * math.cos(math.radians(lat)))

    def _ll_to_tile(lat_, lon_, z):
        n = 2 ** z
        x_ = int((lon_ + 180) / 360 * n)
        lr = math.radians(lat_)
        y_ = int((1 - math.log(math.tan(lr) + 1 / math.cos(lr)) / math.pi) / 2 * n)
        return x_, y_

    # Count total tiles first
    total = 0
    for z in range(zoom_min, zoom_max + 1):
        x1, y2 = _ll_to_tile(lat - lat_delta, lon - lon_delta, z)
        x2, y1 = _ll_to_tile(lat + lat_delta, lon + lon_delta, z)
        n = 2 ** z
        total += (min(n, x2 + 1) - max(0, x1)) * (min(n, y2 + 1) - max(0, y1))

    _tile_cache_progress['total'] = total
    fetched = 0

    for z in range(zoom_min, zoom_max + 1):
        x1, y2 = _ll_to_tile(lat - lat_delta, lon - lon_delta, z)
        x2, y1 = _ll_to_tile(lat + lat_delta, lon + lon_delta, z)
        n = 2 ** z

        for x in range(max(0, x1), min(n, x2 + 1)):
            for y in range(max(0, y1), min(n, y2 + 1)):
                tile_dir = os.path.join(TILE_CACHE_DIR, theme_key, str(z), str(x))
                tile_path = os.path.join(tile_dir, f'{y}.png')

                if os.path.exists(tile_path):
                    fetched += 1
                    _tile_cache_progress['fetched'] = fetched
                    continue

                url = cdn.replace('{z}', str(z)).replace('{x}', str(x)).replace('{y}', str(y))
                try:
                    resp = req_lib.get(url, timeout=10,
                                       headers={'User-Agent': 'ADSB-Visual-Tracker/1.0'})
                    if resp.status_code == 200:
                        os.makedirs(tile_dir, exist_ok=True)
                        with open(tile_path, 'wb') as f:
                            f.write(resp.content)
                except Exception as e:
                    logger.warning("Cache tile failed z=%s x=%s y=%s: %s", z, x, y, e)

                fetched += 1
                _tile_cache_progress['fetched'] = fetched

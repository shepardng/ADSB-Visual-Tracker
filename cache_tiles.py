#!/usr/bin/env python3
"""
cache_tiles.py — Pre-cache map tiles for offline use.

Usage:
    python cache_tiles.py --lat 40.7128 --lon -74.0060 --radius 150
    python cache_tiles.py --from-config          # reads config.json automatically
    python cache_tiles.py --lat 51.5 --lon -0.12 --radius 100 --theme light
"""

import argparse
import json
import math
import os
import sys
import time

import requests

TILE_CACHE_DIR = os.path.join(os.path.expanduser('~'), '.adsb-tracker', 'tiles')

TILE_CDN = {
    'dark':  'https://a.basemaps.cartocdn.com/dark_all/{z}/{x}/{y}.png',
    'light': 'https://a.tile.openstreetmap.org/{z}/{x}/{y}.png',
}

HEADERS = {'User-Agent': 'ADSB-Visual-Tracker/1.0 (tile-cache)'}


def lat_lon_to_tile(lat, lon, zoom):
    """Convert WGS84 lat/lon to Slippy Map tile x, y."""
    n = 2 ** zoom
    x = int((lon + 180.0) / 360.0 * n)
    lat_r = math.radians(lat)
    y = int((1.0 - math.log(math.tan(lat_r) + 1.0 / math.cos(lat_r)) / math.pi) / 2.0 * n)
    return x, y


def enumerate_tiles(lat, lon, radius_km, zoom_min, zoom_max):
    """Yield (z, x, y) tuples for all tiles covering the area."""
    lat_delta = radius_km / 111.32
    lon_delta = radius_km / (111.32 * math.cos(math.radians(lat)))

    for z in range(zoom_min, zoom_max + 1):
        n = 2 ** z
        x1, y2 = lat_lon_to_tile(lat - lat_delta, lon - lon_delta, z)
        x2, y1 = lat_lon_to_tile(lat + lat_delta, lon + lon_delta, z)

        for x in range(max(0, x1), min(n, x2 + 1)):
            for y in range(max(0, y1), min(n, y2 + 1)):
                yield z, x, y


def cache_tiles(lat, lon, radius_km, zoom_min=6, zoom_max=12, theme='dark',
                delay=0.05):
    """Download and cache all tiles for the given area."""
    cdn = TILE_CDN[theme]
    theme_dir = os.path.join(TILE_CACHE_DIR, theme)

    tiles = list(enumerate_tiles(lat, lon, radius_km, zoom_min, zoom_max))
    total = len(tiles)
    fetched = 0
    skipped = 0
    failed = 0

    print(f"Area    : {lat:.4f}, {lon:.4f}  radius={radius_km} km")
    print(f"Zooms   : {zoom_min} – {zoom_max}")
    print(f"Theme   : {theme}")
    print(f"Tiles   : {total}")
    print(f"Cache   : {theme_dir}")
    print()

    for i, (z, x, y) in enumerate(tiles):
        tile_dir  = os.path.join(theme_dir, str(z), str(x))
        tile_path = os.path.join(tile_dir, f'{y}.png')

        if os.path.exists(tile_path):
            skipped += 1
            _progress(i + 1, total, fetched, skipped, failed)
            continue

        url = cdn.replace('{z}', str(z)).replace('{x}', str(x)).replace('{y}', str(y))
        try:
            resp = requests.get(url, timeout=10, headers=HEADERS)
            if resp.status_code == 200:
                os.makedirs(tile_dir, exist_ok=True)
                with open(tile_path, 'wb') as f:
                    f.write(resp.content)
                fetched += 1
            else:
                failed += 1
                print(f"\n  WARN: HTTP {resp.status_code} for z={z} x={x} y={y}", file=sys.stderr)
        except requests.RequestException as e:
            failed += 1
            print(f"\n  WARN: {e} for z={z} x={x} y={y}", file=sys.stderr)

        _progress(i + 1, total, fetched, skipped, failed)

        if delay > 0:
            time.sleep(delay)

    print()
    print(f"\nDone — fetched: {fetched}, skipped: {skipped}, failed: {failed}")


def _progress(done, total, fetched, skipped, failed):
    pct = int(done / total * 100)
    bar = '█' * (pct // 5) + '░' * (20 - pct // 5)
    print(f"\r  [{bar}] {pct:3d}%  {done}/{total}  "
          f"new:{fetched} cached:{skipped} err:{failed}", end='', flush=True)


def main():
    parser = argparse.ArgumentParser(
        description='Pre-cache ADS-B Tracker map tiles for offline use.'
    )
    parser.add_argument('--lat',         type=float, help='Center latitude')
    parser.add_argument('--lon',         type=float, help='Center longitude')
    parser.add_argument('--radius',      type=float, default=150,
                        help='Radius in km (default: 150)')
    parser.add_argument('--zoom-min',    type=int,   default=6)
    parser.add_argument('--zoom-max',    type=int,   default=12)
    parser.add_argument('--theme',       choices=['dark', 'light'], default='dark')
    parser.add_argument('--delay',       type=float, default=0.05,
                        help='Delay between tile requests in seconds (default: 0.05)')
    parser.add_argument('--from-config', action='store_true',
                        help='Read lat/lon/radius from config.json')

    args = parser.parse_args()

    if args.from_config:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        if not os.path.exists(config_path):
            print("ERROR: config.json not found. Run the app first or provide --lat/--lon.",
                  file=sys.stderr)
            sys.exit(1)
        with open(config_path) as f:
            cfg = json.load(f)
        lat       = cfg['location']['latitude']
        lon       = cfg['location']['longitude']
        radius_km = cfg['location']['radius_km']
        theme     = cfg['display'].get('theme', 'dark')
    else:
        if args.lat is None or args.lon is None:
            parser.error("Provide --lat and --lon, or use --from-config.")
        lat       = args.lat
        lon       = args.lon
        radius_km = args.radius
        theme     = args.theme

    cache_tiles(lat, lon, radius_km,
                zoom_min=args.zoom_min,
                zoom_max=args.zoom_max,
                theme=theme,
                delay=args.delay)


if __name__ == '__main__':
    main()

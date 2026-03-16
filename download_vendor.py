#!/usr/bin/env python3
"""
download_vendor.py — Download and cache frontend libraries (Leaflet, Socket.IO).

Called automatically by main.py on first run if vendor files are missing.
Can also be run manually:  python download_vendor.py
"""

import os
import sys
import urllib.request

VENDOR_DIR = os.path.join(os.path.dirname(__file__), 'app', 'web', 'static', 'vendor')

ASSETS = [
    {
        'url': 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.js',
        'dest': 'leaflet.js',
    },
    {
        'url': 'https://unpkg.com/leaflet@1.9.4/dist/leaflet.css',
        'dest': 'leaflet.css',
    },
    {
        'url': 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon.png',
        'dest': 'images/marker-icon.png',
    },
    {
        'url': 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-icon-2x.png',
        'dest': 'images/marker-icon-2x.png',
    },
    {
        'url': 'https://unpkg.com/leaflet@1.9.4/dist/images/marker-shadow.png',
        'dest': 'images/marker-shadow.png',
    },
    {
        'url': 'https://cdn.socket.io/4.7.2/socket.io.min.js',
        'dest': 'socket.io.min.js',
    },
]


def download_vendor(force=False):
    """Download all vendor assets. Skips files already present unless force=True."""
    os.makedirs(VENDOR_DIR, exist_ok=True)

    missing = [a for a in ASSETS
               if force or not os.path.exists(os.path.join(VENDOR_DIR, a['dest']))]

    if not missing:
        return True  # all present

    print(f"Downloading {len(missing)} vendor asset(s) to {VENDOR_DIR} …")

    headers = {'User-Agent': 'ADSB-Visual-Tracker/1.0 (vendor-download)'}
    failed = []

    for asset in missing:
        dest_path = os.path.join(VENDOR_DIR, asset['dest'])
        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        try:
            req = urllib.request.Request(asset['url'], headers=headers)
            with urllib.request.urlopen(req, timeout=15) as resp, \
                 open(dest_path, 'wb') as f:
                f.write(resp.read())
            print(f"  ✓  {asset['dest']}")
        except Exception as e:
            print(f"  ✗  {asset['dest']}  ({e})", file=sys.stderr)
            failed.append(asset['dest'])

    if failed:
        print(
            f"\nWARN: {len(failed)} asset(s) failed to download.\n"
            "The app will try CDN fallbacks in the browser.\n"
            "Re-run once internet is available: python download_vendor.py",
            file=sys.stderr,
        )
        return False

    print("Vendor assets ready.")
    return True


if __name__ == '__main__':
    import argparse
    parser = argparse.ArgumentParser(description='Download frontend vendor assets.')
    parser.add_argument('--force', action='store_true', help='Re-download even if present')
    args = parser.parse_args()
    ok = download_vendor(force=args.force)
    sys.exit(0 if ok else 1)

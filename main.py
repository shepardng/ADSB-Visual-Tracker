#!/usr/bin/env python3
"""
ADS-B Visual Tracker — Entry Point
Runs on Raspberry Pi 3B with eventlet async worker.
"""

import eventlet
eventlet.monkey_patch()

import logging
import os

from app import create_app, socketio
from app.adsb import data_manager
from app.config_manager import load_config
from download_vendor import download_vendor

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s [%(name)s] %(levelname)s: %(message)s',
)
logger = logging.getLogger(__name__)


def main():
    download_vendor()   # no-op if files already present; downloads on first run
    load_config()

    app = create_app()

    data_manager.init(socketio)
    data_manager.start()

    host = os.environ.get('ADSB_HOST', '0.0.0.0')
    port = int(os.environ.get('ADSB_PORT', 5000))

    logger.info("Starting ADS-B Visual Tracker on http://%s:%s", host, port)
    logger.info("Open a browser and navigate to http://localhost:%s", port)

    socketio.run(app, host=host, port=port, debug=False, use_reloader=False)


if __name__ == '__main__':
    main()

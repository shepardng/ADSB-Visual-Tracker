import time
import logging

from .. import socketio
from ..adsb.aircraft_store import store
from ..config_manager import get_config
from ..adsb import data_manager

logger = logging.getLogger(__name__)


def register_events():

    @socketio.on('connect')
    def on_connect():
        logger.debug("Client connected")
        cfg = get_config()
        aircraft = store.get_filtered(cfg)
        socketio.emit('aircraft_update', {
            'aircraft': aircraft,
            'timestamp': time.time(),
            'count': len(aircraft),
        })
        socketio.emit('status_update', data_manager.get_status())

    @socketio.on('disconnect')
    def on_disconnect():
        logger.debug("Client disconnected")

    @socketio.on('request_update')
    def on_request_update():
        cfg = get_config()
        aircraft = store.get_filtered(cfg)
        socketio.emit('aircraft_update', {
            'aircraft': aircraft,
            'timestamp': time.time(),
            'count': len(aircraft),
        })

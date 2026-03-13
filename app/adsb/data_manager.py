import time
import threading
import logging

from .aircraft_store import store
from . import dump1090_client, opensky_client
from ..config_manager import get_config, get_bounding_box

logger = logging.getLogger(__name__)

_thread = None
_stop_event = threading.Event()
_socketio = None
_last_push_time = 0
_last_update_time = 0
_last_error = None
_MIN_PUSH_INTERVAL = 1.0  # max one WebSocket push per second


def init(socketio_instance):
    global _socketio
    _socketio = socketio_instance


def start():
    global _thread, _stop_event
    _stop_event.clear()
    _thread = threading.Thread(target=_run_loop, daemon=True, name='data-manager')
    _thread.start()
    logger.info("Data manager started")


def stop():
    _stop_event.set()


def get_status():
    cfg = get_config()
    return {
        'source': cfg['data_source']['type'],
        'aircraft_count': store.count(),
        'last_update': _last_update_time,
        'error': _last_error,
    }


def _run_loop():
    global _last_push_time, _last_update_time, _last_error

    while not _stop_event.is_set():
        cfg = get_config()
        interval = cfg['data_source'].get('poll_interval_seconds', 10)

        try:
            aircraft_list = _fetch(cfg)

            if aircraft_list is not None:
                trail_length = cfg['display'].get('trail_length', 10)
                for ac in aircraft_list:
                    icao = ac.get('icao')
                    if icao:
                        store.update(icao, ac, trail_length=trail_length)

                store.expire_stale(timeout_sec=60)
                _last_update_time = time.time()
                _last_error = None

                # Throttle WebSocket pushes to at most once per second
                now = time.time()
                if _socketio and (now - _last_push_time) >= _MIN_PUSH_INTERVAL:
                    filtered = store.get_filtered(cfg)
                    _socketio.emit('aircraft_update', {
                        'aircraft': filtered,
                        'timestamp': now,
                        'count': len(filtered),
                    })
                    _socketio.emit('status_update', get_status())
                    _last_push_time = now

        except Exception as e:
            _last_error = str(e)
            logger.error("Data manager error: %s", e, exc_info=True)

        _stop_event.wait(timeout=interval)


def _fetch(cfg):
    source_type = cfg['data_source']['type']

    if source_type == 'dump1090':
        host = cfg['data_source'].get('dump1090_host', 'localhost')
        port = cfg['data_source'].get('dump1090_port', 8080)
        return dump1090_client.fetch_aircraft(host, port)

    elif source_type == 'opensky':
        bbox = get_bounding_box()
        username = cfg['data_source'].get('opensky_username', '')
        password = cfg['data_source'].get('opensky_password', '')
        return opensky_client.fetch_aircraft(*bbox, username=username, password=password)

    else:
        logger.warning("Unknown data source type: %s", source_type)
        return None

import time
import math
from threading import Lock


class AircraftStore:
    """Thread-safe in-memory store for live aircraft state."""

    def __init__(self):
        self._lock = Lock()
        self._aircraft = {}  # icao -> dict

    def update(self, icao, fields, trail_length=10):
        """Upsert aircraft state and append position to trail."""
        with self._lock:
            if icao not in self._aircraft:
                self._aircraft[icao] = {'icao': icao, 'trail': []}

            ac = self._aircraft[icao]
            ac.update(fields)
            ac['last_seen'] = time.time()

            if 'latitude' in fields and 'longitude' in fields:
                lat = fields['latitude']
                lon = fields['longitude']
                if lat is not None and lon is not None:
                    trail = ac.get('trail', [])
                    if not trail or trail[-1] != [lat, lon]:
                        trail.append([lat, lon])
                        ac['trail'] = trail[-trail_length:]

    def expire_stale(self, timeout_sec=60):
        """Remove aircraft not updated within timeout. Returns list of removed ICAOs."""
        cutoff = time.time() - timeout_sec
        with self._lock:
            stale = [
                icao for icao, ac in self._aircraft.items()
                if ac.get('last_seen', 0) < cutoff
            ]
            for icao in stale:
                del self._aircraft[icao]
        return stale

    def get_all(self):
        with self._lock:
            return list(self._aircraft.values())

    def get_filtered(self, config):
        """Return aircraft within configured area and altitude/filter constraints."""
        all_ac = self.get_all()
        loc = config['location']
        flt = config['filters']

        center_lat = loc['latitude']
        center_lon = loc['longitude']
        radius_km = loc['radius_km']
        min_alt = flt.get('min_altitude_ft', 0)
        max_alt = flt.get('max_altitude_ft', 60000)
        show_ground = flt.get('show_ground_vehicles', False)

        result = []
        for ac in all_ac:
            lat = ac.get('latitude')
            lon = ac.get('longitude')
            if lat is None or lon is None:
                continue

            if _haversine_km(center_lat, center_lon, lat, lon) > radius_km:
                continue

            alt = ac.get('altitude_ft')
            if alt is not None:
                if not show_ground and alt == 0:
                    continue
                if alt < min_alt or alt > max_alt:
                    continue

            result.append(dict(ac))

        return result

    def count(self):
        with self._lock:
            return len(self._aircraft)


def _haversine_km(lat1, lon1, lat2, lon2):
    R = 6371.0
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (math.sin(dlat / 2) ** 2
         + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2)
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Module-level singleton used by the rest of the application
store = AircraftStore()

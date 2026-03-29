"""
collectors/opensky.py — OpenSky Network collector for military flight data.
"""

import requests

from config import OPENSKY_URL
from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10


class OpenSkyCollector:
    """
    Fetches live flight state vectors from the OpenSky Network and
    filters for military-pattern callsigns or aircraft near conflict zones.
    """

    MILITARY_PREFIXES = ("RCH", "DUKE", "REACH", "JAKE", "TOPCAT")

    # Rough bounding boxes for known conflict zones (min_lat, max_lat, min_lon, max_lon)
    CONFLICT_BOXES = [
        (44.0, 52.5, 22.0, 40.0),   # Ukraine
        (32.0, 38.0, 35.0, 42.5),   # Syria/Iraq
        (29.0, 38.0, 44.0, 56.0),   # Iran
        (38.0, 43.0, 44.0, 50.0),   # Azerbaijan/Armenia
    ]

    def _is_military(self, callsign: str) -> bool:
        return any(callsign.startswith(p) for p in self.MILITARY_PREFIXES)

    def _near_conflict(self, lat: float, lon: float) -> bool:
        for (min_lat, max_lat, min_lon, max_lon) in self.CONFLICT_BOXES:
            if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
                return True
        return False

    def fetch(self) -> list[list]:
        """
        Return filtered state vectors from OpenSky.

        Each state vector is a list:
        [icao24, callsign, country, ts_pos, ts_last, lon, lat, baro_alt,
         on_ground, velocity, true_track, vert_rate, sensors, geo_alt,
         squawk, spi, position_source]

        Returns:
            Filtered list of state vectors, or [] on failure.
        """
        try:
            resp = requests.get(OPENSKY_URL, timeout=_TIMEOUT)
            resp.raise_for_status()
            states = resp.json().get("states", []) or []
            filtered = []
            for sv in states:
                callsign = (sv[1] or "").strip()
                lat = sv[6]
                lon = sv[5]
                if lat is None or lon is None:
                    continue
                if self._is_military(callsign) or self._near_conflict(lat, lon):
                    filtered.append(sv)
            return filtered
        except Exception as exc:
            logger.warning(f"OpenSky fetch failed: {exc}")
            return []

"""
collectors/usgs_collector.py — Fetches significant earthquake data from USGS.

Uses the USGS Earthquake Hazards Program GeoJSON feed; no API key required.
"""

import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10
_ENDPOINT = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"
_MIN_MAGNITUDE = 4.5


class USGSCollector:
    """Fetches significant earthquake events from the USGS GeoJSON feed."""

    def fetch(self) -> list[dict]:
        """
        Retrieve earthquake records from the USGS significant-week feed.

        Filters to events with magnitude >= 4.5.

        Returns:
            List of dicts with keys: magnitude, place, lat, lon, time, depth.
            Returns [] on failure.
        """
        try:
            resp = requests.get(_ENDPOINT, timeout=_TIMEOUT)
            resp.raise_for_status()
            features = resp.json().get("features", [])
            results = []
            for feat in features:
                props = feat.get("properties", {})
                mag = props.get("mag")
                if mag is None or mag < _MIN_MAGNITUDE:
                    continue
                coords = feat.get("geometry", {}).get("coordinates", [None, None, None])
                lon = coords[0]
                lat = coords[1]
                depth = coords[2]
                results.append({
                    "magnitude": float(mag),
                    "place": props.get("place") or "Unknown",
                    "lat": float(lat) if lat is not None else 0.0,
                    "lon": float(lon) if lon is not None else 0.0,
                    "time": props.get("time") or 0,
                    "depth": float(depth) if depth is not None else 0.0,
                })
            logger.info(f"USGS: fetched {len(results)} earthquakes (mag >= {_MIN_MAGNITUDE}).")
            return results
        except Exception as exc:
            logger.warning(f"USGS fetch failed: {exc}")
            return []


if __name__ == "__main__":
    collector = USGSCollector()
    data = collector.fetch()
    print(f"USGS returned {len(data)} records.")
    for eq in data[:3]:
        print(eq)

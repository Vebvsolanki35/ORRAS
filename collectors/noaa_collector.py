"""
collectors/noaa_collector.py — Fetches active severe weather alerts from NOAA.

Uses the weather.gov alerts API; no API key required.
"""

import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10
_ENDPOINT = "https://api.weather.gov/alerts/active"


class NOAACollector:
    """Fetches active Extreme/Severe weather alerts from NOAA weather.gov."""

    def fetch(self) -> list[dict]:
        """
        Retrieve active weather alerts filtered to Extreme and Severe severity.

        Returns:
            List of dicts with keys: event, areaDesc, severity, description, onset.
            Returns [] on failure.
        """
        try:
            resp = requests.get(
                _ENDPOINT,
                params={"status": "actual", "severity": "Extreme,Severe"},
                headers={"Accept": "application/geo+json"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            features = resp.json().get("features", [])
            results = []
            for feat in features:
                props = feat.get("properties", {})
                results.append({
                    "event": props.get("event") or "Unknown",
                    "areaDesc": props.get("areaDesc") or "Unknown",
                    "severity": props.get("severity") or "Unknown",
                    "description": (props.get("description") or "")[:500],
                    "onset": props.get("onset") or props.get("effective") or "",
                })
            logger.info(f"NOAA: fetched {len(results)} active alerts.")
            return results
        except Exception as exc:
            logger.warning(f"NOAA fetch failed: {exc}")
            return []


if __name__ == "__main__":
    collector = NOAACollector()
    data = collector.fetch()
    print(f"NOAA returned {len(data)} records.")
    for alert in data[:3]:
        print(alert)

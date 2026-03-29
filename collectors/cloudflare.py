"""
collectors/cloudflare.py — Cloudflare Radar collector for traffic anomaly data.
"""

import requests

from config import CLOUDFLARE_RADAR_URL
from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10


class CloudflareRadarCollector:
    """Fetches traffic anomaly location data from Cloudflare Radar (no key required)."""

    def fetch(self) -> list[dict]:
        """
        Return anomaly location records from Cloudflare Radar.

        Returns:
            List of anomaly dicts, or [] on failure.
        """
        try:
            resp = requests.get(
                CLOUDFLARE_RADAR_URL,
                params={"format": "json"},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            result = resp.json()
            return result.get("result", {}).get("locations", [])
        except Exception as exc:
            logger.warning(f"Cloudflare Radar fetch failed: {exc}")
            return []

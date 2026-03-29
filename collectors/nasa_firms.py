"""
collectors/nasa_firms.py — NASA FIRMS collector for active fire hotspot data.
"""

import csv
import io

import requests

from config import NASA_FIRMS_KEY, NASA_FIRMS_URL
from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10


class NASAFIRMSCollector:
    """Fetches active fire hotspot data from NASA FIRMS (CSV format)."""

    # World bounding box: lat_min, lat_max, lon_min, lon_max
    BBOX = "-180,-90,180,90"

    def fetch(self) -> list[dict]:
        """
        Retrieve fire hotspot records from NASA FIRMS.

        Returns:
            List of fire-hotspot dicts, or [] on failure.
        """
        if not NASA_FIRMS_KEY:
            logger.warning("NASA FIRMS: NASA_FIRMS_KEY not set — skipping live fetch.")
            return []
        try:
            url = f"{NASA_FIRMS_URL}{NASA_FIRMS_KEY}/VIIRS_SNPP_NRT/world/1"
            resp = requests.get(url, timeout=_TIMEOUT)
            resp.raise_for_status()
            reader = csv.DictReader(io.StringIO(resp.text))
            rows = list(reader)
            return rows
        except Exception as exc:
            logger.warning(f"NASA FIRMS fetch failed: {exc}")
            return []

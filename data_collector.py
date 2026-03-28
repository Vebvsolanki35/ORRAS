"""
data_collector.py — Live data collection from all data sources.

Each source has a dedicated collector class. A DataCollectionOrchestrator
ties them together and automatically falls back to mock data when a live
source is unavailable or OFFLINE_MODE is enabled.
"""

import csv
import io
from typing import Any

import requests

from config import (
    CLOUDFLARE_RADAR_URL,
    GDELT_URL,
    NASA_FIRMS_KEY,
    NASA_FIRMS_URL,
    NEWSAPI_KEY,
    NEWSAPI_URL,
    OFFLINE_MODE,
    OPENSKY_URL,
)
from mock_data_generator import (
    generate_firms_signals,
    generate_gdelt_signals,
    generate_netblocks_signals,
    generate_news_signals,
    generate_opensky_signals,
    generate_social_signals,
)
from collectors import (
    USGSCollector,
    NOAACollector,
    ReliefWebCollector,
    WHOCollector,
    ACLEDCollector,
)
from utils import get_logger

logger = get_logger(__name__)

# Request timeout for all HTTP calls (seconds)
_TIMEOUT = 10


# ---------------------------------------------------------------------------
# Individual collector classes
# ---------------------------------------------------------------------------

class NewsAPICollector:
    """Fetches conflict/security news articles from the NewsAPI service."""

    QUERY = (
        "attack OR missile OR airstrike OR troops OR protest OR riot "
        "OR bombing OR mobilization OR ceasefire"
    )

    def fetch(self) -> list[dict]:
        """
        Retrieve raw article records from NewsAPI.

        Returns:
            List of article dicts, or [] on failure.
        """
        if not NEWSAPI_KEY:
            logger.warning("NewsAPI: NEWSAPI_KEY not set — skipping live fetch.")
            return []
        try:
            resp = requests.get(
                NEWSAPI_URL,
                headers={"X-Api-Key": NEWSAPI_KEY},
                params={
                    "q": self.QUERY,
                    "language": "en",
                    "sortBy": "publishedAt",
                    "pageSize": 25,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as exc:
            logger.warning(f"NewsAPI fetch failed: {exc}")
            return []


class GDELTCollector:
    """Fetches recent conflict-related documents from the GDELT API (no key needed)."""

    QUERY = "troops OR airstrike OR bombing OR missile OR protest OR riot"

    def fetch(self) -> list[dict]:
        """
        Retrieve article list from GDELT Doc 2.0 API.

        Returns:
            List of article dicts, or [] on failure.
        """
        try:
            resp = requests.get(
                GDELT_URL,
                params={
                    "query": self.QUERY,
                    "mode": "artlist",
                    "format": "json",
                    "maxrecords": 25,
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            return resp.json().get("articles", [])
        except Exception as exc:
            logger.warning(f"GDELT fetch failed: {exc}")
            return []


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


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DataCollectionOrchestrator:
    """
    Coordinates all data collectors.

    For each source, runs the live collector and falls back to mock data
    if the live fetch returns an empty list or OFFLINE_MODE is active.
    """

    def __init__(self) -> None:
        self.newsapi = NewsAPICollector()
        self.gdelt = GDELTCollector()
        self.opensky = OpenSkyCollector()
        self.firms = NASAFIRMSCollector()
        self.cloudflare = CloudflareRadarCollector()
        self.usgs = USGSCollector()
        self.noaa = NOAACollector()
        self.reliefweb = ReliefWebCollector()
        self.who = WHOCollector()
        self.acled = ACLEDCollector()

        # Tracks health status per source: LIVE / MOCK / FAILED / OFFLINE
        self.source_health: dict[str, str] = {
            "NewsAPI": "UNKNOWN",
            "GDELT": "UNKNOWN",
            "OpenSky": "UNKNOWN",
            "NASA FIRMS": "UNKNOWN",
            "NetBlocks": "UNKNOWN",
            "Cloudflare Radar": "UNKNOWN",
            "USGS": "UNKNOWN",
            "NOAA": "UNKNOWN",
            "ReliefWeb": "UNKNOWN",
            "WHO": "UNKNOWN",
            "ACLED": "UNKNOWN",
            "Social/Mock": "UNKNOWN",
        }

    def _collect_source(
        self,
        name: str,
        live_fn,
        mock_fn,
        mock_kwargs: dict | None = None,
    ) -> tuple[str, list]:
        """
        Run a live fetch; fall back to mock on empty result or offline mode.

        Args:
            name: Human-readable source name for logging.
            live_fn: Callable that returns live data.
            mock_fn: Callable that returns mock data.
            mock_kwargs: Optional kwargs for mock_fn.

        Returns:
            Tuple of (status_label, data_list).
        """
        if OFFLINE_MODE:
            data = (mock_fn(**(mock_kwargs or {})))
            logger.info(f"{name}: MOCK (OFFLINE_MODE active) — {len(data)} records")
            return "MOCK", data

        live_data = live_fn()
        if live_data:
            logger.info(f"{name}: LIVE — {len(live_data)} records")
            return "LIVE", live_data

        mock_data = (mock_fn(**(mock_kwargs or {})))
        logger.warning(f"{name}: MOCK (live fetch returned empty) — {len(mock_data)} records")
        return "MOCK", mock_data

    def collect_all(self) -> dict[str, Any]:
        """
        Run all collectors and return raw data keyed by source name.

        Returns:
            Dict with keys: newsapi, gdelt, opensky, firms, netblocks,
            cloudflare, usgs, noaa, reliefweb, who, acled, social.
            Each value is a list of raw records.
        """
        results: dict[str, Any] = {}

        # NewsAPI
        status, data = self._collect_source(
            "NewsAPI", self.newsapi.fetch, generate_news_signals, {"n": 15}
        )
        results["newsapi"] = data
        self.source_health["NewsAPI"] = status

        # GDELT
        status, data = self._collect_source(
            "GDELT", self.gdelt.fetch, generate_gdelt_signals, {"n": 10}
        )
        results["gdelt"] = data
        self.source_health["GDELT"] = status

        # OpenSky
        status, data = self._collect_source(
            "OpenSky", self.opensky.fetch, generate_opensky_signals, {"n": 8}
        )
        results["opensky"] = data
        self.source_health["OpenSky"] = status

        # NASA FIRMS
        status, data = self._collect_source(
            "NASA FIRMS", self.firms.fetch, generate_firms_signals, {"n": 6}
        )
        results["firms"] = data
        self.source_health["NASA FIRMS"] = status

        # Cloudflare Radar
        status, data = self._collect_source(
            "Cloudflare Radar", self.cloudflare.fetch, lambda: [], {}
        )
        if not data:
            data = []  # Cloudflare has no mock; empty is acceptable
        results["cloudflare"] = data
        self.source_health["Cloudflare Radar"] = status if data else "OFFLINE"

        # Social (always mock — no live source)
        social_data = generate_social_signals(n=10)
        results["social"] = social_data
        self.source_health["Social/Mock"] = "MOCK"
        logger.info(f"Social/Mock: MOCK — {len(social_data)} records")

        # NetBlocks (always mock — API requires paid access)
        netblocks_data = generate_netblocks_signals(n=5)
        results["netblocks"] = netblocks_data
        self.source_health["NetBlocks"] = "MOCK"
        logger.info(f"NetBlocks: MOCK — {len(netblocks_data)} records")

        # USGS Earthquakes
        status, data = self._collect_source(
            "USGS", self.usgs.fetch, lambda: [], {}
        )
        results["usgs"] = data
        self.source_health["USGS"] = status if data else "MOCK"

        # NOAA Weather Alerts
        status, data = self._collect_source(
            "NOAA", self.noaa.fetch, lambda: [], {}
        )
        results["noaa"] = data
        self.source_health["NOAA"] = status if data else "MOCK"

        # ReliefWeb Disasters
        status, data = self._collect_source(
            "ReliefWeb", self.reliefweb.fetch, lambda: [], {}
        )
        results["reliefweb"] = data
        self.source_health["ReliefWeb"] = status if data else "MOCK"

        # WHO Outbreaks (always mock)
        who_data = self.who.get_outbreaks()
        results["who"] = who_data
        self.source_health["WHO"] = "MOCK"
        logger.info(f"WHO: MOCK — {len(who_data)} records")

        # ACLED Conflict Events
        status, data = self._collect_source(
            "ACLED", self.acled.fetch, lambda: [], {}
        )
        results["acled"] = data
        self.source_health["ACLED"] = status if data else "MOCK"

        return results

    def get_source_health_report(self) -> dict[str, str]:
        """
        Return a dict mapping each source name to its collection status.

        Returns:
            Dict of {source_name: status_string} where status is one of
            LIVE, MOCK, FAILED, OFFLINE, or UNKNOWN.
        """
        return dict(self.source_health)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== data_collector.py self-test ===\n")
    orchestrator = DataCollectionOrchestrator()
    raw = orchestrator.collect_all()

    health = orchestrator.get_source_health_report()
    print("Source health report:")
    for src, status in health.items():
        badge = "🟢 LIVE" if status == "LIVE" else "🔴 MOCK/OFFLINE"
        count = len(raw.get(src.lower().replace(" ", "").replace("/", ""), []))
        print(f"  {src:20s}: {badge} ({status}) — {count} records")

    print("\nRecord counts per source key:")
    for key, records in raw.items():
        print(f"  {key:15s}: {len(records)}")

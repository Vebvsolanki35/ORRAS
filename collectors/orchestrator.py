"""
collectors/orchestrator.py — DataCollectionOrchestrator that coordinates all collectors.
"""

from typing import Any

from config import OFFLINE_MODE
from mock_data_generator import (
    generate_firms_signals,
    generate_gdelt_signals,
    generate_netblocks_signals,
    generate_news_signals,
    generate_opensky_signals,
    generate_social_signals,
)
from utils import get_logger

from collectors.cloudflare import CloudflareRadarCollector
from collectors.gdelt import GDELTCollector
from collectors.nasa_firms import NASAFIRMSCollector
from collectors.newsapi import NewsAPICollector
from collectors.opensky import OpenSkyCollector

logger = get_logger(__name__)


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
            Dict with keys: newsapi, gdelt, opensky, firms, cloudflare, social.
            Each value is a list of raw records.
        """
        results: dict[str, Any] = {}
        status_map: dict[str, str] = {}

        # NewsAPI
        status, data = self._collect_source(
            "NewsAPI", self.newsapi.fetch, generate_news_signals, {"n": 15}
        )
        results["newsapi"] = data
        status_map["NewsAPI"] = status

        # GDELT
        status, data = self._collect_source(
            "GDELT", self.gdelt.fetch, generate_gdelt_signals, {"n": 10}
        )
        results["gdelt"] = data
        status_map["GDELT"] = status

        # OpenSky
        status, data = self._collect_source(
            "OpenSky", self.opensky.fetch, generate_opensky_signals, {"n": 8}
        )
        results["opensky"] = data
        status_map["OpenSky"] = status

        # NASA FIRMS
        status, data = self._collect_source(
            "NASA FIRMS", self.firms.fetch, generate_firms_signals, {"n": 6}
        )
        results["firms"] = data
        status_map["NASA FIRMS"] = status

        # Cloudflare Radar
        status, data = self._collect_source(
            "Cloudflare Radar", self.cloudflare.fetch, lambda: [], {}
        )
        if not data:
            data = []  # Cloudflare has no mock; empty is acceptable
        results["cloudflare"] = data
        status_map["Cloudflare Radar"] = status if data else "OFFLINE"

        # Social (always mock — no live source)
        social_data = generate_social_signals(n=10)
        results["social"] = social_data
        status_map["Social/Mock"] = "MOCK"
        logger.info(f"Social/Mock: MOCK — {len(social_data)} records")

        # NetBlocks (always mock — API requires paid access)
        netblocks_data = generate_netblocks_signals(n=5)
        results["netblocks"] = netblocks_data
        status_map["NetBlocks"] = "MOCK"
        logger.info(f"NetBlocks: MOCK — {len(netblocks_data)} records")

        results["_status"] = status_map
        return results

"""
collectors/gdelt.py — GDELT collector for conflict-related documents.
"""

import requests

from config import GDELT_URL
from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10


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

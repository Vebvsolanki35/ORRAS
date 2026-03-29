"""
collectors/newsapi.py — NewsAPI collector for conflict/security news articles.
"""

import requests

from config import NEWSAPI_KEY, NEWSAPI_URL
from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10


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

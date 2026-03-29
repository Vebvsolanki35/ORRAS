"""
collectors/reliefweb_collector.py — Fetches disaster records from ReliefWeb API.

No API key required.
"""

import requests

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10
_ENDPOINT = "https://api.reliefweb.int/v1/disasters"


class ReliefWebCollector:
    """Fetches recent disaster records from the ReliefWeb API."""

    def fetch(self) -> list[dict]:
        """
        Retrieve recent disaster records from ReliefWeb.

        Returns:
            List of dicts with keys: name, date, type, country, status.
            Returns [] on failure.
        """
        try:
            resp = requests.get(
                _ENDPOINT,
                params={"appname": "orras", "profile": "list", "limit": 20},
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            records = resp.json().get("data", [])
            results = []
            for rec in records:
                fields = rec.get("fields", {})
                # Country may be a list of dicts
                country_raw = fields.get("country", [])
                if isinstance(country_raw, list) and country_raw:
                    country = country_raw[0].get("name", "Unknown")
                elif isinstance(country_raw, dict):
                    country = country_raw.get("name", "Unknown")
                else:
                    country = str(country_raw) if country_raw else "Unknown"

                # Type may be a list of dicts or a single string
                type_raw = fields.get("type", [])
                if isinstance(type_raw, list) and type_raw:
                    disaster_type = type_raw[0].get("name", "Unknown")
                elif isinstance(type_raw, dict):
                    disaster_type = type_raw.get("name", "Unknown")
                else:
                    disaster_type = str(type_raw) if type_raw else "Unknown"

                date_raw = fields.get("date", {})
                date_str = (
                    date_raw.get("created") or date_raw.get("event") or ""
                    if isinstance(date_raw, dict)
                    else str(date_raw)
                )

                results.append({
                    "name": fields.get("name") or rec.get("id", "Unknown"),
                    "date": date_str,
                    "type": disaster_type,
                    "country": country,
                    "status": fields.get("status") or "unknown",
                })
            logger.info(f"ReliefWeb: fetched {len(results)} disaster records.")
            return results
        except Exception as exc:
            logger.warning(f"ReliefWeb fetch failed: {exc}")
            return []


if __name__ == "__main__":
    collector = ReliefWebCollector()
    data = collector.fetch()
    print(f"ReliefWeb returned {len(data)} records.")
    for rec in data[:3]:
        print(rec)

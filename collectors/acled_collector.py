"""
collectors/acled_collector.py — Fetches armed conflict event data from ACLED.

Falls back to realistic mock data when the ACLED_KEY env variable is not set.
"""

import os
import requests

import sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_logger

logger = get_logger(__name__)

_TIMEOUT = 10
_ENDPOINT = "https://api.acleddata.com/acled/read"

# ---------------------------------------------------------------------------
# Static mock conflict data — 15 events across known conflict zones
# ---------------------------------------------------------------------------

_MOCK_EVENTS = [
    {
        "event_type": "Battle",
        "actor1": "Ukrainian Armed Forces",
        "actor2": "Russian Armed Forces",
        "country": "Ukraine",
        "location": "Bakhmut",
        "fatalities": 14,
        "event_date": "2025-01-08",
        "latitude": 48.5953,
        "longitude": 38.0030,
    },
    {
        "event_type": "Explosion/Remote violence",
        "actor1": "Russian Armed Forces",
        "actor2": "Civilians",
        "country": "Ukraine",
        "location": "Kharkiv",
        "fatalities": 6,
        "event_date": "2025-01-09",
        "latitude": 49.9935,
        "longitude": 36.2304,
    },
    {
        "event_type": "Violence against civilians",
        "actor1": "Janjaweed Militia",
        "actor2": "Civilians",
        "country": "Sudan",
        "location": "El Fasher",
        "fatalities": 22,
        "event_date": "2025-01-07",
        "latitude": 13.6286,
        "longitude": 25.3503,
    },
    {
        "event_type": "Battle",
        "actor1": "Sudanese Armed Forces",
        "actor2": "Rapid Support Forces",
        "country": "Sudan",
        "location": "Omdurman",
        "fatalities": 31,
        "event_date": "2025-01-06",
        "latitude": 15.6445,
        "longitude": 32.4777,
    },
    {
        "event_type": "Explosion/Remote violence",
        "actor1": "Houthi Forces",
        "actor2": "Saudi-led Coalition",
        "country": "Yemen",
        "location": "Sanaa",
        "fatalities": 8,
        "event_date": "2025-01-10",
        "latitude": 15.3694,
        "longitude": 44.1910,
    },
    {
        "event_type": "Battle",
        "actor1": "Islamic State",
        "actor2": "Syrian Democratic Forces",
        "country": "Syria",
        "location": "Deir ez-Zor",
        "fatalities": 17,
        "event_date": "2025-01-05",
        "latitude": 35.3357,
        "longitude": 40.1408,
    },
    {
        "event_type": "Violence against civilians",
        "actor1": "Al-Shabaab",
        "actor2": "Civilians",
        "country": "Somalia",
        "location": "Mogadishu",
        "fatalities": 9,
        "event_date": "2025-01-09",
        "latitude": 2.0469,
        "longitude": 45.3182,
    },
    {
        "event_type": "Protests",
        "actor1": "Opposition Protesters",
        "actor2": "Police Forces",
        "country": "Myanmar",
        "location": "Mandalay",
        "fatalities": 3,
        "event_date": "2025-01-08",
        "latitude": 21.9588,
        "longitude": 96.0891,
    },
    {
        "event_type": "Battle",
        "actor1": "Arakan Army",
        "actor2": "Myanmar Armed Forces",
        "country": "Myanmar",
        "location": "Rakhine State",
        "fatalities": 25,
        "event_date": "2025-01-07",
        "latitude": 20.0881,
        "longitude": 93.0625,
    },
    {
        "event_type": "Strategic developments",
        "actor1": "Israeli Defense Forces",
        "actor2": "Hamas",
        "country": "Israel",
        "location": "Gaza",
        "fatalities": 0,
        "event_date": "2025-01-10",
        "latitude": 31.3547,
        "longitude": 34.3088,
    },
    {
        "event_type": "Explosion/Remote violence",
        "actor1": "Israeli Defense Forces",
        "actor2": "Civilians",
        "country": "Palestine",
        "location": "Gaza City",
        "fatalities": 34,
        "event_date": "2025-01-10",
        "latitude": 31.5017,
        "longitude": 34.4668,
    },
    {
        "event_type": "Battle",
        "actor1": "FARC Dissidents",
        "actor2": "Colombian Armed Forces",
        "country": "Colombia",
        "location": "Caquetá",
        "fatalities": 7,
        "event_date": "2025-01-06",
        "latitude": 1.0000,
        "longitude": -74.0000,
    },
    {
        "event_type": "Violence against civilians",
        "actor1": "Boko Haram",
        "actor2": "Civilians",
        "country": "Nigeria",
        "location": "Maiduguri",
        "fatalities": 19,
        "event_date": "2025-01-08",
        "latitude": 11.8469,
        "longitude": 13.1571,
    },
    {
        "event_type": "Protests",
        "actor1": "Anti-Government Protesters",
        "actor2": "Security Forces",
        "country": "Iran",
        "location": "Tehran",
        "fatalities": 2,
        "event_date": "2025-01-09",
        "latitude": 35.6892,
        "longitude": 51.3890,
    },
    {
        "event_type": "Strategic developments",
        "actor1": "Russian Armed Forces",
        "actor2": "NATO Forces",
        "country": "Belarus",
        "location": "Minsk",
        "fatalities": 0,
        "event_date": "2025-01-07",
        "latitude": 53.9045,
        "longitude": 27.5615,
    },
]


class ACLEDCollector:
    """Fetches armed conflict event data from ACLED, or returns mock data."""

    def fetch(self) -> list[dict]:
        """
        Retrieve conflict events from ACLED API.

        Falls back to realistic mock data if ACLED_KEY is not set.

        Returns:
            List of dicts with keys: event_type, actor1, actor2, country,
            location, fatalities, event_date, latitude, longitude.
        """
        acled_key = os.getenv("ACLED_KEY", "")
        acled_email = os.getenv("ACLED_EMAIL", "")

        if not acled_key or not acled_email:
            logger.warning("ACLED: ACLED_KEY or ACLED_EMAIL not set — returning mock data.")
            return list(_MOCK_EVENTS)

        try:
            resp = requests.get(
                _ENDPOINT,
                params={
                    "key": acled_key,
                    "email": acled_email,
                    "limit": 50,
                    "format": "json",
                },
                timeout=_TIMEOUT,
            )
            resp.raise_for_status()
            raw = resp.json().get("data", [])
            results = []
            for rec in raw:
                results.append({
                    "event_type": rec.get("event_type") or "Unknown",
                    "actor1": rec.get("actor1") or "Unknown",
                    "actor2": rec.get("actor2") or "Unknown",
                    "country": rec.get("country") or "Unknown",
                    "location": rec.get("location") or "Unknown",
                    "fatalities": int(rec.get("fatalities") or 0),
                    "event_date": rec.get("event_date") or "",
                    "latitude": float(rec.get("latitude") or 0.0),
                    "longitude": float(rec.get("longitude") or 0.0),
                })
            logger.info(f"ACLED: fetched {len(results)} conflict events.")
            return results
        except Exception as exc:
            logger.warning(f"ACLED fetch failed: {exc} — returning mock data.")
            return list(_MOCK_EVENTS)


if __name__ == "__main__":
    collector = ACLEDCollector()
    data = collector.fetch()
    print(f"ACLED returned {len(data)} records.")
    for rec in data[:5]:
        print(rec)

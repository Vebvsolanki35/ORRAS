"""
collectors/who_collector.py — Realistic mock WHO disease outbreak data.

No public WHO API exists; this module generates realistic outbreak records
for known active disease situations.
"""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from utils import get_logger

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Static mock outbreak data — 8 realistic records
# ---------------------------------------------------------------------------

_OUTBREAKS = [
    {
        "disease": "Ebola",
        "location": "DR Congo",
        "cases": 312,
        "deaths": 187,
        "status": "active",
        "date": "2024-11-15",
        "lat": -4.0383,
        "lon": 21.7587,
    },
    {
        "disease": "Cholera",
        "location": "Yemen",
        "cases": 45820,
        "deaths": 412,
        "status": "active",
        "date": "2024-12-01",
        "lat": 15.5527,
        "lon": 48.5164,
    },
    {
        "disease": "Cholera",
        "location": "Sudan",
        "cases": 18740,
        "deaths": 628,
        "status": "active",
        "date": "2024-11-20",
        "lat": 12.8628,
        "lon": 30.2176,
    },
    {
        "disease": "Mpox",
        "location": "Nigeria",
        "cases": 1847,
        "deaths": 23,
        "status": "active",
        "date": "2024-12-10",
        "lat": 9.0820,
        "lon": 8.6753,
    },
    {
        "disease": "Dengue",
        "location": "Brazil",
        "cases": 2140000,
        "deaths": 1084,
        "status": "active",
        "date": "2025-01-05",
        "lat": -14.2350,
        "lon": -51.9253,
    },
    {
        "disease": "Dengue",
        "location": "Philippines",
        "cases": 87320,
        "deaths": 312,
        "status": "active",
        "date": "2024-12-22",
        "lat": 12.8797,
        "lon": 121.7740,
    },
    {
        "disease": "Yellow Fever",
        "location": "Angola",
        "cases": 426,
        "deaths": 87,
        "status": "active",
        "date": "2024-11-28",
        "lat": -11.2027,
        "lon": 17.8739,
    },
    {
        "disease": "Measles",
        "location": "Somalia",
        "cases": 9812,
        "deaths": 156,
        "status": "active",
        "date": "2025-01-10",
        "lat": 5.1521,
        "lon": 46.1996,
    },
]


class WHOCollector:
    """Provides realistic mock WHO disease outbreak records."""

    def get_outbreaks(self) -> list[dict]:
        """
        Return a list of realistic disease outbreak records.

        Returns:
            List of dicts with keys: disease, location, cases, deaths,
            status, date, lat, lon.
        """
        logger.info(f"WHO (mock): returning {len(_OUTBREAKS)} outbreak records.")
        return list(_OUTBREAKS)

    # Alias so orchestrator can call .fetch() uniformly
    def fetch(self) -> list[dict]:
        return self.get_outbreaks()


if __name__ == "__main__":
    collector = WHOCollector()
    data = collector.get_outbreaks()
    print(f"WHO returned {len(data)} records.")
    for rec in data:
        print(rec)

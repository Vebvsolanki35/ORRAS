"""
mock_data_generator.py — Realistic synthetic signal generator for ORRAS.

Produces signals that conform to the unified signal schema used throughout
the system. A fixed random seed ensures reproducibility in tests.
"""

import random
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker

from config import SIGNALS_FILE
from utils import classify_severity, generate_id, now_iso, save_json

# Fixed seed for reproducibility
random.seed(42)
fake = Faker()
fake.seed_instance(42)

# ---------------------------------------------------------------------------
# Static reference data
# ---------------------------------------------------------------------------

# Country → (latitude, longitude) approximate centroids
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "Ukraine": (48.3794, 31.1656),
    "Russia": (61.5240, 105.3188),
    "Syria": (34.8021, 38.9968),
    "Iraq": (33.2232, 43.6793),
    "Afghanistan": (33.9391, 67.7100),
    "Yemen": (15.5527, 48.5164),
    "Somalia": (5.1521, 46.1996),
    "Sudan": (12.8628, 30.2176),
    "Ethiopia": (9.1450, 40.4897),
    "Myanmar": (21.9162, 95.9560),
    "Iran": (32.4279, 53.6880),
    "North Korea": (40.3399, 127.5101),
    "China": (35.8617, 104.1954),
    "Taiwan": (23.6978, 120.9605),
    "Pakistan": (30.3753, 69.3451),
    "India": (20.5937, 78.9629),
    "Israel": (31.0461, 34.8516),
    "Lebanon": (33.8547, 35.8623),
    "Palestine": (31.9522, 35.2332),
    "Libya": (26.3351, 17.2283),
    "Mali": (17.5707, -3.9962),
    "Nigeria": (9.0820, 8.6753),
    "DR Congo": (-4.0383, 21.7587),
    "Venezuela": (6.4238, -66.5897),
    "Colombia": (4.5709, -74.2973),
    "Mexico": (23.6345, -102.5528),
    "Belarus": (53.7098, 27.9534),
    "Azerbaijan": (40.1431, 47.5769),
    "Armenia": (40.0691, 45.0382),
    "Serbia": (44.0165, 21.0059),
    "Kosovo": (42.6026, 20.9030),
    "Bosnia": (43.9159, 17.6791),
    "Georgia (Country)": (42.3154, 43.3569),
    "Burkina Faso": (12.3641, -1.5275),
    "Chad": (15.4542, 18.7322),
    "Niger": (17.6078, 8.0817),
    "Cameroon": (7.3697, 12.3547),
    "Central African Republic": (6.6111, 20.9394),
    "South Sudan": (7.8626, 29.6949),
    "Eritrea": (15.1794, 39.7823),
    "Mozambique": (-18.6657, 35.5296),
    "Haiti": (18.9712, -72.2852),
    "Iraq-Syria Border": (34.0, 41.0),
    "Kashmir": (34.2996, 76.1379),
    "South China Sea": (13.5, 115.0),
    "Taiwan Strait": (24.5, 119.5),
    "Persian Gulf": (26.5, 52.0),
    "Red Sea": (20.0, 38.5),
    "Baltic Sea": (58.0, 20.0),
    "Black Sea": (43.0, 34.0),
}

CONFLICT_REGIONS = list(COUNTRY_COORDS.keys())

CONFLICT_HEADLINES = [
    "{troops} massed near {region} border amid escalating tensions",
    "Airstrike reported in {region} capital district",
    "Military deployment along {region} frontier increases",
    "Missile launch detected near {region} coastline",
    "Armed groups clash in {region} northern corridor",
    "Bombing campaign targets infrastructure in {region}",
    "Troops mobilization ordered along {region} perimeter",
    "Artillery shelling reported in {region} eastern province",
    "Naval vessels patrolling disputed waters near {region}",
    "Protest erupts in {region} capital over government crackdown",
    "Riot police deployed in {region} after mass demonstration",
    "Civil unrest spreading across {region} major cities",
    "Internet shutdown reported in {region} amid crackdown",
    "Network blackout affects {region} mobile communications",
    "Diplomatic relations strained between {region} and neighbors",
    "Ceasefire negotiations fail in {region} peace talks",
    "Peace treaty signed by warring factions in {region}",
    "Military exercise conducted near {region} disputed zone",
]

MILITARY_CALLSIGNS = [
    "RCH101", "DUKE22", "REACH45", "JAKE77", "TOPCAT9",
    "RCH202", "DUKE33", "REACH67", "JAKE88", "TOPCAT15",
    "HAVOC1", "STEEL3", "IRON7", "COBRA9", "EAGLE2",
]

SHUTDOWN_COUNTRIES = ["Iran", "Russia", "Ethiopia", "Myanmar", "Belarus",
                      "Venezuela", "Cuba", "Azerbaijan", "Sudan", "Pakistan"]

SOCIAL_KEYWORDS = [
    "military coup", "protest", "riot", "strike", "crackdown",
    "election fraud", "government collapse", "civil war", "massacre",
    "refugee crisis", "sanctions", "invasion", "occupation",
]


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _random_past_timestamp(hours: int = 48) -> str:
    """Return an ISO 8601 timestamp within the past *hours* hours."""
    delta = timedelta(hours=random.uniform(0, hours))
    return (datetime.now(timezone.utc) - delta).isoformat()


def _pick_country() -> tuple[str, float, float]:
    """Pick a random country and return (name, lat, lon)."""
    country = random.choice(CONFLICT_REGIONS)
    lat, lon = COUNTRY_COORDS[country]
    # Add slight jitter so markers don't stack exactly
    lat += random.uniform(-1.5, 1.5)
    lon += random.uniform(-1.5, 1.5)
    return country, round(lat, 4), round(lon, 4)


def _score_and_severity(text: str, multiplier: float = 1.0) -> tuple[float, list[str], str]:
    """Compute raw_score, keywords_matched, and severity from text."""
    from config import KEYWORD_WEIGHTS
    text_lower = text.lower()
    matched = [kw for kw in KEYWORD_WEIGHTS if kw in text_lower]
    score = sum(KEYWORD_WEIGHTS[kw] for kw in matched)
    score = max(0.0, min(30.0, score * multiplier))
    severity = classify_severity(score)
    return round(score, 2), matched, severity


# ---------------------------------------------------------------------------
# Individual generators
# ---------------------------------------------------------------------------

def generate_news_signals(n: int = 15) -> list[dict[str, Any]]:
    """
    Generate NewsAPI-style headline signals.

    Args:
        n: Number of signals to generate.

    Returns:
        List of unified-schema signal dicts.
    """
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        template = random.choice(CONFLICT_HEADLINES)
        title = template.format(troops="troops", region=country)
        title = title[:100]
        description = fake.sentence(nb_words=30)
        raw_score, keywords, severity = _score_and_severity(title + " " + description, 1.0)
        signals.append({
            "id": generate_id(),
            "timestamp": _random_past_timestamp(48),
            "type": "news",
            "source": "NewsAPI",
            "location": country,
            "latitude": lat,
            "longitude": lon,
            "title": title,
            "description": description[:500],
            "raw_score": raw_score,
            "keywords_matched": keywords,
            "severity": severity,
        })
    return signals


def generate_gdelt_signals(n: int = 10) -> list[dict[str, Any]]:
    """
    Generate GDELT event-style signals with actor and event code info.

    Args:
        n: Number of signals to generate.

    Returns:
        List of unified-schema signal dicts.
    """
    gdelt_event_codes = ["14", "18", "19", "20", "172", "173", "174", "175"]
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        actor1 = fake.last_name() + " " + random.choice(["Forces", "Militia", "Government", "Army"])
        actor2 = fake.country()
        event_code = random.choice(gdelt_event_codes)
        title = f"GDELT Event {event_code}: {actor1} vs {actor2} in {country}"[:100]
        description = (
            f"GDELT recorded a conflict event (code {event_code}) involving {actor1} "
            f"and forces from {actor2}. Deployment and mobilization reported. "
            f"{fake.sentence(nb_words=15)}"
        )[:500]
        raw_score, keywords, severity = _score_and_severity(title + " " + description, 1.2)
        signals.append({
            "id": generate_id(),
            "timestamp": _random_past_timestamp(24),
            "type": "news",
            "source": "GDELT",
            "location": country,
            "latitude": lat,
            "longitude": lon,
            "title": title,
            "description": description,
            "raw_score": raw_score,
            "keywords_matched": keywords,
            "severity": severity,
        })
    return signals


def generate_opensky_signals(n: int = 8) -> list[dict[str, Any]]:
    """
    Generate OpenSky-style aircraft anomaly signals.

    Args:
        n: Number of signals to generate.

    Returns:
        List of unified-schema signal dicts.
    """
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        callsign = random.choice(MILITARY_CALLSIGNS)
        altitude = random.randint(5000, 40000)
        speed = random.randint(300, 900)
        squawk = random.choice(["7700", "7600", "7500", random.choice(["1234", "5678", "2000"])])
        title = f"Aircraft {callsign} alt={altitude}ft spd={speed}kts near {country}"[:100]
        description = (
            f"Military-pattern callsign {callsign} observed at {altitude} ft, "
            f"{speed} knots. Squawk code: {squawk}. Unusual routing near conflict zone "
            f"in {country}. Deployment patterns suggest troop movement support. "
            f"{fake.sentence(nb_words=10)}"
        )[:500]
        raw_score, keywords, severity = _score_and_severity(title + " " + description, 1.1)
        signals.append({
            "id": generate_id(),
            "timestamp": _random_past_timestamp(12),
            "type": "movement",
            "source": "OpenSky",
            "location": country,
            "latitude": lat,
            "longitude": lon,
            "title": title,
            "description": description,
            "raw_score": raw_score,
            "keywords_matched": keywords,
            "severity": severity,
        })
    return signals


def generate_firms_signals(n: int = 6) -> list[dict[str, Any]]:
    """
    Generate NASA FIRMS-style fire/heat anomaly signals.

    Args:
        n: Number of signals to generate.

    Returns:
        List of unified-schema signal dicts.
    """
    satellites = ["VIIRS_SNPP", "MODIS_Terra", "MODIS_Aqua", "VIIRS_NOAA20"]
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        brightness = round(random.uniform(300, 600), 1)
        frp = round(random.uniform(10, 500), 1)
        satellite = random.choice(satellites)
        confidence = random.choice(["low", "nominal", "high"])
        title = f"Fire hotspot detected in {country} — FRP={frp} MW"[:100]
        description = (
            f"NASA {satellite} detected fire radiative power of {frp} MW "
            f"at brightness {brightness} K in {country}. Confidence: {confidence}. "
            f"Potential bombing or artillery strike signature. "
            f"{fake.sentence(nb_words=8)}"
        )[:500]
        raw_score, keywords, severity = _score_and_severity(title + " " + description, 1.3)
        signals.append({
            "id": generate_id(),
            "timestamp": _random_past_timestamp(6),
            "type": "satellite",
            "source": "NASA FIRMS",
            "location": country,
            "latitude": lat,
            "longitude": lon,
            "title": title,
            "description": description,
            "raw_score": raw_score,
            "keywords_matched": keywords,
            "severity": severity,
        })
    return signals


def generate_netblocks_signals(n: int = 5) -> list[dict[str, Any]]:
    """
    Generate NetBlocks-style internet shutdown signals.

    Historically affected countries are included.

    Args:
        n: Number of signals to generate.

    Returns:
        List of unified-schema signal dicts.
    """
    signals = []
    for _ in range(n):
        country = random.choice(SHUTDOWN_COUNTRIES)
        lat, lon = COUNTRY_COORDS.get(country, (0.0, 0.0))
        lat += random.uniform(-0.5, 0.5)
        lon += random.uniform(-0.5, 0.5)
        impact_pct = random.randint(20, 95)
        title = f"Internet shutdown detected in {country} — {impact_pct}% connectivity loss"[:100]
        description = (
            f"NetBlocks monitoring detected a {impact_pct}% disruption to internet "
            f"connectivity in {country}. Network blackout consistent with government-ordered "
            f"shutdown during civil unrest or military operation. "
            f"{fake.sentence(nb_words=10)}"
        )[:500]
        raw_score, keywords, severity = _score_and_severity(title + " " + description, 0.9)
        signals.append({
            "id": generate_id(),
            "timestamp": _random_past_timestamp(24),
            "type": "network",
            "source": "NetBlocks",
            "location": country,
            "latitude": round(lat, 4),
            "longitude": round(lon, 4),
            "title": title,
            "description": description,
            "raw_score": raw_score,
            "keywords_matched": keywords,
            "severity": severity,
        })
    return signals


def generate_social_signals(n: int = 10) -> list[dict[str, Any]]:
    """
    Generate Twitter-style trending keyword signals with engagement scores.

    Args:
        n: Number of signals to generate.

    Returns:
        List of unified-schema signal dicts.
    """
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        keyword = random.choice(SOCIAL_KEYWORDS)
        engagement = random.randint(1000, 500000)
        title = f"Trending: #{keyword.replace(' ', '')} in {country} ({engagement:,} engagements)"[:100]
        description = (
            f"Social media trending topic '{keyword}' is surging in {country} "
            f"with {engagement:,} engagements in the past hour. "
            f"Associated terms include riot, protest, unrest. "
            f"{fake.sentence(nb_words=12)}"
        )[:500]
        raw_score, keywords, severity = _score_and_severity(title + " " + description, 0.6)
        signals.append({
            "id": generate_id(),
            "timestamp": _random_past_timestamp(6),
            "type": "social",
            "source": "Social/Mock",
            "location": country,
            "latitude": lat,
            "longitude": lon,
            "title": title,
            "description": description,
            "raw_score": raw_score,
            "keywords_matched": keywords,
            "severity": severity,
        })
    return signals


# ---------------------------------------------------------------------------
# Master aggregator
# ---------------------------------------------------------------------------

def generate_all_mock_signals() -> list[dict[str, Any]]:
    """
    Call all individual generators and return one merged signal list.

    Returns:
        Combined list of all mock signals.
    """
    all_signals = (
        generate_news_signals(15)
        + generate_gdelt_signals(10)
        + generate_opensky_signals(8)
        + generate_firms_signals(6)
        + generate_netblocks_signals(5)
        + generate_social_signals(10)
    )
    return all_signals


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    signals = generate_all_mock_signals()

    # Count per type
    from collections import Counter
    type_counts = Counter(s["type"] for s in signals)
    source_counts = Counter(s["source"] for s in signals)

    print("=== mock_data_generator.py self-test ===\n")
    print(f"Total signals generated: {len(signals)}\n")
    print("Counts by type:")
    for t, c in type_counts.items():
        print(f"  {t:12s}: {c}")
    print("\nCounts by source:")
    for src, c in source_counts.items():
        print(f"  {src:20s}: {c}")

    print("\nSample signal (first):")
    import json
    print(json.dumps(signals[0], indent=2))

    save_json(SIGNALS_FILE, signals)
    print(f"\n✅ Saved {len(signals)} signals to {SIGNALS_FILE}")

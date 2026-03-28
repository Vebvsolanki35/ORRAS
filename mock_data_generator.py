"""
mock_data_generator.py — Realistic synthetic signal generator for ORRAS.

Produces signals that conform to the unified signal schema used throughout
the system. A fixed random seed ensures reproducibility in tests.
"""

import random
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from faker import Faker

from config import (
    DISASTER_KEYWORD_WEIGHTS,
    GEOFENCE_ZONES,
    KEYWORD_WEIGHTS,
    SIGNALS_FILE,
    SOURCE_MULTIPLIERS,
)
from utils import (
    classify_disaster_severity,
    classify_severity,
    generate_id,
    haversine_distance,
    now_iso,
    save_json,
)

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

# Full list of countries for disaster/humanitarian generators
COUNTRY_LIST = list(COUNTRY_COORDS.keys())

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

EARTHQUAKE_REGIONS = [
    ("Japan", 36.2048, 138.2529),
    ("Chile", -30.0, -71.0),
    ("Indonesia", -5.0, 120.0),
    ("Turkey", 38.0, 35.0),
    ("Iran", 32.0, 53.0),
    ("Pakistan", 30.0, 69.0),
    ("Afghanistan", 34.0, 67.0),
    ("Peru", -12.0, -75.0),
    ("Mexico", 19.0, -99.0),
    ("Taiwan", 23.7, 120.9),
    ("Philippines", 12.0, 122.0),
    ("India", 28.0, 78.0),
    ("Nepal", 28.0, 84.0),
    ("Haiti", 18.5, -72.3),
    ("New Zealand", -42.0, 172.0),
]

WEATHER_REGIONS = [
    ("Bangladesh", 23.7, 90.4),
    ("Philippines", 14.0, 121.0),
    ("Vietnam", 16.0, 108.0),
    ("India", 22.0, 80.0),
    ("United States", 35.0, -95.0),
    ("Japan", 33.0, 130.0),
    ("China", 28.0, 110.0),
    ("Indonesia", -6.0, 107.0),
    ("Pakistan", 26.0, 68.0),
    ("Mozambique", -18.0, 35.0),
    ("Haiti", 19.0, -72.0),
    ("Madagascar", -20.0, 47.0),
    ("Myanmar", 17.0, 96.0),
    ("Australia", -25.0, 133.0),
    ("Somalia", 6.0, 46.0),
]

DISEASE_REGIONS = [
    ("Nigeria", 9.1, 8.7),
    ("Congo (DRC)", -4.0, 21.8),
    ("India", 21.0, 78.0),
    ("Pakistan", 30.0, 69.0),
    ("Sudan", 13.0, 30.0),
    ("Ethiopia", 9.1, 40.5),
    ("Somalia", 5.2, 46.2),
    ("Syria", 35.0, 38.0),
    ("Haiti", 18.9, -72.3),
    ("Bangladesh", 23.7, 90.4),
    ("Yemen", 15.6, 48.5),
    ("Cambodia", 12.6, 104.9),
    ("Mali", 17.6, -4.0),
    ("Niger", 17.6, 8.1),
    ("Chad", 15.5, 18.7),
]

HUMANITARIAN_REGIONS = [
    ("Yemen", 15.5, 48.5),
    ("Syria", 34.8, 38.9),
    ("South Sudan", 7.9, 29.7),
    ("Somalia", 5.2, 46.2),
    ("Venezuela", 6.4, -66.6),
    ("Afghanistan", 33.9, 67.7),
    ("Sudan", 12.9, 30.2),
    ("DR Congo", -4.0, 21.8),
    ("Mozambique", -18.7, 35.5),
    ("Haiti", 19.0, -72.3),
    ("Ethiopia", 9.1, 40.5),
    ("Myanmar", 21.9, 96.0),
    ("Palestine", 31.9, 35.2),
    ("Chad", 15.5, 18.7),
    ("Nigeria", 9.1, 8.7),
]

ACLED_REGIONS = list(COUNTRY_COORDS.keys())


# ---------------------------------------------------------------------------
# Helper functions
# ---------------------------------------------------------------------------

def _random_past_timestamp(hours: int = 48) -> str:
    """Return an ISO 8601 timestamp within the past *hours* hours."""
    delta = timedelta(hours=random.uniform(0, hours))
    return (datetime.now(timezone.utc) - delta).isoformat()


def _pick_country() -> tuple[str, float, float]:
    """Pick a random country and return (name, lat, lon)."""
    country = random.choice(CONFLICT_REGIONS)
    lat, lon = COUNTRY_COORDS[country]
    lat += random.uniform(-1.5, 1.5)
    lon += random.uniform(-1.5, 1.5)
    return country, round(lat, 4), round(lon, 4)


def _score_conflict(text: str, multiplier: float = 1.0) -> tuple[float, list[str]]:
    """Return (conflict_score, keywords_matched) from text."""
    text_lower = text.lower()
    matched = [kw for kw in KEYWORD_WEIGHTS if kw in text_lower]
    score = sum(KEYWORD_WEIGHTS[kw] for kw in matched)
    score = max(0.0, min(30.0, score * multiplier))
    return round(score, 2), matched


def _score_disaster(text: str, multiplier: float = 1.0) -> tuple[float, list[str]]:
    """Return (disaster_score, keywords_matched) from text."""
    text_lower = text.lower()
    matched = [kw for kw in DISASTER_KEYWORD_WEIGHTS if kw in text_lower]
    score = sum(DISASTER_KEYWORD_WEIGHTS[kw] for kw in matched)
    score = max(0.0, min(30.0, score * multiplier))
    return round(score, 2), matched


def _score_and_severity(text: str, multiplier: float = 1.0) -> tuple[float, list[str], str]:
    """Compute raw_score, keywords_matched, and severity from text (conflict-focused)."""
    score, matched = _score_conflict(text, multiplier)
    return score, matched, classify_severity(score)


def _get_geofence_zones(lat: float, lon: float) -> list[str]:
    """Return list of geofence zone names that contain the given coordinates."""
    zones = []
    for zone_name, zone_info in GEOFENCE_ZONES.items():
        dist = haversine_distance(lat, lon, zone_info["lat"], zone_info["lon"])
        if dist <= zone_info["radius_km"]:
            zones.append(zone_name)
    return zones


def _dynamic_weight(source: str, conflict_score: float, disaster_score: float) -> float:
    """Calculate a dynamic weight combining source multiplier and scores."""
    multiplier = SOURCE_MULTIPLIERS.get(source, 1.0)
    combined = max(conflict_score, disaster_score)
    base = min(1.0 + combined / 30.0, 2.0)
    return round(base * multiplier, 3)


def _build_signal(
    sig_type: str,
    source: str,
    location: str,
    lat: float,
    lon: float,
    title: str,
    description: str,
    conflict_score: float,
    disaster_score: float,
    keywords_matched: list[str],
    track: str = "conflict",
    correlated: bool = False,
    timestamp_hours: int = 48,
    confidence: str | None = None,
) -> dict[str, Any]:
    """Assemble a fully schema-valid signal dict."""
    raw_score = round(
        conflict_score * 0.6 + disaster_score * 0.4, 2
    ) if track == "both" else (conflict_score if track == "conflict" else disaster_score)
    severity = classify_severity(raw_score)
    conflict_severity = classify_severity(conflict_score)
    disaster_severity = classify_disaster_severity(disaster_score)

    # Derive signal_class from the higher score
    if conflict_score >= disaster_score:
        signal_class = "conflict"
    else:
        signal_class = "disaster"

    if confidence is None:
        if raw_score >= 15:
            confidence = "HIGH"
        elif raw_score >= 7:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

    geofence_zones = _get_geofence_zones(lat, lon)
    dyn_weight = _dynamic_weight(source, conflict_score, disaster_score)

    return {
        "id": generate_id(),
        "timestamp": _random_past_timestamp(timestamp_hours),
        "type": sig_type,
        "source": source,
        "location": location,
        "latitude": lat,
        "longitude": lon,
        "title": title[:100],
        "description": description[:500],
        "raw_score": raw_score,
        "conflict_score": conflict_score,
        "disaster_score": disaster_score,
        "keywords_matched": keywords_matched,
        "severity": severity,
        "conflict_severity": conflict_severity,
        "disaster_severity": disaster_severity,
        "signal_class": signal_class,
        "track": track,
        "geofence_zones": geofence_zones,
        "dynamic_weight": dyn_weight,
        "correlated": correlated,
        "confidence": confidence,
    }


# ---------------------------------------------------------------------------
# Individual generators
# ---------------------------------------------------------------------------

def generate_news_signals(n: int = 15) -> list[dict[str, Any]]:
    """Generate NewsAPI-style headline signals."""
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        template = random.choice(CONFLICT_HEADLINES)
        title = template.format(troops="troops", region=country)
        description = fake.sentence(nb_words=30)
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 1.0)
        d_score, d_kw = _score_disaster(full_text, 1.0)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="news", source="NewsAPI",
            location=country, lat=lat, lon=lon,
            title=title, description=description[:500],
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="conflict",
        ))
    return signals


def generate_gdelt_signals(n: int = 10) -> list[dict[str, Any]]:
    """Generate GDELT event-style signals with actor and event code info."""
    gdelt_event_codes = ["14", "18", "19", "20", "172", "173", "174", "175"]
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        actor1 = fake.last_name() + " " + random.choice(["Forces", "Militia", "Government", "Army"])
        actor2 = fake.country()
        event_code = random.choice(gdelt_event_codes)
        title = f"GDELT Event {event_code}: {actor1} vs {actor2} in {country}"
        description = (
            f"GDELT recorded a conflict event (code {event_code}) involving {actor1} "
            f"and forces from {actor2}. Deployment and mobilization reported. "
            f"{fake.sentence(nb_words=15)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 1.2)
        d_score, d_kw = _score_disaster(full_text, 1.0)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="news", source="GDELT",
            location=country, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="conflict",
            timestamp_hours=24,
        ))
    return signals


def generate_opensky_signals(n: int = 8) -> list[dict[str, Any]]:
    """Generate OpenSky-style aircraft anomaly signals."""
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        callsign = random.choice(MILITARY_CALLSIGNS)
        altitude = random.randint(5000, 40000)
        speed = random.randint(300, 900)
        squawk = random.choice(["7700", "7600", "7500", str(random.randint(1000, 7999))])
        title = f"Aircraft {callsign} alt={altitude}ft spd={speed}kts near {country}"
        description = (
            f"Military-pattern callsign {callsign} observed at {altitude} ft, "
            f"{speed} knots. Squawk code: {squawk}. Unusual routing near conflict zone "
            f"in {country}. Deployment patterns suggest troop movement support. "
            f"{fake.sentence(nb_words=10)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 1.1)
        d_score, d_kw = _score_disaster(full_text, 0.8)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="movement", source="OpenSky",
            location=country, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="conflict",
            timestamp_hours=12,
        ))
    return signals


def generate_firms_signals(n: int = 6) -> list[dict[str, Any]]:
    """Generate NASA FIRMS-style fire/heat anomaly signals."""
    satellites = ["VIIRS_SNPP", "MODIS_Terra", "MODIS_Aqua", "VIIRS_NOAA20"]
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        brightness = round(random.uniform(300, 600), 1)
        frp = round(random.uniform(10, 500), 1)
        satellite = random.choice(satellites)
        confidence_label = random.choice(["low", "nominal", "high"])
        title = f"Fire hotspot detected in {country} — FRP={frp} MW"
        description = (
            f"NASA {satellite} detected fire radiative power of {frp} MW "
            f"at brightness {brightness} K in {country}. Confidence: {confidence_label}. "
            f"Potential bombing or artillery strike signature. "
            f"{fake.sentence(nb_words=8)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 1.3)
        d_score, d_kw = _score_disaster(full_text, 1.3)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="satellite", source="NASA FIRMS",
            location=country, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="both",
            timestamp_hours=6,
        ))
    return signals


def generate_netblocks_signals(n: int = 5) -> list[dict[str, Any]]:
    """Generate NetBlocks-style internet shutdown signals."""
    signals = []
    for _ in range(n):
        country = random.choice(SHUTDOWN_COUNTRIES)
        lat, lon = COUNTRY_COORDS.get(country, (0.0, 0.0))
        lat = round(lat + random.uniform(-0.5, 0.5), 4)
        lon = round(lon + random.uniform(-0.5, 0.5), 4)
        impact_pct = random.randint(20, 95)
        title = f"Internet shutdown detected in {country} — {impact_pct}% connectivity loss"
        description = (
            f"NetBlocks monitoring detected a {impact_pct}% disruption to internet "
            f"connectivity in {country}. Network blackout consistent with government-ordered "
            f"shutdown during civil unrest or military operation. "
            f"{fake.sentence(nb_words=10)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 0.9)
        d_score, d_kw = _score_disaster(full_text, 0.7)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="network", source="NetBlocks",
            location=country, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="conflict",
            timestamp_hours=24,
        ))
    return signals


def generate_social_signals(n: int = 10) -> list[dict[str, Any]]:
    """Generate Twitter-style trending keyword signals with engagement scores."""
    signals = []
    for _ in range(n):
        country, lat, lon = _pick_country()
        keyword = random.choice(SOCIAL_KEYWORDS)
        engagement = random.randint(1000, 500000)
        title = f"Trending: #{keyword.replace(' ', '')} in {country} ({engagement:,} engagements)"
        description = (
            f"Social media trending topic '{keyword}' is surging in {country} "
            f"with {engagement:,} engagements in the past hour. "
            f"Associated terms include riot, protest, unrest. "
            f"{fake.sentence(nb_words=12)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 0.6)
        d_score, d_kw = _score_disaster(full_text, 0.5)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="social", source="Social/Mock",
            location=country, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="conflict",
            timestamp_hours=6,
        ))
    return signals


def generate_earthquake_signals(n: int = 5) -> list[dict[str, Any]]:
    """Generate USGS-style earthquake signals."""
    signals = []
    for _ in range(n):
        region_name, base_lat, base_lon = random.choice(EARTHQUAKE_REGIONS)
        lat = round(base_lat + random.uniform(-2.0, 2.0), 4)
        lon = round(base_lon + random.uniform(-2.0, 2.0), 4)
        magnitude = round(random.uniform(5.0, 8.5), 1)
        depth_km = random.randint(5, 200)
        title = f"Earthquake M{magnitude} near {region_name}, depth {depth_km} km"
        description = (
            f"USGS reports a magnitude {magnitude} earthquake near {region_name} "
            f"at depth {depth_km} km. "
            + ("Potential for casualties and structural damage. Evacuation recommended. " if magnitude >= 6.5 else "")
            + ("Tsunami warning issued. " if magnitude >= 7.5 and depth_km < 50 else "")
            + fake.sentence(nb_words=12)
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 0.5)
        d_score, d_kw = _score_disaster(full_text, 1.3)
        if magnitude >= 7.0:
            d_score = min(30.0, d_score + 10.0)
        elif magnitude >= 6.0:
            d_score = min(30.0, d_score + 5.0)
        d_score = round(d_score, 2)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="satellite", source="USGS",
            location=region_name, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="disaster",
            timestamp_hours=24,
        ))
    return signals


def generate_weather_signals(n: int = 5) -> list[dict[str, Any]]:
    """Generate NOAA-style severe weather signals."""
    weather_events = [
        ("Category 5 hurricane approaching", "Hurricane", 15),
        ("Category 4 typhoon", "Typhoon", 12),
        ("Catastrophic flooding", "Flood", 10),
        ("Severe cyclone warning", "Cyclone", 12),
        ("Extreme monsoon flooding", "Flood", 8),
        ("Tornado outbreak warning", "Tornado", 9),
        ("Severe drought emergency", "Drought", 6),
        ("Blizzard emergency declared", "Blizzard", 5),
        ("Flash flood emergency", "Flood", 9),
        ("Storm surge warning issued", "Storm Surge", 10),
    ]
    signals = []
    for _ in range(n):
        region_name, base_lat, base_lon = random.choice(WEATHER_REGIONS)
        lat = round(base_lat + random.uniform(-1.5, 1.5), 4)
        lon = round(base_lon + random.uniform(-1.5, 1.5), 4)
        event_desc, event_type, base_d_score = random.choice(weather_events)
        wind_speed = random.randint(80, 250)
        affected = random.randint(10000, 5000000)
        title = f"{event_desc} in {region_name} — winds {wind_speed} km/h"
        description = (
            f"NOAA {event_type} warning for {region_name}. "
            f"Maximum sustained winds: {wind_speed} km/h. "
            f"Estimated {affected:,} people in affected zone. "
            f"Evacuation orders issued. Casualties and missing persons reported. "
            f"{fake.sentence(nb_words=10)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 0.3)
        d_score, d_kw = _score_disaster(full_text, 1.2)
        d_score = min(30.0, round(d_score + base_d_score, 2))
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="satellite", source="NOAA",
            location=region_name, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="disaster",
            timestamp_hours=12,
        ))
    return signals


def generate_disease_signals(n: int = 4) -> list[dict[str, Any]]:
    """Generate WHO/CDC-style disease outbreak signals."""
    diseases = [
        ("Ebola outbreak", 12),
        ("Cholera epidemic", 9),
        ("Mpox outbreak", 7),
        ("Measles outbreak", 6),
        ("Dengue fever epidemic", 7),
        ("Marburg virus case cluster", 11),
        ("Polio resurgence", 8),
        ("Yellow fever outbreak", 8),
        ("Meningitis epidemic", 7),
        ("COVID-19 variant surge", 9),
    ]
    signals = []
    for _ in range(n):
        region_name, base_lat, base_lon = random.choice(DISEASE_REGIONS)
        lat = round(base_lat + random.uniform(-1.0, 1.0), 4)
        lon = round(base_lon + random.uniform(-1.0, 1.0), 4)
        disease, base_d = random.choice(diseases)
        cases = random.randint(50, 10000)
        deaths = random.randint(5, cases // 3)
        title = f"{disease} in {region_name} — {cases} cases, {deaths} deaths"
        description = (
            f"WHO reports confirmed {disease} in {region_name}. "
            f"{cases} confirmed cases and {deaths} deaths recorded. "
            f"Mass casualty event possible without rapid intervention. "
            f"Evacuation of healthcare workers underway. "
            f"Outbreak declared. {fake.sentence(nb_words=10)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 0.2)
        d_score, d_kw = _score_disaster(full_text, 1.2)
        d_score = min(30.0, round(d_score + base_d, 2))
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="news", source="WHO",
            location=region_name, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="disaster",
            timestamp_hours=48,
        ))
    return signals


def generate_humanitarian_signals(n: int = 6) -> list[dict[str, Any]]:
    """Generate ReliefWeb/OCHA-style humanitarian crisis signals."""
    crisis_types = [
        ("Famine emergency declared", 10),
        ("Mass displacement reported", 8),
        ("Refugee crisis — border surge", 7),
        ("Aid access blocked", 9),
        ("Humanitarian corridor established", -2),
        ("Emergency food distribution begins", -1),
        ("Mass casualty event at displacement camp", 12),
        ("Clean water shortage — epidemic risk", 8),
        ("Cholera outbreak in refugee camp", 10),
        ("Child malnutrition crisis", 7),
    ]
    signals = []
    for _ in range(n):
        region_name, base_lat, base_lon = random.choice(HUMANITARIAN_REGIONS)
        lat = round(base_lat + random.uniform(-1.0, 1.0), 4)
        lon = round(base_lon + random.uniform(-1.0, 1.0), 4)
        crisis, base_d = random.choice(crisis_types)
        displaced = random.randint(10000, 3000000)
        title = f"{crisis} in {region_name} — {displaced:,} displaced"
        description = (
            f"OCHA/ReliefWeb: {crisis} in {region_name}. "
            f"{displaced:,} people displaced. "
            f"Famine conditions spreading. Refugee camps overwhelmed. "
            f"Evacuation and rescue operations ongoing. "
            f"{fake.sentence(nb_words=12)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 0.8)
        d_score, d_kw = _score_disaster(full_text, 1.1)
        d_score = min(30.0, max(0.0, round(d_score + base_d, 2)))
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="news", source="ReliefWeb",
            location=region_name, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="both",
            timestamp_hours=72,
        ))
    return signals


def generate_acled_signals(n: int = 8) -> list[dict[str, Any]]:
    """Generate ACLED-style political violence and conflict event signals."""
    event_types = [
        ("Battles", "Armed clash between state forces and rebel groups", 12),
        ("Explosions/Remote Violence", "IED detonated in marketplace", 14),
        ("Violence against civilians", "Targeted attack on civilian population", 13),
        ("Protests", "Mass protest against government forces", 5),
        ("Riots", "Violent riot erupts in city center", 8),
        ("Strategic development", "Military deployment and mobilization ordered", 7),
        ("Assassination", "Political assassination reported", 15),
        ("Coup", "Military coup attempt underway", 16),
    ]
    signals = []
    for _ in range(n):
        country = random.choice(ACLED_REGIONS)
        lat, lon = COUNTRY_COORDS[country]
        lat = round(lat + random.uniform(-1.5, 1.5), 4)
        lon = round(lon + random.uniform(-1.5, 1.5), 4)
        event_type, event_desc, base_c = random.choice(event_types)
        fatalities = random.randint(0, 50)
        actor = fake.last_name() + " " + random.choice(["Forces", "Militia", "Army", "Group"])
        title = f"ACLED {event_type}: {event_desc} in {country} ({fatalities} fatalities)"
        description = (
            f"ACLED records {event_type} event in {country}. {event_desc}. "
            f"{fatalities} fatalities reported. Actor: {actor}. "
            f"Troops and deployment observed in the area. "
            f"{fake.sentence(nb_words=12)}"
        )[:500]
        full_text = title + " " + description
        c_score, c_kw = _score_conflict(full_text, 1.0)
        c_score = min(30.0, round(c_score + base_c * 0.5, 2))
        d_score, d_kw = _score_disaster(full_text, 0.6)
        keywords = list(set(c_kw + d_kw))
        signals.append(_build_signal(
            sig_type="news", source="ACLED",
            location=country, lat=lat, lon=lon,
            title=title, description=description,
            conflict_score=c_score, disaster_score=d_score,
            keywords_matched=keywords, track="conflict",
            timestamp_hours=48,
        ))
    return signals


# ---------------------------------------------------------------------------
# Master aggregator
# ---------------------------------------------------------------------------

def generate_all_mock_signals() -> list[dict[str, Any]]:
    """Call all individual generators and return one merged signal list."""
    return (
        generate_news_signals(15)
        + generate_gdelt_signals(10)
        + generate_opensky_signals(8)
        + generate_firms_signals(6)
        + generate_netblocks_signals(5)
        + generate_social_signals(10)
        + generate_earthquake_signals(5)
        + generate_weather_signals(5)
        + generate_disease_signals(4)
        + generate_humanitarian_signals(6)
        + generate_acled_signals(8)
    )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json

    signals = generate_all_mock_signals()

    type_counts = Counter(s["type"] for s in signals)
    source_counts = Counter(s["source"] for s in signals)

    print("=== mock_data_generator.py self-test ===\n")
    print(f"Total signals generated: {len(signals)}\n")
    print("Counts by type:")
    for t, c in sorted(type_counts.items()):
        print(f"  {t:12s}: {c}")
    print("\nCounts by source:")
    for src, c in sorted(source_counts.items()):
        print(f"  {src:25s}: {c}")

    # Validate all required fields are present
    required_fields = [
        "id", "timestamp", "type", "source", "location", "latitude", "longitude",
        "title", "description", "raw_score", "conflict_score", "disaster_score",
        "keywords_matched", "severity", "conflict_severity", "disaster_severity",
        "signal_class", "track", "geofence_zones", "dynamic_weight", "correlated",
        "confidence",
    ]
    for sig in signals:
        for field in required_fields:
            assert field in sig, f"Missing field '{field}' in signal: {sig.get('id')}"
    print(f"\n✅ All {len(required_fields)} required fields present in every signal.")

    print("\nSample signal (first):")
    print(json.dumps(signals[0], indent=2))

    save_json(SIGNALS_FILE, signals)
    print(f"\n✅ Saved {len(signals)} signals to {SIGNALS_FILE}")


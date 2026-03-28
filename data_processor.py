"""
data_processor.py — Normalises raw collector output into the unified signal schema.

Each source has a dedicated normaliser function. The DataProcessor class
orchestrates all normalisers, deduplicates results, and validates every signal.
"""

from typing import Any

from utils import classify_severity, generate_id, get_logger, now_iso, truncate_text

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Country → (lat, lon) lookup (50+ countries)
# ---------------------------------------------------------------------------
COUNTRY_COORDS: dict[str, tuple[float, float]] = {
    "ukraine": (48.3794, 31.1656),
    "russia": (61.5240, 105.3188),
    "syria": (34.8021, 38.9968),
    "iraq": (33.2232, 43.6793),
    "afghanistan": (33.9391, 67.7100),
    "yemen": (15.5527, 48.5164),
    "somalia": (5.1521, 46.1996),
    "sudan": (12.8628, 30.2176),
    "ethiopia": (9.1450, 40.4897),
    "myanmar": (21.9162, 95.9560),
    "iran": (32.4279, 53.6880),
    "north korea": (40.3399, 127.5101),
    "china": (35.8617, 104.1954),
    "taiwan": (23.6978, 120.9605),
    "pakistan": (30.3753, 69.3451),
    "india": (20.5937, 78.9629),
    "israel": (31.0461, 34.8516),
    "lebanon": (33.8547, 35.8623),
    "palestine": (31.9522, 35.2332),
    "libya": (26.3351, 17.2283),
    "mali": (17.5707, -3.9962),
    "nigeria": (9.0820, 8.6753),
    "dr congo": (-4.0383, 21.7587),
    "venezuela": (6.4238, -66.5897),
    "colombia": (4.5709, -74.2973),
    "mexico": (23.6345, -102.5528),
    "belarus": (53.7098, 27.9534),
    "azerbaijan": (40.1431, 47.5769),
    "armenia": (40.0691, 45.0382),
    "serbia": (44.0165, 21.0059),
    "kosovo": (42.6026, 20.9030),
    "bosnia": (43.9159, 17.6791),
    "georgia": (42.3154, 43.3569),
    "burkina faso": (12.3641, -1.5275),
    "chad": (15.4542, 18.7322),
    "niger": (17.6078, 8.0817),
    "cameroon": (7.3697, 12.3547),
    "central african republic": (6.6111, 20.9394),
    "south sudan": (7.8626, 29.6949),
    "eritrea": (15.1794, 39.7823),
    "mozambique": (-18.6657, 35.5296),
    "haiti": (18.9712, -72.2852),
    "united states": (37.0902, -95.7129),
    "united kingdom": (55.3781, -3.4360),
    "france": (46.2276, 2.2137),
    "germany": (51.1657, 10.4515),
    "turkey": (38.9637, 35.2433),
    "saudi arabia": (23.8859, 45.0792),
    "egypt": (26.8206, 30.8025),
    "south africa": (-30.5595, 22.9375),
    "brazil": (-14.2350, -51.9253),
    "argentina": (-38.4161, -63.6167),
    "japan": (36.2048, 138.2529),
    "south korea": (35.9078, 127.7669),
    "philippines": (12.8797, 121.7740),
    "indonesia": (-0.7893, 113.9213),
    "thailand": (15.8700, 100.9925),
    "vietnam": (14.0583, 108.2772),
    "cambodia": (12.5657, 104.9910),
    "malaysia": (4.2105, 101.9758),
}

# Country bounding boxes for reverse-geocoding: (min_lat, max_lat, min_lon, max_lon)
COUNTRY_BBOXES: dict[str, tuple[float, float, float, float]] = {
    "ukraine": (44.0, 52.5, 22.0, 40.3),
    "russia": (41.0, 81.9, 19.0, 180.0),
    "syria": (32.3, 37.4, 35.7, 42.4),
    "iraq": (29.0, 37.4, 38.8, 48.6),
    "iran": (25.0, 39.8, 44.0, 63.3),
    "afghanistan": (29.4, 38.5, 60.5, 74.9),
    "ukraine_east": (47.0, 51.5, 33.0, 40.2),
    "israel": (29.5, 33.3, 34.2, 35.9),
    "lebanon": (33.0, 34.7, 35.1, 36.6),
    "taiwan": (21.9, 25.3, 119.9, 122.0),
    "north korea": (37.7, 43.0, 124.2, 130.7),
    "pakistan": (23.6, 37.1, 60.9, 77.2),
    "china": (18.0, 53.6, 73.5, 134.8),
}


def _guess_country(text: str) -> str:
    """Guess a country name from free text by simple substring matching."""
    if not text:
        return "Unknown"
    text_lower = text.lower()
    for country in COUNTRY_COORDS:
        if country in text_lower:
            return country.title()
    return "Unknown"


def _coords_for_country(country: str) -> tuple[float, float]:
    """Return (lat, lon) for a country name, defaulting to (0.0, 0.0)."""
    return COUNTRY_COORDS.get(country.lower(), (0.0, 0.0))


def _reverse_geocode(lat: float, lon: float) -> str:
    """Determine country name from lat/lon using bounding box lookup."""
    for country, (min_lat, max_lat, min_lon, max_lon) in COUNTRY_BBOXES.items():
        if min_lat <= lat <= max_lat and min_lon <= lon <= max_lon:
            return country.replace("_", " ").title()
    return "Unknown"


# ---------------------------------------------------------------------------
# Required schema fields with their types
# ---------------------------------------------------------------------------
REQUIRED_FIELDS: dict[str, type] = {
    "id": str,
    "timestamp": str,
    "type": str,
    "source": str,
    "location": str,
    "latitude": float,
    "longitude": float,
    "title": str,
    "description": str,
    "raw_score": float,
    "keywords_matched": list,
    "severity": str,
}


def _validate_signal(signal: dict) -> bool:
    """
    Validate that a signal contains all required fields with correct types.

    Logs a warning for each invalid field but does not raise.

    Returns:
        True if valid, False otherwise.
    """
    for field, expected_type in REQUIRED_FIELDS.items():
        if field not in signal:
            logger.warning(f"Signal missing field '{field}': {signal.get('id', '?')}")
            return False
        if not isinstance(signal[field], expected_type):
            logger.warning(
                f"Signal field '{field}' wrong type "
                f"(expected {expected_type.__name__}, got {type(signal[field]).__name__}): "
                f"{signal.get('id', '?')}"
            )
            return False
    return True


def _fill_defaults(signal: dict) -> dict:
    """Fill any missing required fields with safe default values."""
    defaults: dict[str, Any] = {
        "id": generate_id(),
        "timestamp": now_iso(),
        "type": "news",
        "source": "Unknown",
        "location": "Unknown",
        "latitude": 0.0,
        "longitude": 0.0,
        "title": "No title",
        "description": "",
        "raw_score": 0.0,
        "keywords_matched": [],
        "severity": "LOW",
    }
    for field, default in defaults.items():
        if field not in signal or signal[field] is None:
            signal[field] = default
    return signal


# ---------------------------------------------------------------------------
# Individual normalisers
# ---------------------------------------------------------------------------

def normalize_newsapi(articles: list) -> list[dict]:
    """
    Normalise raw NewsAPI article records into the unified schema.

    Args:
        articles: List of raw article dicts from NewsAPI.

    Returns:
        List of normalised signal dicts.
    """
    signals = []
    for art in articles:
        if not isinstance(art, dict):
            continue
        title = truncate_text(art.get("title") or "", 100)
        desc = truncate_text(art.get("description") or art.get("content") or "", 500)
        published = art.get("publishedAt") or now_iso()
        source_name = (art.get("source") or {}).get("name") or "NewsAPI"

        # Try to identify location from source name or title
        location = _guess_country(title) or _guess_country(source_name) or "Unknown"
        lat, lon = _coords_for_country(location)

        signal = _fill_defaults({
            "id": generate_id(),
            "timestamp": published,
            "type": "news",
            "source": "NewsAPI",
            "location": location,
            "latitude": float(lat),
            "longitude": float(lon),
            "title": title,
            "description": desc,
            "raw_score": 0.0,
            "keywords_matched": [],
            "severity": "LOW",
        })
        signals.append(signal)
    return signals


def normalize_gdelt(articles: list) -> list[dict]:
    """
    Normalise raw GDELT article records into the unified schema.

    Args:
        articles: List of raw article dicts from GDELT.

    Returns:
        List of normalised signal dicts.
    """
    signals = []
    for art in articles:
        if not isinstance(art, dict):
            continue
        title = truncate_text(art.get("title") or "", 100)
        url = art.get("url") or ""
        published = art.get("seendate") or art.get("pubdate") or now_iso()
        location = _guess_country(title) or _guess_country(url) or "Unknown"
        lat, lon = _coords_for_country(location)

        signal = _fill_defaults({
            "id": generate_id(),
            "timestamp": published,
            "type": "news",
            "source": "GDELT",
            "location": location,
            "latitude": float(lat),
            "longitude": float(lon),
            "title": title,
            "description": truncate_text(art.get("domain") or url or "", 500),
            "raw_score": 0.0,
            "keywords_matched": [],
            "severity": "LOW",
        })
        signals.append(signal)
    return signals


def normalize_opensky(states: list) -> list[dict]:
    """
    Normalise OpenSky state vectors into the unified schema.

    State vector layout:
    [icao24, callsign, origin_country, time_position, last_contact,
     longitude, latitude, baro_altitude, on_ground, velocity,
     true_track, vertical_rate, sensors, geo_altitude, squawk,
     spi, position_source]

    Args:
        states: List of state vector lists from OpenSky.

    Returns:
        List of normalised signal dicts.
    """
    signals = []
    for sv in states:
        # Accept both list/tuple (live) and pre-built dicts (mock)
        if isinstance(sv, dict):
            signals.append(_fill_defaults(sv))
            continue
        if not isinstance(sv, (list, tuple)) or len(sv) < 17:
            continue
        callsign = (sv[1] or "UNKNOWN").strip()
        lat = sv[6] or 0.0
        lon = sv[5] or 0.0
        altitude = sv[7] or 0
        speed = sv[9] or 0
        squawk = sv[14] or "0000"
        location = _reverse_geocode(lat, lon)

        title = truncate_text(
            f"Aircraft {callsign} alt={altitude:.0f}m spd={speed:.0f}m/s near {location}", 100
        )
        description = (
            f"Military-pattern callsign {callsign} at {altitude:.0f}m, "
            f"{speed:.0f} m/s. Squawk {squawk}. Unusual routing near {location}. "
            "Possible troop movement or deployment support."
        )[:500]

        signal = _fill_defaults({
            "id": generate_id(),
            "timestamp": now_iso(),
            "type": "movement",
            "source": "OpenSky",
            "location": location,
            "latitude": float(lat),
            "longitude": float(lon),
            "title": title,
            "description": description,
            "raw_score": 0.0,
            "keywords_matched": [],
            "severity": "LOW",
        })
        signals.append(signal)
    return signals


def normalize_firms(hotspots: list) -> list[dict]:
    """
    Normalise NASA FIRMS CSV rows into the unified schema.

    Args:
        hotspots: List of dicts parsed from CSV.

    Returns:
        List of normalised signal dicts.
    """
    signals = []
    for row in hotspots:
        if isinstance(row, dict) and "source" in row and row.get("source") == "NASA FIRMS":
            # Already in unified schema (mock path)
            signals.append(_fill_defaults(row))
            continue
        if not isinstance(row, dict):
            continue
        try:
            lat = float(row.get("latitude") or row.get("lat") or 0)
            lon = float(row.get("longitude") or row.get("lon") or 0)
        except ValueError:
            lat, lon = 0.0, 0.0
        brightness = row.get("bright_ti4") or row.get("brightness") or "N/A"
        frp = row.get("frp") or "N/A"
        location = _reverse_geocode(lat, lon) if (lat or lon) else "Unknown"
        title = truncate_text(f"Fire hotspot in {location} — FRP={frp} MW", 100)
        description = (
            f"NASA FIRMS detected fire at ({lat:.2f}, {lon:.2f}). "
            f"Brightness: {brightness} K, FRP: {frp} MW. "
            "Potential bombing or artillery strike signature."
        )[:500]

        # Map FRP to a raw severity hint
        try:
            frp_val = float(frp)
            raw_score = min(30.0, frp_val / 20.0)
        except (ValueError, TypeError):
            raw_score = 5.0

        signal = _fill_defaults({
            "id": generate_id(),
            "timestamp": now_iso(),
            "type": "satellite",
            "source": "NASA FIRMS",
            "location": location,
            "latitude": lat,
            "longitude": lon,
            "title": title,
            "description": description,
            "raw_score": raw_score,
            "keywords_matched": [],
            "severity": classify_severity(raw_score),
        })
        signals.append(signal)
    return signals


def normalize_cloudflare(anomalies: list) -> list[dict]:
    """
    Normalise Cloudflare Radar traffic anomaly records into the unified schema.

    Args:
        anomalies: List of anomaly location dicts from Cloudflare.

    Returns:
        List of normalised signal dicts.
    """
    signals = []
    for item in anomalies:
        if not isinstance(item, dict):
            continue
        location = item.get("alpha2") or item.get("location") or "Unknown"
        lat, lon = _coords_for_country(location)
        title = truncate_text(f"Network anomaly detected in {location}", 100)
        description = truncate_text(
            f"Cloudflare Radar detected traffic anomaly in {location}. "
            f"Potential network disruption or shutdown. Details: {item}",
            500,
        )
        signal = _fill_defaults({
            "id": generate_id(),
            "timestamp": now_iso(),
            "type": "network",
            "source": "Cloudflare Radar",
            "location": location,
            "latitude": float(lat),
            "longitude": float(lon),
            "title": title,
            "description": description,
            "raw_score": 0.0,
            "keywords_matched": [],
            "severity": "LOW",
        })
        signals.append(signal)
    return signals


def normalize_mock(signals: list) -> list[dict]:
    """
    Pass-through normaliser for mock / pre-built signals.

    Validates all required fields and fills defaults for any missing ones.

    Args:
        signals: List of signal dicts (already close to schema).

    Returns:
        Validated and completed list of signal dicts.
    """
    result = []
    for sig in signals:
        if not isinstance(sig, dict):
            continue
        sig = _fill_defaults(sig)
        # Coerce numeric fields
        sig["latitude"] = float(sig["latitude"])
        sig["longitude"] = float(sig["longitude"])
        sig["raw_score"] = float(sig["raw_score"])
        result.append(sig)
    return result


# ---------------------------------------------------------------------------
# DataProcessor orchestrator
# ---------------------------------------------------------------------------

class DataProcessor:
    """
    Transforms raw collector output into a deduplicated, validated list of
    unified-schema signals.
    """

    SOURCE_NORMALISERS = {
        "newsapi": normalize_newsapi,
        "gdelt": normalize_gdelt,
        "opensky": normalize_opensky,
        "firms": normalize_firms,
        "cloudflare": normalize_cloudflare,
        "social": normalize_mock,
        "netblocks": normalize_mock,
    }

    def process_all(self, raw_data: dict) -> list[dict]:
        """
        Normalise all raw source data and return merged, deduplicated signals.

        Args:
            raw_data: Dict mapping source key → list of raw records.

        Returns:
            Merged list of validated, normalised signal dicts.
        """
        all_signals: list[dict] = []
        seen_ids: set[str] = set()

        for source_key, records in raw_data.items():
            if source_key.startswith("_"):
                continue  # skip metadata like "_status"
            normaliser = self.SOURCE_NORMALISERS.get(source_key)
            if normaliser is None:
                logger.warning(f"No normaliser for source key '{source_key}' — skipping.")
                continue

            try:
                normalised = normaliser(records)
            except Exception as exc:
                logger.error(f"Normalisation failed for '{source_key}': {exc}")
                continue

            for sig in normalised:
                if not _validate_signal(sig):
                    sig = _fill_defaults(sig)
                sig_id = sig["id"]
                if sig_id in seen_ids:
                    continue
                seen_ids.add(sig_id)
                all_signals.append(sig)

        logger.info(f"DataProcessor: {len(all_signals)} signals after deduplication.")
        return all_signals


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from mock_data_generator import generate_all_mock_signals

    print("=== data_processor.py self-test ===\n")

    # Build fake raw_data dict
    mock_signals = generate_all_mock_signals()
    raw_data = {
        "social": [s for s in mock_signals if s["source"] == "Social/Mock"],
        "netblocks": [s for s in mock_signals if s["source"] == "NetBlocks"],
        "newsapi": [],   # empty — will get normalised to nothing
        "gdelt": [],
        "opensky": [],
        "firms": [],
        "cloudflare": [],
    }

    processor = DataProcessor()
    signals = processor.process_all(raw_data)

    print(f"Total processed signals: {len(signals)}\n")
    print("Sample 3 signals:")
    for sig in signals[:3]:
        print(json.dumps(sig, indent=2))
        print()

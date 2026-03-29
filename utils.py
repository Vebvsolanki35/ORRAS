"""
utils.py — Shared helper utilities for the ORRAS system.

Provides: ID generation, timestamps, logging, JSON I/O, severity
classification, geographic distance, and text truncation.
"""

import json
import logging
import math
import os
import uuid
from datetime import datetime, timezone
from typing import Any

from config import RISK_THRESHOLDS, DISASTER_THRESHOLDS


# ---------------------------------------------------------------------------
# ID & time
# ---------------------------------------------------------------------------

def generate_id() -> str:
    """Return a random UUID4 string."""
    return str(uuid.uuid4())


def now_iso() -> str:
    """Return the current UTC time formatted as an ISO 8601 string."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------

def get_logger(name: str) -> logging.Logger:
    """
    Return a configured logger that writes to both console and 'orras.log'.

    Args:
        name: Typically the module's __name__.

    Returns:
        A logging.Logger instance.
    """
    logger = logging.getLogger(name)
    if logger.handlers:
        # Avoid adding duplicate handlers if called multiple times
        return logger

    logger.setLevel(logging.DEBUG)
    fmt = logging.Formatter(
        "%(asctime)s [%(levelname)s] %(name)s — %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    # Console handler
    ch = logging.StreamHandler()
    ch.setLevel(logging.INFO)
    ch.setFormatter(fmt)
    logger.addHandler(ch)

    # File handler
    fh = logging.FileHandler("orras.log", encoding="utf-8")
    fh.setLevel(logging.DEBUG)
    fh.setFormatter(fmt)
    logger.addHandler(fh)

    return logger


# ---------------------------------------------------------------------------
# JSON I/O
# ---------------------------------------------------------------------------

def load_json(filepath: str) -> list:
    """
    Safely load a JSON file.

    Returns an empty list if the file does not exist or contains invalid JSON.

    Args:
        filepath: Path to the JSON file.

    Returns:
        Parsed data, or [] on any error.
    """
    if not os.path.exists(filepath):
        return []
    try:
        with open(filepath, "r", encoding="utf-8") as f:
            return json.load(f)
    except (json.JSONDecodeError, OSError):
        return []


def save_json(filepath: str, data: Any) -> None:
    """
    Atomically save *data* to a JSON file with pretty-printing.

    Writes to a temporary file first, then replaces the target to avoid
    partial writes on crash.

    Args:
        filepath: Destination path.
        data: JSON-serialisable Python object.
    """
    tmp_path = filepath + ".tmp"
    with open(tmp_path, "w", encoding="utf-8") as f:
        json.dump(data, f, indent=2, ensure_ascii=False)
    os.replace(tmp_path, filepath)


# ---------------------------------------------------------------------------
# Severity classification
# ---------------------------------------------------------------------------

def classify_disaster_severity(score: float) -> str:
    """Map a numeric score to a disaster severity label."""
    thresholds = DISASTER_THRESHOLDS
    catastrophic_min = thresholds["CATASTROPHIC"][0]  # 20
    severe_min = thresholds["SEVERE"][0]              # 10
    moderate_min = thresholds["MODERATE"][0]          # 5

    if score >= catastrophic_min:
        return "CATASTROPHIC"
    if score >= severe_min:
        return "SEVERE"
    if score >= moderate_min:
        return "MODERATE"
    return "MINOR"


def safe_float(val: Any, default: float = 0.0) -> float:
    """Safely convert a value to float, returning *default* on failure."""
    try:
        return float(val)
    except (TypeError, ValueError):
        return default


def days_ago(n: int) -> str:
    """Return an ISO 8601 UTC string for *n* days in the past."""
    from datetime import timedelta
    return (datetime.now(timezone.utc) - timedelta(days=n)).isoformat()


# ---------------------------------------------------------------------------
# Country coordinates lookup
# ---------------------------------------------------------------------------

COUNTRY_COORDINATES: dict[str, tuple[float, float]] = {
    "Afghanistan":          (33.9391, 67.7100),
    "Algeria":              (28.0339, 1.6596),
    "Argentina":            (-38.4161, -63.6167),
    "Armenia":              (40.0691, 45.0382),
    "Australia":            (-25.2744, 133.7751),
    "Azerbaijan":           (40.1431, 47.5769),
    "Bangladesh":           (23.6850, 90.3563),
    "Belarus":              (53.7098, 27.9534),
    "Brazil":               (-14.2350, -51.9253),
    "Burma (Myanmar)":      (21.9162, 95.9560),
    "Cambodia":             (12.5657, 104.9910),
    "Cameroon":             (7.3697, 12.3547),
    "Canada":               (56.1304, -106.3468),
    "Central African Rep.": (6.6111, 20.9394),
    "Chad":                 (15.4542, 18.7322),
    "Chile":                (-35.6751, -71.5430),
    "China":                (35.8617, 104.1954),
    "Colombia":             (4.5709, -74.2973),
    "Congo (DRC)":          (-4.0383, 21.7587),
    "Cuba":                 (21.5218, -77.7812),
    "Egypt":                (26.8206, 30.8025),
    "Ethiopia":             (9.1450, 40.4897),
    "France":               (46.2276, 2.2137),
    "Germany":              (51.1657, 10.4515),
    "Ghana":                (7.9465, -1.0232),
    "Greece":               (39.0742, 21.8243),
    "Haiti":                (18.9712, -72.2852),
    "India":                (20.5937, 78.9629),
    "Indonesia":            (-0.7893, 113.9213),
    "Iran":                 (32.4279, 53.6880),
    "Iraq":                 (33.2232, 43.6793),
    "Israel":               (31.0461, 34.8516),
    "Japan":                (36.2048, 138.2529),
    "Jordan":               (30.5852, 36.2384),
    "Kazakhstan":           (48.0196, 66.9237),
    "Kenya":                (-0.0236, 37.9062),
    "Kuwait":               (29.3117, 47.4818),
    "Lebanon":              (33.8547, 35.8623),
    "Libya":                (26.3351, 17.2283),
    "Mali":                 (17.5707, -3.9962),
    "Mexico":               (23.6345, -102.5528),
    "Morocco":              (31.7917, -7.0926),
    "Mozambique":           (-18.6657, 35.5296),
    "Niger":                (17.6078, 8.0817),
    "Nigeria":              (9.0820, 8.6753),
    "North Korea":          (40.3399, 127.5101),
    "Pakistan":             (30.3753, 69.3451),
    "Palestine":            (31.9522, 35.2332),
    "Peru":                 (-9.1900, -75.0152),
    "Philippines":          (12.8797, 121.7740),
    "Russia":               (61.5240, 105.3188),
    "Saudi Arabia":         (23.8859, 45.0792),
    "Somalia":              (5.1521, 46.1996),
    "South Africa":         (-30.5595, 22.9375),
    "South Korea":          (35.9078, 127.7669),
    "South Sudan":          (6.8770, 31.3070),
    "Spain":                (40.4637, -3.7492),
    "Sri Lanka":            (7.8731, 80.7718),
    "Sudan":                (12.8628, 30.2176),
    "Syria":                (34.8021, 38.9968),
    "Taiwan":               (23.6978, 120.9605),
    "Thailand":             (15.8700, 100.9925),
    "Turkey":               (38.9637, 35.2433),
    "Uganda":               (1.3733, 32.2903),
    "Ukraine":              (48.3794, 31.1656),
    "United Kingdom":       (55.3781, -3.4360),
    "United States":        (37.0902, -95.7129),
    "Venezuela":            (6.4238, -66.5897),
    "Vietnam":              (14.0583, 108.2772),
    "Yemen":                (15.5527, 48.5164),
    "Zimbabwe":             (-19.0154, 29.1549),
}


def classify_risk_level(score: float) -> str:
    """
    Map a numeric score to a severity label.

    Uses boundary comparisons so floating-point scores between the integer
    boundaries defined in RISK_THRESHOLDS (e.g. 5.5, 10.3) are classified
    correctly rather than falling through to an incorrect default.

    Args:
        score: A numeric risk score (typically 0–30).

    Returns:
        One of "LOW", "MEDIUM", "HIGH", or "CRITICAL".
    """
    # Retrieve boundary integers from config (LOW≤5, MEDIUM 6-10, HIGH 11-20, CRITICAL≥21)
    # Use >= comparisons from highest to lowest to handle fractional scores in gaps.
    thresholds = RISK_THRESHOLDS
    critical_min = thresholds["CRITICAL"][0]   # 21
    high_min = thresholds["HIGH"][0]           # 11
    medium_min = thresholds["MEDIUM"][0]       # 6

    if score >= critical_min:
        return "CRITICAL"
    if score >= high_min:
        return "HIGH"
    if score >= medium_min:
        return "MEDIUM"
    return "LOW"


# Alias for backward compatibility
classify_severity = classify_risk_level


# ---------------------------------------------------------------------------
# Geography
# ---------------------------------------------------------------------------

def haversine_distance(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Calculate the great-circle distance between two points on Earth.

    Args:
        lat1, lon1: Latitude and longitude of the first point (degrees).
        lat2, lon2: Latitude and longitude of the second point (degrees).

    Returns:
        Distance in kilometres.
    """
    R = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)

    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return R * c


# ---------------------------------------------------------------------------
# Text
# ---------------------------------------------------------------------------

def truncate_text(text: str, max_chars: int = 300) -> str:
    """
    Safely truncate *text* to at most *max_chars* characters.

    Appends '…' when truncation occurs.

    Args:
        text: Input string (may be None).
        max_chars: Maximum allowed length including the ellipsis.

    Returns:
        Truncated string.
    """
    if not text:
        return ""
    text = str(text)
    if len(text) <= max_chars:
        return text
    return text[: max_chars - 1] + "…"


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== utils.py self-test ===\n")

    uid = generate_id()
    print(f"generate_id()       → {uid}")
    assert len(uid) == 36, "UUID should be 36 chars"

    ts = now_iso()
    print(f"now_iso()           → {ts}")
    assert "T" in ts, "Timestamp should contain 'T'"

    log = get_logger("test")
    log.info("Logger works!")
    print("get_logger()        → Logger created, message logged.")

    # JSON round-trip
    test_path = "/tmp/orras_utils_test.json"
    test_data = [{"key": "value", "num": 42}]
    save_json(test_path, test_data)
    loaded = load_json(test_path)
    assert loaded == test_data, f"Round-trip failed: {loaded}"
    print(f"save_json / load_json → OK ({test_path})")

    # Missing file returns []
    assert load_json("/tmp/nonexistent_orras.json") == []
    print("load_json (missing) → [] ✓")

    scores = [0, 5, 5.5, 6, 10, 10.5, 11, 20, 21, 100]
    expected = ["LOW", "LOW", "LOW", "MEDIUM", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL"]
    for s, e in zip(scores, expected):
        result = classify_severity(s)
        assert result == e, f"Score {s}: expected {e}, got {result}"
    print(f"classify_severity() → {[classify_severity(s) for s in scores]}")

    d_scores = [0, 4, 5, 9, 10, 19, 20, 50]
    d_expected = ["MINOR", "MINOR", "MODERATE", "MODERATE", "SEVERE", "SEVERE", "CATASTROPHIC", "CATASTROPHIC"]
    for s, e in zip(d_scores, d_expected):
        result = classify_disaster_severity(s)
        assert result == e, f"Score {s}: expected {e}, got {result}"
    print(f"classify_disaster_severity() → {[classify_disaster_severity(s) for s in d_scores]}")

    assert safe_float("3.14") == 3.14
    assert safe_float(None) == 0.0
    assert safe_float("bad", 99.0) == 99.0
    print("safe_float()        → OK ✓")

    da = days_ago(7)
    assert "T" in da
    print(f"days_ago(7)         → {da}")

    dist = haversine_distance(51.5, -0.1, 48.8, 2.3)  # London → Paris
    print(f"haversine_distance(London→Paris) → {dist:.1f} km (expected ~341 km)")
    assert 330 < dist < 360, f"Unexpected distance: {dist}"

    short = truncate_text("Hello", 300)
    long_text = "A" * 400
    trunc = truncate_text(long_text, 300)
    assert short == "Hello"
    assert len(trunc) == 300
    print(f"truncate_text()     → short OK, long truncated to {len(trunc)} chars ✓")

    assert "Ukraine" in COUNTRY_COORDINATES
    assert len(COUNTRY_COORDINATES) >= 60
    print(f"COUNTRY_COORDINATES → {len(COUNTRY_COORDINATES)} entries ✓")

    print("\n✅ All utils.py tests passed.")

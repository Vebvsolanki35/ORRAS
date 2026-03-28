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

from config import RISK_THRESHOLDS


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

def classify_severity(score: float) -> str:
    """
    Map a numeric score to a severity label using RISK_THRESHOLDS.

    Args:
        score: A numeric risk score (typically 0–30).

    Returns:
        One of "LOW", "MEDIUM", "HIGH", or "CRITICAL".
    """
    for level, (low, high) in RISK_THRESHOLDS.items():
        if low <= score <= high:
            return level
    return "CRITICAL"


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

    scores = [0, 5, 6, 10, 11, 20, 21, 100]
    expected = ["LOW", "LOW", "MEDIUM", "MEDIUM", "HIGH", "HIGH", "CRITICAL", "CRITICAL"]
    for s, e in zip(scores, expected):
        result = classify_severity(s)
        assert result == e, f"Score {s}: expected {e}, got {result}"
    print(f"classify_severity() → {[classify_severity(s) for s in scores]}")

    dist = haversine_distance(51.5, -0.1, 48.8, 2.3)  # London → Paris
    print(f"haversine_distance(London→Paris) → {dist:.1f} km (expected ~341 km)")
    assert 330 < dist < 360, f"Unexpected distance: {dist}"

    short = truncate_text("Hello", 300)
    long_text = "A" * 400
    trunc = truncate_text(long_text, 300)
    assert short == "Hello"
    assert len(trunc) == 300
    print(f"truncate_text()     → short OK, long truncated to {len(trunc)} chars ✓")

    print("\n✅ All utils.py tests passed.")

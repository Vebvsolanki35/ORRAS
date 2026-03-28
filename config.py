"""
config.py — Single source of truth for all ORRAS constants and configuration.

Reads sensitive values from the environment (via python-dotenv) and exposes
all thresholds, weights, and file-path constants used across every module.
"""

import os
from dotenv import load_dotenv

# Load variables from a local .env file if present
load_dotenv()

# ---------------------------------------------------------------------------
# API keys & mode flags
# ---------------------------------------------------------------------------
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")
NASA_FIRMS_KEY: str = os.getenv("NASA_FIRMS_KEY", "")
OFFLINE_MODE: bool = os.getenv("OFFLINE_MODE", "false").lower() == "true"

# ---------------------------------------------------------------------------
# Base URLs for the six data sources
# ---------------------------------------------------------------------------
NEWSAPI_URL: str = "https://newsapi.org/v2/everything"
GDELT_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
OPENSKY_URL: str = "https://opensky-network.org/api/states/all"
NASA_FIRMS_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
CLOUDFLARE_RADAR_URL: str = (
    "https://api.cloudflare.com/client/v4/radar/traffic-anomalies/locations"
)
NETBLOCKS_URL: str = "https://api.netblocks.org/v1/report"  # illustrative

# ---------------------------------------------------------------------------
# Keyword weights — positive weights signal risk, negative weights reduce it
# ---------------------------------------------------------------------------
KEYWORD_WEIGHTS: dict[str, int] = {
    "attack": 10,
    "missile": 10,
    "airstrike": 10,
    "bombing": 10,
    "troops": 7,
    "deployment": 7,
    "mobilization": 7,
    "protest": 5,
    "riot": 5,
    "unrest": 5,
    "shutdown": 6,
    "blackout": 6,
    "disruption": 6,
    "drill": 2,
    "exercise": 2,
    "ceasefire": -3,
    "peace": -3,
    "treaty": -3,
}

# ---------------------------------------------------------------------------
# Source reliability multipliers — applied to raw keyword scores
# ---------------------------------------------------------------------------
SOURCE_MULTIPLIERS: dict[str, float] = {
    "NASA FIRMS": 1.3,
    "GDELT": 1.2,
    "OpenSky": 1.1,
    "NewsAPI": 1.0,
    "NetBlocks": 0.9,
    "Cloudflare Radar": 0.9,
    "Social/Mock": 0.6,
}

# ---------------------------------------------------------------------------
# Risk level thresholds — (inclusive_min, inclusive_max)
# ---------------------------------------------------------------------------
RISK_THRESHOLDS: dict[str, tuple] = {
    "LOW": (0, 5),
    "MEDIUM": (6, 10),
    "HIGH": (11, 20),
    "CRITICAL": (21, float("inf")),
}

# ---------------------------------------------------------------------------
# Correlation bonuses for co-occurring signal types within a region window
# Keys are frozensets so order doesn't matter during lookup.
# ---------------------------------------------------------------------------
CORRELATION_BONUSES: dict[tuple, int] = {
    ("troop_movement", "network_shutdown"): 15,
    ("news_conflict", "satellite_fire", "troop_movement"): 25,
    ("network_shutdown", "social_unrest"): 10,
    ("aircraft_anomaly", "naval_movement"): 12,
}

# ---------------------------------------------------------------------------
# Statistical anomaly detection
# ---------------------------------------------------------------------------
Z_SCORE_THRESHOLD: float = 2.0
ROLLING_WINDOW_DAYS: int = 7

# ---------------------------------------------------------------------------
# Escalation tracking
# ---------------------------------------------------------------------------
ESCALATION_WINDOW_HOURS: int = 72
ESCALATION_LEVEL_JUMP: int = 2

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_REFRESH_SECONDS: int = 60

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------
DATA_DIR: str = "data/"
SIGNALS_FILE: str = "data/signals.json"
ESCALATION_FILE: str = "data/escalation_history.json"
ALERT_LOG_FILE: str = "data/alert_log.json"

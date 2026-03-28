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
ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
AI_MODEL: str = "claude-opus-4-5"
NEWSAPI_KEY: str = os.getenv("NEWSAPI_KEY", "")
NASA_FIRMS_KEY: str = os.getenv("NASA_FIRMS_KEY", "")
ACLED_KEY: str = os.getenv("ACLED_KEY", "")
ACLED_EMAIL: str = os.getenv("ACLED_EMAIL", "")
OFFLINE_MODE: bool = os.getenv("OFFLINE_MODE", "false").lower() == "true"
AI_FEATURES_ENABLED: bool = os.getenv("AI_FEATURES_ENABLED", "true").lower() == "true"

# ---------------------------------------------------------------------------
# Base URLs for data sources
# ---------------------------------------------------------------------------
NEWSAPI_URL: str = "https://newsapi.org/v2/everything"
GDELT_URL: str = "https://api.gdeltproject.org/api/v2/doc/doc"
OPENSKY_URL: str = "https://opensky-network.org/api/states/all"
FIRMS_URL: str = "https://firms.modaps.eosdis.nasa.gov/api/area/csv/"
NASA_FIRMS_URL: str = FIRMS_URL  # backward-compat alias
CLOUDFLARE_URL: str = "https://api.cloudflare.com/client/v4/radar/traffic-anomalies/locations"
CLOUDFLARE_RADAR_URL: str = CLOUDFLARE_URL  # backward-compat alias
NETBLOCKS_URL: str = "https://api.netblocks.org/v1/report"
USGS_URL: str = "https://earthquake.usgs.gov/earthquakes/feed/v1.0/summary/significant_week.geojson"
NOAA_URL: str = "https://api.weather.gov/alerts/active"
RELIEFWEB_URL: str = "https://api.reliefweb.int/v1/disasters"
ACLED_URL: str = "https://api.acleddata.com/acled/read"

# ---------------------------------------------------------------------------
# Keyword weights — Conflict
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
    "coup": 8,
    "assassination": 9,
    "martial law": 8,
    "cyberattack": 9,
    "ransomware": 8,
    "hack": 7,
}

# ---------------------------------------------------------------------------
# Keyword weights — Disaster
# ---------------------------------------------------------------------------
DISASTER_KEYWORD_WEIGHTS: dict[str, int] = {
    "magnitude 7+": 15,
    "catastrophic": 12,
    "mass casualty": 12,
    "category 5": 11,
    "category 4": 9,
    "tsunami": 10,
    "earthquake": 7,
    "hurricane": 7,
    "cyclone": 7,
    "typhoon": 7,
    "volcanic": 8,
    "eruption": 8,
    "flood": 6,
    "wildfire": 6,
    "outbreak": 6,
    "epidemic": 7,
    "famine": 6,
    "refugee": 4,
    "evacuation": 5,
    "rescue": 4,
    "casualties": 6,
    "deaths": 5,
    "missing": 3,
    "contained": -3,
    "recovery": -2,
    "aid delivered": -2,
}

# ---------------------------------------------------------------------------
# Source base weights
# ---------------------------------------------------------------------------
BASE_WEIGHTS: dict[str, float] = {
    "ACLED": 5.0,
    "GDELT": 4.0,
    "NetBlocks": 5.0,
    "NASA FIRMS": 4.0,
    "NewsAPI": 2.0,
    "Social/Mock": 1.0,
    "OpenSky": 3.0,
    "Cloudflare Radar": 3.5,
    "USGS": 4.5,
    "NOAA": 4.0,
    "ReliefWeb": 3.5,
    "WHO": 4.5,
    "OCHA": 4.0,
}

# ---------------------------------------------------------------------------
# Source reliability multipliers — applied to raw keyword scores
# ---------------------------------------------------------------------------
SOURCE_MULTIPLIERS: dict[str, float] = {
    "NASA FIRMS": 1.3,
    "USGS": 1.3,
    "GDELT": 1.2,
    "NOAA": 1.2,
    "WHO": 1.2,
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
# Disaster severity thresholds
# ---------------------------------------------------------------------------
DISASTER_THRESHOLDS: dict[str, tuple] = {
    "MINOR": (0, 4),
    "MODERATE": (5, 9),
    "SEVERE": (10, 19),
    "CATASTROPHIC": (20, float("inf")),
}

# ---------------------------------------------------------------------------
# Correlation bonuses for co-occurring signal types within a region window
# ---------------------------------------------------------------------------
CORRELATION_BONUSES: dict[tuple, int] = {
    ("troop_movement", "network_shutdown"): 15,
    ("news_conflict", "satellite_fire", "troop_movement"): 25,
    ("network_shutdown", "social_unrest"): 10,
    ("aircraft_anomaly", "naval_movement"): 12,
}

# ---------------------------------------------------------------------------
# Fusion weights
# ---------------------------------------------------------------------------
CONFLICT_WEIGHT: float = 0.6
DISASTER_WEIGHT: float = 0.4

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
# Forecasting
# ---------------------------------------------------------------------------
FORECAST_DAYS: int = 3
MIN_HISTORY_DAYS: int = 3

# ---------------------------------------------------------------------------
# Geofence Zones
# ---------------------------------------------------------------------------
GEOFENCE_ZONES: dict[str, dict] = {
    "Taiwan Strait":    {"lat": 23.5, "lon": 120.0, "radius_km": 300,  "priority": "CRITICAL"},
    "South China Sea":  {"lat": 14.0, "lon": 114.0, "radius_km": 500,  "priority": "HIGH"},
    "Ukraine Border":   {"lat": 49.0, "lon": 32.0,  "radius_km": 200,  "priority": "CRITICAL"},
    "Korean DMZ":       {"lat": 38.0, "lon": 127.0, "radius_km": 100,  "priority": "HIGH"},
    "Strait of Hormuz": {"lat": 26.5, "lon": 56.5,  "radius_km": 150,  "priority": "HIGH"},
    "Gaza Strip":       {"lat": 31.4, "lon": 34.4,  "radius_km": 50,   "priority": "CRITICAL"},
    "Kashmir LoC":      {"lat": 34.0, "lon": 74.0,  "radius_km": 200,  "priority": "HIGH"},
    "Sahel Region":     {"lat": 15.0, "lon": 0.0,   "radius_km": 800,  "priority": "HIGH"},
}

# ---------------------------------------------------------------------------
# Resources
# ---------------------------------------------------------------------------
RESOURCE_REGISTRY: dict[str, dict] = {
    "rescue_team":        {"count": 10, "capacity": 20,   "type": "disaster"},
    "ambulance":          {"count": 15, "capacity": 1,    "type": "disaster"},
    "helicopter":         {"count": 5,  "capacity": 8,    "type": "both"},
    "field_hospital":     {"count": 3,  "capacity": 100,  "type": "disaster"},
    "water_supply":       {"count": 20, "capacity": 500,  "type": "disaster"},
    "food_ration":        {"count": 50, "capacity": 1000, "type": "disaster"},
    "emergency_shelter":  {"count": 8,  "capacity": 200,  "type": "disaster"},
    "surveillance_drone": {"count": 8,  "capacity": 1,    "type": "conflict"},
    "security_team":      {"count": 12, "capacity": 10,   "type": "conflict"},
    "comms_unit":         {"count": 6,  "capacity": 50,   "type": "conflict"},
    "evacuation_bus":     {"count": 10, "capacity": 50,   "type": "both"},
    "satellite_link":     {"count": 4,  "capacity": 1,    "type": "both"},
    "command_center":     {"count": 2,  "capacity": 30,   "type": "both"},
}

# ---------------------------------------------------------------------------
# Dashboard
# ---------------------------------------------------------------------------
DASHBOARD_REFRESH_SECONDS: int = 60
MAX_ALERTS_DISPLAYED: int = 20
ALERT_DEDUP_WINDOW_MINUTES: int = 60

# ---------------------------------------------------------------------------
# Data file paths
# ---------------------------------------------------------------------------
DATA_DIR: str = "data/"
SIGNALS_FILE: str = "data/signals.json"
ESCALATION_FILE: str = "data/escalation_history.json"
ALERT_LOG_FILE: str = "data/alert_log.json"
DB_PATH: str = "data/orras.db"
DB_CLEANUP_DAYS: int = 90

# ---------------------------------------------------------------------------
# Safety Engine
# ---------------------------------------------------------------------------
SAFETY_SCORE_WEIGHTS: dict[str, float] = {
    "cyber": 0.20,
    "nuclear": 0.25,
    "infrastructure": 0.20,
    "maritime": 0.10,
    "economic": 0.15,
    "humanitarian": 0.10,
}

# ---------------------------------------------------------------------------
# Prediction Engine
# ---------------------------------------------------------------------------
FORECAST_CONFIDENCE_THRESHOLD: float = 0.6

# ---------------------------------------------------------------------------
# Report Engine
# ---------------------------------------------------------------------------
REPORTS_DIR: str = "data/reports/"
MAX_REPORT_SIGNALS: int = 100

# ---------------------------------------------------------------------------
# UI
# ---------------------------------------------------------------------------
THEME_DEFAULT: str = "Dark"
TICKER_SPEED_SECONDS: int = 30
GLOBE_DEFAULT_CENTER: dict = {"lat": 20, "lon": 0}
GLOBE_ROTATION_SPEED: float = 0.5

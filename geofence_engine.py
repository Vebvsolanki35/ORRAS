"""
geofence_engine.py — Geofence zone tagging for ORRAS signals.

Checks each signal's latitude/longitude against the GEOFENCE_ZONES defined
in config.py and tags signals with the zones they fall within.
"""

import math
from typing import Any

from config import GEOFENCE_ZONES
from utils import get_logger

logger = get_logger(__name__)


def haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """
    Compute the great-circle distance in kilometres between two points.

    Args:
        lat1, lon1: Coordinates of point 1 (degrees).
        lat2, lon2: Coordinates of point 2 (degrees).

    Returns:
        Distance in kilometres.
    """
    r = 6371.0  # Earth radius in km
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlambda = math.radians(lon2 - lon1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlambda / 2) ** 2
    return r * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


# Priority ordering for severity escalation
_PRIORITY_ORDER = {"CRITICAL": 3, "HIGH": 2, "MEDIUM": 1, "LOW": 0}


class GeofenceEngine:
    """
    Tags signals with geofence zones and computes zone-level activity metrics.

    A signal is inside a zone when:
        haversine_km(signal_lat, signal_lon, zone_lat, zone_lon) <= zone_radius_km
    """

    def __init__(self, zones: dict[str, dict] | None = None) -> None:
        self.zones = zones or GEOFENCE_ZONES

    def get_zones_for_signal(self, signal: dict) -> list[str]:
        """
        Return the names of all geofence zones that contain this signal.

        Args:
            signal: Signal dict with 'latitude' and 'longitude' keys.

        Returns:
            List of zone names (may be empty).
        """
        lat = float(signal.get("latitude") or 0.0)
        lon = float(signal.get("longitude") or 0.0)

        if lat == 0.0 and lon == 0.0:
            return []

        matched: list[str] = []
        for zone_name, zone in self.zones.items():
            dist = haversine_km(lat, lon, zone["lat"], zone["lon"])
            if dist <= zone["radius_km"]:
                matched.append(zone_name)
        return matched

    def tag_signal(self, signal: dict) -> dict:
        """
        Add 'geofence_zones' and 'in_critical_zone' fields to a signal.

        Args:
            signal: Signal dict (modified in-place).

        Returns:
            Updated signal dict.
        """
        zones = self.get_zones_for_signal(signal)
        signal["geofence_zones"] = zones

        # Check if any matched zone is CRITICAL priority
        in_critical = any(
            self.zones.get(z, {}).get("priority") == "CRITICAL" for z in zones
        )
        signal["in_critical_zone"] = in_critical
        return signal

    def tag_all(self, signals: list[dict]) -> list[dict]:
        """
        Tag all signals with their geofence zones.

        Args:
            signals: List of signal dicts.

        Returns:
            Updated list with geofence_zones and in_critical_zone on each signal.
        """
        result = [self.tag_signal(s) for s in signals]
        in_zone = sum(1 for s in result if s.get("geofence_zones"))
        in_critical = sum(1 for s in result if s.get("in_critical_zone"))
        logger.info(
            f"GeofenceEngine: tagged {len(result)} signals — "
            f"{in_zone} in a zone, {in_critical} in a CRITICAL zone."
        )
        return result

    def get_zone_activity(self, signals: list[dict]) -> list[dict]:
        """
        Compute signal counts and max severity per geofence zone.

        Args:
            signals: List of tagged signal dicts.

        Returns:
            List of zone activity dicts sorted by signal count descending:
            [{zone, priority, signal_count, critical_count, max_severity}]
        """
        activity: dict[str, dict[str, Any]] = {}

        for sig in signals:
            for zone_name in sig.get("geofence_zones", []):
                if zone_name not in activity:
                    activity[zone_name] = {
                        "zone": zone_name,
                        "priority": self.zones.get(zone_name, {}).get("priority", "LOW"),
                        "signal_count": 0,
                        "critical_count": 0,
                        "max_fusion_score": 0.0,
                    }
                entry = activity[zone_name]
                entry["signal_count"] += 1

                sev = sig.get("fusion_severity") or sig.get("severity", "LOW")
                if sev == "CRITICAL":
                    entry["critical_count"] += 1

                score = float(sig.get("fusion_score") or sig.get("raw_score") or 0.0)
                if score > entry["max_fusion_score"]:
                    entry["max_fusion_score"] = score

        result = list(activity.values())
        result.sort(key=lambda z: z["signal_count"], reverse=True)
        return result

    def get_critical_zone_signals(self, signals: list[dict]) -> list[dict]:
        """
        Return only signals that fall within a CRITICAL priority zone.

        Args:
            signals: List of tagged signal dicts.

        Returns:
            Filtered list of signals inside CRITICAL zones.
        """
        return [s for s in signals if s.get("in_critical_zone")]


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== geofence_engine.py self-test ===\n")

    test_signals = [
        # Inside Ukraine Border zone (lat=49.0, lon=32.0, r=200km)
        {"id": "g-001", "title": "Shelling near Kyiv", "latitude": 50.45, "longitude": 30.52,
         "raw_score": 18.0, "fusion_score": 14.0, "fusion_severity": "HIGH"},
        # Inside Taiwan Strait zone
        {"id": "g-002", "title": "Military exercises", "latitude": 24.0, "longitude": 121.0,
         "raw_score": 12.0, "fusion_score": 9.0, "fusion_severity": "MEDIUM"},
        # Inside Gaza Strip zone
        {"id": "g-003", "title": "Airstrike reported", "latitude": 31.5, "longitude": 34.5,
         "raw_score": 22.0, "fusion_score": 20.0, "fusion_severity": "CRITICAL"},
        # Not in any zone
        {"id": "g-004", "title": "Minor protest", "latitude": 51.5, "longitude": -0.1,
         "raw_score": 3.0, "fusion_score": 2.0, "fusion_severity": "LOW"},
        # Zero coordinates (no geolocation)
        {"id": "g-005", "title": "Unknown location event", "latitude": 0.0, "longitude": 0.0,
         "raw_score": 5.0, "fusion_score": 4.0, "fusion_severity": "LOW"},
    ]

    engine = GeofenceEngine()
    tagged = engine.tag_all(test_signals)

    print("Tagged signals:")
    for sig in tagged:
        print(
            f"  [{sig['id']}] zones={sig['geofence_zones']}  "
            f"in_critical={sig['in_critical_zone']}"
        )

    print("\nZone activity:")
    for za in engine.get_zone_activity(tagged):
        print(
            f"  {za['zone']:20s} priority={za['priority']:8s}  "
            f"count={za['signal_count']}  critical={za['critical_count']}  "
            f"max_score={za['max_fusion_score']}"
        )

    critical_sigs = engine.get_critical_zone_signals(tagged)
    print(f"\nSignals in CRITICAL zones: {len(critical_sigs)}")
    print("\n✅ geofence_engine.py self-test complete.")

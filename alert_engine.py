"""
alert_engine.py — Alert generation and deduplication for ORRAS.

Generates structured alert records from scored, fused, and geofenced signals.
Deduplicates alerts within a configurable time window, prioritises by severity,
and maintains an in-memory alert log with persistence to JSON.
"""

import json
import os
from datetime import datetime, timedelta, timezone
from typing import Any

from config import (
    ALERT_DEDUP_WINDOW_MINUTES,
    ALERT_LOG_FILE,
    MAX_ALERTS_DISPLAYED,
)
from utils import generate_id, get_logger, now_iso

logger = get_logger(__name__)

# Severity priority for sorting (higher = more urgent)
_SEVERITY_PRIORITY: dict[str, int] = {
    "CRITICAL": 4,
    "HIGH": 3,
    "MEDIUM": 2,
    "LOW": 1,
}

# Minimum fusion/raw scores required to generate an alert per severity level
_ALERT_SCORE_THRESHOLDS: dict[str, float] = {
    "CRITICAL": 20.0,
    "HIGH":     10.0,
    "MEDIUM":    5.0,
    "LOW":       0.0,
}


def _build_alert(signal: dict) -> dict:
    """
    Construct a structured alert record from a signal.

    Args:
        signal: A fused, geofenced signal dict.

    Returns:
        Alert dict with id, timestamp, severity, title, location,
        fusion_score, geofence_zones, source, and signal_id.
    """
    severity = (
        signal.get("fusion_severity")
        or signal.get("severity")
        or "LOW"
    ).upper()

    return {
        "id": generate_id(),
        "timestamp": now_iso(),
        "severity": severity,
        "title": signal.get("title") or "Untitled Signal",
        "location": signal.get("location") or "Unknown",
        "fusion_score": float(signal.get("fusion_score") or signal.get("raw_score") or 0.0),
        "geofence_zones": signal.get("geofence_zones") or [],
        "in_critical_zone": bool(signal.get("in_critical_zone")),
        "source": signal.get("source") or "Unknown",
        "signal_class": signal.get("signal_class") or "unclassified",
        "track": signal.get("track") or "both",
        "signal_id": signal.get("id") or "",
    }


class AlertEngine:
    """
    Generates, deduplicates, and manages alerts derived from scored signals.
    """

    def __init__(
        self,
        dedup_window_minutes: int = ALERT_DEDUP_WINDOW_MINUTES,
        max_alerts: int = MAX_ALERTS_DISPLAYED,
        log_file: str = ALERT_LOG_FILE,
    ) -> None:
        self.dedup_window_minutes = dedup_window_minutes
        self.max_alerts = max_alerts
        self.log_file = log_file
        self._alerts: list[dict] = []
        self._load_log()

    # ------------------------------------------------------------------
    # Public interface
    # ------------------------------------------------------------------

    def generate_alerts(self, signals: list[dict]) -> list[dict]:
        """
        Generate alert records from a list of fused signals.

        Only signals that meet the minimum score threshold for their severity
        are converted to alerts.  Alerts are deduplicated against the current
        alert log before being added.

        Args:
            signals: List of fused, geofenced signal dicts.

        Returns:
            List of newly generated alert dicts (not the full log).
        """
        new_alerts: list[dict] = []
        for sig in signals:
            severity = (
                sig.get("fusion_severity")
                or sig.get("severity")
                or "LOW"
            ).upper()
            score = float(sig.get("fusion_score") or sig.get("raw_score") or 0.0)
            threshold = _ALERT_SCORE_THRESHOLDS.get(severity, 0.0)

            if score < threshold:
                continue

            if self._is_duplicate(sig):
                continue

            alert = _build_alert(sig)
            self._alerts.append(alert)
            new_alerts.append(alert)

        if new_alerts:
            logger.info(f"AlertEngine: generated {len(new_alerts)} new alert(s).")
            self._save_log()

        return new_alerts

    def get_active_alerts(
        self,
        min_severity: str = "LOW",
        n: int | None = None,
    ) -> list[dict]:
        """
        Return active alerts sorted by severity (descending) then timestamp.

        Args:
            min_severity: Minimum severity to include ("LOW", "MEDIUM", "HIGH",
                          "CRITICAL").
            n: Optional limit on the number of alerts returned.

        Returns:
            Sorted list of alert dicts.
        """
        min_priority = _SEVERITY_PRIORITY.get(min_severity.upper(), 1)
        filtered = [
            a for a in self._alerts
            if _SEVERITY_PRIORITY.get(a.get("severity", "LOW"), 1) >= min_priority
        ]
        filtered.sort(
            key=lambda a: (
                -_SEVERITY_PRIORITY.get(a.get("severity", "LOW"), 0),
                a.get("timestamp", ""),
            )
        )
        if n is not None:
            return filtered[:n]
        return filtered[: self.max_alerts]

    def get_alert_counts(self) -> dict[str, int]:
        """
        Return a count of alerts per severity level.

        Returns:
            Dict: {LOW: n, MEDIUM: n, HIGH: n, CRITICAL: n}
        """
        counts: dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for alert in self._alerts:
            sev = alert.get("severity", "LOW")
            if sev in counts:
                counts[sev] += 1
        return counts

    def clear_old_alerts(self, older_than_hours: int = 24) -> int:
        """
        Remove alerts older than the specified number of hours.

        Args:
            older_than_hours: Alerts older than this are removed.

        Returns:
            Number of alerts removed.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=older_than_hours)
        before = len(self._alerts)
        self._alerts = [
            a for a in self._alerts
            if _parse_timestamp(a.get("timestamp", "")) >= cutoff
        ]
        removed = before - len(self._alerts)
        if removed:
            logger.info(f"AlertEngine: cleared {removed} old alert(s).")
            self._save_log()
        return removed

    def get_critical_zone_alerts(self) -> list[dict]:
        """
        Return all alerts that originated from a CRITICAL geofence zone.

        Returns:
            List of alert dicts where in_critical_zone is True.
        """
        return [a for a in self._alerts if a.get("in_critical_zone")]

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _is_duplicate(self, signal: dict) -> bool:
        """
        Check if an alert for this signal already exists within the dedup window.

        Two signals are considered duplicates if they share the same location
        and title within the dedup window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(minutes=self.dedup_window_minutes)
        sig_title = (signal.get("title") or "").lower()
        sig_location = (signal.get("location") or "").lower()

        for alert in self._alerts:
            if _parse_timestamp(alert.get("timestamp", "")) < cutoff:
                continue
            if (
                alert.get("title", "").lower() == sig_title
                and alert.get("location", "").lower() == sig_location
            ):
                return True
        return False

    def _load_log(self) -> None:
        """Load persisted alerts from the log file if it exists."""
        if not os.path.exists(self.log_file):
            return
        try:
            with open(self.log_file, "r", encoding="utf-8") as fh:
                data = json.load(fh)
            self._alerts = data if isinstance(data, list) else []
            logger.info(f"AlertEngine: loaded {len(self._alerts)} alert(s) from log.")
        except Exception as exc:
            logger.warning(f"AlertEngine: failed to load alert log: {exc}")
            self._alerts = []

    def _save_log(self) -> None:
        """Persist the current alert list to the log file."""
        try:
            os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
            with open(self.log_file, "w", encoding="utf-8") as fh:
                json.dump(self._alerts, fh, indent=2, default=str)
        except Exception as exc:
            logger.warning(f"AlertEngine: failed to save alert log: {exc}")


# ---------------------------------------------------------------------------
# Internal utility
# ---------------------------------------------------------------------------

def _parse_timestamp(ts: str) -> datetime:
    """Parse an ISO 8601 timestamp; return epoch on failure."""
    try:
        ts = ts.replace("Z", "+00:00")
        dt = datetime.fromisoformat(ts)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt
    except (ValueError, TypeError, AttributeError):
        return datetime(1970, 1, 1, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== alert_engine.py self-test ===\n")

    import tempfile

    with tempfile.NamedTemporaryFile(suffix=".json", delete=False) as tmp:
        tmp_log = tmp.name

    engine = AlertEngine(log_file=tmp_log, dedup_window_minutes=60, max_alerts=20)

    test_signals = [
        {
            "id": "s-001", "title": "Missile airstrike near capital",
            "location": "Kyiv, Ukraine",
            "raw_score": 22.0, "fusion_score": 20.0,
            "fusion_severity": "CRITICAL",
            "geofence_zones": ["Ukraine Border"], "in_critical_zone": True,
            "source": "NewsAPI", "signal_class": "armed_conflict", "track": "conflict",
        },
        {
            "id": "s-002", "title": "M7.1 earthquake tsunami warning",
            "location": "Pacific Coast, Japan",
            "raw_score": 8.0, "fusion_score": 18.0,
            "fusion_severity": "HIGH",
            "geofence_zones": [], "in_critical_zone": False,
            "source": "USGS", "signal_class": "earthquake", "track": "disaster",
        },
        {
            "id": "s-003", "title": "Minor protest reported",
            "location": "London, UK",
            "raw_score": 2.0, "fusion_score": 1.5,
            "fusion_severity": "LOW",
            "geofence_zones": [], "in_critical_zone": False,
            "source": "Social/Mock", "signal_class": "civil_unrest", "track": "conflict",
        },
        # Duplicate of s-001 — should be deduplicated
        {
            "id": "s-004", "title": "Missile airstrike near capital",
            "location": "Kyiv, Ukraine",
            "raw_score": 20.0, "fusion_score": 19.0,
            "fusion_severity": "CRITICAL",
            "geofence_zones": ["Ukraine Border"], "in_critical_zone": True,
            "source": "GDELT", "signal_class": "armed_conflict", "track": "conflict",
        },
    ]

    new_alerts = engine.generate_alerts(test_signals)
    print(f"New alerts generated: {len(new_alerts)}")
    for alert in new_alerts:
        print(
            f"  [{alert['severity']:8s}] {alert['title'][:40]:40s}  "
            f"score={alert['fusion_score']:5.1f}  zone={alert['geofence_zones']}"
        )

    print(f"\nActive alerts (all): {len(engine.get_active_alerts())}")
    print(f"Alert counts: {engine.get_alert_counts()}")
    print(f"Critical zone alerts: {len(engine.get_critical_zone_alerts())}")

    os.unlink(tmp_log)
    print("\n✅ alert_engine.py self-test complete.")

"""
escalation_tracker.py — Regional risk escalation tracker for ORRAS.

Maintains a time-series of region risk snapshots and alerts when a region's
severity level increases rapidly within the configured window.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from config import ESCALATION_FILE, ESCALATION_LEVEL_JUMP, ESCALATION_WINDOW_HOURS
from utils import classify_severity, get_logger, load_json, now_iso, save_json

logger = get_logger(__name__)

# Numeric mapping for severity level comparisons
SEVERITY_LEVELS = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
LEVEL_NAMES = {v: k for k, v in SEVERITY_LEVELS.items()}


class EscalationTracker:
    """
    Tracks regional risk scores over time and detects rapid escalation events.
    """

    def compute_region_risk(self, signals: list[dict]) -> dict[str, dict]:
        """
        Compute the current average risk score and severity for each region.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            Dict: {region: {"score": float, "severity": str, "timestamp": str}}
        """
        region_scores: dict[str, list[float]] = {}
        for sig in signals:
            location = sig.get("location") or "Unknown"
            score = sig.get("raw_score") or 0.0
            region_scores.setdefault(location, []).append(float(score))

        result = {}
        for region, scores in region_scores.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            result[region] = {
                "score": round(avg, 2),
                "severity": classify_severity(avg),
                "timestamp": now_iso(),
            }
        return result

    def load_history(self) -> list[dict]:
        """
        Load escalation history from the JSON file.

        Returns:
            List of snapshot dicts, or [] if file is missing/empty.
        """
        return load_json(ESCALATION_FILE)

    def save_snapshot(self, region_risk: dict[str, dict]) -> None:
        """
        Append the current region risk snapshot to the escalation history file.

        Args:
            region_risk: Output of compute_region_risk().
        """
        history = self.load_history()
        snapshot = {
            "timestamp": now_iso(),
            "regions": region_risk,
        }
        history.append(snapshot)
        save_json(ESCALATION_FILE, history)
        logger.info(f"EscalationTracker: snapshot saved ({len(region_risk)} regions).")

    def detect_rapid_escalation(self, history: list[dict]) -> list[dict]:
        """
        Scan the history for regions that escalated ≥ ESCALATION_LEVEL_JUMP
        severity levels within ESCALATION_WINDOW_HOURS hours.

        Args:
            history: List of snapshot dicts (from load_history).

        Returns:
            List of rapid-escalation alert dicts, each containing:
            {region, from_level, to_level, hours, alert}
        """
        if not history:
            return []

        cutoff = datetime.now(timezone.utc) - timedelta(hours=ESCALATION_WINDOW_HOURS)
        alerts = []

        # Gather all region entries within the window
        region_timeline: dict[str, list[tuple[datetime, int]]] = {}
        for snapshot in history:
            ts_str = snapshot.get("timestamp") or ""
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
            if ts < cutoff:
                continue
            for region, data in (snapshot.get("regions") or {}).items():
                sev = data.get("severity") or "LOW"
                level = SEVERITY_LEVELS.get(sev, 0)
                region_timeline.setdefault(region, []).append((ts, level))

        for region, entries in region_timeline.items():
            if len(entries) < 2:
                continue
            entries.sort(key=lambda x: x[0])
            first_ts, first_level = entries[0]
            last_ts, last_level = entries[-1]
            delta = last_level - first_level
            if delta >= ESCALATION_LEVEL_JUMP:
                hours_elapsed = (last_ts - first_ts).total_seconds() / 3600.0
                alerts.append({
                    "region": region,
                    "from_level": LEVEL_NAMES.get(first_level, "LOW"),
                    "to_level": LEVEL_NAMES.get(last_level, "CRITICAL"),
                    "hours": round(hours_elapsed, 1),
                    "alert": "RAPID ESCALATION",
                })
                logger.warning(
                    f"EscalationTracker: RAPID ESCALATION in {region} "
                    f"({LEVEL_NAMES.get(first_level)} → {LEVEL_NAMES.get(last_level)} "
                    f"in {hours_elapsed:.1f}h)"
                )

        return alerts

    def get_trend_data(self, region: str, days: int = 7) -> pd.DataFrame:
        """
        Return a DataFrame of daily average risk scores for a region.

        Args:
            region: Region name to look up.
            days: Number of days of history to include.

        Returns:
            DataFrame with columns: [date, avg_score, severity].
        """
        history = self.load_history()
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)

        daily_scores: dict[str, list[float]] = {}
        for snapshot in history:
            ts_str = snapshot.get("timestamp") or ""
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue
            if ts < cutoff:
                continue
            region_data = (snapshot.get("regions") or {}).get(region)
            if region_data:
                date_str = ts.date().isoformat()
                daily_scores.setdefault(date_str, []).append(
                    float(region_data.get("score") or 0.0)
                )

        rows = []
        for date_str, scores in sorted(daily_scores.items()):
            avg = sum(scores) / len(scores)
            rows.append({
                "date": date_str,
                "avg_score": round(avg, 2),
                "severity": classify_severity(avg),
            })

        return pd.DataFrame(rows, columns=["date", "avg_score", "severity"])

    def run(self, signals: list[dict]) -> dict:
        """
        Full pipeline: compute region risk, save snapshot, detect escalation.

        Args:
            signals: Current list of unified-schema signals.

        Returns:
            Summary dict with keys: region_risk, escalation_alerts.
        """
        region_risk = self.compute_region_risk(signals)
        self.save_snapshot(region_risk)
        history = self.load_history()
        alerts = self.detect_rapid_escalation(history)
        return {
            "region_risk": region_risk,
            "escalation_alerts": alerts,
        }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from mock_data_generator import generate_all_mock_signals
    from threat_engine import ThreatEngine

    print("=== escalation_tracker.py self-test ===\n")

    signals = generate_all_mock_signals()
    engine = ThreatEngine()
    scored = engine.score_all(signals)

    tracker = EscalationTracker()
    result = tracker.run(scored)

    print(f"Region risk computed for {len(result['region_risk'])} regions.")
    print(f"Rapid escalation alerts: {len(result['escalation_alerts'])}\n")

    print("Top 5 regions by score:")
    sorted_regions = sorted(
        result["region_risk"].items(), key=lambda x: x[1]["score"], reverse=True
    )
    for region, data in sorted_regions[:5]:
        print(f"  {region:25s}: score={data['score']:5.1f}  severity={data['severity']}")

    print("\nEscalation alerts:")
    for alert in result["escalation_alerts"]:
        print(f"  {alert}")

    # Test trend data
    if sorted_regions:
        top_region = sorted_regions[0][0]
        trend_df = tracker.get_trend_data(top_region)
        print(f"\nTrend data for '{top_region}':")
        print(trend_df.to_string(index=False) if not trend_df.empty else "  (no history yet)")

    print("\n✅ escalation_tracker.py self-test complete.")

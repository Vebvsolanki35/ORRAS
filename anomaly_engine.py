"""
anomaly_engine.py — Statistical anomaly detector for ORRAS.

Uses Z-score analysis over a rolling 7-day window to flag regions that show
an unusual spike in signal volume today compared to their baseline.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from config import ROLLING_WINDOW_DAYS, Z_SCORE_THRESHOLD
from utils import get_logger, now_iso

logger = get_logger(__name__)


class AnomalyEngine:
    """
    Detects statistical anomalies in signal activity by region using Z-scores.
    """

    def compute_daily_counts(self, signals: list[dict]) -> pd.DataFrame:
        """
        Count the number of signals per region per calendar day.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            DataFrame with columns: [location, date, count].
        """
        rows = []
        for sig in signals:
            ts_str = sig.get("timestamp") or ""
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            except (ValueError, AttributeError):
                ts = datetime.now(timezone.utc)
            rows.append({
                "location": sig.get("location") or "Unknown",
                "date": ts.date().isoformat(),
            })

        if not rows:
            return pd.DataFrame(columns=["location", "date", "count"])

        df = pd.DataFrame(rows)
        counts = (
            df.groupby(["location", "date"])
            .size()
            .reset_index(name="count")
        )
        return counts

    def compute_z_scores(self, df: pd.DataFrame) -> pd.DataFrame:
        """
        Compute rolling 7-day Z-scores per location.

        For each location, calculates the rolling mean and std over
        ROLLING_WINDOW_DAYS days, then computes z = (count - mean) / std.
        Fills NaN std with 1 to avoid division by zero.

        Args:
            df: DataFrame with columns [location, date, count].

        Returns:
            DataFrame with added columns: rolling_mean, rolling_std, z_score.
        """
        if df.empty:
            return df.assign(rolling_mean=[], rolling_std=[], z_score=[])

        results = []
        for location, group in df.groupby("location"):
            group = group.sort_values("date").copy()
            group["rolling_mean"] = (
                group["count"]
                .rolling(window=ROLLING_WINDOW_DAYS, min_periods=1)
                .mean()
            )
            group["rolling_std"] = (
                group["count"]
                .rolling(window=ROLLING_WINDOW_DAYS, min_periods=1)
                .std()
                .fillna(1.0)
            )
            # Avoid division by zero
            group["rolling_std"] = group["rolling_std"].replace(0, 1.0)
            group["z_score"] = (
                (group["count"] - group["rolling_mean"]) / group["rolling_std"]
            )
            results.append(group)

        if not results:
            return df.assign(rolling_mean=0.0, rolling_std=1.0, z_score=0.0)

        return pd.concat(results, ignore_index=True)

    def detect_anomalies(self, signals: list[dict]) -> list[dict]:
        """
        Run the full anomaly detection pipeline.

        Returns anomaly records for any location where today's Z-score
        exceeds Z_SCORE_THRESHOLD.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            List of anomaly dicts, each containing:
            {location, date, signal_count, z_score, rolling_mean, alert}
        """
        df = self.compute_daily_counts(signals)
        if df.empty:
            return []

        df_z = self.compute_z_scores(df)
        today = datetime.now(timezone.utc).date().isoformat()

        anomalies = []
        today_rows = df_z[df_z["date"] == today]
        for _, row in today_rows.iterrows():
            if row["z_score"] > Z_SCORE_THRESHOLD:
                anomalies.append({
                    "location": row["location"],
                    "date": row["date"],
                    "signal_count": int(row["count"]),
                    "z_score": round(float(row["z_score"]), 2),
                    "rolling_mean": round(float(row["rolling_mean"]), 2),
                    "alert": "ANOMALY DETECTED",
                })

        logger.info(f"AnomalyEngine: {len(anomalies)} anomalies detected today.")
        return anomalies

    def summarize_anomalies(self, anomalies: list[dict]) -> str:
        """
        Build a human-readable summary string for the dashboard banner.

        Args:
            anomalies: List of anomaly dicts from detect_anomalies().

        Returns:
            Summary string, or empty string if no anomalies.
        """
        if not anomalies:
            return ""
        parts = [
            f"{a['location']} (z={a['z_score']:.1f}, {a['signal_count']} signals)"
            for a in anomalies
        ]
        return f"⚠️ ANOMALY DETECTED in {len(anomalies)} region(s): {', '.join(parts)}"


# ---------------------------------------------------------------------------
# Self-test — guarantees at least one anomaly via synthetic multi-day data
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import timezone

    print("=== anomaly_engine.py self-test ===\n")

    def _ts(days_ago: int) -> str:
        ts = datetime.now(timezone.utc) - timedelta(days=days_ago)
        return ts.isoformat()

    # Build synthetic signals: Ukraine gets normal volume for 6 days,
    # then a spike today → should trigger an anomaly
    synthetic: list[dict] = []
    _id = 0

    def _sig(location: str, days_ago: int) -> dict:
        global _id
        _id += 1
        return {
            "id": str(_id),
            "timestamp": _ts(days_ago),
            "type": "news",
            "source": "NewsAPI",
            "location": location,
            "latitude": 48.0,
            "longitude": 31.0,
            "title": "Test signal",
            "description": "test",
            "raw_score": 5.0,
            "keywords_matched": [],
            "severity": "LOW",
        }

    # 6 historical days: 1 signal per day for Ukraine
    for d in range(6, 0, -1):
        synthetic.append(_sig("Ukraine", d))

    # Today: 8 signals for Ukraine (spike)
    for _ in range(8):
        synthetic.append(_sig("Ukraine", 0))

    # Russia: only 1 signal today — should NOT trigger anomaly
    synthetic.append(_sig("Russia", 0))

    engine = AnomalyEngine()
    anomalies = engine.detect_anomalies(synthetic)

    print(f"Total signals: {len(synthetic)}")
    print(f"Anomalies detected: {len(anomalies)}\n")
    for a in anomalies:
        print(
            f"  {a['location']:20s} z={a['z_score']:5.2f} "
            f"count={a['signal_count']} mean={a['rolling_mean']} — {a['alert']}"
        )

    summary = engine.summarize_anomalies(anomalies)
    print(f"\nDashboard summary: {summary}")

    assert any(a["location"] == "Ukraine" for a in anomalies), \
        "Expected Ukraine anomaly not found!"
    print("\n✅ anomaly_engine.py self-test passed.")

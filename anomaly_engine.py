"""
anomaly_engine.py — Statistical anomaly detector for ORRAS.

Flags regions whose current signal volume is unusual using one of two
baselines:

  ``temporal``  Z-score against the region's own prior-day rolling baseline
                (the primary method, used once enough history exists).
  ``peer``      Z-score against the cross-sectional distribution of all
                regions for the same day (cold-start fallback, used when a
                region has no usable history yet).

The previous implementation compared each day's count against a rolling
window that *included that same day*, so with a single day of data the
deviation was always zero and no anomaly could ever be flagged. Baselines
here are computed strictly from prior observations, and the peer baseline
keeps detection working on a freshly-deployed system.
"""

from datetime import datetime, timedelta, timezone

import pandas as pd

from config import (
    ANOMALY_MIN_BASELINE_POINTS,
    ANOMALY_PEER_MIN_REGIONS,
    ROLLING_WINDOW_DAYS,
    Z_SCORE_THRESHOLD,
)
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
        Compute rolling Z-scores per location against *prior* days only.

        For each location the rolling mean/std are taken over the preceding
        ROLLING_WINDOW_DAYS observations, excluding the current day. Using
        ``shift(1)`` is what makes the score meaningful: a region with only
        one day of data yields NaN rather than a spurious 0.0.

        Args:
            df: DataFrame with columns [location, date, count].

        Returns:
            DataFrame with added columns: rolling_mean, rolling_std,
            z_score, baseline_points, has_baseline.
        """
        empty_extra = {
            "rolling_mean": pd.Series(dtype="float64"),
            "rolling_std": pd.Series(dtype="float64"),
            "z_score": pd.Series(dtype="float64"),
            "baseline_points": pd.Series(dtype="int64"),
            "has_baseline": pd.Series(dtype="bool"),
        }
        if df.empty:
            return df.assign(**empty_extra)

        results = []
        for _location, group in df.groupby("location"):
            group = group.sort_values("date").copy()

            # Baseline = statistics of strictly earlier days.
            prior = group["count"].shift(1)
            group["rolling_mean"] = (
                prior.rolling(window=ROLLING_WINDOW_DAYS, min_periods=1).mean()
            )
            group["rolling_std"] = (
                prior.rolling(window=ROLLING_WINDOW_DAYS, min_periods=1).std()
            )
            group["baseline_points"] = (
                prior.rolling(window=ROLLING_WINDOW_DAYS, min_periods=1).count()
            ).fillna(0).astype(int)

            # A std of 0 (flat history) is degenerate; fall back to 1 so a
            # genuine spike still registers instead of dividing by zero.
            group["rolling_std"] = group["rolling_std"].fillna(0.0).replace(0, 1.0)

            group["z_score"] = (
                (group["count"] - group["rolling_mean"]) / group["rolling_std"]
            )
            group["has_baseline"] = (
                group["baseline_points"] >= ANOMALY_MIN_BASELINE_POINTS
            )
            results.append(group)

        if not results:
            return df.assign(
                rolling_mean=0.0, rolling_std=1.0, z_score=0.0,
                baseline_points=0, has_baseline=False,
            )

        return pd.concat(results, ignore_index=True)

    def compute_peer_z_scores(self, df: pd.DataFrame, date: str) -> pd.DataFrame:
        """
        Compute cross-sectional Z-scores for every location on one day.

        Compares each region's count for *date* against the distribution of
        all regions' counts that same day. This is the cold-start baseline:
        it answers "is this region unusually busy compared with everywhere
        else right now?", which needs no history at all.

        Args:
            df:   DataFrame with columns [location, date, count].
            date: ISO date string to evaluate.

        Returns:
            DataFrame with columns [location, count, peer_mean, peer_std,
            z_score]. Empty DataFrame when there are too few regions.
        """
        if df.empty:
            return pd.DataFrame(
                columns=["location", "count", "peer_mean", "peer_std", "z_score"]
            )

        day = df[df["date"] == date]
        if len(day) < ANOMALY_PEER_MIN_REGIONS:
            return pd.DataFrame(
                columns=["location", "count", "peer_mean", "peer_std", "z_score"]
            )

        mean = float(day["count"].mean())
        std = float(day["count"].std(ddof=0))

        # A perfectly flat day yields std == 0; use 1 so an outlier region
        # still separates from the pack.
        if std == 0:
            std = 1.0

        out = day[["location", "count"]].copy()
        out["peer_mean"] = mean
        out["peer_std"] = std
        out["z_score"] = (out["count"] - mean) / std
        return out.reset_index(drop=True)

    def detect_anomalies(self, signals: list[dict]) -> list[dict]:
        """
        Run the full anomaly detection pipeline.

        Uses a region's own prior-day history where available and falls back
        to the cross-sectional peer baseline when it is not, so anomalies can
        be reported from the very first run.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            List of anomaly dicts sorted by descending Z-score, each with:
            location, region (alias), date, signal_count, z_score,
            baseline, method, prior_days, and alert.
        """
        df = self.compute_daily_counts(signals)
        if df.empty:
            logger.info("AnomalyEngine: no signal data to analyse.")
            return []

        today = datetime.now(timezone.utc).date().isoformat()
        df_z = self.compute_z_scores(df)
        today_rows = df_z[df_z["date"] == today]

        anomalies: list[dict] = []

        # ── Primary: temporal baseline from the region's own history ────────
        for _, row in today_rows.iterrows():
            if not bool(row["has_baseline"]):
                continue
            z = float(row["z_score"])
            if z > Z_SCORE_THRESHOLD:
                anomalies.append({
                    "location": row["location"],
                    "region": row["location"],  # alias for downstream consumers
                    "date": row["date"],
                    "signal_count": int(row["count"]),
                    "z_score": round(z, 2),
                    "rolling_mean": round(float(row["rolling_mean"]), 2),
                    "baseline": round(float(row["rolling_mean"]), 2),
                    "method": "temporal",
                    "prior_days": int(row["baseline_points"]),
                    "alert": "ANOMALY DETECTED",
                })

        scored_by_history = {a["location"] for a in anomalies}

        # ── Fallback: peer baseline for regions without usable history ──────
        peer = self.compute_peer_z_scores(df, today)
        for _, row in peer.iterrows():
            location = row["location"]
            if location in scored_by_history:
                continue
            z = float(row["z_score"])
            if z > Z_SCORE_THRESHOLD:
                anomalies.append({
                    "location": location,
                    "region": location,
                    "date": today,
                    "signal_count": int(row["count"]),
                    "z_score": round(z, 2),
                    "rolling_mean": round(float(row["peer_mean"]), 2),
                    "baseline": round(float(row["peer_mean"]), 2),
                    "method": "peer",
                    "prior_days": 0,
                    "alert": "ANOMALY DETECTED",
                })

        anomalies.sort(key=lambda a: a["z_score"], reverse=True)

        temporal = sum(1 for a in anomalies if a["method"] == "temporal")
        peer_n = len(anomalies) - temporal
        logger.info(
            f"AnomalyEngine: {len(anomalies)} anomalies detected today "
            f"({temporal} temporal, {peer_n} peer-baseline)."
        )
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
    assert all(a["method"] == "temporal" for a in anomalies), \
        "Ukraine has history, so the temporal baseline should have been used."

    # ── Cold-start test ────────────────────────────────────────────────────
    # A single day of data has no prior history, so detection must fall back
    # to the peer baseline rather than reporting nothing.
    print("\n--- cold-start (single day, no history) ---")
    cold: list[dict] = []
    for location, count in [("Iran", 12), ("Chad", 2), ("Peru", 3),
                            ("Cuba", 2), ("Nepal", 3), ("Mali", 2)]:
        for _ in range(count):
            cold.append(_sig(location, 0))

    cold_anomalies = engine.detect_anomalies(cold)
    print(f"Anomalies detected: {len(cold_anomalies)}")
    for a in cold_anomalies:
        print(f"  {a['location']:10s} z={a['z_score']:5.2f} "
              f"count={a['signal_count']} method={a['method']}")

    assert any(a["location"] == "Iran" for a in cold_anomalies), \
        "Expected Iran to be flagged via the peer baseline."
    assert all(a["method"] == "peer" for a in cold_anomalies), \
        "With no history every anomaly must use the peer baseline."
    print("✅ cold-start peer baseline works.")

    # ── Regression: flat data must not produce false positives ─────────────
    print("\n--- flat data (no anomalies expected) ---")
    flat: list[dict] = []
    for location in ("Iran", "Chad", "Peru", "Cuba", "Nepal", "Mali"):
        for _ in range(3):
            flat.append(_sig(location, 0))
    flat_anomalies = engine.detect_anomalies(flat)
    print(f"Anomalies detected: {len(flat_anomalies)} (expected 0)")
    assert not flat_anomalies, f"Uniform data should not be anomalous: {flat_anomalies}"
    print("✅ no false positives on uniform data.")

    print("\n✅ anomaly_engine.py self-test passed.")

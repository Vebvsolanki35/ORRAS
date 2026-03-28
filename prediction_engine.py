"""
prediction_engine.py — Short-range risk forecasting for the ORRAS system.

Uses linear regression and weighted-average methods to project regional
risk scores 1–7 days into the future based on escalation history snapshots.

All forecasting is done with pure numpy (no external ML libraries needed)
so the module stays lightweight and fully offline-capable.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import numpy as np
import pandas as pd

from config import FORECAST_DAYS, MIN_HISTORY_DAYS, RISK_THRESHOLDS
from utils import classify_severity, get_logger

logger = get_logger(__name__)


class PredictionEngine:
    """
    Forecasts regional risk scores using two complementary methods:
      - Linear regression (numpy polyfit) for trend extrapolation.
      - Weighted moving average that emphasises the most recent data.

    All methods accept and return plain Python types so they integrate
    cleanly with the rest of the ORRAS pipeline.
    """

    # Minimum number of data points required before any forecast is attempted
    MIN_POINTS: int = MIN_HISTORY_DAYS  # imported from config (default 3)

    # Number of recent days used for linear-regression fitting
    REGRESSION_WINDOW: int = 7

    # Weight multiplier applied to the most recent half of the window
    RECENCY_WEIGHT: int = 3

    # ---------------------------------------------------------------------------
    # Data preparation
    # ---------------------------------------------------------------------------

    def prepare_time_series(self, history: list, region: str) -> pd.DataFrame:
        """
        Extract a daily risk-score time series for one region from the
        escalation history produced by EscalationTracker.

        Each entry in *history* is a snapshot dict with the structure:
            {
                "timestamp": "<ISO-8601 string>",
                "regions": {
                    "<region_name>": {"score": float, "severity": str, ...},
                    ...
                }
            }

        Multiple snapshots for the same calendar day are averaged together
        so the returned DataFrame has at most one row per day.

        Args:
            history: List of snapshot dicts (from EscalationTracker.load_history).
            region:  Region name to extract (must match the keys in "regions").

        Returns:
            DataFrame with columns [date (str), score (float), severity (str)]
            sorted by date ascending. Empty DataFrame if no data found.
        """
        # Accumulate scores per calendar day
        daily_scores: dict[str, list[float]] = {}

        for snapshot in history:
            ts_str = snapshot.get("timestamp", "")
            regions_map = snapshot.get("regions", {})
            region_data = regions_map.get(region)
            if region_data is None:
                continue  # this snapshot doesn't include the requested region

            # Parse ISO timestamp; tolerate both offset-aware and naive strings
            try:
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                continue

            date_key = ts.date().isoformat()  # e.g. "2024-06-15"
            score = float(region_data.get("score", 0.0))
            daily_scores.setdefault(date_key, []).append(score)

        if not daily_scores:
            return pd.DataFrame(columns=["date", "score", "severity"])

        # Build rows, averaging multiple snapshots on the same day
        rows = []
        for date_key in sorted(daily_scores.keys()):
            scores = daily_scores[date_key]
            avg_score = round(sum(scores) / len(scores), 2)
            rows.append(
                {
                    "date": date_key,
                    "score": avg_score,
                    "severity": classify_severity(avg_score),
                }
            )

        return pd.DataFrame(rows)

    # ---------------------------------------------------------------------------
    # Forecasting methods
    # ---------------------------------------------------------------------------

    def forecast_linear(self, df: pd.DataFrame, days: int = FORECAST_DAYS) -> list:
        """
        Project risk scores forward using a linear regression fit on the
        most recent REGRESSION_WINDOW data points.

        The regression is fitted on integer day indices (0, 1, 2, …) to
        avoid floating-point issues with date arithmetic. Predicted scores
        are clamped to [0, 100] to prevent nonsensical extrapolations.

        Args:
            df:   Time-series DataFrame from prepare_time_series.
            days: Number of future days to forecast.

        Returns:
            List of forecast dicts, one per future day:
            {date: str, predicted_score: float, severity: str, method: str}
            Returns [] if there are fewer than MIN_POINTS rows.
        """
        if len(df) < self.MIN_POINTS:
            logger.warning("forecast_linear: insufficient data points.")
            return []

        # Use only the most recent REGRESSION_WINDOW days
        window = df.tail(self.REGRESSION_WINDOW).reset_index(drop=True)
        x = np.arange(len(window), dtype=float)
        y = window["score"].values.astype(float)

        # Fit a first-degree polynomial (slope + intercept)
        coefficients = np.polyfit(x, y, deg=1)
        slope, intercept = coefficients[0], coefficients[1]

        # The next forecast point starts at index len(window)
        last_date = datetime.strptime(window["date"].iloc[-1], "%Y-%m-%d").date()
        forecasts = []
        for step in range(1, days + 1):
            future_x = len(window) - 1 + step  # continue the index sequence
            raw_score = slope * future_x + intercept
            predicted_score = float(np.clip(raw_score, 0.0, 100.0))
            future_date = (last_date + timedelta(days=step)).isoformat()
            forecasts.append(
                {
                    "date": future_date,
                    "predicted_score": round(predicted_score, 2),
                    "severity": classify_severity(predicted_score),
                    "method": "linear",
                }
            )

        return forecasts

    def forecast_weighted_average(
        self, df: pd.DataFrame, days: int = FORECAST_DAYS
    ) -> list:
        """
        Project risk scores using a weighted average of recent observations.

        The most recent half of the available window receives RECENCY_WEIGHT×
        the weight of the older half, which biases the forecast toward the
        current direction of travel without over-fitting a straight line.

        Args:
            df:   Time-series DataFrame from prepare_time_series.
            days: Number of future days to forecast.

        Returns:
            Same structure as forecast_linear, with method="weighted_avg".
            Returns [] if there are fewer than MIN_POINTS rows.
            The decay formula is ``weighted_avg + momentum * 0.5**step``,
            so momentum halves each successive day, pulling the forecast
            toward the long-run weighted average over the horizon.
        """
        if len(df) < self.MIN_POINTS:
            logger.warning("forecast_weighted_average: insufficient data points.")
            return []

        # Work on the most recent REGRESSION_WINDOW days
        window = df.tail(self.REGRESSION_WINDOW).reset_index(drop=True)
        scores = window["score"].values.astype(float)
        n = len(scores)

        # Assign weights: recent half gets RECENCY_WEIGHT, older half gets 1
        midpoint = n // 2
        weights = np.ones(n, dtype=float)
        weights[midpoint:] = float(self.RECENCY_WEIGHT)

        weighted_avg = float(np.average(scores, weights=weights))

        # Blend the weighted average with the most recent score to project
        # momentum: if recent score > weighted_avg the series is climbing.
        last_score = float(scores[-1])
        momentum = last_score - weighted_avg  # positive → rising, negative → falling

        last_date = datetime.strptime(window["date"].iloc[-1], "%Y-%m-%d").date()
        forecasts = []
        for step in range(1, days + 1):
            # Momentum decays by 50 % each step so the projection reverts toward average
            decay = 0.5 ** step
            raw_score = weighted_avg + momentum * decay
            predicted_score = float(np.clip(raw_score, 0.0, 100.0))
            future_date = (last_date + timedelta(days=step)).isoformat()
            forecasts.append(
                {
                    "date": future_date,
                    "predicted_score": round(predicted_score, 2),
                    "severity": classify_severity(predicted_score),
                    "method": "weighted_avg",
                }
            )

        return forecasts

    # ---------------------------------------------------------------------------
    # Trend characterisation
    # ---------------------------------------------------------------------------

    def detect_trend_direction(self, df: pd.DataFrame) -> str:
        """
        Classify the recent trend as one of four states based on the last
        3 data points.

        Decision logic:
          - VOLATILE  : high variance (std > 3.0), regardless of direction
          - ESCALATING: slope > +0.5 per day
          - DE-ESCALATING: slope < -0.5 per day
          - STABLE    : slope within ±0.5 per day

        Args:
            df: Time-series DataFrame from prepare_time_series.

        Returns:
            One of "ESCALATING" | "DE-ESCALATING" | "STABLE" | "VOLATILE".
        """
        if len(df) < 2:
            return "STABLE"

        # Examine at most the last 3 data points
        recent = df.tail(3)
        scores = recent["score"].values.astype(float)

        variance = float(np.std(scores))
        if variance > 3.0:
            return "VOLATILE"

        # Simple slope from first to last point in the window
        x = np.arange(len(scores), dtype=float)
        if len(x) > 1:
            coefficients = np.polyfit(x, scores, deg=1)
            slope = coefficients[0]
        else:
            slope = 0.0

        if slope > 0.5:
            return "ESCALATING"
        if slope < -0.5:
            return "DE-ESCALATING"
        return "STABLE"

    # ---------------------------------------------------------------------------
    # Confidence estimation
    # ---------------------------------------------------------------------------

    def compute_forecast_confidence(self, df: pd.DataFrame) -> float:
        """
        Estimate how reliable the forecast is likely to be, on a 0.0–1.0 scale.

        Three factors contribute to confidence:
          1. Data volume  — more days of history → higher confidence (caps at 14 days).
          2. Low variance — a stable, consistent series is easier to forecast.
          3. Clear trend  — a decisive slope (positive or negative) scores higher
                            than a flat line that could break either way.

        Args:
            df: Time-series DataFrame from prepare_time_series.

        Returns:
            Confidence score in [0.0, 1.0]. Returns 0.0 for insufficient data.
        """
        if len(df) < self.MIN_POINTS:
            return 0.0

        scores = df["score"].values.astype(float)

        # Factor 1: data volume (0 → 1 over 14 days)
        volume_score = min(len(scores) / 14.0, 1.0)

        # Factor 2: low variance (std=0 → 1.0, std=10 → 0.0, clamped)
        std = float(np.std(scores))
        variance_score = max(0.0, 1.0 - std / 10.0)

        # Factor 3: clear trend — abs(slope) mapped to 0–1
        x = np.arange(len(scores), dtype=float)
        coefficients = np.polyfit(x, scores, deg=1)
        slope = float(abs(coefficients[0]))
        trend_score = min(slope / 5.0, 1.0)  # saturates at slope ≥ 5

        # Weighted combination: volume and variance matter most
        confidence = (
            0.40 * volume_score
            + 0.35 * variance_score
            + 0.25 * trend_score
        )
        return round(float(np.clip(confidence, 0.0, 1.0)), 3)

    # ---------------------------------------------------------------------------
    # Batch forecasting
    # ---------------------------------------------------------------------------

    def forecast_all_regions(self, history: list) -> dict:
        """
        Run the full forecasting pipeline for every region that has at least
        MIN_HISTORY_DAYS days of data in the escalation history.

        Uses the linear method as the primary forecast; the weighted-average
        result is included in `forecast_points` for comparison.

        Args:
            history: Full escalation history list (from EscalationTracker.load_history).

        Returns:
            Dict keyed by region name:
            {
                region: {
                    "current": float,           # latest observed score
                    "predicted_3day": float,    # linear forecast 3 days out
                    "direction": str,           # trend direction label
                    "confidence": float,        # 0.0–1.0
                    "forecast_points": list,    # list of linear forecast dicts
                }
            }
        """
        # Collect all unique region names across the entire history
        all_regions: set[str] = set()
        for snapshot in history:
            all_regions.update((snapshot.get("regions") or {}).keys())

        results = {}
        for region in sorted(all_regions):
            df = self.prepare_time_series(history, region)

            # Skip regions without enough data to forecast
            if len(df) < self.MIN_POINTS:
                logger.debug(
                    f"forecast_all_regions: skipping '{region}' "
                    f"(only {len(df)} day(s) of data)."
                )
                continue

            linear_pts = self.forecast_linear(df, days=FORECAST_DAYS)
            if not linear_pts:
                continue

            current_score = float(df["score"].iloc[-1])
            predicted_3day = linear_pts[-1]["predicted_score"]  # last point = day 3
            direction = self.detect_trend_direction(df)
            confidence = self.compute_forecast_confidence(df)

            results[region] = {
                "current": round(current_score, 2),
                "predicted_3day": predicted_3day,
                "direction": direction,
                "confidence": confidence,
                "forecast_points": linear_pts,
            }
            logger.info(
                f"Forecast for '{region}': current={current_score:.1f} → "
                f"day3={predicted_3day:.1f} ({direction}, conf={confidence:.2f})"
            )

        return results

    def get_high_risk_outlook(self, forecasts: dict) -> list:
        """
        Identify regions forecast to reach HIGH or CRITICAL severity within
        the next forecast window.

        Args:
            forecasts: Output of forecast_all_regions().

        Returns:
            List of dicts for qualifying regions, sorted by predicted score
            descending. Each dict mirrors the forecast_all_regions output
            with the region name added under the key "region".
        """
        HIGH_THRESHOLD = float(RISK_THRESHOLDS["HIGH"][0])  # 11.0 by default

        high_risk = []
        for region, data in forecasts.items():
            if data.get("predicted_3day", 0.0) >= HIGH_THRESHOLD:
                high_risk.append({"region": region, **data})

        # Sort highest predicted score first
        high_risk.sort(key=lambda x: x["predicted_3day"], reverse=True)
        return high_risk


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import date, timedelta

    print("=== prediction_engine.py self-test ===\n")

    # Build synthetic escalation history spanning 10 days for 3 regions
    base_date = datetime.now(timezone.utc) - timedelta(days=10)

    def _make_snapshot(day_offset: int, regions_data: dict) -> dict:
        ts = (base_date + timedelta(days=day_offset)).isoformat()
        return {"timestamp": ts, "regions": regions_data}

    # Eastern Europe: steadily escalating (LOW → CRITICAL)
    # Middle East: gradually de-escalating
    # West Africa: noisy / stable
    import random

    random.seed(42)
    history = []
    for d in range(11):
        history.append(
            _make_snapshot(
                d,
                {
                    "Eastern Europe": {
                        "score": round(3.0 + d * 2.2 + random.uniform(-0.5, 0.5), 2),
                        "severity": "varies",
                    },
                    "Middle East": {
                        "score": round(24.0 - d * 1.8 + random.uniform(-0.5, 0.5), 2),
                        "severity": "varies",
                    },
                    "West Africa": {
                        "score": round(7.0 + random.uniform(-3.0, 3.0), 2),
                        "severity": "varies",
                    },
                },
            )
        )

    engine = PredictionEngine()

    # --- prepare_time_series ---
    print("--- prepare_time_series (Eastern Europe) ---")
    df_ee = engine.prepare_time_series(history, "Eastern Europe")
    print(df_ee.to_string(index=False))
    print()

    # --- forecast_linear ---
    print("--- forecast_linear ---")
    linear_forecast = engine.forecast_linear(df_ee)
    for pt in linear_forecast:
        print(f"  {pt}")
    print()

    # --- forecast_weighted_average ---
    print("--- forecast_weighted_average ---")
    wa_forecast = engine.forecast_weighted_average(df_ee)
    for pt in wa_forecast:
        print(f"  {pt}")
    print()

    # --- detect_trend_direction ---
    print("--- detect_trend_direction ---")
    for region in ["Eastern Europe", "Middle East", "West Africa"]:
        df = engine.prepare_time_series(history, region)
        direction = engine.detect_trend_direction(df)
        print(f"  {region}: {direction}")
    print()

    # --- compute_forecast_confidence ---
    print("--- compute_forecast_confidence ---")
    for region in ["Eastern Europe", "Middle East", "West Africa"]:
        df = engine.prepare_time_series(history, region)
        conf = engine.compute_forecast_confidence(df)
        print(f"  {region}: confidence={conf:.3f}")
    print()

    # --- forecast_all_regions ---
    print("--- forecast_all_regions ---")
    all_forecasts = engine.forecast_all_regions(history)
    for region, data in all_forecasts.items():
        print(
            f"  {region}: current={data['current']:.1f} → "
            f"day3={data['predicted_3day']:.1f} "
            f"({data['direction']}, conf={data['confidence']:.2f})"
        )
    print()

    # --- get_high_risk_outlook ---
    print("--- get_high_risk_outlook ---")
    outlook = engine.get_high_risk_outlook(all_forecasts)
    if outlook:
        for item in outlook:
            print(
                f"  ⚠  {item['region']}: predicted={item['predicted_3day']:.1f} "
                f"({classify_severity(item['predicted_3day'])})"
            )
    else:
        print("  No regions forecast to reach HIGH/CRITICAL.")

    print("\n✅ prediction_engine.py self-test complete.")

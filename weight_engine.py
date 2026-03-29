"""
weight_engine.py — Dynamic signal weighting for the ORRAS system.

Computes a dynamic_weight for each signal by combining:
  1. Base source reliability weight
  2. Recency multiplier (how fresh the signal is)
  3. Corroboration multiplier (same location, same timeframe, multiple sources)

The dynamic_weight is then used to adjust raw_score.
"""

from datetime import datetime, timezone

from utils import get_logger, haversine_distance

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Base weights per data source
# ---------------------------------------------------------------------------

BASE_WEIGHTS: dict[str, float] = {
    "NASA FIRMS": 1.3,
    "USGS": 1.3,
    "GDELT": 1.2,
    "OpenSky": 1.1,
    "NOAA": 1.1,
    "NewsAPI": 1.0,
    "ReliefWeb": 1.0,
    "ACLED": 1.0,
    "WHO": 1.0,
    "NetBlocks": 0.9,
    "Cloudflare Radar": 0.9,
    "Social/Mock": 0.6,
}

# Corroboration: km radius and hour window for co-location check
_CORROBORATION_RADIUS_KM = 300.0
_CORROBORATION_HOURS = 1


class WeightEngine:
    """
    Applies dynamic weighting to normalised signals.

    Weights are composites of source reliability, recency, and corroboration.
    """

    def get_base_weight(self, source: str) -> float:
        """
        Look up the base reliability weight for a source.

        Args:
            source: Source name string (e.g. "NewsAPI", "USGS").

        Returns:
            Base weight float; defaults to 1.0 for unknown sources.
        """
        return BASE_WEIGHTS.get(source, 1.0)

    def compute_recency_multiplier(self, timestamp: str) -> float:
        """
        Compute a freshness multiplier based on signal age.

        Rules:
            - Last 1 hour  → 1.5×
            - Last 6 hours → 1.2×
            - Last 24 hours → 1.0×
            - Older         → 0.7×

        Args:
            timestamp: ISO 8601 timestamp string.

        Returns:
            Recency multiplier float.
        """
        try:
            # Parse timestamp; support both offset-aware and naive strings
            ts = timestamp.replace("Z", "+00:00")
            signal_time = datetime.fromisoformat(ts)
            # Ensure timezone-aware for comparison
            if signal_time.tzinfo is None:
                signal_time = signal_time.replace(tzinfo=timezone.utc)
            now = datetime.now(timezone.utc)
            age_hours = (now - signal_time).total_seconds() / 3600.0
        except (ValueError, TypeError, AttributeError):
            return 1.0  # fallback for unparseable timestamps

        if age_hours <= 1.0:
            return 1.5
        if age_hours <= 6.0:
            return 1.2
        if age_hours <= 24.0:
            return 1.0
        return 0.7

    def compute_corroboration_multiplier(
        self, signal: dict, all_signals: list[dict]
    ) -> float:
        """
        Compute a corroboration multiplier based on co-located, near-simultaneous signals.

        Two signals are considered corroborating if they are:
          - Within _CORROBORATION_RADIUS_KM km of each other
          - Within _CORROBORATION_HOURS hours of each other
          - From a different source

        Rules:
            - 2 corroborating sources → 1.3×
            - 3+ corroborating sources → 1.5×

        Args:
            signal: The signal being evaluated.
            all_signals: All signals in the current batch.

        Returns:
            Corroboration multiplier float.
        """
        sig_lat = signal.get("latitude") or 0.0
        sig_lon = signal.get("longitude") or 0.0
        sig_source = signal.get("source", "")
        sig_time_str = signal.get("timestamp", "")

        try:
            ts = sig_time_str.replace("Z", "+00:00")
            sig_time = datetime.fromisoformat(ts)
            if sig_time.tzinfo is None:
                sig_time = sig_time.replace(tzinfo=timezone.utc)
        except (ValueError, TypeError, AttributeError):
            return 1.0

        corroborating_sources: set[str] = set()

        for other in all_signals:
            if other is signal:
                continue
            other_source = other.get("source", "")
            if other_source == sig_source:
                continue

            other_lat = other.get("latitude") or 0.0
            other_lon = other.get("longitude") or 0.0

            try:
                dist_km = haversine_distance(sig_lat, sig_lon, other_lat, other_lon)
            except Exception:
                continue

            if dist_km > _CORROBORATION_RADIUS_KM:
                continue

            try:
                ots = other.get("timestamp", "").replace("Z", "+00:00")
                other_time = datetime.fromisoformat(ots)
                if other_time.tzinfo is None:
                    other_time = other_time.replace(tzinfo=timezone.utc)
                time_diff_hours = abs((sig_time - other_time).total_seconds()) / 3600.0
            except (ValueError, TypeError, AttributeError):
                continue

            if time_diff_hours <= _CORROBORATION_HOURS:
                corroborating_sources.add(other_source)

        n = len(corroborating_sources)
        if n >= 2:
            return 1.5
        if n == 1:
            return 1.3
        return 1.0

    def compute_dynamic_weight(
        self, signal: dict, all_signals: list[dict]
    ) -> float:
        """
        Compute the final dynamic weight for a signal.

        Multiplies base_weight × recency_multiplier × corroboration_multiplier,
        then clamps the result to [0.5, 8.0].

        Args:
            signal: Signal dict.
            all_signals: Full signal batch for corroboration lookup.

        Returns:
            Dynamic weight float in [0.5, 8.0].
        """
        base = self.get_base_weight(signal.get("source", ""))
        recency = self.compute_recency_multiplier(signal.get("timestamp", ""))
        corroboration = self.compute_corroboration_multiplier(signal, all_signals)

        weight = base * recency * corroboration
        weight = max(0.5, min(8.0, weight))
        return round(weight, 4)

    def apply_weights(self, signals: list[dict]) -> list[dict]:
        """
        Compute and apply dynamic_weight to every signal.

        Updates:
          - signal["dynamic_weight"] = computed dynamic weight
          - signal["raw_score"] = raw_score * dynamic_weight / 5.0
            (normalises to roughly the same 0-30 range)

        Args:
            signals: List of signal dicts.

        Returns:
            Updated list with dynamic_weight and adjusted raw_score.
        """
        for sig in signals:
            dw = self.compute_dynamic_weight(sig, signals)
            sig["dynamic_weight"] = dw
            old_score = float(sig.get("raw_score") or 0.0)
            sig["raw_score"] = round(old_score * dw / 5.0, 4)

        logger.info(f"WeightEngine: applied weights to {len(signals)} signals.")
        return signals


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from datetime import timedelta
    from utils import generate_id, now_iso

    print("=== weight_engine.py self-test ===\n")

    def _ts_hours_ago(h: float) -> str:
        dt = datetime.now(timezone.utc) - timedelta(hours=h)
        return dt.isoformat()

    test_signals = [
        {
            "id": generate_id(),
            "source": "USGS",
            "timestamp": _ts_hours_ago(0.5),   # 30 min ago
            "latitude": 48.4,
            "longitude": 30.5,
            "raw_score": 20.0,
            "title": "M6.5 earthquake near Kyiv",
        },
        {
            "id": generate_id(),
            "source": "NewsAPI",
            "timestamp": _ts_hours_ago(0.5),   # same time, same location
            "latitude": 48.5,
            "longitude": 30.6,
            "raw_score": 12.0,
            "title": "Earthquake reported near Kyiv",
        },
        {
            "id": generate_id(),
            "source": "GDELT",
            "timestamp": _ts_hours_ago(0.5),   # same time, same location
            "latitude": 48.3,
            "longitude": 30.4,
            "raw_score": 10.0,
            "title": "Seismic event near Ukraine capital",
        },
        {
            "id": generate_id(),
            "source": "Social/Mock",
            "timestamp": _ts_hours_ago(30),    # older than 24h
            "latitude": 15.0,
            "longitude": 45.0,
            "raw_score": 5.0,
            "title": "Old social media signal",
        },
    ]

    engine = WeightEngine()

    print("Base weights:")
    for src in ["USGS", "NASA FIRMS", "NewsAPI", "Social/Mock", "Unknown"]:
        print(f"  {src:20s}: {engine.get_base_weight(src)}")

    print("\nRecency multipliers:")
    for h, label in [(0.5, "0.5h ago"), (3, "3h ago"), (12, "12h ago"), (36, "36h ago")]:
        ts = _ts_hours_ago(h)
        print(f"  {label:12s}: {engine.compute_recency_multiplier(ts)}")

    weighted = engine.apply_weights(test_signals)

    print("\nApplied weights:")
    for sig in weighted:
        print(f"  source={sig['source']:20s}  dynamic_weight={sig['dynamic_weight']}  "
              f"raw_score={sig['raw_score']}")

    print("\n✅ weight_engine.py self-test complete.")

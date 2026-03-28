"""
correlation_engine.py — Compound signal detector that applies bonus scores when
multiple distinct signal types co-occur in the same region within a time window.
"""

from datetime import datetime, timedelta, timezone
from typing import Any

from config import CORRELATION_BONUSES
from utils import classify_severity, get_logger

logger = get_logger(__name__)


class CorrelationEngine:
    """
    Detects correlated multi-source threat signals within geographic regions.
    """

    def group_by_region_and_window(
        self, signals: list[dict], hours: int = 24
    ) -> dict[str, list[dict]]:
        """
        Group signals by location, keeping only those within the last *hours* hours.

        Args:
            signals: List of unified-schema signal dicts.
            hours: Look-back window in hours.

        Returns:
            Dict mapping region name → list of signals within the window.
        """
        cutoff = datetime.now(timezone.utc) - timedelta(hours=hours)
        groups: dict[str, list[dict]] = {}

        for sig in signals:
            location = sig.get("location") or "Unknown"
            ts_str = sig.get("timestamp") or ""
            try:
                # Handle both offset-aware and naive timestamps
                ts = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
                if ts.tzinfo is None:
                    ts = ts.replace(tzinfo=timezone.utc)
            except (ValueError, AttributeError):
                ts = datetime.now(timezone.utc)

            if ts >= cutoff:
                groups.setdefault(location, []).append(sig)

        return groups

    def detect_signal_types(self, signals: list[dict]) -> set[str]:
        """
        Infer the threat sub-types present in a list of signals.

        Sub-type classification rules:
        - troop_movement  : type==movement AND any of (troops, deployment, mobilization) in keywords
        - network_shutdown: type==network
        - news_conflict   : type==news AND raw_score > 8
        - satellite_fire  : type==satellite
        - social_unrest   : type==social AND any of (riot, protest, unrest) in keywords
        - aircraft_anomaly: type==movement AND source==OpenSky

        Args:
            signals: List of signals from a single region window.

        Returns:
            Set of sub-type strings present.
        """
        subtypes: set[str] = set()
        troop_kws = {"troops", "deployment", "mobilization"}
        unrest_kws = {"riot", "protest", "unrest"}

        for sig in signals:
            sig_type = sig.get("type", "")
            source = sig.get("source", "")
            keywords = set(sig.get("keywords_matched") or [])
            score = sig.get("raw_score", 0)

            if sig_type == "movement":
                if keywords & troop_kws:
                    subtypes.add("troop_movement")
                if source == "OpenSky":
                    subtypes.add("aircraft_anomaly")
            elif sig_type == "network":
                subtypes.add("network_shutdown")
            elif sig_type == "news" and score > 8:
                subtypes.add("news_conflict")
            elif sig_type == "satellite":
                subtypes.add("satellite_fire")
            elif sig_type == "social":
                if keywords & unrest_kws:
                    subtypes.add("social_unrest")

        return subtypes

    def apply_correlation_bonuses(
        self, region: str, signals: list[dict]
    ) -> float:
        """
        Calculate the total correlation bonus for a region's signal set.

        Checks every key in CORRELATION_BONUSES to see if all required
        sub-types are present.

        Args:
            region: Region name (used for logging only).
            signals: Signals in this region's window.

        Returns:
            Total bonus score (float).
        """
        subtypes = self.detect_signal_types(signals)
        total_bonus = 0.0

        for combo, bonus in CORRELATION_BONUSES.items():
            combo_set = set(combo)
            if combo_set.issubset(subtypes):
                logger.info(
                    f"CorrelationEngine: bonus +{bonus} for {region} "
                    f"(matched {combo})"
                )
                total_bonus += bonus

        return total_bonus

    def correlate_all(self, signals: list[dict]) -> list[dict]:
        """
        Apply regional correlation bonuses to every signal in the list.

        Steps:
        1. Group signals by region within a 24-hour window.
        2. For each region, compute correlation bonus.
        3. Distribute the bonus proportionally across the region's signals.
        4. Re-classify severity after score adjustment.
        5. Flag correlated signals.

        Args:
            signals: Full list of scored signal dicts.

        Returns:
            Updated list of signal dicts with correlation fields added.
        """
        # Work on copies so we don't mutate the originals
        updated = [dict(sig) for sig in signals]

        # Build an id → index map for efficient updates
        id_to_idx: dict[str, int] = {sig["id"]: i for i, sig in enumerate(updated)}

        groups = self.group_by_region_and_window(updated, hours=24)

        for region, region_signals in groups.items():
            bonus = self.apply_correlation_bonuses(region, region_signals)
            if bonus == 0.0:
                for sig in region_signals:
                    idx = id_to_idx.get(sig["id"])
                    if idx is not None:
                        updated[idx]["correlated"] = False
                        updated[idx]["correlation_bonus"] = 0.0
                continue

            # Distribute bonus evenly across the region's signals
            n = len(region_signals)
            per_signal_bonus = bonus / n if n > 0 else 0.0

            for sig in region_signals:
                idx = id_to_idx.get(sig["id"])
                if idx is None:
                    continue
                new_score = min(30.0, updated[idx]["raw_score"] + per_signal_bonus)
                updated[idx]["raw_score"] = round(new_score, 2)
                updated[idx]["severity"] = classify_severity(new_score)
                updated[idx]["correlated"] = True
                updated[idx]["correlation_bonus"] = round(per_signal_bonus, 2)

        logger.info(
            f"CorrelationEngine: processed {len(groups)} regions, "
            f"{len(updated)} signals total."
        )
        return updated


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from mock_data_generator import generate_all_mock_signals
    from threat_engine import ThreatEngine

    print("=== correlation_engine.py self-test ===\n")

    signals = generate_all_mock_signals()
    engine_threat = ThreatEngine()
    scored = engine_threat.score_all(signals)

    engine_corr = CorrelationEngine()
    correlated = engine_corr.correlate_all(scored)

    bonus_signals = [s for s in correlated if s.get("correlated")]
    print(f"Total signals: {len(correlated)}")
    print(f"Signals with correlation bonus: {len(bonus_signals)}\n")

    print("Sample correlated signals:")
    for sig in bonus_signals[:5]:
        print(
            f"  [{sig['severity']:8s}] score={sig['raw_score']:5.1f} "
            f"bonus=+{sig['correlation_bonus']} | {sig['location']:20s} | {sig['title'][:50]}"
        )

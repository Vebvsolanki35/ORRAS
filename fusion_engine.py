"""
fusion_engine.py — Dual-track signal fusion for the ORRAS system.

Combines conflict-track scores and disaster-track scores into a single
composite fusion score, applying configurable weights for each track.
"""

from config import CONFLICT_WEIGHT, DISASTER_WEIGHT
from utils import classify_severity, get_logger

logger = get_logger(__name__)

# Fusion severity thresholds
_FUSION_THRESHOLDS: dict[str, float] = {
    "CRITICAL":     21.0,
    "HIGH":         11.0,
    "MEDIUM":        6.0,
    "LOW":           0.0,
}


def classify_fusion_severity(score: float) -> str:
    """
    Map a numeric fusion score to a severity label.

    Thresholds:
      CRITICAL : score >= 21
      HIGH     : score >= 11
      MEDIUM   : score >= 6
      LOW      : score <  6

    Args:
        score: Numeric fusion score (0–30).

    Returns:
        One of "LOW", "MEDIUM", "HIGH", "CRITICAL".
    """
    if score >= _FUSION_THRESHOLDS["CRITICAL"]:
        return "CRITICAL"
    if score >= _FUSION_THRESHOLDS["HIGH"]:
        return "HIGH"
    if score >= _FUSION_THRESHOLDS["MEDIUM"]:
        return "MEDIUM"
    return "LOW"


class FusionEngine:
    """
    Fuses conflict and disaster scores into a single composite score.

    fusion_score = (raw_score * CONFLICT_WEIGHT) + (disaster_score * DISASTER_WEIGHT)

    The result is clamped to [0, 30].
    """

    def __init__(
        self,
        conflict_weight: float = CONFLICT_WEIGHT,
        disaster_weight: float = DISASTER_WEIGHT,
    ) -> None:
        self.conflict_weight = conflict_weight
        self.disaster_weight = disaster_weight

    def fuse_signal(self, signal: dict) -> dict:
        """
        Compute a fusion score for a single signal.

        Reads raw_score (conflict track) and disaster_score (disaster track),
        applies weighted combination, clamps to [0, 30], and sets:
          - fusion_score
          - fusion_severity

        Args:
            signal: A unified-schema signal dict (modified in-place).

        Returns:
            The same signal dict with fusion_score and fusion_severity set.
        """
        conflict_score = float(signal.get("raw_score") or 0.0)
        disaster_score = float(signal.get("disaster_score") or 0.0)
        track = signal.get("track", "both")

        # Apply track gating: only use the relevant score per track
        if track == "conflict":
            disaster_score = 0.0
        elif track == "disaster":
            conflict_score = 0.0

        fusion = (conflict_score * self.conflict_weight) + (
            disaster_score * self.disaster_weight
        )
        fusion = round(max(0.0, min(30.0, fusion)), 2)

        signal["fusion_score"] = fusion
        signal["fusion_severity"] = classify_fusion_severity(fusion)
        return signal

    def fuse_all(self, signals: list[dict]) -> list[dict]:
        """
        Apply fuse_signal to every signal in the list.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            Updated list with fusion_score and fusion_severity on each signal.
        """
        result = [self.fuse_signal(s) for s in signals]
        logger.info(f"FusionEngine: fused {len(result)} signals.")
        return result

    def get_top_fused(self, signals: list[dict], n: int = 10) -> list[dict]:
        """
        Return the top-n signals sorted by fusion_score descending.

        Args:
            signals: List of fused signal dicts.
            n: Maximum number of results to return.

        Returns:
            List of up to n signals with the highest fusion scores.
        """
        scored = [s for s in signals if "fusion_score" in s]
        scored.sort(key=lambda s: s["fusion_score"], reverse=True)
        return scored[:n]

    def get_severity_distribution(self, signals: list[dict]) -> dict[str, int]:
        """
        Count signals per fusion severity level.

        Args:
            signals: List of fused signal dicts.

        Returns:
            Dict: {LOW: n, MEDIUM: n, HIGH: n, CRITICAL: n}
        """
        dist: dict[str, int] = {"LOW": 0, "MEDIUM": 0, "HIGH": 0, "CRITICAL": 0}
        for sig in signals:
            sev = sig.get("fusion_severity") or classify_fusion_severity(
                float(sig.get("fusion_score") or 0.0)
            )
            if sev in dist:
                dist[sev] += 1
        return dist


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== fusion_engine.py self-test ===\n")

    test_signals = [
        {
            "id": "f-001", "title": "Missile strike near conflict zone",
            "raw_score": 20.0, "disaster_score": 5.0, "track": "conflict",
        },
        {
            "id": "f-002", "title": "Earthquake and tsunami warning",
            "raw_score": 3.0, "disaster_score": 22.0, "track": "disaster",
        },
        {
            "id": "f-003", "title": "Armed conflict amid flooding disaster",
            "raw_score": 15.0, "disaster_score": 14.0, "track": "both",
        },
        {
            "id": "f-004", "title": "Minor unrest reported",
            "raw_score": 4.0, "disaster_score": 2.0, "track": "conflict",
        },
    ]

    engine = FusionEngine()
    fused = engine.fuse_all(test_signals)

    print("Fused signals:")
    for sig in fused:
        print(
            f"  [{sig['id']}] fusion_score={sig['fusion_score']:5.2f}  "
            f"severity={sig['fusion_severity']:8s}  track={sig.get('track', 'both')}"
        )

    print("\nTop 2 by fusion score:")
    for sig in engine.get_top_fused(fused, n=2):
        print(f"  {sig['id']}: {sig['fusion_score']}")

    dist = engine.get_severity_distribution(fused)
    print(f"\nSeverity distribution: {dist}")
    print("\n✅ fusion_engine.py self-test complete.")

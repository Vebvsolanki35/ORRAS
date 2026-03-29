"""
threat_engine.py — Keyword-based threat scoring for individual signals.

Computes a conflict_score for each signal by matching KEYWORD_WEIGHTS against
the signal's text, applies a source reliability multiplier, and classifies
severity. Supports dual-track signals (conflict / disaster / both).
"""

from collections import Counter
from typing import Any

from config import KEYWORD_WEIGHTS, SOURCE_MULTIPLIERS
from utils import classify_severity, get_logger, load_json

logger = get_logger(__name__)


class ThreatEngine:
    """
    Scores individual signals and ranks them by conflict threat level.
    """

    def score_signal(self, signal: dict) -> dict:
        """
        Compute a conflict threat score for a single signal.

        Algorithm:
        1. Concatenate title + description, lower-case.
        2. Sum KEYWORD_WEIGHTS for each matched keyword.
        3. Multiply by SOURCE_MULTIPLIERS for the signal's source (default 1.0).
        4. Clamp to [0, 30].
        5. Set raw_score, conflict_score (same value), keywords_matched,
           severity and conflict_severity from classify_severity.

        For disaster-only signals (track == "disaster"):
           conflict_score = 0, conflict_severity = "LOW".

        Args:
            signal: A unified-schema signal dict (modified in-place).

        Returns:
            The same signal dict with updated fields.
        """
        track = signal.get("track", "conflict")

        # Disaster-only signals receive zero conflict scoring
        if track == "disaster":
            signal.setdefault("raw_score", 0.0)
            signal["conflict_score"] = 0.0
            signal["conflict_severity"] = "LOW"
            signal.setdefault("keywords_matched", [])
            signal.setdefault("severity", "LOW")
            return signal

        text = (
            (signal.get("title") or "") + " " + (signal.get("description") or "")
        ).lower()

        matched: list[str] = []
        total_weight: float = 0.0
        for keyword, weight in KEYWORD_WEIGHTS.items():
            if keyword in text:
                matched.append(keyword)
                total_weight += weight

        multiplier = SOURCE_MULTIPLIERS.get(signal.get("source", ""), 1.0)
        raw_score = max(0.0, min(30.0, total_weight * multiplier))

        signal["raw_score"] = round(raw_score, 2)
        signal["conflict_score"] = round(raw_score, 2)
        signal["keywords_matched"] = matched
        signal["severity"] = classify_severity(raw_score)
        signal["conflict_severity"] = classify_severity(raw_score)

        return signal

    def score_all(self, signals: list[dict]) -> list[dict]:
        """
        Score every signal, sorting descending by raw_score.

        Only scores signals where track == "conflict" or "both" (or unset).
        Disaster-only signals receive conflict_score=0 and conflict_severity="LOW".

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            List sorted by raw_score (highest first).
        """
        scored = [self.score_signal(sig) for sig in signals]
        scored.sort(key=lambda s: s.get("raw_score") or 0.0, reverse=True)
        logger.info(f"ThreatEngine: scored {len(scored)} signals.")
        return scored

    def get_top_keywords(self, signals: list[dict], n: int = 20) -> dict[str, int]:
        """
        Aggregate all matched keywords across signals and return the top n.

        Args:
            signals: Scored signal list (each with 'keywords_matched').
            n: Number of top keywords to return.

        Returns:
            Dict mapping keyword → occurrence count, highest first.
        """
        counter: Counter = Counter()
        for sig in signals:
            counter.update(sig.get("keywords_matched") or [])
        return dict(counter.most_common(n))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from config import SIGNALS_FILE
    from mock_data_generator import generate_all_mock_signals
    from utils import save_json

    print("=== threat_engine.py self-test ===\n")

    signals = load_json(SIGNALS_FILE)
    if not signals:
        print("No signals.json found — generating mock signals…")
        signals = generate_all_mock_signals()
        save_json(SIGNALS_FILE, signals)

    # Tag some signals with explicit tracks for testing
    for i, sig in enumerate(signals):
        if i % 5 == 0:
            sig["track"] = "disaster"
        elif i % 5 == 1:
            sig["track"] = "both"
        else:
            sig["track"] = "conflict"

    engine = ThreatEngine()
    scored = engine.score_all(signals)

    conflict_sigs = [s for s in scored if s.get("track") != "disaster"]
    disaster_sigs = [s for s in scored if s.get("track") == "disaster"]

    print(f"Total signals scored: {len(scored)}")
    print(f"  Conflict/both: {len(conflict_sigs)}")
    print(f"  Disaster-only (conflict_score=0): {len(disaster_sigs)}\n")

    print("Top 5 signals by conflict score:")
    for i, sig in enumerate(conflict_sigs[:5], 1):
        print(
            f"  {i}. [{sig['conflict_severity']:8s}] conflict_score={sig['conflict_score']:5.1f} | "
            f"{sig['location']:25s} | {sig['title'][:55]}"
        )

    assert all(s["conflict_score"] == 0.0 for s in disaster_sigs), \
        "Disaster-only signals must have conflict_score=0"
    assert all(s["conflict_severity"] == "LOW" for s in disaster_sigs), \
        "Disaster-only signals must have conflict_severity=LOW"

    print("\nTop keyword counts:")
    kw = engine.get_top_keywords(scored)
    for keyword, count in list(kw.items())[:10]:
        print(f"  {keyword:20s}: {count}")

    print("\n✅ threat_engine.py self-test passed.")

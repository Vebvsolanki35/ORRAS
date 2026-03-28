"""
threat_engine.py — Keyword-based threat scoring for individual signals.

Computes a raw_score for each signal by matching KEYWORD_WEIGHTS against the
signal's text, applies a source reliability multiplier, and classifies severity.
"""

from collections import Counter
from typing import Any

from config import KEYWORD_WEIGHTS, SOURCE_MULTIPLIERS
from utils import classify_severity, get_logger, load_json

logger = get_logger(__name__)


class ThreatEngine:
    """
    Scores individual signals and ranks them by threat level.
    """

    def score_signal(self, signal: dict) -> dict:
        """
        Compute a threat score for a single signal.

        Algorithm:
        1. Concatenate title + description, lower-case.
        2. Sum KEYWORD_WEIGHTS for each matched keyword.
        3. Multiply by SOURCE_MULTIPLIERS for the signal's source.
        4. Clamp to [0, 30].

        Args:
            signal: A unified-schema signal dict (modified in-place).

        Returns:
            The same signal dict with updated raw_score, keywords_matched,
            and severity fields.
        """
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
        signal["keywords_matched"] = matched
        signal["severity"] = classify_severity(raw_score)

        return signal

    def score_all(self, signals: list[dict]) -> list[dict]:
        """
        Score every signal in the list, then sort descending by raw_score.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            List sorted by raw_score (highest first).
        """
        scored = [self.score_signal(sig) for sig in signals]
        scored.sort(key=lambda s: s["raw_score"], reverse=True)
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

    # Load existing signals or generate fresh ones
    signals = load_json(SIGNALS_FILE)
    if not signals:
        print("No signals.json found — generating mock signals…")
        signals = generate_all_mock_signals()
        save_json(SIGNALS_FILE, signals)

    engine = ThreatEngine()
    scored = engine.score_all(signals)

    print(f"Total signals scored: {len(scored)}\n")
    print("Top 5 signals by threat score:")
    for i, sig in enumerate(scored[:5], 1):
        print(
            f"  {i}. [{sig['severity']:8s}] score={sig['raw_score']:5.1f} | "
            f"{sig['location']:25s} | {sig['title'][:60]}"
        )

    print("\nTop keyword counts:")
    kw = engine.get_top_keywords(scored)
    for keyword, count in list(kw.items())[:10]:
        print(f"  {keyword:20s}: {count}")

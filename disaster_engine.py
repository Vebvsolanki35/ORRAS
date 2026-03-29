"""
disaster_engine.py — Disaster-track scoring engine for ORRAS.

Scores signals against DISASTER_KEYWORD_WEIGHTS, applies source multipliers
specific to disaster data providers, and classifies disaster severity.
Supports dual-track architecture: conflict-only signals receive zero disaster
scores; disaster/both signals are fully scored.
"""

from collections import defaultdict
from typing import Any

from config import DISASTER_KEYWORD_WEIGHTS
from utils import classify_severity, get_logger

logger = get_logger(__name__)

# Disaster source multipliers
_DISASTER_SOURCE_MULTIPLIERS: dict[str, float] = {
    "USGS": 1.3,
    "NOAA": 1.2,
    "NASA FIRMS": 1.3,
    "WHO": 1.2,
    "ReliefWeb": 1.0,
}


def classify_disaster_severity(score: float) -> str:
    """
    Map a numeric score to a disaster severity label.

    Thresholds:
      CATASTROPHIC : score >= 21
      SEVERE       : score >= 11
      MODERATE     : score >= 6
      MINOR        : score <  6

    Args:
        score: Numeric disaster score (0–30).

    Returns:
        One of "MINOR", "MODERATE", "SEVERE", "CATASTROPHIC".
    """
    if score >= 21:
        return "CATASTROPHIC"
    if score >= 11:
        return "SEVERE"
    if score >= 6:
        return "MODERATE"
    return "MINOR"


class DisasterEngine:
    """
    Scores individual signals on the disaster track and provides
    aggregation helpers for hotspot detection and index computation.
    """

    def score_disaster_signal(self, signal: dict) -> dict:
        """
        Compute a disaster score for a single signal.

        Algorithm:
        1. Concatenate title + description, lower-case.
        2. Sum DISASTER_KEYWORD_WEIGHTS for each matched keyword.
        3. Multiply by the disaster source multiplier (default 1.0).
        4. Clamp to [0, 30].
        5. Set disaster_score, disaster_keywords_matched,
           disaster_severity from classify_disaster_severity.

        For conflict-only signals (track == "conflict"):
           disaster_score = 0, disaster_severity = "MINOR".

        Args:
            signal: A unified-schema signal dict (modified in-place).

        Returns:
            The same signal dict with updated disaster fields.
        """
        track = signal.get("track", "disaster")

        # Conflict-only signals receive zero disaster scoring
        if track == "conflict":
            signal["disaster_score"] = 0.0
            signal["disaster_severity"] = "MINOR"
            signal.setdefault("disaster_keywords_matched", [])
            return signal

        text = (
            (signal.get("title") or "") + " " + (signal.get("description") or "")
        ).lower()

        matched: list[str] = []
        total_weight: float = 0.0
        for keyword, weight in DISASTER_KEYWORD_WEIGHTS.items():
            if keyword in text:
                matched.append(keyword)
                total_weight += weight

        source = signal.get("source", "")
        multiplier = _DISASTER_SOURCE_MULTIPLIERS.get(source, 1.0)
        disaster_score = max(0.0, min(30.0, total_weight * multiplier))

        signal["disaster_score"] = round(disaster_score, 2)
        signal["disaster_keywords_matched"] = matched
        signal["disaster_severity"] = classify_disaster_severity(disaster_score)

        return signal

    def score_all(self, signals: list[dict]) -> list[dict]:
        """
        Apply score_disaster_signal to every signal in the list.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            The same list with disaster fields set on each signal.
        """
        scored = [self.score_disaster_signal(sig) for sig in signals]
        logger.info(f"DisasterEngine: scored {len(scored)} signals.")
        return scored

    def get_disaster_hotspots(self, signals: list[dict], n: int = 5) -> list[dict]:
        """
        Identify the top-n locations by average disaster score.

        Args:
            signals: List of scored signal dicts.
            n: Number of hotspots to return.

        Returns:
            List of dicts (sorted by avg_disaster_score desc), each with:
            {location, avg_disaster_score, signal_count, max_severity}
        """
        location_scores: dict[str, list[float]] = defaultdict(list)
        for sig in signals:
            location = sig.get("location") or "Unknown"
            score = float(sig.get("disaster_score") or 0.0)
            location_scores[location].append(score)

        hotspots = []
        for location, scores in location_scores.items():
            avg = sum(scores) / len(scores) if scores else 0.0
            max_sev = classify_disaster_severity(max(scores, default=0.0))
            hotspots.append({
                "location": location,
                "avg_disaster_score": round(avg, 2),
                "signal_count": len(scores),
                "max_severity": max_sev,
            })

        hotspots.sort(key=lambda h: h["avg_disaster_score"], reverse=True)
        return hotspots[:n]

    def compute_disaster_index(self, signals: list[dict]) -> dict[str, int]:
        """
        Count signals per disaster severity level.

        Args:
            signals: List of scored signal dicts.

        Returns:
            Dict: {MINOR: n, MODERATE: n, SEVERE: n, CATASTROPHIC: n}
        """
        index: dict[str, int] = {
            "MINOR": 0,
            "MODERATE": 0,
            "SEVERE": 0,
            "CATASTROPHIC": 0,
        }
        for sig in signals:
            sev = sig.get("disaster_severity") or classify_disaster_severity(
                float(sig.get("disaster_score") or 0.0)
            )
            if sev in index:
                index[sev] += 1
        logger.info(f"DisasterEngine: index computed — {index}")
        return index


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from mock_data_generator import generate_all_mock_signals

    print("=== disaster_engine.py self-test ===\n")

    signals = generate_all_mock_signals()

    # Assign tracks: every 3rd signal is disaster, every 4th is both, rest conflict
    for i, sig in enumerate(signals):
        if i % 4 == 0:
            sig["track"] = "disaster"
        elif i % 4 == 1:
            sig["track"] = "both"
        else:
            sig["track"] = "conflict"

    # Inject a handful of explicit disaster signals
    import uuid
    from datetime import datetime, timezone

    disaster_templates = [
        ("Earthquake M7.2 strikes Turkey coast", "earthquake tsunami casualties evacuation magnitude 7.2"),
        ("Flood emergency declared in Bangladesh", "flood displacement aid relief casualties civilian"),
        ("Wildfire outbreak in California", "wildfire evacuation casualties surge emergency"),
        ("Hurricane Category 4 nears Haiti", "hurricane storm surge displacement evacuation"),
        ("WHO alerts: disease outbreak in DR Congo", "outbreak disease epidemic casualties aid famine"),
    ]
    for title, desc in disaster_templates:
        signals.append({
            "id": str(uuid.uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "type": "news",
            "source": "ReliefWeb",
            "location": "Test Region",
            "latitude": 10.0,
            "longitude": 20.0,
            "title": title,
            "description": desc,
            "raw_score": 0.0,
            "keywords_matched": [],
            "severity": "LOW",
            "track": "disaster",
        })

    engine = DisasterEngine()
    scored = engine.score_all(signals)

    disaster_scored = [s for s in scored if s.get("track") in ("disaster", "both")]
    conflict_only = [s for s in scored if s.get("track") == "conflict"]

    print(f"Total signals: {len(scored)}")
    print(f"  Disaster/both scored: {len(disaster_scored)}")
    print(f"  Conflict-only (disaster_score=0): {len(conflict_only)}\n")

    print("Top 5 disaster signals by score:")
    top5 = sorted(disaster_scored, key=lambda s: s["disaster_score"], reverse=True)[:5]
    for i, sig in enumerate(top5, 1):
        print(
            f"  {i}. [{sig['disaster_severity']:12s}] score={sig['disaster_score']:5.1f} | "
            f"{sig['location']:20s} | {sig['title'][:50]}"
        )

    hotspots = engine.get_disaster_hotspots(scored, n=5)
    print("\nTop 5 disaster hotspots:")
    for h in hotspots:
        print(
            f"  {h['location']:25s} avg={h['avg_disaster_score']:5.2f} "
            f"count={h['signal_count']} max={h['max_severity']}"
        )

    index = engine.compute_disaster_index(scored)
    print(f"\nDisaster index: {index}")

    assert all(s["disaster_score"] == 0.0 for s in conflict_only), \
        "Conflict-only signals must have disaster_score=0"
    assert all(s["disaster_severity"] == "MINOR" for s in conflict_only), \
        "Conflict-only signals must have disaster_severity=MINOR"

    # Verify injected disaster signals got scored
    injected = [s for s in scored if s.get("location") == "Test Region"]
    assert any(s["disaster_score"] > 0 for s in injected), \
        "Injected disaster signals must have non-zero disaster_score"

    print("\n✅ disaster_engine.py self-test passed.")

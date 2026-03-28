"""
confidence_engine.py — Multi-source confidence scorer for ORRAS.

Assigns a confidence level to each region based on how many independent data
sources have reported signals for that region. More sources → higher confidence.
"""

from utils import get_logger

logger = get_logger(__name__)

# Confidence mapping: source_count → (label, score)
_CONFIDENCE_MAP = {
    1: ("Low", 0.33),
    2: ("Medium", 0.66),
}
_HIGH_CONFIDENCE = ("High", 1.0)


class ConfidenceEngine:
    """
    Scores the confidence of threat intelligence by region based on
    source diversity.
    """

    def score_confidence(self, signals: list[dict]) -> dict[str, dict]:
        """
        Group signals by region and compute confidence from source diversity.

        Mapping:
        - 1 unique source  → Low   (0.33)
        - 2 unique sources → Medium (0.66)
        - 3+ unique sources → High  (1.0)

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            Dict: {
                region: {
                    "source_count": int,
                    "sources": list[str],
                    "confidence": str,       # "Low" | "Medium" | "High"
                    "confidence_score": float  # 0.0 – 1.0
                }
            }
        """
        region_sources: dict[str, set[str]] = {}
        for sig in signals:
            location = sig.get("location") or "Unknown"
            source = sig.get("source") or "Unknown"
            region_sources.setdefault(location, set()).add(source)

        result: dict[str, dict] = {}
        for region, sources in region_sources.items():
            n = len(sources)
            if n >= 3:
                label, score = _HIGH_CONFIDENCE
            else:
                label, score = _CONFIDENCE_MAP.get(n, ("Low", 0.33))
            result[region] = {
                "source_count": n,
                "sources": sorted(sources),
                "confidence": label,
                "confidence_score": round(score, 2),
            }

        logger.info(f"ConfidenceEngine: scored {len(result)} regions.")
        return result

    def annotate_signals(
        self, signals: list[dict], confidence_map: dict[str, dict]
    ) -> list[dict]:
        """
        Add confidence and confidence_score fields to each signal based on
        its region's confidence rating.

        Args:
            signals: List of unified-schema signal dicts.
            confidence_map: Output of score_confidence().

        Returns:
            List of signals with "confidence" and "confidence_score" added.
        """
        annotated = []
        for sig in signals:
            sig = dict(sig)  # copy to avoid mutating original
            location = sig.get("location") or "Unknown"
            conf_data = confidence_map.get(location, {})
            sig["confidence"] = conf_data.get("confidence", "Low")
            sig["confidence_score"] = conf_data.get("confidence_score", 0.33)
            annotated.append(sig)
        return annotated


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from mock_data_generator import generate_all_mock_signals
    from threat_engine import ThreatEngine

    print("=== confidence_engine.py self-test ===\n")

    signals = generate_all_mock_signals()
    engine_threat = ThreatEngine()
    scored = engine_threat.score_all(signals)

    conf_engine = ConfidenceEngine()
    conf_map = conf_engine.score_confidence(scored)
    annotated = conf_engine.annotate_signals(scored, conf_map)

    print(f"Regions scored: {len(conf_map)}\n")

    # Show distribution of confidence levels
    from collections import Counter
    dist = Counter(v["confidence"] for v in conf_map.values())
    print("Confidence distribution:")
    for level, count in sorted(dist.items()):
        print(f"  {level:8s}: {count} region(s)")

    # Show high-confidence regions
    high = {r: d for r, d in conf_map.items() if d["confidence"] == "High"}
    if high:
        print("\nHigh-confidence regions (3+ sources):")
        for region, data in list(high.items())[:5]:
            print(f"  {region:25s}: {data['sources']}")

    print(f"\nSample annotated signal:")
    print(json.dumps(annotated[0], indent=2))

    print("\n✅ confidence_engine.py self-test passed.")

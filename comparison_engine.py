"""
comparison_engine.py — Regional comparison and ranking engine for ORRAS v2.0.

Provides tools to profile individual regions, compare pairs of regions,
rank all regions by threat score, and find regions with similar threat
profiles based on keyword overlap and score proximity.
"""

from collections import Counter
from typing import Any

from utils import classify_severity, get_logger, now_iso

logger = get_logger(__name__)


class ComparisonEngine:
    """
    Analyses and compares regional threat profiles derived from signal data.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _signals_for_region(self, signals: list[dict], region: str) -> list[dict]:
        """Return signals that belong to *region* (case-insensitive)."""
        region_lower = region.lower()
        return [s for s in signals if (s.get("location") or "").lower() == region_lower]

    def _all_regions(self, signals: list[dict]) -> list[str]:
        """Return deduplicated list of region names present in *signals*."""
        seen: dict[str, str] = {}
        for s in signals:
            loc = s.get("location") or "Unknown"
            seen[loc.lower()] = loc
        return list(seen.values())

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_region_profile(self, signals: list[dict], region: str) -> dict[str, Any]:
        """
        Build a comprehensive threat profile for a single region.

        Args:
            signals: Full list of unified-schema signal dicts.
            region:  Region / country name to profile.

        Returns:
            Dict with keys: region, current_score, severity, signal_count,
            top_keywords, source_breakdown, type_breakdown, confidence,
            trend, top_signals.
        """
        region_signals = self._signals_for_region(signals, region)

        if not region_signals:
            logger.warning(f"ComparisonEngine: no signals found for region '{region}'.")
            return {
                "region": region,
                "current_score": 0.0,
                "severity": "LOW",
                "signal_count": 0,
                "top_keywords": [],
                "source_breakdown": {},
                "type_breakdown": {},
                "confidence": "LOW",
                "trend": "STABLE",
                "top_signals": [],
            }

        # Average raw_score across all signals for this region
        scores = [float(s.get("raw_score") or 0.0) for s in region_signals]
        current_score = round(sum(scores) / len(scores), 2)

        # Aggregate keywords across all signals
        all_keywords: list[str] = []
        for s in region_signals:
            kw = s.get("keywords_matched") or []
            all_keywords.extend(kw if isinstance(kw, list) else [kw])
        top_keywords = [kw for kw, _ in Counter(all_keywords).most_common(5)]

        # Count by source and type
        source_breakdown = dict(Counter(s.get("source") or "Unknown" for s in region_signals))
        type_breakdown = dict(Counter(s.get("type") or "Unknown" for s in region_signals))

        # Confidence based on number of unique sources
        unique_sources = len(source_breakdown)
        if unique_sources >= 3:
            confidence = "HIGH"
        elif unique_sources == 2:
            confidence = "MEDIUM"
        else:
            confidence = "LOW"

        # Trend: compare avg score of last 3 vs first 3 signals (sorted by timestamp)
        sorted_signals = sorted(
            region_signals,
            key=lambda s: s.get("timestamp") or "",
        )
        sorted_scores = [float(s.get("raw_score") or 0.0) for s in sorted_signals]

        if len(sorted_scores) >= 6:
            first_avg = sum(sorted_scores[:3]) / 3
            last_avg = sum(sorted_scores[-3:]) / 3
            if last_avg > first_avg:
                trend = "RISING"
            elif last_avg < first_avg:
                trend = "FALLING"
            else:
                trend = "STABLE"
        else:
            trend = "STABLE"

        # Top 3 signals by raw_score
        top_signals = sorted(region_signals, key=lambda s: float(s.get("raw_score") or 0.0), reverse=True)[:3]

        logger.info(f"ComparisonEngine: profiled '{region}' — score={current_score}, severity={classify_severity(current_score)}.")

        return {
            "region": region,
            "current_score": current_score,
            "severity": classify_severity(current_score),
            "signal_count": len(region_signals),
            "top_keywords": top_keywords,
            "source_breakdown": source_breakdown,
            "type_breakdown": type_breakdown,
            "confidence": confidence,
            "trend": trend,
            "top_signals": top_signals,
        }

    def compare_regions(
        self, signals: list[dict], region1: str, region2: str
    ) -> dict[str, Any]:
        """
        Compare two regions head-to-head and identify shared / unique keywords.

        Args:
            signals: Full list of unified-schema signal dicts.
            region1: First region name.
            region2: Second region name.

        Returns:
            Dict with keys: region1 profile, region2 profile, winner_score,
            score_delta, common_keywords, unique_to_r1, unique_to_r2, summary.
        """
        profile1 = self.get_region_profile(signals, region1)
        profile2 = self.get_region_profile(signals, region2)

        kw1 = set(profile1["top_keywords"])
        kw2 = set(profile2["top_keywords"])
        common_keywords = sorted(kw1 & kw2)
        unique_to_r1 = sorted(kw1 - kw2)
        unique_to_r2 = sorted(kw2 - kw1)

        score1 = profile1["current_score"]
        score2 = profile2["current_score"]
        score_delta = round(abs(score1 - score2), 2)

        if score1 > score2:
            winner_score = region1
        elif score2 > score1:
            winner_score = region2
        else:
            winner_score = "TIE"

        summary = (
            f"{winner_score} leads with a score delta of {score_delta:.1f}. "
            f"{region1}: {profile1['severity']} ({score1}), "
            f"{region2}: {profile2['severity']} ({score2}). "
            f"Common threat indicators: {', '.join(common_keywords) or 'none'}."
        ) if winner_score != "TIE" else (
            f"{region1} and {region2} are tied at score {score1}. "
            f"Common threat indicators: {', '.join(common_keywords) or 'none'}."
        )

        logger.info(f"ComparisonEngine: compared '{region1}' vs '{region2}' — winner={winner_score}.")

        return {
            region1: profile1,
            region2: profile2,
            "winner_score": winner_score,
            "score_delta": score_delta,
            "common_keywords": common_keywords,
            "unique_to_r1": unique_to_r1,
            "unique_to_r2": unique_to_r2,
            "summary": summary,
        }

    def rank_all_regions(self, signals: list[dict]) -> list[dict[str, Any]]:
        """
        Rank every region present in *signals* by descending threat score.

        Args:
            signals: Full list of unified-schema signal dicts.

        Returns:
            List of region profile dicts with an added ``rank`` field,
            ordered from highest to lowest current_score.
        """
        regions = self._all_regions(signals)
        profiles = [self.get_region_profile(signals, r) for r in regions]
        profiles.sort(key=lambda p: p["current_score"], reverse=True)

        for i, profile in enumerate(profiles, start=1):
            profile["rank"] = i

        logger.info(f"ComparisonEngine: ranked {len(profiles)} regions.")
        return profiles

    def find_similar_regions(
        self, signals: list[dict], target_region: str, n: int = 3
    ) -> list[dict[str, Any]]:
        """
        Find the *n* regions most similar to *target_region*.

        Similarity is computed as a weighted combination of:
          - Jaccard keyword overlap (weight 0.6)
          - Score proximity normalised to [0, 1] (weight 0.4)

        Args:
            signals:       Full list of unified-schema signal dicts.
            target_region: Region to find neighbours for.
            n:             Number of similar regions to return.

        Returns:
            List of dicts: each is the region profile augmented with
            ``similarity_score`` and ``rank`` fields.
        """
        target_profile = self.get_region_profile(signals, target_region)
        target_kw = set(target_profile["top_keywords"])
        target_score = target_profile["current_score"]

        all_regions = [r for r in self._all_regions(signals) if r.lower() != target_region.lower()]

        # Determine the score range for normalisation
        all_scores = [
            float(s.get("raw_score") or 0.0) for s in signals
        ]
        score_range = max(all_scores) - min(all_scores) if len(all_scores) > 1 else 1.0
        score_range = score_range or 1.0  # avoid division by zero

        scored: list[tuple[float, dict]] = []
        for region in all_regions:
            profile = self.get_region_profile(signals, region)
            region_kw = set(profile["top_keywords"])

            # Jaccard similarity for keyword overlap
            union = target_kw | region_kw
            jaccard = len(target_kw & region_kw) / len(union) if union else 0.0

            # Normalised score proximity (1 = identical score)
            score_proximity = 1.0 - min(abs(profile["current_score"] - target_score) / score_range, 1.0)

            similarity = round(0.6 * jaccard + 0.4 * score_proximity, 4)
            profile["similarity_score"] = similarity
            scored.append((similarity, profile))

        scored.sort(key=lambda x: x[0], reverse=True)
        results = []
        for rank, (_, profile) in enumerate(scored[:n], start=1):
            profile["rank"] = rank
            results.append(profile)

        logger.info(f"ComparisonEngine: found {len(results)} similar regions to '{target_region}'.")
        return results


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from mock_data_generator import generate_all_mock_signals

    print("=== comparison_engine.py self-test ===\n")
    signals = generate_all_mock_signals()

    engine = ComparisonEngine()

    # --- get_region_profile ---
    regions = list({s.get("location") for s in signals if s.get("location")})
    target = regions[0]
    profile = engine.get_region_profile(signals, target)
    print(f"Profile for '{target}':")
    print(f"  score={profile['current_score']}, severity={profile['severity']}, "
          f"confidence={profile['confidence']}, trend={profile['trend']}, "
          f"signals={profile['signal_count']}")
    assert "rank" not in profile, "rank should not be in a plain profile"
    assert profile["severity"] in ("LOW", "MEDIUM", "HIGH", "CRITICAL")

    # --- compare_regions ---
    r1, r2 = regions[0], regions[1] if len(regions) > 1 else regions[0]
    comparison = engine.compare_regions(signals, r1, r2)
    print(f"\nComparison '{r1}' vs '{r2}':")
    print(f"  winner={comparison['winner_score']}, delta={comparison['score_delta']}")
    print(f"  summary: {comparison['summary']}")
    assert "winner_score" in comparison

    # --- rank_all_regions ---
    ranked = engine.rank_all_regions(signals)
    print(f"\nRanked regions (top 3 of {len(ranked)}):")
    for r in ranked[:3]:
        print(f"  #{r['rank']} {r['region']} — score={r['current_score']}, severity={r['severity']}")
    assert ranked[0]["rank"] == 1
    assert ranked[0]["current_score"] >= ranked[-1]["current_score"]

    # --- find_similar_regions ---
    similar = engine.find_similar_regions(signals, target, n=3)
    print(f"\nRegions similar to '{target}':")
    for s in similar:
        print(f"  #{s['rank']} {s['region']} — similarity={s['similarity_score']}")
    assert len(similar) <= 3

    print("\n✅ All comparison_engine.py tests passed.")

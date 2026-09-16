"""
quality_engine.py — Data-quality and pipeline-health assessment for ORRAS.

An intelligence platform is only as trustworthy as the signals feeding it.
This module measures that trustworthiness: it scores the current signal set
across completeness, geolocation, freshness, duplication and source
diversity, and reports per-source breakdowns so an analyst can see exactly
which feeds are degrading the picture.

All scoring is deterministic and offline-safe — it reads only the signal
dicts already produced by the pipeline.
"""

from __future__ import annotations

import re
from collections import Counter
from datetime import datetime, timedelta, timezone
from typing import Any

from utils import get_logger

logger = get_logger(__name__)

# Fields a signal must carry to be usable end-to-end in the dashboard.
REQUIRED_FIELDS: tuple[str, ...] = (
    "id", "timestamp", "type", "source", "location",
    "latitude", "longitude", "title", "severity",
)

# Fields that strengthen a signal but are not strictly required.
OPTIONAL_FIELDS: tuple[str, ...] = (
    "description", "raw_score", "conflict_score", "disaster_score",
    "confidence", "signal_class", "track", "fusion_score",
)

# Placeholder values that indicate geolocation failed.
_UNKNOWN_LOCATIONS = {"", "unknown", "n/a", "none", "-"}


def _is_unknown_location(location: Any) -> bool:
    """Return True when a location value carries no real geographic meaning."""
    if not isinstance(location, str):
        return True
    return location.strip().lower() in _UNKNOWN_LOCATIONS


def _parse_ts(value: Any) -> datetime | None:
    """Parse an ISO-8601 timestamp, returning None when it is unusable."""
    if not isinstance(value, str) or not value:
        return None
    try:
        ts = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    if ts.tzinfo is None:
        ts = ts.replace(tzinfo=timezone.utc)
    return ts


def _normalise_title(title: Any) -> str:
    """Lower-case and strip a title so near-duplicates can be compared."""
    if not isinstance(title, str):
        return ""
    return re.sub(r"[^a-z0-9 ]+", " ", title.lower()).strip()


class QualityEngine:
    """
    Computes data-quality metrics and an overall trust score for a signal set.

    The composite score is a weighted blend of five sub-scores, each in
    [0, 100]:

      completeness  — required fields present and non-empty
      geolocation   — signals resolved to a real place with valid coordinates
      freshness     — share of signals inside the freshness window
      uniqueness    — absence of duplicate ids / near-duplicate titles
      diversity     — how evenly the signal load is spread across sources

    Weights emphasise completeness and geolocation because a signal that
    cannot be placed on a map is of little operational use.
    """

    #: Weight applied to each sub-score in the composite.
    WEIGHTS: dict[str, float] = {
        "completeness": 0.25,
        "geolocation": 0.25,
        "freshness": 0.20,
        "uniqueness": 0.15,
        "diversity": 0.15,
    }

    #: A signal older than this is considered stale.
    FRESHNESS_WINDOW_HOURS: int = 48

    def __init__(self, freshness_window_hours: int = FRESHNESS_WINDOW_HOURS) -> None:
        self.freshness_window_hours = freshness_window_hours

    # ------------------------------------------------------------------
    # Sub-scores
    # ------------------------------------------------------------------

    def score_completeness(self, signals: list[dict]) -> dict:
        """
        Measure field-level completeness across the signal set.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict with ``score`` (0–100) and per-field ``missing`` counts.
        """
        if not signals:
            return {"score": 0.0, "missing": {}, "empty_required": 0}

        missing: Counter = Counter()
        empty_required = 0
        total_fields = 0

        for sig in signals:
            for field in REQUIRED_FIELDS:
                total_fields += 1
                value = sig.get(field)
                if field not in sig or value is None:
                    missing[field] += 1
                    empty_required += 1
                elif isinstance(value, str) and not value.strip():
                    missing[field] += 1
                    empty_required += 1

        score = 100.0 * (1.0 - (empty_required / total_fields)) if total_fields else 0.0
        return {
            "score": round(max(0.0, min(100.0, score)), 2),
            "missing": dict(missing),
            "empty_required": empty_required,
        }

    def score_geolocation(self, signals: list[dict]) -> dict:
        """
        Measure how many signals resolved to a real place with valid coords.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict with ``score``, ``unresolved`` count and ``bad_coords`` count.
        """
        if not signals:
            return {"score": 0.0, "unresolved": 0, "bad_coords": 0}

        unresolved = 0
        bad_coords = 0

        for sig in signals:
            if _is_unknown_location(sig.get("location")):
                unresolved += 1

            lat, lon = sig.get("latitude"), sig.get("longitude")
            try:
                lat_f, lon_f = float(lat), float(lon)
            except (TypeError, ValueError):
                bad_coords += 1
                continue
            if not (-90.0 <= lat_f <= 90.0 and -180.0 <= lon_f <= 180.0):
                bad_coords += 1
            elif lat_f == 0.0 and lon_f == 0.0:
                # (0, 0) is the classic "we failed to geocode" sentinel.
                bad_coords += 1

        unplaced = max(unresolved, bad_coords)
        score = 100.0 * (1.0 - (unplaced / len(signals)))
        return {
            "score": round(max(0.0, min(100.0, score)), 2),
            "unresolved": unresolved,
            "bad_coords": bad_coords,
        }

    def score_freshness(self, signals: list[dict]) -> dict:
        """
        Measure how much of the signal set is recent enough to act on.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict with ``score``, ``stale`` count, ``unparseable`` count and
            the oldest/newest timestamps observed.
        """
        if not signals:
            return {
                "score": 0.0, "stale": 0, "unparseable": 0,
                "oldest": None, "newest": None,
            }

        now = datetime.now(timezone.utc)
        cutoff = now - timedelta(hours=self.freshness_window_hours)

        timestamps: list[datetime] = []
        unparseable = 0
        for sig in signals:
            ts = _parse_ts(sig.get("timestamp"))
            if ts is None:
                unparseable += 1
            else:
                timestamps.append(ts)

        if not timestamps:
            return {
                "score": 0.0, "stale": len(signals), "unparseable": unparseable,
                "oldest": None, "newest": None,
            }

        fresh = sum(1 for ts in timestamps if ts >= cutoff)
        score = 100.0 * fresh / len(signals)
        return {
            "score": round(max(0.0, min(100.0, score)), 2),
            "stale": len(signals) - fresh,
            "unparseable": unparseable,
            "oldest": min(timestamps).isoformat(),
            "newest": max(timestamps).isoformat(),
        }

    def score_uniqueness(self, signals: list[dict]) -> dict:
        """
        Detect duplicate identifiers and near-duplicate headlines.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict with ``score``, ``duplicate_ids`` and ``near_duplicate_titles``.
        """
        if not signals:
            return {"score": 0.0, "duplicate_ids": 0, "near_duplicate_titles": 0}

        ids = [sig.get("id") for sig in signals if sig.get("id")]
        duplicate_ids = len(ids) - len(set(ids))

        titles = [_normalise_title(sig.get("title")) for sig in signals]
        titles = [t for t in titles if t]
        title_counts = Counter(titles)
        near_duplicate_titles = sum(c - 1 for c in title_counts.values() if c > 1)

        dupes = duplicate_ids + near_duplicate_titles
        score = 100.0 * (1.0 - min(1.0, dupes / len(signals)))
        return {
            "score": round(max(0.0, min(100.0, score)), 2),
            "duplicate_ids": duplicate_ids,
            "near_duplicate_titles": near_duplicate_titles,
        }

    def score_diversity(self, signals: list[dict]) -> dict:
        """
        Measure how evenly the signal load is spread across sources.

        A feed dominated by one source means the platform has effectively
        single-source vision, which undermines the whole fusion premise.
        Scored with normalised Shannon entropy.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict with ``score``, ``source_count``, ``dominant_source`` and
            ``dominant_share`` (0.0–1.0).
        """
        if not signals:
            return {
                "score": 0.0, "source_count": 0,
                "dominant_source": None, "dominant_share": 0.0,
            }

        counts = Counter(sig.get("source") or "Unknown" for sig in signals)
        total = sum(counts.values())
        source_count = len(counts)

        if source_count <= 1:
            return {
                "score": 0.0, "source_count": source_count,
                "dominant_source": counts.most_common(1)[0][0],
                "dominant_share": 1.0,
            }

        import math

        entropy = -sum(
            (c / total) * math.log(c / total) for c in counts.values() if c
        )
        max_entropy = math.log(source_count)
        score = 100.0 * (entropy / max_entropy) if max_entropy else 0.0

        dominant, dominant_n = counts.most_common(1)[0]
        return {
            "score": round(max(0.0, min(100.0, score)), 2),
            "source_count": source_count,
            "dominant_source": dominant,
            "dominant_share": round(dominant_n / total, 4),
        }

    # ------------------------------------------------------------------
    # Composite
    # ------------------------------------------------------------------

    def assess(self, signals: list[dict]) -> dict:
        """
        Run every sub-score and combine them into one quality report.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict with keys: total_signals, sub-scores under ``dimensions``,
            ``score`` (composite 0–100), ``grade`` (A–F), ``findings``
            (list of human-readable issues) and ``by_source`` breakdown.
        """
        if not signals:
            return {
                "total_signals": 0,
                "dimensions": {},
                "score": 0.0,
                "grade": "N/A",
                "findings": ["No signals to assess."],
                "by_source": {},
            }

        dimensions = {
            "completeness": self.score_completeness(signals),
            "geolocation": self.score_geolocation(signals),
            "freshness": self.score_freshness(signals),
            "uniqueness": self.score_uniqueness(signals),
            "diversity": self.score_diversity(signals),
        }

        composite = sum(
            dimensions[name]["score"] * weight
            for name, weight in self.WEIGHTS.items()
        )

        return {
            "total_signals": len(signals),
            "dimensions": dimensions,
            "score": round(composite, 2),
            "grade": self.grade_for(composite),
            "findings": self.build_findings(dimensions, len(signals)),
            "by_source": self.by_source(signals),
        }

    @staticmethod
    def grade_for(score: float) -> str:
        """Map a 0–100 quality score onto a letter grade."""
        if score >= 90:
            return "A"
        if score >= 80:
            return "B"
        if score >= 70:
            return "C"
        if score >= 60:
            return "D"
        return "F"

    def build_findings(self, dimensions: dict, total: int) -> list[str]:
        """
        Turn sub-scores into plain-language, actionable findings.

        Args:
            dimensions: Output of the individual score_* methods.
            total:      Number of signals assessed.

        Returns:
            List of finding strings (empty when the data is healthy).
        """
        findings: list[str] = []

        geo = dimensions.get("geolocation", {})
        if geo.get("unresolved"):
            findings.append(
                f"{geo['unresolved']} signal(s) could not be resolved to a "
                f"country — they will not appear on the map."
            )
        if geo.get("bad_coords"):
            findings.append(
                f"{geo['bad_coords']} signal(s) have missing or out-of-range "
                f"coordinates."
            )

        fresh = dimensions.get("freshness", {})
        if fresh.get("stale"):
            findings.append(
                f"{fresh['stale']} signal(s) are older than "
                f"{self.freshness_window_hours}h."
            )
        if fresh.get("unparseable"):
            findings.append(
                f"{fresh['unparseable']} signal(s) have unparseable timestamps."
            )

        uniq = dimensions.get("uniqueness", {})
        if uniq.get("duplicate_ids"):
            findings.append(
                f"{uniq['duplicate_ids']} duplicate signal id(s) detected."
            )
        if uniq.get("near_duplicate_titles"):
            findings.append(
                f"{uniq['near_duplicate_titles']} near-duplicate headline(s) "
                f"detected — the same event may be counted more than once."
            )

        div = dimensions.get("diversity", {})
        if div.get("dominant_share", 0) > 0.5:
            pct = round(div["dominant_share"] * 100)
            findings.append(
                f"Source mix is concentrated: {div.get('dominant_source')} "
                f"supplies {pct}% of all signals."
            )

        comp = dimensions.get("completeness", {})
        missing = comp.get("missing") or {}
        if missing:
            top = sorted(missing.items(), key=lambda kv: kv[1], reverse=True)[:3]
            detail = ", ".join(f"{k} ({v})" for k, v in top)
            findings.append(f"Missing required fields: {detail}.")

        return findings

    @staticmethod
    def by_source(signals: list[dict]) -> dict[str, dict]:
        """
        Break the signal set down per source for a health table.

        Args:
            signals: Unified-schema signal dicts.

        Returns:
            Dict keyed by source name with counts, severity mix, mean score
            and an unresolved-location count.
        """
        buckets: dict[str, dict[str, Any]] = {}

        for sig in signals:
            source = sig.get("source") or "Unknown"
            entry = buckets.setdefault(
                source,
                {
                    "count": 0,
                    "critical": 0,
                    "high": 0,
                    "unresolved": 0,
                    "score_sum": 0.0,
                },
            )
            entry["count"] += 1
            severity = str(sig.get("severity") or "LOW").upper()
            if severity == "CRITICAL":
                entry["critical"] += 1
            elif severity == "HIGH":
                entry["high"] += 1
            if _is_unknown_location(sig.get("location")):
                entry["unresolved"] += 1
            try:
                entry["score_sum"] += float(sig.get("raw_score") or 0.0)
            except (TypeError, ValueError):
                pass

        for entry in buckets.values():
            count = entry["count"] or 1
            entry["mean_score"] = round(entry["score_sum"] / count, 2)
            del entry["score_sum"]

        return dict(sorted(buckets.items(), key=lambda kv: kv[1]["count"], reverse=True))


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from datetime import timedelta

    print("=== quality_engine.py self-test ===\n")

    now = datetime.now(timezone.utc)

    def _sig(i: int, **over) -> dict:
        base = {
            "id": f"sig-{i}",
            "timestamp": (now - timedelta(hours=1)).isoformat(),
            "type": "news",
            "source": "GDELT",
            "location": "Ukraine",
            "latitude": 48.3,
            "longitude": 31.2,
            "title": f"Distinct event number {i}",
            "description": "test",
            "severity": "HIGH",
            "raw_score": 12.0,
        }
        base.update(over)
        return base

    # Healthy set: 3 sources, all located, all fresh, all unique
    healthy = [
        _sig(0, source="GDELT"),
        _sig(1, source="NewsAPI"),
        _sig(2, source="ACLED"),
        _sig(3, source="USGS"),
    ]
    engine = QualityEngine()
    report = engine.assess(healthy)
    print(f"Healthy set → score={report['score']} grade={report['grade']}")
    print(f"  findings: {report['findings'] or 'none'}")
    assert report["score"] >= 90, f"Expected a high score, got {report['score']}"
    assert not report["findings"], "Healthy data should produce no findings"

    # Degraded set: unknown locations, stale, duplicates, one dominant source
    degraded = [
        _sig(i, source="GDELT", title="Same headline") for i in range(8)
    ] + [
        _sig(100 + i, location="Unknown", latitude=0.0, longitude=0.0,
             timestamp=(now - timedelta(days=10)).isoformat())
        for i in range(4)
    ]
    report2 = engine.assess(degraded)
    print(f"\nDegraded set → score={report2['score']} grade={report2['grade']}")
    for f in report2["findings"]:
        print(f"  - {f}")
    assert report2["score"] < report["score"], "Degraded data must score lower"
    assert report2["findings"], "Degraded data should produce findings"
    assert report2["dimensions"]["uniqueness"]["near_duplicate_titles"] == 7
    assert report2["dimensions"]["geolocation"]["unresolved"] == 4

    # Empty input must not raise
    empty = engine.assess([])
    assert empty["score"] == 0.0 and empty["grade"] == "N/A"
    print("\nEmpty set → handled gracefully.")

    print("\n✅ quality_engine.py self-test passed.")

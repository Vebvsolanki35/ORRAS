"""
safety_engine.py — Multi-domain safety scoring engine for ORRAS v2.0.

Scores signals across six safety categories (cyber, nuclear, infrastructure,
maritime, economic, humanitarian), computes a weighted overall safety index,
detects sudden spikes within categories, and generates a professional SITREP.
"""

from collections import defaultdict
from typing import Any

from utils import classify_severity, get_logger, now_iso

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Category definitions — keywords drive category-signal matching
# ---------------------------------------------------------------------------

SAFETY_CATEGORIES: dict[str, dict[str, Any]] = {
    "cyber": {
        "name": "Cyber Threat Level",
        "description": "Network attacks, data breaches, infrastructure threats",
        "keywords": [
            "cyberattack", "hack", "malware", "ddos", "breach",
            "ransomware", "phishing", "exploit", "vulnerability",
        ],
    },
    "nuclear": {
        "name": "Nuclear/CBRN Risk",
        "description": "Chemical, biological, radiological, nuclear signals",
        "keywords": [
            "nuclear", "radiation", "chemical weapon", "biological",
            "wmd", "dirty bomb", "enrichment", "warhead",
        ],
    },
    "infrastructure": {
        "name": "Critical Infrastructure",
        "description": "Power grids, water systems, transport hubs",
        "keywords": [
            "power grid", "blackout", "pipeline", "dam", "water supply",
            "airport", "port", "railway", "bridge",
        ],
    },
    "maritime": {
        "name": "Maritime Security",
        "description": "Shipping lanes, naval movements, piracy",
        "keywords": [
            "naval", "ship", "fleet", "maritime", "piracy",
            "strait", "blockade", "submarine", "carrier",
        ],
    },
    "economic": {
        "name": "Economic Stability",
        "description": "Sanctions, market shocks, supply chain disruption",
        "keywords": [
            "sanctions", "embargo", "inflation", "currency",
            "supply chain", "oil price", "trade war", "default",
        ],
    },
    "humanitarian": {
        "name": "Humanitarian Crisis",
        "description": "Refugee flows, famine, disease outbreaks",
        "keywords": [
            "refugee", "famine", "epidemic", "displacement",
            "aid", "casualties", "civilian", "evacuation",
        ],
    },
}

# Weights must sum to 1.0
_CATEGORY_WEIGHTS: dict[str, float] = {
    "cyber": 0.20,
    "nuclear": 0.25,
    "infrastructure": 0.20,
    "maritime": 0.10,
    "economic": 0.15,
    "humanitarian": 0.10,
}

# Safety status thresholds (score 0-100 where higher = more threat)
_STATUS_THRESHOLDS = [
    (75, "CRITICAL"),
    (50, "AT RISK"),
    (25, "ELEVATED"),
    (0,  "SECURE"),
]

# Severity multipliers used when weighting keyword matches
_SEVERITY_MULTIPLIERS: dict[str, float] = {
    "CRITICAL": 3.0,
    "HIGH": 2.0,
    "MEDIUM": 1.5,
    "LOW": 1.0,
}


def _status_from_score(score: float) -> str:
    """Map a 0–100 threat score to a status label."""
    for threshold, label in _STATUS_THRESHOLDS:
        if score >= threshold:
            return label
    return "SECURE"


def _safety_grade(overall_score: float) -> str:
    """Map an overall safety score (0–100, higher = safer) to a letter grade."""
    if overall_score >= 90:
        return "A"
    if overall_score >= 75:
        return "B"
    if overall_score >= 60:
        return "C"
    if overall_score >= 45:
        return "D"
    return "F"


class SafetyEngine:
    """
    Scores global safety across six threat domains and produces composite
    safety indices and professional briefings.
    """

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _signal_matches_category(self, signal: dict, category: str) -> bool:
        """
        Return True if the signal contains any keyword for the given category.

        Matching is performed against the signal's keywords_matched list,
        title, and summary fields for maximum recall.
        """
        keywords = SAFETY_CATEGORIES[category]["keywords"]
        # Fields to search
        text_blob = " ".join(
            filter(None, [
                signal.get("title") or "",
                signal.get("summary") or "",
                signal.get("description") or "",
                " ".join(signal.get("keywords_matched") or []),
            ])
        ).lower()
        return any(kw.lower() in text_blob for kw in keywords)

    def _score_from_matches(self, matched_signals: list[dict]) -> float:
        """
        Convert a list of keyword-matching signals to a 0–100 threat score.

        Each match contributes a severity-weighted point; the total is then
        normalised to the 0–100 range using a soft cap at 30 raw points.
        """
        if not matched_signals:
            return 0.0

        raw = 0.0
        for sig in matched_signals:
            severity = sig.get("severity") or classify_severity(float(sig.get("raw_score") or 0.0))
            multiplier = _SEVERITY_MULTIPLIERS.get(severity, 1.0)
            raw += multiplier

        # Soft normalisation: 30 raw points → 100
        normalised = min(raw / 30.0 * 100.0, 100.0)
        return round(normalised, 2)

    # ------------------------------------------------------------------
    # score_category
    # ------------------------------------------------------------------

    def score_category(self, signals: list[dict], category: str) -> dict[str, Any]:
        """
        Evaluate the threat level for a single safety category.

        Args:
            signals:  Full list of unified-schema signal dicts.
            category: One of the six SAFETY_CATEGORIES keys.

        Returns:
            Dict with keys: category, score (0–100), status, signal_count,
            top_signals, regions_affected, trend.
        """
        if category not in SAFETY_CATEGORIES:
            raise ValueError(f"Unknown category '{category}'. Valid: {list(SAFETY_CATEGORIES)}")

        matched = [s for s in signals if self._signal_matches_category(s, category)]
        score = self._score_from_matches(matched)
        status = _status_from_score(score)

        top_signals = sorted(
            matched,
            key=lambda s: float(s.get("raw_score") or 0.0),
            reverse=True,
        )[:5]

        regions_affected = sorted({s.get("location") or "Unknown" for s in matched})

        # Trend: compare first half vs second half matched signals (by timestamp)
        sorted_matched = sorted(matched, key=lambda s: s.get("timestamp") or "")
        half = max(len(sorted_matched) // 2, 1)
        first_scores = [float(s.get("raw_score") or 0.0) for s in sorted_matched[:half]]
        last_scores = [float(s.get("raw_score") or 0.0) for s in sorted_matched[half:]]
        first_avg = sum(first_scores) / len(first_scores) if first_scores else 0.0
        last_avg = sum(last_scores) / len(last_scores) if last_scores else 0.0

        if last_avg > first_avg * 1.10:
            trend = "RISING"
        elif last_avg < first_avg * 0.90:
            trend = "FALLING"
        else:
            trend = "STABLE"

        logger.info(
            f"SafetyEngine: category='{category}', score={score}, status={status}, "
            f"matched={len(matched)} signals."
        )

        return {
            "category": category,
            "score": score,
            "status": status,
            "signal_count": len(matched),
            "top_signals": top_signals,
            "regions_affected": regions_affected,
            "trend": trend,
        }

    # ------------------------------------------------------------------
    # score_all_categories
    # ------------------------------------------------------------------

    def score_all_categories(self, signals: list[dict]) -> dict[str, dict[str, Any]]:
        """
        Score all six safety categories in one call.

        Args:
            signals: Full list of unified-schema signal dicts.

        Returns:
            Dict mapping each category key to its score_category result.
        """
        results = {}
        for category in SAFETY_CATEGORIES:
            results[category] = self.score_category(signals, category)
        logger.info("SafetyEngine: scored all 6 categories.")
        return results

    # ------------------------------------------------------------------
    # compute_overall_safety_index
    # ------------------------------------------------------------------

    def compute_overall_safety_index(
        self, category_scores: dict[str, dict[str, Any]]
    ) -> dict[str, Any]:
        """
        Compute a weighted overall safety index from per-category scores.

        The weighted threat score is converted to a safety score via:
            overall_score = 100 - weighted_threat_score

        so that a *higher* overall_score means a *safer* environment.

        Args:
            category_scores: Output of score_all_categories().

        Returns:
            Dict with keys: overall_score, safety_grade, most_critical, summary.
        """
        weighted_threat = 0.0
        for cat, weight in _CATEGORY_WEIGHTS.items():
            cat_score = category_scores.get(cat, {}).get("score") or 0.0
            weighted_threat += cat_score * weight

        overall_score = round(max(0.0, 100.0 - weighted_threat), 2)
        grade = _safety_grade(overall_score)

        # Identify the most critical category (highest threat score)
        most_critical = max(
            category_scores.keys(),
            key=lambda c: category_scores[c].get("score") or 0.0,
        ) if category_scores else "N/A"

        most_critical_name = SAFETY_CATEGORIES.get(most_critical, {}).get("name", most_critical)
        most_critical_score = category_scores.get(most_critical, {}).get("score", 0.0)

        summary = (
            f"Overall Safety Index: {overall_score}/100 (Grade {grade}). "
            f"Most critical domain: {most_critical_name} (score {most_critical_score:.1f}). "
            f"Weighted global threat level: {weighted_threat:.1f}/100."
        )

        logger.info(f"SafetyEngine: overall_score={overall_score}, grade={grade}, most_critical={most_critical}.")

        return {
            "overall_score": overall_score,
            "safety_grade": grade,
            "most_critical": most_critical,
            "summary": summary,
        }

    # ------------------------------------------------------------------
    # detect_safety_anomalies
    # ------------------------------------------------------------------

    def detect_safety_anomalies(self, signals: list[dict]) -> list[dict[str, Any]]:
        """
        Detect sudden spikes in any safety category by comparing the most
        recent 25 % of signals against the baseline of the earlier 75 %.

        A spike is flagged when the recent average score is more than 50 %
        higher than the baseline average (or the baseline is zero and recent
        is non-zero).

        Args:
            signals: Full list of unified-schema signal dicts.

        Returns:
            List of anomaly alert dicts per affected category, each with:
            category, baseline_score, spike_score, delta, alert_level, detail.
        """
        # Sort signals chronologically
        sorted_signals = sorted(signals, key=lambda s: s.get("timestamp") or "")
        n = len(sorted_signals)
        if n < 4:
            logger.warning("SafetyEngine: not enough signals to detect anomalies.")
            return []

        split = max(1, int(n * 0.75))
        baseline_signals = sorted_signals[:split]
        recent_signals = sorted_signals[split:]

        anomalies: list[dict[str, Any]] = []

        for category in SAFETY_CATEGORIES:
            baseline_matched = [s for s in baseline_signals if self._signal_matches_category(s, category)]
            recent_matched = [s for s in recent_signals if self._signal_matches_category(s, category)]

            baseline_score = self._score_from_matches(baseline_matched)
            spike_score = self._score_from_matches(recent_matched)

            is_spike = (
                (baseline_score == 0.0 and spike_score > 0.0) or
                (baseline_score > 0.0 and spike_score > baseline_score * 1.50)
            )

            if is_spike:
                delta = round(spike_score - baseline_score, 2)
                alert_level = "CRITICAL" if delta > 30 else ("HIGH" if delta > 15 else "MEDIUM")
                anomalies.append({
                    "category": category,
                    "baseline_score": baseline_score,
                    "spike_score": spike_score,
                    "delta": delta,
                    "alert_level": alert_level,
                    "detail": (
                        f"Spike detected in '{SAFETY_CATEGORIES[category]['name']}': "
                        f"baseline {baseline_score:.1f} → recent {spike_score:.1f} "
                        f"(+{delta:.1f} pts, {alert_level} alert)."
                    ),
                })

        logger.info(f"SafetyEngine: detected {len(anomalies)} safety anomaly/anomalies.")
        return anomalies

    # ------------------------------------------------------------------
    # generate_safety_brief
    # ------------------------------------------------------------------

    def generate_safety_brief(
        self,
        category_scores: dict[str, dict[str, Any]],
        overall: dict[str, Any],
    ) -> str:
        """
        Generate a professional safety SITREP in plain text.

        Args:
            category_scores: Output of score_all_categories().
            overall:         Output of compute_overall_safety_index().

        Returns:
            Multi-section SITREP string.
        """
        ts = now_iso()
        grade = overall.get("safety_grade", "N/A")
        overall_score = overall.get("overall_score", 0.0)
        most_critical = overall.get("most_critical", "N/A")
        most_critical_name = SAFETY_CATEGORIES.get(most_critical, {}).get("name", most_critical)

        lines: list[str] = [
            "=" * 65,
            "ORRAS SAFETY SITUATION REPORT (SITREP)",
            f"Generated: {ts}",
            "=" * 65,
            "",
            f"OVERALL SAFETY INDEX : {overall_score:.1f} / 100  [Grade {grade}]",
            f"MOST CRITICAL DOMAIN : {most_critical_name.upper()}",
            "",
            "-" * 65,
            "DOMAIN BREAKDOWN",
            "-" * 65,
        ]

        # Sort domains by score descending for priority ordering
        sorted_cats = sorted(
            category_scores.items(),
            key=lambda kv: kv[1].get("score") or 0.0,
            reverse=True,
        )
        for cat_key, result in sorted_cats:
            cat_info = SAFETY_CATEGORIES.get(cat_key, {})
            name = cat_info.get("name", cat_key).upper()
            score = result.get("score", 0.0)
            status = result.get("status", "UNKNOWN")
            trend = result.get("trend", "STABLE")
            sig_count = result.get("signal_count", 0)
            regions = result.get("regions_affected") or []
            region_str = ", ".join(regions[:3]) + ("…" if len(regions) > 3 else "") if regions else "None"

            lines.append(
                f"  [{status:<9}] {name:<30} Score: {score:5.1f}  Trend: {trend}"
            )
            lines.append(f"             Signals: {sig_count}  Regions: {region_str}")

        lines += [
            "",
            "-" * 65,
            "ASSESSMENT",
            "-" * 65,
            overall.get("summary", "No summary available."),
            "",
            "END OF SITREP",
            "=" * 65,
        ]

        brief = "\n".join(lines)
        logger.info("SafetyEngine: generated professional safety brief.")
        return brief


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from mock_data_generator import generate_all_mock_signals

    print("=== safety_engine.py self-test ===\n")
    signals = generate_all_mock_signals()
    engine = SafetyEngine()

    # --- score_category ---
    result = engine.score_category(signals, "cyber")
    print(f"Cyber category: score={result['score']}, status={result['status']}, "
          f"signals={result['signal_count']}, trend={result['trend']}")
    assert 0 <= result["score"] <= 100
    assert result["status"] in ("SECURE", "ELEVATED", "AT RISK", "CRITICAL")

    # --- score_all_categories ---
    all_scores = engine.score_all_categories(signals)
    print(f"\nAll categories scored ({len(all_scores)} categories):")
    for cat, res in all_scores.items():
        print(f"  {cat:<16} score={res['score']:5.1f}  status={res['status']}")
    assert len(all_scores) == 6

    # --- compute_overall_safety_index ---
    overall = engine.compute_overall_safety_index(all_scores)
    print(f"\nOverall Safety Index: {overall['overall_score']}/100 (Grade {overall['safety_grade']})")
    print(f"Most critical: {overall['most_critical']}")
    print(f"Summary: {overall['summary']}")
    assert 0 <= overall["overall_score"] <= 100
    assert overall["safety_grade"] in ("A", "B", "C", "D", "F")

    # --- detect_safety_anomalies ---
    anomalies = engine.detect_safety_anomalies(signals)
    print(f"\nSafety anomalies detected: {len(anomalies)}")
    for a in anomalies:
        print(f"  [{a['alert_level']}] {a['category']}: {a['detail']}")

    # --- generate_safety_brief ---
    brief = engine.generate_safety_brief(all_scores, overall)
    print(f"\n{brief}")
    assert "SITREP" in brief
    assert "OVERALL SAFETY INDEX" in brief

    print("\n✅ All safety_engine.py tests passed.")

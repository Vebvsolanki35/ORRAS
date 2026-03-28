"""
timeline_engine.py — Temporal analysis and narrative generation for ORRAS v2.0.

Builds global and region-specific timelines from signal data, detects
turning points where severity levels shift, generates human-readable
narrative summaries, and exports timelines to JSON.
"""

import json
from collections import defaultdict
from datetime import datetime, timezone
from typing import Any

from utils import classify_severity, get_logger, now_iso

logger = get_logger(__name__)


def _parse_date(ts_str: str) -> str:
    """Extract the ISO-8601 date portion (YYYY-MM-DD) from a timestamp string."""
    try:
        dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
        return dt.date().isoformat()
    except (ValueError, AttributeError):
        return datetime.now(timezone.utc).date().isoformat()


def _severity_rank(severity: str) -> int:
    """Return a numeric rank for a severity label (higher = more severe)."""
    return {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}.get(severity, 0)


class TimelineEngine:
    """
    Builds temporal views of threat activity at global and regional level,
    detects turning points, and generates narrative summaries.
    """

    # ------------------------------------------------------------------
    # build_global_timeline
    # ------------------------------------------------------------------

    def build_global_timeline(
        self, signals: list[dict], days: int = 30
    ) -> list[dict[str, Any]]:
        """
        Aggregate all signals into a day-by-day global timeline.

        Args:
            signals: Full list of unified-schema signal dicts.
            days:    Maximum number of most-recent calendar days to include.

        Returns:
            List of timeline entry dicts sorted chronologically, each
            containing: date, events, peak_severity, total_signals,
            top_region, summary.
        """
        # Group signals by calendar day
        day_buckets: dict[str, list[dict]] = defaultdict(list)
        for sig in signals:
            day = _parse_date(sig.get("timestamp") or "")
            day_buckets[day].append(sig)

        # Sort days and apply the *days* window
        sorted_days = sorted(day_buckets.keys())
        if len(sorted_days) > days:
            sorted_days = sorted_days[-days:]

        timeline: list[dict[str, Any]] = []
        for day in sorted_days:
            day_signals = day_buckets[day]

            # Top 3 signals by raw_score
            top_events = sorted(
                day_signals,
                key=lambda s: float(s.get("raw_score") or 0.0),
                reverse=True,
            )[:3]

            # Peak severity across all signals that day
            severities = [s.get("severity") or classify_severity(float(s.get("raw_score") or 0.0)) for s in day_signals]
            peak_severity = max(severities, key=_severity_rank) if severities else "LOW"

            # Most frequent region that day
            from collections import Counter
            region_counts = Counter(s.get("location") or "Unknown" for s in day_signals)
            top_region = region_counts.most_common(1)[0][0] if region_counts else "Unknown"

            summary = (
                f"Elevated activity in {top_region} with {len(day_signals)} signal(s); "
                f"peak severity {peak_severity}."
            )

            timeline.append({
                "date": day,
                "events": top_events,
                "peak_severity": peak_severity,
                "total_signals": len(day_signals),
                "top_region": top_region,
                "summary": summary,
            })

        logger.info(f"TimelineEngine: built global timeline with {len(timeline)} days.")
        return timeline

    # ------------------------------------------------------------------
    # build_region_timeline
    # ------------------------------------------------------------------

    def build_region_timeline(
        self, signals: list[dict], history: list[dict], region: str
    ) -> list[dict[str, Any]]:
        """
        Build a day-by-day threat timeline for a specific region.

        An *escalation_event* flag is set when today's score exceeds the
        previous day's score by more than 20 % (relative) or 3 points
        (absolute), whichever is smaller threshold triggers first.

        Args:
            signals: Full list of unified-schema signal dicts (recent data).
            history: Historical score records [{date, region, score}] from
                     the escalation tracker or similar persistence layer.
            region:  Region / country name to build the timeline for.

        Returns:
            Chronologically sorted list of daily timeline entries.
        """
        region_lower = region.lower()

        # Collect live signals for this region grouped by day
        day_buckets: dict[str, list[dict]] = defaultdict(list)
        for sig in signals:
            if (sig.get("location") or "").lower() == region_lower:
                day = _parse_date(sig.get("timestamp") or "")
                day_buckets[day].append(sig)

        # Build a score lookup from historical records for this region
        hist_scores: dict[str, float] = {}
        for record in history:
            if (record.get("region") or record.get("location") or "").lower() == region_lower:
                date = record.get("date") or _parse_date(record.get("timestamp") or "")
                hist_scores[date] = float(record.get("score") or record.get("raw_score") or 0.0)

        # Merge live signal days into hist_scores
        for day, day_signals in day_buckets.items():
            scores = [float(s.get("raw_score") or 0.0) for s in day_signals]
            hist_scores[day] = round(sum(scores) / len(scores), 2) if scores else 0.0

        sorted_days = sorted(hist_scores.keys())
        timeline: list[dict[str, Any]] = []
        prev_score: float | None = None

        for day in sorted_days:
            day_score = hist_scores[day]
            day_signals = day_buckets.get(day, [])
            severity = classify_severity(day_score)

            # Escalation check
            escalation_event = False
            if prev_score is not None:
                absolute_jump = day_score - prev_score
                relative_jump = absolute_jump / (prev_score or 1.0)
                if absolute_jump > 3.0 or relative_jump > 0.20:
                    escalation_event = True

            timeline.append({
                "date": day,
                "region": region,
                "score": day_score,
                "severity": severity,
                "signal_count": len(day_signals),
                "signals": day_signals,
                "escalation_event": escalation_event,
            })
            prev_score = day_score

        logger.info(
            f"TimelineEngine: built region timeline for '{region}' "
            f"with {len(timeline)} entries, "
            f"{sum(1 for e in timeline if e['escalation_event'])} escalation(s)."
        )
        return timeline

    # ------------------------------------------------------------------
    # find_turning_points
    # ------------------------------------------------------------------

    def find_turning_points(
        self, history: list[dict], region: str
    ) -> list[dict[str, Any]]:
        """
        Identify dates where the severity level changed for a given region.

        Args:
            history: List of records [{date, region/location, score}].
            region:  Region to analyse.

        Returns:
            List of turning point dicts: {date, from_severity, to_severity,
            signals_that_day}.
        """
        region_lower = region.lower()

        # Collect (date, score) pairs for this region
        day_scores: dict[str, float] = {}
        day_signals: dict[str, list[dict]] = defaultdict(list)

        for record in history:
            rec_region = (record.get("region") or record.get("location") or "").lower()
            if rec_region != region_lower:
                continue
            date = record.get("date") or _parse_date(record.get("timestamp") or "")
            score = float(record.get("score") or record.get("raw_score") or 0.0)
            # Keep the highest score for the day (or overwrite — same outcome for severity)
            day_scores[date] = max(day_scores.get(date, 0.0), score)
            day_signals[date].append(record)

        if not day_scores:
            logger.warning(f"TimelineEngine: no history data for region '{region}'.")
            return []

        sorted_days = sorted(day_scores.keys())
        turning_points: list[dict[str, Any]] = []
        prev_severity: str | None = None

        for day in sorted_days:
            severity = classify_severity(day_scores[day])
            if prev_severity is not None and severity != prev_severity:
                turning_points.append({
                    "date": day,
                    "from_severity": prev_severity,
                    "to_severity": severity,
                    "signals_that_day": day_signals[day],
                })
            prev_severity = severity

        logger.info(
            f"TimelineEngine: found {len(turning_points)} turning point(s) for '{region}'."
        )
        return turning_points

    # ------------------------------------------------------------------
    # generate_timeline_summary
    # ------------------------------------------------------------------

    def generate_timeline_summary(self, timeline: list[dict[str, Any]]) -> str:
        """
        Generate a concise narrative paragraph describing the timeline.

        Works for both global and regional timeline formats.

        Args:
            timeline: Output of build_global_timeline or build_region_timeline.

        Returns:
            Multi-sentence narrative string.
        """
        if not timeline:
            return "No timeline data available."

        total_days = len(timeline)
        total_signals = sum(e.get("total_signals") or e.get("signal_count") or 0 for e in timeline)

        # Peak severity across the whole timeline
        all_severities = [e.get("peak_severity") or e.get("severity") or "LOW" for e in timeline]
        overall_peak = max(all_severities, key=_severity_rank)

        # Count escalation events if present (regional timeline)
        escalation_count = sum(1 for e in timeline if e.get("escalation_event"))

        # Most active day
        most_active = max(
            timeline,
            key=lambda e: e.get("total_signals") or e.get("signal_count") or 0,
        )
        most_active_date = most_active.get("date", "unknown")
        most_active_count = most_active.get("total_signals") or most_active.get("signal_count") or 0

        # Trend: compare first half vs second half average signal volume
        half = max(total_days // 2, 1)
        first_half_avg = (
            sum(e.get("total_signals") or e.get("signal_count") or 0 for e in timeline[:half]) / half
        )
        second_half_avg = (
            sum(e.get("total_signals") or e.get("signal_count") or 0 for e in timeline[half:]) / max(total_days - half, 1)
        )
        trend_desc = "an upward trend" if second_half_avg > first_half_avg else "a downward trend"

        region_note = ""
        region = timeline[0].get("region")
        if region:
            region_note = f" in {region}"
            if escalation_count:
                region_note += f" with {escalation_count} escalation event(s)"

        narrative = (
            f"The timeline spans {total_days} day(s){region_note}, "
            f"recording {total_signals} total signal(s). "
            f"Peak severity reached {overall_peak}. "
            f"The most active day was {most_active_date} ({most_active_count} signal(s)). "
            f"Signal volume shows {trend_desc} over the observed period."
        )

        logger.info("TimelineEngine: generated timeline summary narrative.")
        return narrative

    # ------------------------------------------------------------------
    # export_timeline_json
    # ------------------------------------------------------------------

    def export_timeline_json(self, timeline: list[dict[str, Any]], filepath: str) -> None:
        """
        Serialise the timeline to a pretty-printed JSON file.

        Signal objects embedded in timeline entries are stripped down to
        their most important fields to keep file size manageable.

        Args:
            timeline: Timeline list as returned by build_* methods.
            filepath: Destination file path (will be created or overwritten).
        """
        _SIGNAL_KEYS = ("id", "timestamp", "location", "source", "raw_score", "severity", "title")

        def _slim_signal(sig: dict) -> dict:
            return {k: sig.get(k) for k in _SIGNAL_KEYS if sig.get(k) is not None}

        def _serialise_entry(entry: dict) -> dict:
            out = dict(entry)
            # Slim down embedded signal lists
            for key in ("events", "signals"):
                if key in out and isinstance(out[key], list):
                    out[key] = [_slim_signal(s) for s in out[key]]
            return out

        serialisable = [_serialise_entry(e) for e in timeline]

        tmp_path = filepath + ".tmp"
        with open(tmp_path, "w", encoding="utf-8") as fh:
            json.dump(serialisable, fh, indent=2, ensure_ascii=False, default=str)
        import os
        os.replace(tmp_path, filepath)

        logger.info(f"TimelineEngine: exported {len(timeline)}-entry timeline to '{filepath}'.")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    from mock_data_generator import generate_all_mock_signals

    print("=== timeline_engine.py self-test ===\n")
    signals = generate_all_mock_signals()
    engine = TimelineEngine()

    # --- build_global_timeline ---
    global_tl = engine.build_global_timeline(signals, days=30)
    print(f"Global timeline: {len(global_tl)} day(s)")
    if global_tl:
        sample = global_tl[0]
        print(f"  First day: {sample['date']}, signals={sample['total_signals']}, "
              f"peak_sev={sample['peak_severity']}, top_region={sample['top_region']}")
        print(f"  Summary: {sample['summary']}")
    assert all("date" in e and "peak_severity" in e for e in global_tl)

    # --- build_region_timeline ---
    regions = list({s.get("location") for s in signals if s.get("location")})
    target = regions[0]
    region_tl = engine.build_region_timeline(signals, [], target)
    print(f"\nRegion timeline for '{target}': {len(region_tl)} day(s)")
    escalations = [e for e in region_tl if e.get("escalation_event")]
    print(f"  Escalation events: {len(escalations)}")
    assert all("escalation_event" in e for e in region_tl)

    # --- find_turning_points ---
    # Build synthetic history from signals
    history = []
    for sig in signals:
        if (sig.get("location") or "").lower() == target.lower():
            history.append({
                "region": target,
                "date": _parse_date(sig.get("timestamp") or ""),
                "score": sig.get("raw_score") or 0.0,
            })
    turning = engine.find_turning_points(history, target)
    print(f"\nTurning points for '{target}': {len(turning)}")
    for tp in turning[:3]:
        print(f"  {tp['date']}: {tp['from_severity']} → {tp['to_severity']}")

    # --- generate_timeline_summary ---
    summary = engine.generate_timeline_summary(global_tl)
    print(f"\nTimeline summary:\n  {summary}")
    assert "day" in summary.lower()

    # --- export_timeline_json ---
    export_path = "data/test_timeline_export.json"
    engine.export_timeline_json(global_tl, export_path)
    import os
    assert os.path.exists(export_path), "Export file should exist"
    print(f"\nExported to '{export_path}' ✓")
    os.remove(export_path)

    print("\n✅ All timeline_engine.py tests passed.")

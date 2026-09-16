"""
tests/test_engines.py — Unit tests for the ORRAS analytics engines.

Covers the logic that cannot be validated by simply rendering a page:
alert-schema normalisation, quality scoring, anomaly baselines, cold-start
forecasting, escalation backfill, and database schema migration.

Run with:  python tests/test_engines.py
"""

from __future__ import annotations

import os
import sys
import tempfile
from datetime import datetime, timedelta, timezone

from harness import Results, quiet


def _sig(i: int = 0, **over) -> dict:
    """Build a minimal valid unified-schema signal."""
    now = datetime.now(timezone.utc)
    base = {
        "id": f"sig-{i}",
        "timestamp": (now - timedelta(hours=1)).isoformat(),
        "type": "news",
        "source": "GDELT",
        "location": "Ukraine",
        "latitude": 48.3,
        "longitude": 31.2,
        "title": f"Event {i}",
        "description": "test",
        "severity": "HIGH",
        "raw_score": 12.0,
    }
    base.update(over)
    return base


def test_alert_normalisation(r: Results) -> None:
    r.begin("alert schema normalisation")
    from utils import alert_region, alert_severity, normalize_alert, normalize_alert_log

    # Legacy schema (region / max_severity)
    legacy = {
        "timestamp": "2026-03-28T18:59:59+00:00",
        "region": "Myanmar",
        "max_severity": "CRITICAL",
        "recommendation": "Escalate",
        "signal_count": 1,
        "top_signals": ["Internet shutdown detected in Myanmar"],
    }
    r.check("legacy region read", alert_region(legacy) == "Myanmar")
    r.check("legacy severity read", alert_severity(legacy) == "CRITICAL")

    # Current schema (location / severity)
    current = {
        "id": "a1", "timestamp": "2026-09-15T10:00:00+00:00",
        "severity": "HIGH", "title": "T", "location": "Iran",
    }
    r.check("current region read", alert_region(current) == "Iran")
    r.check("current severity read", alert_severity(current) == "HIGH")

    # Neither schema present → safe defaults, never a crash
    r.check("empty dict region", alert_region({}) == "Unknown")
    r.check("empty dict severity", alert_severity({}) == "LOW")
    r.check("non-dict input tolerated", alert_region(None) == "Unknown")

    # Normalised record carries both key names with no duplicates
    norm = normalize_alert(legacy)
    r.check(
        "normalised legacy has both region keys",
        norm["region"] == norm["location"] == "Myanmar",
    )
    r.check(
        "normalised severity is unified",
        norm["severity"] == norm["max_severity"] == "CRITICAL",
    )
    r.check("normalised record gets an id", bool(norm.get("id")))

    # The real-world failure this guards: a mixed log loaded into a DataFrame
    # produced duplicate 'severity' columns and crashed arrow conversion.
    import pandas as pd

    mixed = normalize_alert_log([legacy, current, {}])
    df = pd.DataFrame(mixed)
    r.check(
        "mixed log yields no duplicate columns",
        not df.columns.duplicated().any(),
        f"columns={list(df.columns)}",
    )
    try:
        quiet(lambda: df.astype(str))
        r.ok("mixed log is DataFrame-safe")
    except Exception as exc:  # noqa: BLE001
        r.fail("mixed log is DataFrame-safe", str(exc))


def test_styler_shim(r: Results) -> None:
    r.begin("pandas Styler shim")
    import pandas as pd

    from utils import style_map

    df = pd.DataFrame({"Severity": ["HIGH", "LOW"], "n": [1, 2]})
    styled = quiet(style_map, df.style, lambda v: "color: red", subset=["Severity"])
    r.check(
        "style_map returns a Styler",
        isinstance(styled, pd.io.formats.style.Styler),
    )
    try:
        html = quiet(styled.to_html)
        r.check("style_map output renders to HTML", "color: red" in html)
    except Exception as exc:  # noqa: BLE001
        r.fail("style_map output renders to HTML", str(exc))


def test_data_dir_bootstrap(r: Results) -> None:
    """
    Guard against the fresh-clone failure: git does not track empty
    directories, so a checkout has no data/ until something creates it.
    Any code path that writes there must create the directory itself.
    """
    r.begin("data directory bootstrap")
    import tempfile

    from utils import save_json

    with tempfile.TemporaryDirectory() as tmp:
        nested = os.path.join(tmp, "data", "nested", "escalation_history.json")
        try:
            save_json(nested, [{"a": 1}])
            r.ok("save_json creates missing parent directories")
        except Exception as exc:  # noqa: BLE001
            r.fail("save_json creates missing parent directories", str(exc))
            return

        r.check("written file is readable", os.path.exists(nested))
        r.check("no .tmp file left behind", not os.path.exists(nested + ".tmp"))


def test_quality_engine(r: Results) -> None:
    r.begin("quality engine")
    from quality_engine import QualityEngine

    engine = QualityEngine()

    healthy = [
        _sig(i, source=src, title=f"Unique event {i}")
        for i, src in enumerate(["GDELT", "NewsAPI", "ACLED", "USGS"])
    ]
    report = quiet(engine.assess, healthy)
    r.check("healthy data scores highly", report["score"] >= 90,
            f"score={report['score']}")
    r.check("healthy data has no findings", not report["findings"])
    r.check("grade assigned", report["grade"] in {"A", "B", "C", "D", "F"})

    degraded = (
        [_sig(i, source="GDELT", title="Same headline") for i in range(8)]
        + [
            _sig(
                100 + i, location="Unknown", latitude=0.0, longitude=0.0,
                timestamp=(datetime.now(timezone.utc) - timedelta(days=10)).isoformat(),
            )
            for i in range(4)
        ]
    )
    bad = quiet(engine.assess, degraded)
    r.check("degraded data scores lower", bad["score"] < report["score"],
            f"{bad['score']} < {report['score']}")
    r.check("degraded data produces findings", bool(bad["findings"]))
    r.check(
        "unresolved locations detected",
        bad["dimensions"]["geolocation"]["unresolved"] == 4,
    )
    r.check(
        "duplicate titles detected",
        bad["dimensions"]["uniqueness"]["near_duplicate_titles"] == 7,
    )
    r.check(
        "source concentration detected",
        bad["dimensions"]["diversity"]["dominant_share"] == 1.0,
    )

    empty = quiet(engine.assess, [])
    r.check("empty input handled", empty["score"] == 0.0 and empty["grade"] == "N/A")

    # Report must be JSON-serialisable (it is rendered and exported).
    import json

    try:
        json.dumps(report, default=str)
        r.ok("quality report is JSON-serialisable")
    except Exception as exc:  # noqa: BLE001
        r.fail("quality report is JSON-serialisable", str(exc))


def test_anomaly_engine(r: Results) -> None:
    r.begin("anomaly engine")
    from anomaly_engine import AnomalyEngine

    engine = AnomalyEngine()
    now = datetime.now(timezone.utc)

    # Multi-day history with a spike today → temporal baseline
    temporal: list[dict] = []
    for d in range(6, 0, -1):
        temporal.append(_sig(
            d, location="Ukraine",
            timestamp=(now - timedelta(days=d)).isoformat(),
        ))
    for i in range(8):
        temporal.append(_sig(
            100 + i, location="Ukraine", timestamp=now.isoformat(),
        ))
    for i in range(2):
        temporal.append(_sig(
            200 + i, location="Russia", timestamp=now.isoformat(),
        ))

    found = quiet(engine.detect_anomalies, temporal)
    ukraine = [a for a in found if a["location"] == "Ukraine"]
    r.check("temporal spike detected", bool(ukraine),
            f"{len(found)} anomalies")
    if ukraine:
        r.check(
            "temporal method used when history exists",
            ukraine[0]["method"] == "temporal",
            ukraine[0]["method"],
        )

    # Single day, no history → peer baseline (the old code found nothing here)
    cold: list[dict] = []
    for loc, n in [("Iran", 12), ("Chad", 2), ("Peru", 3),
                   ("Cuba", 2), ("Nepal", 3), ("Mali", 2)]:
        for i in range(n):
            cold.append(_sig(i, location=loc, timestamp=now.isoformat(),
                             title=f"{loc} event {i}"))
    cold_found = quiet(engine.detect_anomalies, cold)
    r.check("cold-start detection works",
            any(a["location"] == "Iran" for a in cold_found),
            f"{len(cold_found)} anomalies")
    r.check("cold-start uses peer method",
            all(a["method"] == "peer" for a in cold_found))

    # Uniform data must not produce false positives
    flat: list[dict] = []
    for loc in ("Iran", "Chad", "Peru", "Cuba", "Nepal", "Mali"):
        for i in range(3):
            flat.append(_sig(i, location=loc, timestamp=now.isoformat(),
                             title=f"{loc} event {i}"))
    r.check("uniform data yields no anomalies",
            not quiet(engine.detect_anomalies, flat))

    r.check("empty input handled", quiet(engine.detect_anomalies, []) == [])


def test_prediction_cold_start(r: Results) -> None:
    r.begin("prediction engine")
    from prediction_engine import PredictionEngine

    engine = PredictionEngine()
    now = datetime.now(timezone.utc)

    def _snap(day_offset: int, score: float) -> dict:
        ts = (now - timedelta(days=day_offset)).isoformat()
        return {"timestamp": ts, "regions": {"Testland": {
            "score": score, "severity": "MEDIUM", "timestamp": ts,
        }}}

    # One day → no forecast at all (no observable trend)
    r.check("single day is not forecastable",
            not quiet(engine.forecast_all_regions, [_snap(0, 10.0)]))

    # Two days → cold-start forecast with capped confidence
    two = [_snap(1, 8.0), _snap(0, 12.0)]
    f2 = quiet(engine.forecast_all_regions, two)
    r.check("two days produces a cold-start forecast", "Testland" in f2, str(f2))
    if "Testland" in f2:
        entry = f2["Testland"]
        r.check("cold-start flagged", entry["cold_start"] is True)
        r.check("cold-start uses weighted average",
                entry["method"] == "weighted_average", entry["method"])
        r.check("cold-start confidence capped",
                entry["confidence"] <= engine.COLD_START_MAX_CONFIDENCE,
                f"conf={entry['confidence']}")
        r.check("history_days recorded", entry["history_days"] == 2)

    # Five days → mature regression forecast
    five = [_snap(d, 5.0 + d) for d in range(4, -1, -1)]
    f5 = quiet(engine.forecast_all_regions, five)
    r.check("five days produces a mature forecast", "Testland" in f5)
    if "Testland" in f5:
        r.check("mature forecast not flagged cold-start",
                f5["Testland"]["cold_start"] is False)
        r.check("mature forecast uses linear regression",
                f5["Testland"]["method"] == "linear")

    # Readiness reporting
    ready = quiet(engine.forecast_readiness, five)
    r.check("readiness counts days", ready["days_available"] == 5, str(ready))
    r.check("readiness counts regions", ready["regions"] == 1)
    r.check("readiness reports maturity", ready["mature"] == 1)

    empty_ready = quiet(engine.forecast_readiness, [])
    r.check("readiness handles empty history",
            empty_ready["days_available"] == 0 and empty_ready["regions"] == 0)


def test_escalation_backfill(r: Results) -> None:
    r.begin("escalation backfill")
    import prediction_engine  # noqa: F401
    from escalation_tracker import EscalationTracker

    # Redirect history to a temp file so the test never touches repo data.
    import escalation_tracker

    with tempfile.TemporaryDirectory() as tmp:
        tmp_file = os.path.join(tmp, "escalation_history.json")
        original = escalation_tracker.ESCALATION_FILE
        escalation_tracker.ESCALATION_FILE = tmp_file
        try:
            tracker = EscalationTracker()
            now = datetime.now(timezone.utc)

            signals = []
            for day in range(3, 0, -1):
                for i in range(2):
                    signals.append(_sig(
                        i, location="Testland", raw_score=10.0,
                        timestamp=(now - timedelta(days=day)).isoformat(),
                    ))

            added = quiet(tracker.backfill_from_signals, signals)
            r.check("backfill writes day-snapshots", added == 3, f"added={added}")

            again = quiet(tracker.backfill_from_signals, signals)
            r.check("backfill is idempotent", again == 0, f"added={again}")

            history = quiet(tracker.load_history)
            r.check("history contains the derived days", len(history) == 3)
            r.check(
                "derived snapshot carries region scores",
                "Testland" in (history[-1].get("regions") or {}),
            )

            # Snapshots must be usable by the prediction engine.
            from prediction_engine import PredictionEngine
            f = quiet(PredictionEngine().forecast_all_regions, history)
            r.check("backfilled history is forecastable", "Testland" in f, str(f))

            # Pruning caps growth
            for i in range(10):
                quiet(tracker.save_snapshot, {"Testland": {
                    "score": 1.0, "severity": "LOW",
                    "timestamp": now.isoformat(),
                }})
            before = len(quiet(tracker.load_history))
            removed = quiet(tracker.prune_history, 5)
            after = len(quiet(tracker.load_history))
            r.check("prune removes excess snapshots", removed == before - 5,
                    f"{before} -> {after}")
            r.check("prune respects the cap", after == 5, f"after={after}")
        finally:
            escalation_tracker.ESCALATION_FILE = original


def test_database_migration(r: Results) -> None:
    r.begin("database schema migration")
    import sqlite3

    from database_engine import DatabaseEngine

    with tempfile.TemporaryDirectory() as tmp:
        db_path = os.path.join(tmp, "test.db")

        # Simulate a stale database: alerts table missing newer columns.
        stale = sqlite3.connect(db_path)
        stale.execute("""
            CREATE TABLE alerts (
                id TEXT PRIMARY KEY, timestamp TEXT, region TEXT,
                severity TEXT, recommendation TEXT, signal_count INTEGER
            )
        """)
        stale.commit()
        stale.close()

        engine = DatabaseEngine(db_path=db_path)
        r.check("engine opens a stale database", os.path.exists(db_path))

        tables = engine.list_tables()
        r.check("canonical tables created", "signals" in tables and "alerts" in tables,
                f"tables={tables}")

        conn = engine.connect()
        cols = {row["name"] for row in conn.execute("PRAGMA table_info(alerts)")}
        conn.close()

        for needed in ("location", "alert_type", "title", "acknowledged"):
            r.check(f"alerts.{needed} added by migration", needed in cols,
                    f"cols={sorted(cols)}")

        r.check("row counting works", engine.count_rows("alerts") == 0)
        r.check("unknown table counts 0", engine.count_rows("nope") == 0)


def main() -> int:
    r = Results("Engine unit tests")
    for fn in (
        test_alert_normalisation,
        test_data_dir_bootstrap,
        test_styler_shim,
        test_quality_engine,
        test_anomaly_engine,
        test_prediction_cold_start,
        test_escalation_backfill,
        test_database_migration,
    ):
        try:
            fn(r)
        except Exception:  # noqa: BLE001
            import traceback

            r.fail(f"{fn.__name__} completed", traceback.format_exc())
    return r.summary()


if __name__ == "__main__":
    sys.exit(main())

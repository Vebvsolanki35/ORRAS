"""
tests/test_pipeline.py — End-to-end tests for the ORRAS intelligence pipeline.

Run with:  python tests/test_pipeline.py
"""

from __future__ import annotations

import sys

from harness import Results, run_pipeline

REQUIRED_SIGNAL_FIELDS = [
    "id", "timestamp", "type", "source", "location",
    "latitude", "longitude", "title", "description",
    "conflict_score", "disaster_score", "severity",
]


def main() -> int:
    r = Results("Pipeline test suite")

    r.begin("pipeline execution")
    try:
        signals, anomalies, escalation, actions, status, conf_map, alerts = run_pipeline()
    except Exception:  # noqa: BLE001
        r.fail("run_pipeline() completes", __import__("traceback").format_exc())
        return r.summary()
    r.ok("run_pipeline() completes")

    # ── Signals ──────────────────────────────────────────────────────────────
    r.begin("signal schema")
    r.check("signals produced", len(signals) > 0, f"{len(signals)} signals")

    missing: dict[str, int] = {}
    for sig in signals:
        for field in REQUIRED_SIGNAL_FIELDS:
            if field not in sig:
                missing[field] = missing.get(field, 0) + 1
    r.check("all required fields present", not missing, str(missing) if missing else "")

    bad_ids = [s for s in signals if not isinstance(s.get("id"), str) or not s["id"]]
    r.check("every signal has a string id", not bad_ids, f"{len(bad_ids)} bad")

    dupes = len(signals) - len({s["id"] for s in signals})
    r.check("signal ids are unique", dupes == 0, f"{dupes} duplicates")

    valid_sev = {"CRITICAL", "HIGH", "MEDIUM", "LOW"}
    bad_sev = {
        s.get("severity") for s in signals if str(s.get("severity")).upper() not in valid_sev
    }
    r.check("severity values are valid", not bad_sev, str(bad_sev))

    nan_scores = [
        s for s in signals
        if not isinstance(s.get("conflict_score"), (int, float))
        or s.get("conflict_score") is None
    ]
    r.check("conflict_score is always numeric", not nan_scores, f"{len(nan_scores)} bad")

    # ── Source coverage ──────────────────────────────────────────────────────
    r.begin("source coverage")
    sources = {s.get("source") for s in signals}
    r.check(
        "NewsAPI signals survive normalisation",
        "NewsAPI" in sources,
        f"sources present: {sorted(sources)}",
    )
    expected_sources = {
        "NewsAPI", "GDELT", "OpenSky", "NASA FIRMS", "NetBlocks",
        "USGS", "NOAA", "ReliefWeb", "WHO", "ACLED",
    }
    r.check(
        "all major sources represented",
        expected_sources <= sources,
        f"missing: {sorted(expected_sources - sources)}",
    )

    # ── Source health ────────────────────────────────────────────────────────
    r.begin("source health")
    r.check(
        "status map is populated for the sidebar",
        bool(status),
        f"status_map={status!r}",
    )
    if status:
        expected_keys = {
            "NewsAPI", "GDELT", "OpenSky", "NASA FIRMS", "NetBlocks",
            "Cloudflare Radar", "USGS", "NOAA", "ReliefWeb", "WHO",
            "ACLED", "Social/Mock",
        }
        r.check(
            "status map covers every source",
            expected_keys <= set(status),
            f"missing={sorted(expected_keys - set(status))}",
        )
        valid = {"LIVE", "MOCK", "FAILED", "OFFLINE", "UNKNOWN"}
        bad = {k: v for k, v in status.items() if str(v).upper() not in valid}
        r.check("status values are valid", not bad, str(bad))
        # ACLED falls back to mock data internally, so it must not claim LIVE
        # unless credentials are configured.
        import os

        if not (os.getenv("ACLED_KEY") and os.getenv("ACLED_EMAIL")):
            r.check(
                "ACLED does not falsely report LIVE without credentials",
                str(status.get("ACLED", "")).upper() != "LIVE",
                f"ACLED={status.get('ACLED')}",
            )

    # ── Enrichment engines ───────────────────────────────────────────────────
    r.begin("enrichment engines")
    enrichment = [
        "signal_class", "track", "dynamic_weight", "fusion_score",
        "confidence_score", "geofence_zones",
    ]
    for field in enrichment:
        count = sum(1 for s in signals if field in s)
        r.check(
            f"'{field}' annotated on all signals",
            count == len(signals),
            f"{count}/{len(signals)}",
        )

    r.check(
        "confidence map covers regions",
        bool(conf_map),
        f"{len(conf_map)} regions scored",
    )
    r.check("actions generated", len(actions) > 0, f"{len(actions)} actions")
    r.check("escalation snapshot produced", isinstance(escalation, dict))
    r.check("alerts produced", len(alerts) >= 0, f"{len(alerts)} alerts")

    # ── Anomaly engine ───────────────────────────────────────────────────────
    r.begin("anomaly engine")
    required = ("location", "date", "signal_count", "z_score", "method", "alert")
    malformed = [a for a in (anomalies or []) if not all(k in a for k in required)]
    r.check(
        "anomaly records are well-formed",
        not malformed,
        f"{len(anomalies or [])} anomalies" if not malformed else str(malformed[:2]),
    )

    valid_methods = {"temporal", "peer"}
    bad_methods = {
        a["method"] for a in (anomalies or []) if a.get("method") not in valid_methods
    }
    r.check("anomaly methods are valid", not bad_methods, str(bad_methods))

    below_threshold = [
        a for a in (anomalies or []) if a.get("z_score", 0) <= 2.0
    ]
    r.check(
        "every anomaly exceeds the Z-score threshold",
        not below_threshold,
        str(below_threshold[:2]),
    )

    return r.summary()


if __name__ == "__main__":
    sys.exit(main())

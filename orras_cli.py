"""
orras_cli.py — Command-line interface for ORRAS.

Runs the intelligence pipeline headlessly (no browser, no Streamlit UI) and
prints or exports the results. Useful for automation, cron jobs, CI smoke
tests, and piping ORRAS output into other tooling.

Examples:
    python orras_cli.py sitrep
    python orras_cli.py signals --format json --out signals.json
    python orras_cli.py quality
    python orras_cli.py sources
    python orras_cli.py health
"""

from __future__ import annotations

import argparse
import json
import sys
import time
from typing import Any

from utils import get_logger

logger = get_logger("orras.cli")

_SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------

def run_pipeline() -> dict:
    """
    Execute the full ORRAS pipeline and return every artefact.

    Returns:
        Dict with keys: signals, anomalies, escalation, actions, status,
        confidence, alerts, quality, elapsed_seconds.
    """
    started = time.time()

    from data_collector import DataCollectionOrchestrator
    from data_processor import DataProcessor
    from threat_engine import ThreatEngine
    from correlation_engine import CorrelationEngine
    from anomaly_engine import AnomalyEngine
    from escalation_tracker import EscalationTracker
    from confidence_engine import ConfidenceEngine
    from action_engine import ActionEngine
    from classifier_engine import ClassifierEngine
    from weight_engine import WeightEngine
    from disaster_engine import DisasterEngine
    from fusion_engine import FusionEngine
    from geofence_engine import GeofenceEngine
    from alert_engine import AlertEngine

    raw = DataCollectionOrchestrator().collect_all()
    status = raw.pop("_status", {})

    signals = DataProcessor().process_all(raw)
    signals = ThreatEngine().score_all(signals)
    signals = CorrelationEngine().correlate_all(signals)
    anomalies = AnomalyEngine().detect_anomalies(signals)
    escalation = EscalationTracker().run(signals)

    signals = ClassifierEngine().classify_all(signals)
    signals = WeightEngine().apply_weights(signals)
    signals = DisasterEngine().score_all(signals)
    signals = FusionEngine().fuse_all(signals)
    signals = GeofenceEngine().tag_all(signals)

    conf_engine = ConfidenceEngine()
    confidence = conf_engine.score_confidence(signals)
    signals = conf_engine.annotate_signals(signals, confidence)

    actions = ActionEngine().generate_region_actions(signals)
    alerts = AlertEngine().generate_alerts(signals)

    try:
        from quality_engine import QualityEngine

        quality = QualityEngine().assess(signals)
    except Exception as exc:  # noqa: BLE001
        logger.warning(f"Quality assessment unavailable: {exc}")
        quality = {}

    return {
        "signals": signals,
        "anomalies": anomalies,
        "escalation": escalation,
        "actions": actions,
        "status": status,
        "confidence": confidence,
        "alerts": alerts,
        "quality": quality,
        "elapsed_seconds": round(time.time() - started, 2),
    }


def _emit(data: Any, fmt: str, out: str | None) -> None:
    """Write *data* as JSON or CSV to stdout or to *out*."""
    if fmt == "json":
        text = json.dumps(data, indent=2, default=str)
    else:
        import pandas as pd

        rows = data if isinstance(data, list) else [data]
        text = pd.DataFrame(rows).to_csv(index=False)

    if out:
        with open(out, "w", encoding="utf-8") as fh:
            fh.write(text)
        print(f"✅ Wrote {out}")
    else:
        print(text)


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_sitrep(args: argparse.Namespace) -> int:
    """Print a text situation report."""
    result = run_pipeline()
    signals = result["signals"]
    quality = result["quality"] or {}

    by_region: dict[str, list[float]] = {}
    for sig in signals:
        by_region.setdefault(sig.get("location") or "Unknown", []).append(
            float(sig.get("raw_score") or 0.0)
        )
    ranked = sorted(
        ((r, sum(v) / len(v)) for r, v in by_region.items()),
        key=lambda kv: kv[1],
        reverse=True,
    )

    print("=" * 68)
    print("ORRAS SITUATION REPORT")
    print("=" * 68)
    print(f"Signals      : {len(signals)}")
    print(f"Regions      : {len(by_region)}")
    print(f"Anomalies    : {len(result['anomalies'])}")
    print(f"New alerts   : {len(result['alerts'])}")
    if quality:
        print(f"Quality      : {quality['score']}/100 (grade {quality['grade']})")
    print(f"Pipeline     : {result['elapsed_seconds']}s")

    live = sum(1 for v in result["status"].values() if str(v).upper() == "LIVE")
    print(f"Sources      : {live}/{len(result['status'])} live")
    print()

    print("TOP REGIONS BY RISK")
    print("-" * 68)
    for region, score in ranked[:10]:
        print(f"  {region:<28} {score:6.2f}")

    if result["anomalies"]:
        print()
        print("ANOMALIES")
        print("-" * 68)
        for anom in result["anomalies"]:
            print(
                f"  {anom['location']:<28} z={anom['z_score']:<6} "
                f"n={anom['signal_count']:<4} ({anom['method']})"
            )

    if quality.get("findings"):
        print()
        print("DATA-QUALITY FINDINGS")
        print("-" * 68)
        for finding in quality["findings"]:
            print(f"  - {finding}")

    actions = result["actions"] or []
    if actions:
        print()
        print("PRIORITY ACTIONS")
        print("-" * 68)
        ordered = sorted(
            actions,
            key=lambda a: _SEV_ORDER.get(str(a.get("severity", "LOW")).upper(), 3),
        )
        for action in ordered[:10]:
            sev = str(action.get("severity", "LOW")).upper()
            rec = action.get("recommendation") or action.get("action") or ""
            print(f"  [{sev:<8}] {action.get('region', '?')}: {rec}")

    print()
    return 0


def cmd_signals(args: argparse.Namespace) -> int:
    """Export the current signal set."""
    result = run_pipeline()
    signals = result["signals"]

    if args.top:
        signals = sorted(
            signals,
            key=lambda s: float(s.get("raw_score") or 0.0),
            reverse=True,
        )[: args.top]

    if args.format == "json":
        _emit(signals, args.format, args.out)
    else:
        keys = ["timestamp", "source", "location", "type", "severity",
                "raw_score", "fusion_score", "confidence", "title"]
        _emit([{k: s.get(k) for k in keys} for s in signals], args.format, args.out)
    return 0


def cmd_quality(args: argparse.Namespace) -> int:
    """Report data-quality metrics."""
    result = run_pipeline()
    _emit(result["quality"], args.format, args.out)
    return 0


def cmd_sources(args: argparse.Namespace) -> int:
    """Report per-source collection status."""
    result = run_pipeline()
    _emit(result["status"], args.format, args.out)
    return 0


def cmd_health(args: argparse.Namespace) -> int:
    """Combined machine-readable health check (exit 1 when degraded)."""
    result = run_pipeline()
    quality = result["quality"] or {}
    live = sum(1 for v in result["status"].values() if str(v).upper() == "LIVE")

    report = {
        "ok": True,
        "signals": len(result["signals"]),
        "regions": len({s.get("location") for s in result["signals"]}),
        "sources_live": live,
        "sources_total": len(result["status"]),
        "sources": result["status"],
        "anomalies": len(result["anomalies"]),
        "quality_score": quality.get("score"),
        "quality_grade": quality.get("grade"),
        "findings": quality.get("findings", []),
        "elapsed_seconds": result["elapsed_seconds"],
    }

    # A run with no signals at all is a genuine failure.
    if not result["signals"]:
        report["ok"] = False

    _emit(report, args.format, args.out)
    return 0 if report["ok"] else 1


def cmd_selftest(args: argparse.Namespace) -> int:
    """Run every module's built-in self-test."""
    import subprocess

    modules = [
        "utils", "anomaly_engine", "quality_engine", "escalation_tracker",
        "prediction_engine", "threat_engine", "correlation_engine",
        "confidence_engine", "action_engine", "classifier_engine",
        "weight_engine", "disaster_engine", "fusion_engine",
        "geofence_engine", "comparison_engine", "timeline_engine",
        "safety_engine", "alert_engine", "database_engine",
    ]

    failures = []
    for module in modules:
        proc = subprocess.run(
            [sys.executable, f"{module}.py"],
            capture_output=True,
            text=True,
            timeout=300,
        )
        ok = proc.returncode == 0
        print(f"  [{'PASS' if ok else 'FAIL'}] {module}.py")
        if not ok:
            failures.append((module, proc.stderr or proc.stdout))

    if failures:
        print(f"\n{len(failures)} module self-test(s) failed:")
        for module, output in failures:
            print(f"\n### {module}\n{output[-2000:]}")
        return 1

    print(f"\n✅ All {len(modules)} module self-tests passed.")
    return 0


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="orras_cli",
        description="ORRAS command-line intelligence pipeline",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sitrep", help="print a text situation report")
    p.set_defaults(func=cmd_sitrep)

    p = sub.add_parser("signals", help="export the current signal set")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--out", help="write to a file instead of stdout")
    p.add_argument("--top", type=int, help="limit to the N highest-scoring signals")
    p.set_defaults(func=cmd_signals)

    p = sub.add_parser("quality", help="report data-quality metrics")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--out", help="write to a file instead of stdout")
    p.set_defaults(func=cmd_quality)

    p = sub.add_parser("sources", help="report per-source collection status")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--out", help="write to a file instead of stdout")
    p.set_defaults(func=cmd_sources)

    p = sub.add_parser("health", help="machine-readable health check")
    p.add_argument("--format", choices=["json", "csv"], default="json")
    p.add_argument("--out", help="write to a file instead of stdout")
    p.set_defaults(func=cmd_health)

    p = sub.add_parser("selftest", help="run every module's built-in self-test")
    p.set_defaults(func=cmd_selftest)

    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    try:
        return args.func(args)
    except KeyboardInterrupt:
        return 130
    except Exception as exc:  # noqa: BLE001
        print(f"❌ {type(exc).__name__}: {exc}", file=sys.stderr)
        if "--debug" in sys.argv:
            raise
        return 1


if __name__ == "__main__":
    sys.exit(main())

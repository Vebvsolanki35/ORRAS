"""
data_collector.py — Live data collection from all six external sources.

Each source has a dedicated collector class inside the ``collectors`` package.
This module re-exports all classes for backward compatibility so that existing
code that imports directly from ``data_collector`` continues to work unchanged.
"""

# ---------------------------------------------------------------------------
# Re-exports from the collectors package (backward compatibility)
# ---------------------------------------------------------------------------

from collectors import (  # noqa: F401
    CloudflareRadarCollector,
    DataCollectionOrchestrator,
    GDELTCollector,
    NASAFIRMSCollector,
    NewsAPICollector,
    OpenSkyCollector,
)

# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== data_collector.py self-test ===\n")
    orchestrator = DataCollectionOrchestrator()
    raw = orchestrator.collect_all()

    status_map = raw.pop("_status", {})
    print("Source collection status:")
    for src, status in status_map.items():
        badge = "🟢 LIVE" if status == "LIVE" else "🔴 MOCK/OFFLINE"
        print(f"  {src:20s}: {badge} — {len(raw.get(src.lower().replace(' ', '').replace('/', ''), []))} records")

    print("\nRecord counts per source key:")
    for key, records in raw.items():
        print(f"  {key:15s}: {len(records)}")

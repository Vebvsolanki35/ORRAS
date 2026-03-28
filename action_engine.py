"""
action_engine.py — Recommendation engine for ORRAS.

Generates region-specific action recommendations based on the current maximum
severity level observed and logs alerts for medium-to-critical events.
"""

from utils import get_logger, load_json, now_iso, save_json
from config import ALERT_LOG_FILE

logger = get_logger(__name__)

# Severity order for sorting (highest first)
_SEVERITY_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


class ActionEngine:
    """
    Generates and logs actionable recommendations for each threat region.
    """

    RECOMMENDATIONS: dict[str, str] = {
        "LOW":      "Continue monitoring. No action required.",
        "MEDIUM":   "Increase monitoring frequency. Prepare contingency plans.",
        "HIGH":     "Issue alert. Notify stakeholders. Prepare response protocols.",
        "CRITICAL": "Immediate escalation required. Activate full emergency protocol.",
    }

    def recommend(self, severity: str) -> str:
        """
        Return the recommendation string for a given severity level.

        Args:
            severity: One of "LOW", "MEDIUM", "HIGH", "CRITICAL".

        Returns:
            Recommendation string.
        """
        return self.RECOMMENDATIONS.get(severity.upper(), self.RECOMMENDATIONS["LOW"])

    def generate_region_actions(self, signals: list[dict]) -> list[dict]:
        """
        Build one action record per region, sorted by severity (critical first).

        For each region:
        - Find the maximum severity level.
        - Retrieve the top 3 signal titles (by raw_score).
        - Compose an action dict.

        Args:
            signals: List of unified-schema signal dicts.

        Returns:
            List of action dicts, sorted by severity descending:
            [{region, max_severity, recommendation, signal_count, top_signals}]
        """
        # Group signals by region
        region_signals: dict[str, list[dict]] = {}
        for sig in signals:
            location = sig.get("location") or "Unknown"
            region_signals.setdefault(location, []).append(sig)

        actions = []
        for region, sigs in region_signals.items():
            # Determine max severity
            sev_order = _SEVERITY_ORDER
            max_sev = min(
                (s.get("severity", "LOW") for s in sigs),
                key=lambda s: sev_order.get(s, 3),
                default="LOW",
            )

            # Top 3 signals by score
            sorted_sigs = sorted(sigs, key=lambda s: s.get("raw_score", 0), reverse=True)
            top_titles = [s.get("title", "No title") for s in sorted_sigs[:3]]

            actions.append({
                "region": region,
                "max_severity": max_sev,
                "recommendation": self.recommend(max_sev),
                "signal_count": len(sigs),
                "top_signals": top_titles,
            })

        # Sort: CRITICAL → HIGH → MEDIUM → LOW
        actions.sort(key=lambda a: _SEVERITY_ORDER.get(a["max_severity"], 3))
        return actions

    def log_alerts(self, actions: list[dict]) -> None:
        """
        Append MEDIUM / HIGH / CRITICAL actions to the alert log file.

        Each log entry includes the current timestamp and the action dict.

        Args:
            actions: Output of generate_region_actions().
        """
        loggable_levels = {"MEDIUM", "HIGH", "CRITICAL"}
        alert_log = load_json(ALERT_LOG_FILE)
        new_entries = []

        for action in actions:
            if action.get("max_severity") in loggable_levels:
                entry = {
                    "timestamp": now_iso(),
                    **action,
                }
                new_entries.append(entry)

        if new_entries:
            alert_log.extend(new_entries)
            save_json(ALERT_LOG_FILE, alert_log)
            logger.info(f"ActionEngine: logged {len(new_entries)} alert(s) to {ALERT_LOG_FILE}.")
        else:
            logger.info("ActionEngine: no alerts above LOW threshold to log.")


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    import json
    from mock_data_generator import generate_all_mock_signals
    from threat_engine import ThreatEngine
    from correlation_engine import CorrelationEngine
    from confidence_engine import ConfidenceEngine

    print("=== action_engine.py self-test ===\n")

    signals = generate_all_mock_signals()
    signals = ThreatEngine().score_all(signals)
    signals = CorrelationEngine().correlate_all(signals)
    conf_map = ConfidenceEngine().score_confidence(signals)
    signals = ConfidenceEngine().annotate_signals(signals, conf_map)

    action_engine = ActionEngine()
    actions = action_engine.generate_region_actions(signals)

    print(f"Actions generated for {len(actions)} regions.\n")
    print("Top 5 action recommendations:")
    for a in actions[:5]:
        print(
            f"  [{a['max_severity']:8s}] {a['region']:25s} "
            f"({a['signal_count']} signals) — {a['recommendation']}"
        )
        for title in a["top_signals"]:
            print(f"      • {title[:70]}")

    action_engine.log_alerts(actions)
    print(f"\nAlert log updated: {ALERT_LOG_FILE}")
    print("\n✅ action_engine.py self-test passed.")

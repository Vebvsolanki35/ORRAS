"""
ai_assistant.py — Claude-powered intelligence analysis for the ORRAS system.

Provides three standalone analyst functions (threat summary, global SITREP,
daily brief) and an interactive AIAssistant class that maintains multi-turn
conversation history with ORRAS data injected as context.

When ANTHROPIC_API_KEY is not set, every function falls back to realistic
mock responses so the rest of the system keeps working offline.
"""

import os
from datetime import datetime, timezone

import anthropic

from utils import classify_severity, get_logger, now_iso

logger = get_logger(__name__)

# ---------------------------------------------------------------------------
# Low-level Claude helper
# ---------------------------------------------------------------------------

def query_claude(system_prompt: str, user_message: str) -> str:
    """
    Send a single-turn request to Claude and return the text response.

    Falls back to a mock response when the API key is absent so that every
    caller can work in offline / test mode without special-casing.

    Args:
        system_prompt: Role and context instructions for Claude.
        user_message:  The analyst query or data payload.

    Returns:
        Claude's text reply, or a mock intelligence paragraph.
    """
    api_key = os.getenv("ANTHROPIC_API_KEY", "")
    if not api_key:
        logger.debug("ANTHROPIC_API_KEY not set — returning mock response.")
        return _mock_response(user_message)

    client = anthropic.Anthropic(api_key=api_key)
    message = client.messages.create(
        model="claude-opus-4-5",
        max_tokens=1024,
        system=system_prompt,
        messages=[{"role": "user", "content": user_message}],
    )
    return message.content[0].text


# ---------------------------------------------------------------------------
# Mock fallback — professional intelligence-style prose
# ---------------------------------------------------------------------------

# Static mock paragraphs rotated by a simple hash so different inputs yield
# slightly different-looking responses without being truly random.
_MOCK_PARAGRAPHS = [
    (
        "Current intelligence indicators suggest a moderate-to-high probability of continued "
        "instability across the assessed region. Multiple SIGINT and OSINT streams converge on "
        "elevated troop concentrations near contested border areas, consistent with pre-offensive "
        "posturing. Economic pressure and internal political fragmentation are likely exacerbating "
        "the security environment."
    ),
    (
        "All-source analysis indicates a deteriorating security situation driven by compounding "
        "logistics disruptions and escalating militant activity. Satellite imagery corroborates "
        "ground-truth reporting of increased vehicular movement along key supply corridors. "
        "Regional actors are assessed with high confidence to be repositioning assets in "
        "anticipation of further kinetic operations."
    ),
    (
        "The intelligence picture reflects heightened operational tempo with a credible threat "
        "window of 24–72 hours. Cross-domain correlation of network anomalies, civil unrest "
        "patterns, and aerial sortie data supports an escalation assessment. Allied liaison "
        "reporting is consistent with primary source accounts; confidence in the overall "
        "assessment is assessed at MEDIUM-HIGH."
    ),
    (
        "Baseline threat indicators remain elevated relative to the 30-day rolling average. "
        "No significant force withdrawal or de-escalatory signalling has been observed through "
        "monitored channels. The preponderance of evidence supports maintaining the current "
        "alert posture and increasing collection priorities on secondary nodes of interest."
    ),
]


def _mock_response(seed_text: str) -> str:
    """Return a mock intelligence paragraph deterministically seeded by input text."""
    idx = hash(seed_text[:64]) % len(_MOCK_PARAGRAPHS)
    return _MOCK_PARAGRAPHS[idx]


# ---------------------------------------------------------------------------
# Standalone analyst functions
# ---------------------------------------------------------------------------

def generate_threat_summary(signals: list, region: str) -> str:
    """
    Produce a 3-paragraph threat assessment for a specific region.

    Args:
        signals: List of scored signal dicts (must contain 'location' and 'raw_score').
        region:  The geographic region being assessed.

    Returns:
        A multi-paragraph threat assessment string.
    """
    # Filter signals that belong to the target region
    regional_signals = [s for s in signals if s.get("location") == region]

    if not regional_signals:
        scores_summary = "No signals available for this region."
    else:
        avg_score = sum(s.get("raw_score", 0) for s in regional_signals) / len(regional_signals)
        max_score = max(s.get("raw_score", 0) for s in regional_signals)
        severity = classify_severity(avg_score)
        scores_summary = (
            f"Region: {region} | Signals: {len(regional_signals)} | "
            f"Avg score: {avg_score:.1f} | Max score: {max_score:.1f} | "
            f"Severity: {severity}"
        )
        # Include a brief list of sources for context
        sources = list({s.get("source_type", "unknown") for s in regional_signals})
        scores_summary += f" | Sources: {', '.join(sources)}"

    system_prompt = (
        "You are a senior intelligence analyst producing classified threat assessments. "
        "Write in a formal, precise military-intelligence style. Avoid speculation beyond "
        "what the data supports. Structure your response as exactly three paragraphs: "
        "(1) current situation overview, (2) threat actor assessment and capability analysis, "
        "(3) near-term outlook and recommended collection priorities."
    )
    user_message = (
        f"Produce a threat assessment for the region: {region}\n\n"
        f"Signal Intelligence Summary:\n{scores_summary}\n\n"
        f"Assessment timestamp: {now_iso()}"
    )

    logger.info(f"Generating threat summary for region: {region}")
    return query_claude(system_prompt, user_message)


def generate_global_sitrep(all_signals: list, anomalies: list) -> str:
    """
    Produce a full global situation report (SITREP) in standard military format.

    Sections: BLUF, Key Developments, Regional Breakdown, Recommended Actions.

    Args:
        all_signals: Complete list of scored signal dicts from all regions.
        anomalies:   List of anomaly dicts from the anomaly engine.

    Returns:
        A formatted SITREP string.
    """
    # Build a compact data payload to fit within reasonable token limits
    if all_signals:
        # Aggregate per-region stats
        region_stats: dict[str, dict] = {}
        for sig in all_signals:
            loc = sig.get("location", "Unknown")
            score = float(sig.get("raw_score", 0))
            entry = region_stats.setdefault(loc, {"scores": [], "count": 0})
            entry["scores"].append(score)
            entry["count"] += 1

        top_regions = sorted(
            [
                {
                    "region": r,
                    "avg_score": round(sum(d["scores"]) / len(d["scores"]), 1),
                    "severity": classify_severity(sum(d["scores"]) / len(d["scores"])),
                    "signal_count": d["count"],
                }
                for r, d in region_stats.items()
            ],
            key=lambda x: x["avg_score"],
            reverse=True,
        )[:10]  # top 10 regions for the brief

        region_lines = "\n".join(
            f"  {i+1}. {r['region']}: score={r['avg_score']} ({r['severity']}, "
            f"{r['signal_count']} signals)"
            for i, r in enumerate(top_regions)
        )
    else:
        region_lines = "  No regional signals available."

    anomaly_lines = (
        "\n".join(
            f"  - {a.get('region', 'Unknown')}: {a.get('description', 'anomaly detected')}"
            for a in (anomalies or [])[:5]
        )
        or "  No anomalies flagged."
    )

    system_prompt = (
        "You are the senior duty officer producing a classified Global Situation Report. "
        "Follow this exact structure:\n"
        "BLUF (Bottom Line Up Front): 2-3 sentences of the most critical takeaway.\n"
        "KEY DEVELOPMENTS: Bullet list of 3-5 significant developments.\n"
        "REGIONAL BREAKDOWN: Brief paragraph on the top-risk regions.\n"
        "RECOMMENDED ACTIONS: Numbered list of 3-4 concrete actions for commanders.\n"
        "Use formal military-intelligence prose. Be specific and data-driven."
    )
    user_message = (
        f"Generate a Global SITREP as of {now_iso()}\n\n"
        f"TOP RISK REGIONS:\n{region_lines}\n\n"
        f"FLAGGED ANOMALIES:\n{anomaly_lines}\n\n"
        f"Total signals in system: {len(all_signals)}"
    )

    logger.info("Generating global SITREP.")
    return query_claude(system_prompt, user_message)


def generate_daily_brief(signals: list, escalations: list, anomalies: list) -> str:
    """
    Produce a daily intelligence brief summarising the past 24 hours.

    Args:
        signals:     All scored signals from the current cycle.
        escalations: List of rapid-escalation alert dicts.
        anomalies:   List of anomaly dicts.

    Returns:
        A formatted daily intelligence brief string.
    """
    total_signals = len(signals)
    critical_count = sum(1 for s in signals if classify_severity(s.get("raw_score", 0)) == "CRITICAL")
    high_count = sum(1 for s in signals if classify_severity(s.get("raw_score", 0)) == "HIGH")

    escalation_lines = (
        "\n".join(
            f"  - {e.get('region', '?')}: {e.get('from_level', '?')} → "
            f"{e.get('to_level', '?')} over {e.get('hours', '?')}h"
            for e in (escalations or [])
        )
        or "  None detected."
    )

    anomaly_lines = (
        "\n".join(
            f"  - {a.get('region', '?')}: z-score={a.get('z_score', '?'):.2f}"
            if isinstance(a.get("z_score"), (int, float))
            else f"  - {a.get('region', '?')}: anomaly"
            for a in (anomalies or [])[:6]
        )
        or "  None detected."
    )

    system_prompt = (
        "You are a senior intelligence analyst writing a daily intelligence brief for senior "
        "leadership. Be concise, authoritative, and analytical. Lead with the most significant "
        "developments. Highlight trend changes. The brief should read as a polished document "
        "suitable for a 3-star general. Use section headers: EXECUTIVE SUMMARY, THREAT LANDSCAPE, "
        "ANOMALOUS ACTIVITY, OUTLOOK."
    )
    user_message = (
        f"Daily Intelligence Brief — {datetime.now(timezone.utc).strftime('%d %b %Y %H%MZ')}\n\n"
        f"Signal Overview:\n"
        f"  Total signals collected: {total_signals}\n"
        f"  CRITICAL-severity signals: {critical_count}\n"
        f"  HIGH-severity signals: {high_count}\n\n"
        f"Rapid Escalation Events:\n{escalation_lines}\n\n"
        f"Statistical Anomalies:\n{anomaly_lines}"
    )

    logger.info("Generating daily intelligence brief.")
    return query_claude(system_prompt, user_message)


# ---------------------------------------------------------------------------
# AIAssistant — interactive multi-turn analyst
# ---------------------------------------------------------------------------

class AIAssistant:
    """
    Stateful AI analyst that maintains a rolling conversation history.

    Keeps the last 10 turns so Claude retains context across multiple
    questions while staying well within token budget. ORRAS signal data
    is injected into a system prompt so the assistant always has situational
    awareness without repeating data in every user message.
    """

    # Maximum number of (user + assistant) turn pairs to remember
    MAX_HISTORY_TURNS: int = 10

    def __init__(self) -> None:
        # Each entry is {"role": "user"|"assistant", "content": str}
        self._history: list[dict] = []
        logger.debug("AIAssistant initialised.")

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def chat(self, user_message: str, context_signals: list) -> str:
        """
        Send a message to Claude and get an analyst response.

        The current ORRAS signal data is included in the system prompt so
        Claude can answer questions about the live threat picture.

        Args:
            user_message:    The analyst's question or command.
            context_signals: Current scored signals for situational context.

        Returns:
            Claude's response text.
        """
        system_prompt = self._build_system_prompt(context_signals)

        # Add the new user turn
        self._history.append({"role": "user", "content": user_message})

        # Trim to the last MAX_HISTORY_TURNS pairs (2 messages per turn)
        max_messages = self.MAX_HISTORY_TURNS * 2
        if len(self._history) > max_messages:
            self._history = self._history[-max_messages:]

        api_key = os.getenv("ANTHROPIC_API_KEY", "")
        if not api_key:
            logger.debug("ANTHROPIC_API_KEY not set — chat returning mock response.")
            reply = _mock_response(user_message)
        else:
            client = anthropic.Anthropic(api_key=api_key)
            message = client.messages.create(
                model="claude-opus-4-5",
                max_tokens=1024,
                system=system_prompt,
                messages=self._history,
            )
            reply = message.content[0].text

        # Append assistant reply to keep history coherent
        self._history.append({"role": "assistant", "content": reply})
        return reply

    def reset(self) -> None:
        """Clear the entire conversation history."""
        self._history.clear()
        logger.info("AIAssistant: conversation history cleared.")

    def get_history(self) -> list:
        """
        Return a copy of the full conversation history.

        Returns:
            List of {"role": str, "content": str} dicts.
        """
        return list(self._history)

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_system_prompt(self, signals: list) -> str:
        """
        Build the system prompt by injecting a snapshot of current signal data.

        Args:
            signals: Current scored signals.

        Returns:
            System prompt string for Claude.
        """
        if signals:
            region_scores: dict[str, list[float]] = {}
            for s in signals:
                loc = s.get("location", "Unknown")
                region_scores.setdefault(loc, []).append(float(s.get("raw_score", 0)))

            top_regions = sorted(
                [
                    (r, round(sum(v) / len(v), 1))
                    for r, v in region_scores.items()
                ],
                key=lambda x: x[1],
                reverse=True,
            )[:8]

            context_block = "Top risk regions (region: avg_score):\n" + "\n".join(
                f"  {r}: {sc} ({classify_severity(sc)})" for r, sc in top_regions
            )
        else:
            context_block = "No signal data currently available."

        return (
            "You are ORRAS-AI, an expert military intelligence analyst embedded in the ORRAS "
            "(Operational Risk & Resource Allocation System) platform. You have direct access "
            "to real-time multi-source intelligence signals. Be analytical, concise, and "
            "evidence-based. When uncertain, state your confidence level explicitly. "
            "Never fabricate data — if information is unavailable, say so.\n\n"
            f"CURRENT ORRAS SNAPSHOT ({now_iso()}):\n{context_block}"
        )


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    print("=== ai_assistant.py self-test ===\n")

    # Build a handful of synthetic signals to exercise all paths
    sample_signals = [
        {"location": "Eastern Europe", "raw_score": 22.0, "source_type": "news_conflict"},
        {"location": "Eastern Europe", "raw_score": 18.5, "source_type": "troop_movement"},
        {"location": "Middle East",    "raw_score": 15.0, "source_type": "satellite_fire"},
        {"location": "Middle East",    "raw_score": 9.0,  "source_type": "social_unrest"},
        {"location": "South Asia",     "raw_score": 12.0, "source_type": "aircraft_anomaly"},
        {"location": "West Africa",    "raw_score": 6.5,  "source_type": "news_conflict"},
    ]
    sample_escalations = [
        {"region": "Eastern Europe", "from_level": "MEDIUM", "to_level": "CRITICAL", "hours": 18.0},
    ]
    sample_anomalies = [
        {"region": "Eastern Europe", "z_score": 3.7, "description": "unusual signal spike"},
        {"region": "Middle East",    "z_score": 2.3, "description": "network disruption"},
    ]

    # 1. Threat summary
    print("--- generate_threat_summary ---")
    summary = generate_threat_summary(sample_signals, "Eastern Europe")
    print(summary[:300], "...\n")

    # 2. Global SITREP
    print("--- generate_global_sitrep ---")
    sitrep = generate_global_sitrep(sample_signals, sample_anomalies)
    print(sitrep[:400], "...\n")

    # 3. Daily brief
    print("--- generate_daily_brief ---")
    brief = generate_daily_brief(sample_signals, sample_escalations, sample_anomalies)
    print(brief[:400], "...\n")

    # 4. AIAssistant multi-turn chat
    print("--- AIAssistant.chat ---")
    assistant = AIAssistant()

    r1 = assistant.chat("What is the highest-risk region right now?", sample_signals)
    print(f"Turn 1: {r1[:200]}...\n")

    r2 = assistant.chat("Why is that region so elevated?", sample_signals)
    print(f"Turn 2 (context-aware): {r2[:200]}...\n")

    print(f"History length: {len(assistant.get_history())} messages")

    assistant.reset()
    print(f"After reset, history length: {len(assistant.get_history())}")

    print("\n✅ ai_assistant.py self-test complete.")

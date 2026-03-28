"""
01_AI_Assistant.py — ORRAS v2.0 AI Intelligence Chat Interface

Provides a conversational interface powered by Claude/mock responses,
with context-aware signal awareness and quick-prompt actions.
"""

import streamlit as st

st.set_page_config(
    page_title="ORRAS AI Assistant",
    page_icon="🤖",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Module imports with graceful fallback
# ---------------------------------------------------------------------------
try:
    from mock_data_generator import generate_all_mock_signals
except ImportError as e:
    st.error(f"❌ Failed to import mock_data_generator: {e}")
    st.stop()

try:
    from threat_engine import ThreatEngine
except ImportError as e:
    st.error(f"❌ Failed to import threat_engine: {e}")
    st.stop()

try:
    from anomaly_engine import AnomalyEngine
except ImportError as e:
    st.error(f"❌ Failed to import anomaly_engine: {e}")
    st.stop()

try:
    from escalation_tracker import EscalationTracker
except ImportError as e:
    st.error(f"❌ Failed to import escalation_tracker: {e}")
    st.stop()

try:
    from ai_assistant import (
        AIAssistant,
        generate_global_sitrep,
        generate_threat_summary,
        generate_daily_brief,
    )
except ImportError as e:
    st.error(f"❌ Failed to import ai_assistant: {e}")
    st.stop()

try:
    from ui_components import render_ai_message, render_severity_badge, render_metric_card
except ImportError as e:
    st.error(f"❌ Failed to import ui_components: {e}")
    st.stop()

try:
    from utils import classify_severity
except ImportError as e:
    st.error(f"❌ Failed to import utils: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Data loading (cached)
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_signals() -> list:
    try:
        signals = generate_all_mock_signals()
        return ThreatEngine().score_all(signals)
    except Exception as e:
        st.warning(f"⚠️ Signal load error: {e}")
        return []


@st.cache_data(ttl=60)
def load_anomalies(signal_count: int) -> list:
    try:
        signals = load_signals()
        return AnomalyEngine().detect_anomalies(signals)
    except Exception as e:
        return []


@st.cache_data(ttl=60)
def load_escalations(signal_count: int) -> list:
    try:
        tracker = EscalationTracker()
        result = tracker.run(load_signals())
        return result.get("escalation_alerts", [])
    except Exception as e:
        return []


# ---------------------------------------------------------------------------
# Session state initialisation
# ---------------------------------------------------------------------------

if "chat_history" not in st.session_state:
    st.session_state.chat_history = []

if "ai_assistant" not in st.session_state:
    try:
        st.session_state.ai_assistant = AIAssistant()
    except Exception:
        st.session_state.ai_assistant = None

# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

with st.spinner("Loading intelligence data…"):
    signals = load_signals()

signal_count = len(signals)
anomalies = load_anomalies(signal_count)
escalations = load_escalations(signal_count)

# ---------------------------------------------------------------------------
# Compute summary metrics from signals
# ---------------------------------------------------------------------------

def _global_risk_level(sigs: list) -> str:
    if not sigs:
        return "LOW"
    scores = [float(s.get("raw_score") or 0) for s in sigs]
    return classify_severity(max(scores))


def _top_threats(sigs: list, n: int = 3) -> list:
    """Return top-n regions by max raw_score."""
    region_max: dict[str, float] = {}
    for s in sigs:
        loc = s.get("location") or "Unknown"
        sc = float(s.get("raw_score") or 0)
        region_max[loc] = max(region_max.get(loc, 0.0), sc)
    sorted_regions = sorted(region_max.items(), key=lambda x: x[1], reverse=True)
    return sorted_regions[:n]


global_risk = _global_risk_level(signals)
top_threats = _top_threats(signals)

# ---------------------------------------------------------------------------
# Sidebar
# ---------------------------------------------------------------------------

with st.sidebar:
    st.markdown("### 🌐 Global Risk Status")
    st.markdown(render_severity_badge(global_risk), unsafe_allow_html=True)

    st.markdown("---")
    st.markdown("### 🔥 Top Active Threats")
    if top_threats:
        for region, score in top_threats:
            severity = classify_severity(score)
            badge = render_severity_badge(severity)
            st.markdown(
                f"**{region}** — `{score:.1f}` {badge}",
                unsafe_allow_html=True,
            )
    else:
        st.info("No threat data available.")

    st.markdown("---")
    if st.button("🗑️ Clear Conversation", use_container_width=True):
        st.session_state.chat_history = []
        if st.session_state.ai_assistant:
            try:
                st.session_state.ai_assistant.reset()
            except Exception:
                pass
        st.rerun()

    st.markdown("---")
    st.markdown(f"📡 **Signals loaded:** {signal_count}")
    st.markdown(f"⚠️ **Anomalies detected:** {len(anomalies)}")
    st.markdown(f"🚨 **Escalation alerts:** {len(escalations)}")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown("# 🤖 ORRAS-AI Intelligence Assistant")
st.markdown("*Ask anything about current threat intelligence*")
st.divider()

# ---------------------------------------------------------------------------
# Quick-prompt buttons
# ---------------------------------------------------------------------------

st.markdown("#### ⚡ Quick Intelligence Actions")
col1, col2, col3, col4 = st.columns(4)

quick_prompt: str | None = None

with col1:
    if st.button("📊 Generate Global SITREP", use_container_width=True):
        quick_prompt = "Generate a comprehensive Global SITREP based on current threat intelligence."

with col2:
    if st.button("🔍 Analyze top threats", use_container_width=True):
        quick_prompt = "Analyze the top active threats and provide a detailed breakdown."

with col3:
    if st.button("⚠️ Explain current anomalies", use_container_width=True):
        quick_prompt = "Explain the current anomalies detected in the signal data and their implications."

with col4:
    if st.button("📋 Daily intelligence brief", use_container_width=True):
        quick_prompt = "Generate today's daily intelligence brief."

# ---------------------------------------------------------------------------
# Handle quick prompt actions
# ---------------------------------------------------------------------------

if quick_prompt:
    with st.spinner("🤖 Generating intelligence report…"):
        try:
            if "SITREP" in quick_prompt:
                response = generate_global_sitrep(signals, anomalies)
            elif "daily intelligence brief" in quick_prompt.lower():
                response = generate_daily_brief(signals, escalations, anomalies)
            elif st.session_state.ai_assistant:
                response = st.session_state.ai_assistant.chat(quick_prompt, signals)
            else:
                response = "AI Assistant is not available."
        except Exception as e:
            response = f"Unable to generate response: {e}"

    st.session_state.chat_history.append({"role": "user", "content": quick_prompt})
    st.session_state.chat_history.append({"role": "assistant", "content": response})
    st.rerun()

# ---------------------------------------------------------------------------
# Chat history display
# ---------------------------------------------------------------------------

st.markdown("#### 💬 Conversation")

chat_container = st.container()

with chat_container:
    if not st.session_state.chat_history:
        st.markdown(
            render_ai_message(
                "assistant",
                "Hello! I'm the ORRAS AI Intelligence Assistant. I have access to current "
                "threat signals, anomaly data, and escalation history.\n\n"
                "You can use the quick action buttons above or type your own question below. "
                "Try asking about specific regions, threat trends, or request a full SITREP.",
            ),
            unsafe_allow_html=True,
        )
    else:
        for msg in st.session_state.chat_history:
            st.markdown(
                render_ai_message(msg["role"], msg["content"]),
                unsafe_allow_html=True,
            )

# ---------------------------------------------------------------------------
# Chat input
# ---------------------------------------------------------------------------

if user_input := st.chat_input("Ask about threats, regions, anomalies, or request analysis…"):
    st.session_state.chat_history.append({"role": "user", "content": user_input})

    with st.spinner("🤖 Thinking…"):
        try:
            if st.session_state.ai_assistant:
                response = st.session_state.ai_assistant.chat(user_input, signals)
            else:
                response = "AI Assistant unavailable. Please check your configuration."
        except Exception as e:
            response = f"An error occurred while generating a response: {e}"

    st.session_state.chat_history.append({"role": "assistant", "content": response})
    st.rerun()

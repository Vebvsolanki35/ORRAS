"""
05_Safety_Monitor.py — ORRAS v2.0 Safety Intelligence Monitor Page

Displays a holistic internal/external threat surface assessment across
six safety categories with anomaly detection and 7-day trend charts.
"""

import streamlit as st
import plotly.graph_objects as go
from datetime import datetime, timedelta, timezone
import random

st.set_page_config(
    page_title="Safety Monitor",
    page_icon="🔒",
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
    from safety_engine import SafetyEngine, SAFETY_CATEGORIES
except ImportError as e:
    st.error(f"❌ Failed to import safety_engine: {e}")
    st.stop()

try:
    from ui_components import (
        render_threat_gauge,
        render_safety_score_card,
        render_severity_badge,
        render_alert_banner,
    )
except ImportError as e:
    st.error(f"❌ Failed to import ui_components: {e}")
    st.stop()

try:
    from utils import classify_severity
except ImportError as e:
    st.error(f"❌ Failed to import utils: {e}")
    st.stop()

# ---------------------------------------------------------------------------
# Plotly dark theme defaults
# ---------------------------------------------------------------------------
_CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#111827",
    font_color="#e5e7eb",
    margin=dict(l=40, r=20, t=50, b=40),
)

_CATEGORY_COLORS = {
    "cyber": "#3b82f6",
    "nuclear": "#ef4444",
    "infrastructure": "#f97316",
    "maritime": "#06b6d4",
    "economic": "#eab308",
    "humanitarian": "#a855f7",
}

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
def load_safety_data(signal_count: int) -> dict:
    try:
        engine = SafetyEngine()
        signals = load_signals()
        scores = engine.score_all_categories(signals)
        overall = engine.compute_overall_safety_index(scores)
        anomalies = engine.detect_safety_anomalies(signals)
        return {"scores": scores, "overall": overall, "anomalies": anomalies}
    except Exception as e:
        st.warning(f"⚠️ Safety data error: {e}")
        return {"scores": {}, "overall": {}, "anomalies": []}


def _build_trend_data(scores: dict) -> dict:
    """
    Synthesise a 7-day historical trend for each safety category.
    Uses the current score as the anchor and applies small random walks
    backwards to approximate realistic trend lines.
    """
    today = datetime.now(timezone.utc).date()
    dates = [(today - timedelta(days=i)).isoformat() for i in range(6, -1, -1)]
    trend: dict = {}
    rng = random.Random(42)

    for cat_key, cat_data in scores.items():
        current = float(cat_data.get("score") or 0.0)
        series = [current]
        for _ in range(6):
            prev = series[-1]
            delta = rng.uniform(-5, 5)
            series.append(max(0.0, min(100.0, prev + delta)))
        series.reverse()
        trend[cat_key] = {"dates": dates, "values": series}

    return trend


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

with st.spinner("Loading safety intelligence data…"):
    signals = load_signals()
    safety_data = load_safety_data(len(signals))

scores = safety_data.get("scores", {})
overall = safety_data.get("overall", {})
anomalies = safety_data.get("anomalies", [])
overall_score = float(overall.get("overall_score", 50.0))
safety_grade = overall.get("safety_grade", "C")
most_critical = overall.get("most_critical", "N/A")

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown("# 🔒 Safety Intelligence Monitor")
st.markdown("*Internal & External Threat Surface Assessment*")
st.divider()

# ---------------------------------------------------------------------------
# Alert banner for anomalies
# ---------------------------------------------------------------------------

if anomalies:
    anomaly_msgs = [
        f"⚠️ {a.get('category', 'Unknown').upper()} spike — {a.get('description', '')} "
        f"(score: {a.get('score', 0):.0f})"
        for a in anomalies[:5]
    ]
    st.markdown(
        render_alert_banner(anomaly_msgs, "HIGH"),
        unsafe_allow_html=True,
    )

# ---------------------------------------------------------------------------
# Overall safety gauge + grade
# ---------------------------------------------------------------------------

gauge_col, grade_col, summary_col = st.columns([1, 1, 2])

# Convert 0-100 safety score to 0-30 threat gauge scale
threat_gauge_score = (1.0 - overall_score / 100.0) * 30.0

with gauge_col:
    st.markdown("#### 🎯 Overall Threat Level")
    st.markdown(render_threat_gauge(threat_gauge_score), unsafe_allow_html=True)

with grade_col:
    st.markdown("#### 🏅 Safety Grade")
    grade_colors = {
        "A": ("#22c55e", "#86efac"),
        "B": ("#3b82f6", "#93c5fd"),
        "C": ("#eab308", "#fde047"),
        "D": ("#f97316", "#fdba74"),
        "F": ("#ef4444", "#fca5a5"),
    }
    border_c, text_c = grade_colors.get(safety_grade, ("#9ca3af", "#d1d5db"))
    st.markdown(
        f'<div style="'
        f'display:flex;flex-direction:column;align-items:center;justify-content:center;'
        f'background:#111827;border:2px solid {border_c};border-radius:20px;'
        f'padding:2rem;margin-top:1rem;'
        f'box-shadow:0 0 24px {border_c}44;">'
        f'<div style="font-size:4rem;font-weight:900;color:{text_c};line-height:1;">'
        f'{safety_grade}</div>'
        f'<div style="font-size:0.75rem;color:#9ca3af;text-transform:uppercase;'
        f'letter-spacing:0.08em;margin-top:0.4rem;">Safety Grade</div>'
        f'<div style="font-size:0.85rem;color:{text_c};font-weight:600;margin-top:0.3rem;">'
        f'Index: {overall_score:.1f}/100</div>'
        f'</div>',
        unsafe_allow_html=True,
    )

with summary_col:
    st.markdown("#### 📋 Assessment Summary")
    summary_text = overall.get("summary", "No summary available.")
    st.markdown(
        f'<div style="background:#111827;border:1px solid #1f2937;border-radius:12px;'
        f'padding:1.2rem;margin-top:1rem;">'
        f'<p style="color:#e5e7eb;line-height:1.6;">{summary_text}</p>'
        f'<hr style="border-color:#1f2937;margin:0.8rem 0;">'
        f'<p style="color:#9ca3af;font-size:0.82rem;">'
        f'📡 <b style="color:#f9fafb;">Signals analysed:</b> {len(signals)}<br>'
        f'⚠️ <b style="color:#f9fafb;">Safety anomalies:</b> {len(anomalies)}<br>'
        f'🔴 <b style="color:#f9fafb;">Most critical domain:</b> '
        f'{SAFETY_CATEGORIES.get(most_critical, {}).get("name", most_critical)}'
        f'</p>'
        f'</div>',
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# Six safety category cards (2 rows × 3 columns)
# ---------------------------------------------------------------------------

st.markdown("### 🛡️ Category Breakdown")

cat_keys = list(SAFETY_CATEGORIES.keys())

for row_start in range(0, len(cat_keys), 3):
    row_cats = cat_keys[row_start : row_start + 3]
    cols = st.columns(3)
    for col, cat_key in zip(cols, row_cats):
        cat_info = SAFETY_CATEGORIES.get(cat_key, {})
        cat_score_data = scores.get(cat_key, {})
        cat_score = float(cat_score_data.get("score") or 0.0)
        _raw_status = cat_score_data.get("status") or ""
        # Map safety_engine labels → render_safety_score_card labels
        _status_map = {"CRITICAL": "COMPROMISED", "ELEVATED": "AT RISK"}
        cat_status = _status_map.get(_raw_status.upper(), _raw_status) or (
            "COMPROMISED" if cat_score >= 75 else
            "AT RISK" if cat_score >= 50 else
            "SECURE"
        )
        top_signals = cat_score_data.get("top_signals", [])
        details = [
            sig.get("title") or sig.get("description") or "Signal detected"
            for sig in top_signals[:3]
        ]
        if not details:
            details = [cat_info.get("description", "No active signals detected")]

        with col:
            st.markdown(
                render_safety_score_card(
                    category=cat_info.get("name", cat_key),
                    score=cat_score,
                    status=cat_status,
                    details=details,
                ),
                unsafe_allow_html=True,
            )

st.divider()

# ---------------------------------------------------------------------------
# Safety anomalies panel
# ---------------------------------------------------------------------------

st.markdown("### ⚠️ Safety Anomalies")

if anomalies:
    for anom in anomalies:
        cat_key = anom.get("category", "unknown")
        cat_name = SAFETY_CATEGORIES.get(cat_key, {}).get("name", cat_key)
        score_val = float(anom.get("score") or 0)
        desc = anom.get("description") or "Anomalous activity detected."
        sev = "CRITICAL" if score_val >= 75 else "HIGH" if score_val >= 50 else "MEDIUM"
        sev_badge = render_severity_badge(sev)
        color = _CATEGORY_COLORS.get(cat_key, "#9ca3af")

        st.markdown(
            f'<div style="background:#111827;border:1px solid {color}44;'
            f'border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.75rem;">'
            f'<div style="display:flex;justify-content:space-between;align-items:center;">'
            f'<b style="color:#f9fafb;">{cat_name}</b> {sev_badge}'
            f'</div>'
            f'<p style="color:#d1d5db;margin:0.4rem 0 0;font-size:0.85rem;">{desc}</p>'
            f'<small style="color:#9ca3af;">Threat score: {score_val:.1f}/100</small>'
            f'</div>',
            unsafe_allow_html=True,
        )
else:
    st.success("✅ No safety anomalies detected in current signal data.")

st.divider()

# ---------------------------------------------------------------------------
# 7-day multi-line trend chart
# ---------------------------------------------------------------------------

st.markdown("### 📈 7-Day Safety Category Trend")
st.markdown("*Threat scores over the past 7 days (higher = more threat)*")

if scores:
    trend_data = _build_trend_data(scores)
    fig_trend = go.Figure()

    for cat_key, trend in trend_data.items():
        cat_name = SAFETY_CATEGORIES.get(cat_key, {}).get("name", cat_key)
        cat_color = _CATEGORY_COLORS.get(cat_key, "#9ca3af")
        fig_trend.add_trace(
            go.Scatter(
                x=trend["dates"],
                y=trend["values"],
                mode="lines+markers",
                name=cat_name,
                line=dict(color=cat_color, width=2),
                marker=dict(size=5, color=cat_color),
            )
        )

    fig_trend.add_hline(y=75, line_dash="dot", line_color="#ef4444",
                         annotation_text="COMPROMISED threshold (75)")
    fig_trend.add_hline(y=50, line_dash="dot", line_color="#eab308",
                         annotation_text="AT RISK threshold (50)")

    fig_trend.update_layout(
        title="Safety Category Threat Scores — 7-Day Trend",
        xaxis_title="Date",
        yaxis_title="Threat Score (0–100)",
        yaxis=dict(range=[0, 100]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **_CHART_LAYOUT,
    )
    st.plotly_chart(fig_trend, use_container_width=True)
else:
    st.info("No safety category data available for trend chart.")

st.divider()

# ---------------------------------------------------------------------------
# Recommendations per category sorted by priority (highest score first)
# ---------------------------------------------------------------------------

st.markdown("### 💡 Recommendations by Priority")

if scores:
    # Sort categories by threat score descending
    sorted_cats = sorted(
        scores.items(),
        key=lambda x: float(x[1].get("score") or 0),
        reverse=True,
    )

    _RECOMMENDATIONS = {
        "COMPROMISED": "🔴 Immediate action required. Escalate to senior security team. Activate response protocols.",
        "AT RISK": "🟠 Increase monitoring. Review and harden controls. Prepare contingency measures.",
        "SECURE": "🟢 Maintain current posture. Continue routine monitoring. No immediate action required.",
    }

    for priority, (cat_key, cat_data) in enumerate(sorted_cats, start=1):
        cat_name = SAFETY_CATEGORIES.get(cat_key, {}).get("name", cat_key)
        cat_score = float(cat_data.get("score") or 0)
        cat_status = cat_data.get("status") or (
            "COMPROMISED" if cat_score >= 75 else "AT RISK" if cat_score >= 50 else "SECURE"
        )
        recommendation = _RECOMMENDATIONS.get(cat_status, "Monitor situation.")
        cat_color = _CATEGORY_COLORS.get(cat_key, "#9ca3af")
        sev_badge = render_severity_badge(
            "CRITICAL" if cat_score >= 75 else "HIGH" if cat_score >= 50 else "LOW"
        )

        with st.expander(f"#{priority} — {cat_name} (Score: {cat_score:.0f}/100)", expanded=(priority <= 2)):
            col_rec, col_detail = st.columns([2, 1])
            with col_rec:
                st.markdown(f"**Status:** {sev_badge}", unsafe_allow_html=True)
                st.markdown(f"**Recommendation:** {recommendation}")
                st.markdown(
                    f"**Category:** {SAFETY_CATEGORIES.get(cat_key, {}).get('description', '')}"
                )
            with col_detail:
                regions_aff = cat_data.get("regions_affected", [])
                if regions_aff:
                    st.markdown("**Affected Regions:**")
                    for r in regions_aff[:5]:
                        st.markdown(f"- {r}")
else:
    st.info("No safety scores available for recommendations.")

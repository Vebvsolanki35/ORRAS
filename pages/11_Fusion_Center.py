"""
11_Fusion_Center.py — ORRAS v3.0 Intelligence Fusion Center

Fusion matrix heatmap, compound events, dual-track bar chart,
source corroboration, signal flow pie, fusion confidence bars,
AI SITREP, real-time alert feed with acknowledge.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from collections import Counter

st.set_page_config(
    page_title="Fusion Center",
    page_icon="⚡",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
try:
    from mock_data_generator import generate_all_mock_signals
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from threat_engine import ThreatEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from anomaly_engine import AnomalyEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from correlation_engine import CorrelationEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from escalation_tracker import EscalationTracker
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from ai_assistant import generate_global_sitrep
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from ui_components import render_severity_badge, render_metric_card
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from utils import classify_severity
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

_CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#111827",
    font_color="#e5e7eb",
    margin=dict(l=40, r=20, t=50, b=40),
)

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_fusion_data() -> dict:
    try:
        raw = generate_all_mock_signals()
        signals = ThreatEngine().score_all(raw)
        correlated = CorrelationEngine().correlate_all(signals)
        anomalies = AnomalyEngine().detect_anomalies(signals)
        tracker = EscalationTracker()
        esc_result = tracker.run(signals)
        escalations = esc_result.get("escalation_alerts", [])
        return {
            "signals": signals,
            "correlated": correlated,
            "anomalies": anomalies,
            "escalations": escalations,
        }
    except Exception as e:
        st.warning(f"⚠️ {e}")
        return {"signals": [], "correlated": [], "anomalies": [], "escalations": []}


# ---------------------------------------------------------------------------
# Helper: compound events detection
# ---------------------------------------------------------------------------

_COMPOUND_PATTERNS = {
    "Conflict + Cyber": {"cyber", "internet", "network", "shutdown"},
    "Disaster + Humanitarian": {"flood", "earthquake", "famine", "refugee"},
    "Military + Nuclear": {"nuclear", "missile", "launch", "deployment"},
    "Disease + Conflict": {"outbreak", "disease", "epidemic", "military", "conflict"},
}


def _detect_compound_events(signals: list) -> list[dict]:
    events = []
    for event_name, kws in _COMPOUND_PATTERNS.items():
        matched_regions: dict[str, list] = {}
        for s in signals:
            text = ((s.get("title") or "") + " " + (s.get("description") or "")).lower()
            if any(k in text for k in kws):
                loc = s.get("location", "Unknown")
                matched_regions.setdefault(loc, []).append(s)
        for region, sigs in matched_regions.items():
            if len(sigs) >= 2:
                events.append({
                    "event": event_name,
                    "region": region,
                    "signal_count": len(sigs),
                    "severity": classify_severity(max(float(s.get("raw_score") or 0) for s in sigs)),
                })
    return events


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "acknowledged_alerts" not in st.session_state:
    st.session_state.acknowledged_alerts = set()

# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown("# ⚡ Intelligence Fusion Center")
st.divider()

with st.spinner("Fusing intelligence streams…"):
    data = load_fusion_data()

signals = data["signals"]
correlated = data["correlated"]
anomalies = data["anomalies"]
escalations = data["escalations"]

# ---------------------------------------------------------------------------
# 1. Fusion Matrix Heatmap
# ---------------------------------------------------------------------------

st.markdown("### 🔥 Signal Fusion Matrix (Regions × Signal Types)")

signal_types = sorted(set(s.get("type", "unknown") for s in signals))

# Top 15 regions by signal count
region_counts = Counter(s.get("location", "Unknown") for s in signals)
top_regions = [r for r, _ in region_counts.most_common(15)]

matrix_data = []
for region in top_regions:
    row = []
    for stype in signal_types:
        count = sum(1 for s in signals
                    if s.get("location") == region and s.get("type") == stype)
        row.append(count)
    matrix_data.append(row)

fig_heat = go.Figure(go.Heatmap(
    z=matrix_data,
    x=signal_types,
    y=top_regions,
    colorscale="YlOrRd",
    colorbar=dict(title="Signal Count"),
    hovertemplate="Region: %{y}<br>Type: %{x}<br>Count: %{z}<extra></extra>",
))
fig_heat.update_layout(**_CHART_LAYOUT, height=420, title="Signal Count by Region and Type")
st.plotly_chart(fig_heat, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Compound Event Cards
# ---------------------------------------------------------------------------

st.markdown("### 💥 Compound Events Detected")
compound_events = _detect_compound_events(signals)

if compound_events:
    cols = st.columns(min(3, len(compound_events)))
    for i, evt in enumerate(compound_events[:9]):
        with cols[i % 3]:
            sev_color = {"CRITICAL": "#ef4444", "HIGH": "#f97316",
                         "MEDIUM": "#eab308", "LOW": "#22c55e"}.get(evt["severity"], "#6b7280")
            st.markdown(f"""
<div style="background:#111827;border-left:3px solid {sev_color};padding:10px;border-radius:6px;margin-bottom:8px">
<b style="color:{sev_color}">{evt['event']}</b><br>
<span style="color:#9ca3af">📍 {evt['region']}</span><br>
<span style="color:#6b7280;font-size:0.85em">{evt['signal_count']} corroborating signals</span>
</div>
""", unsafe_allow_html=True)
else:
    st.info("No compound events detected in current signal window.")

st.divider()

# ---------------------------------------------------------------------------
# 3. Dual-track regional comparison chart
# ---------------------------------------------------------------------------

st.markdown("### 📊 Dual-Track Regional Score Comparison")

# Build per-region conflict vs disaster proxy scores
region_conflict: dict[str, float] = {}
region_disaster: dict[str, float] = {}

_DISASTER_KWS = {"flood", "earthquake", "fire", "disease", "outbreak", "hurricane", "cyclone"}
_CONFLICT_KWS = {"war", "military", "missile", "troops", "strike", "invasion", "battle", "bomb"}

for s in signals:
    loc = s.get("location", "Unknown")
    score = float(s.get("raw_score") or 0)
    text = ((s.get("title") or "") + " " + (s.get("description") or "")).lower()
    kws = set(s.get("keywords_matched") or [])
    if kws & _DISASTER_KWS or any(k in text for k in _DISASTER_KWS):
        region_disaster[loc] = max(region_disaster.get(loc, 0), score)
    else:
        region_conflict[loc] = max(region_conflict.get(loc, 0), score)

all_regions_dual = set(list(region_conflict.keys()) + list(region_disaster.keys()))
top10 = sorted(all_regions_dual, key=lambda r: region_conflict.get(r, 0) + region_disaster.get(r, 0), reverse=True)[:10]

fig_bar = go.Figure()
fig_bar.add_trace(go.Bar(
    name="Conflict Score",
    x=top10,
    y=[region_conflict.get(r, 0) for r in top10],
    marker_color="#ef4444",
))
fig_bar.add_trace(go.Bar(
    name="Disaster Score",
    x=top10,
    y=[region_disaster.get(r, 0) for r in top10],
    marker_color="#3b82f6",
))
fig_bar.update_layout(**_CHART_LAYOUT, barmode="group", height=380,
                      title="Conflict vs Disaster Score — Top 10 Regions",
                      xaxis_tickangle=-30)
st.plotly_chart(fig_bar, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 4. Source Corroboration Analysis
# ---------------------------------------------------------------------------

st.markdown("### 🤝 Source Corroboration Analysis")

source_regions: dict[str, set] = {}
for s in signals:
    src = s.get("source", "Unknown")
    loc = s.get("location", "Unknown")
    source_regions.setdefault(src, set()).add(loc)

sources = list(source_regions.keys())
corroboration_rows = []
for i, s1 in enumerate(sources):
    for s2 in sources[i+1:]:
        overlap = source_regions[s1] & source_regions[s2]
        if overlap:
            corroboration_rows.append({
                "Source 1": s1,
                "Source 2": s2,
                "Shared Regions": len(overlap),
                "Regions": ", ".join(sorted(overlap)[:5]),
            })

if corroboration_rows:
    df_corr = pd.DataFrame(corroboration_rows).sort_values("Shared Regions", ascending=False)
    st.dataframe(df_corr, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 5. Signal Flow Pie
# ---------------------------------------------------------------------------

col_pie, col_bar = st.columns(2)

with col_pie:
    st.markdown("### 📡 Signal Flow by Source")
    src_counts = Counter(s.get("source", "Unknown") for s in signals)
    fig_pie = go.Figure(go.Pie(
        labels=list(src_counts.keys()),
        values=list(src_counts.values()),
        hole=0.4,
        textinfo="label+percent",
    ))
    fig_pie.update_layout(**_CHART_LAYOUT, height=320)
    st.plotly_chart(fig_pie, use_container_width=True)

# ---------------------------------------------------------------------------
# 6. Fusion Confidence by Region
# ---------------------------------------------------------------------------

with col_bar:
    st.markdown("### 🎯 Fusion Confidence by Region")
    # Confidence ~ number of unique sources reporting on region / total sources
    total_sources = len(source_regions)
    region_source_count: dict[str, int] = {}
    for src, regions_set in source_regions.items():
        for r in regions_set:
            region_source_count[r] = region_source_count.get(r, 0) + 1

    top_conf = sorted(region_source_count.items(), key=lambda x: x[1], reverse=True)[:12]
    conf_vals = [round(count / max(1, total_sources) * 100, 1) for _, count in top_conf]
    conf_regions = [r for r, _ in top_conf]

    fig_conf = go.Figure(go.Bar(
        x=conf_vals,
        y=conf_regions,
        orientation="h",
        marker=dict(
            color=conf_vals,
            colorscale="RdYlGn",
            showscale=False,
        ),
    ))
    fig_conf.update_layout(**_CHART_LAYOUT, height=320,
                           xaxis_title="Confidence (%)", yaxis_title="")
    st.plotly_chart(fig_conf, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 7. AI SITREP Section
# ---------------------------------------------------------------------------

st.markdown("### 🤖 AI-Generated SITREP")

if "fusion_sitrep" not in st.session_state:
    st.session_state.fusion_sitrep = None

if st.button("🔄 Generate / Regenerate SITREP", use_container_width=True):
    with st.spinner("Generating SITREP…"):
        try:
            st.session_state.fusion_sitrep = generate_global_sitrep(signals, anomalies)
        except Exception as e:
            st.session_state.fusion_sitrep = f"SITREP generation error: {e}"

if st.session_state.fusion_sitrep:
    st.markdown(f"""
<div style="background:#111827;border:1px solid #374151;border-radius:8px;padding:16px;
     font-family:monospace;font-size:0.85em;color:#e5e7eb;white-space:pre-wrap">
{st.session_state.fusion_sitrep}
</div>
""", unsafe_allow_html=True)
else:
    st.info("Click 'Generate SITREP' to produce an AI-powered intelligence summary.")

st.divider()

# ---------------------------------------------------------------------------
# 8. Real-Time Alert Feed
# ---------------------------------------------------------------------------

st.markdown("### 🚨 Unified Real-Time Alert Feed")

all_alerts = []
for esc in escalations:
    all_alerts.append({
        "id": f"ESC-{esc.get('region','')}",
        "type": "Escalation",
        "region": esc.get("region", "Unknown"),
        "severity": esc.get("max_severity", "MEDIUM"),
        "message": esc.get("recommendation", "Escalation detected"),
        "timestamp": esc.get("timestamp", "")[:19],
    })
for anom in anomalies:
    region = anom.get("region") or anom.get("location") or "Unknown"
    all_alerts.append({
        "id": f"ANOM-{region}",
        "type": "Anomaly",
        "region": region,
        "severity": "HIGH",
        "message": f"Signal spike detected in {region}",
        "timestamp": "",
    })

# Sort newest first (use reverse index as proxy)
all_alerts = list(reversed(all_alerts))

if not all_alerts:
    st.info("No active alerts in the current feed.")

for i, alert in enumerate(all_alerts[:20]):
    alert_id = alert["id"]
    is_acked = alert_id in st.session_state.acknowledged_alerts

    sev_color = {"CRITICAL": "#ef4444", "HIGH": "#f97316",
                 "MEDIUM": "#eab308", "LOW": "#22c55e"}.get(alert["severity"], "#6b7280")
    acked_text = "✅ Acknowledged" if is_acked else ""

    col_alert, col_btn = st.columns([5, 1])
    with col_alert:
        st.markdown(f"""
<div style="background:#111827;border-left:3px solid {sev_color};padding:8px 12px;
     border-radius:4px;margin-bottom:4px;opacity:{'0.5' if is_acked else '1'}">
<span style="color:{sev_color};font-weight:bold">[{alert['severity']}] {alert['type']}</span>
<span style="color:#9ca3af"> — {alert['region']}</span>
<span style="color:#6b7280;font-size:0.85em"> {alert['timestamp']}</span><br>
<span style="color:#d1d5db;font-size:0.9em">{alert['message']}</span>
{f'<span style="color:#22c55e"> {acked_text}</span>' if is_acked else ''}
</div>
""", unsafe_allow_html=True)
    with col_btn:
        if not is_acked:
            if st.button("✓ Ack", key=f"ack_{i}_{alert_id}"):
                st.session_state.acknowledged_alerts.add(alert_id)
                st.rerun()

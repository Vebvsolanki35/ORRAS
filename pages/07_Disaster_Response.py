"""
07_Disaster_Response.py — ORRAS v3.0 Disaster Response Intelligence Center

Dual-track disaster monitoring: globe map, type breakdown, hotspots,
disease outbreaks, earthquake feed, resource deployment, evacuation panel.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
from datetime import datetime, timedelta, timezone
import random

st.set_page_config(
    page_title="Disaster Response",
    page_icon="🌋",
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
    from ui_components import render_metric_card, render_severity_badge, render_safety_score_card
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
# Disaster classification helpers
# ---------------------------------------------------------------------------

_DISASTER_KEYWORDS = {
    "earthquake": ["earthquake", "seismic", "tremor", "aftershock", "usgs", "magnitude"],
    "flood": ["flood", "flooding", "inundation", "cyclone", "hurricane", "typhoon", "storm surge"],
    "fire": ["wildfire", "fire", "blaze", "arson", "firestorm", "burn"],
    "weather": ["tornado", "drought", "heatwave", "blizzard", "snowstorm", "severe weather", "climate"],
    "disease": ["outbreak", "epidemic", "disease", "cholera", "ebola", "pandemic", "virus", "who"],
    "humanitarian": ["refugee", "famine", "starvation", "displacement", "humanitarian crisis", "aid"],
}

_DISASTER_COLORS = {
    "earthquake": "#9333ea",   # purple
    "flood": "#3b82f6",        # blue
    "fire": "#ef4444",         # red
    "weather": "#f97316",      # orange
    "disease": "#ec4899",      # pink
    "humanitarian": "#14b8a6", # teal
}


def _classify_disaster(signal: dict) -> str:
    text = ((signal.get("title") or "") + " " + (signal.get("description") or "")).lower()
    for dtype, kws in _DISASTER_KEYWORDS.items():
        if any(k in text for k in kws):
            return dtype
    return "humanitarian"


def _disaster_score(signal: dict) -> float:
    """Derive a disaster score based on raw_score and keyword density."""
    base = float(signal.get("raw_score") or 0) * 3.0
    text = ((signal.get("title") or "") + " " + (signal.get("description") or "")).lower()
    bonus = sum(2.0 for kws in _DISASTER_KEYWORDS.values() for k in kws if k in text)
    return min(100.0, base + bonus)


@st.cache_data(ttl=60)
def load_disaster_signals() -> list:
    try:
        signals = ThreatEngine().score_all(generate_all_mock_signals())
        for s in signals:
            s["disaster_type"] = _classify_disaster(s)
            s["disaster_score"] = round(_disaster_score(s), 1)
        return sorted(signals, key=lambda x: x["disaster_score"], reverse=True)
    except Exception as e:
        st.warning(f"⚠️ {e}")
        return []


# ---------------------------------------------------------------------------
# Mock supplementary feeds
# ---------------------------------------------------------------------------

def _mock_disease_outbreaks() -> list[dict]:
    random.seed(7)
    outbreaks = [
        {"Disease": "Cholera", "Region": "South Sudan", "Cases": 1204, "Deaths": 34, "Status": "Active"},
        {"Disease": "Ebola", "Region": "DR Congo", "Cases": 89, "Deaths": 12, "Status": "Contained"},
        {"Disease": "Mpox", "Region": "Nigeria", "Cases": 450, "Deaths": 5, "Status": "Monitoring"},
        {"Disease": "Dengue", "Region": "Myanmar", "Cases": 3200, "Deaths": 28, "Status": "Active"},
        {"Disease": "Typhoid", "Region": "Haiti", "Cases": 670, "Deaths": 9, "Status": "Active"},
    ]
    return outbreaks


def _mock_earthquake_feed() -> pd.DataFrame:
    random.seed(11)
    today = datetime.now(timezone.utc)
    rows = []
    for i in range(7):
        day = (today - timedelta(days=6 - i)).strftime("%b %d")
        count = random.randint(1, 8)
        for _ in range(count):
            rows.append({"Day": day, "Magnitude": round(random.uniform(3.5, 7.2), 1)})
    return pd.DataFrame(rows)


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown("# 🌋 Disaster Response Intelligence Center")
st.divider()

with st.spinner("Loading disaster intelligence…"):
    signals = load_disaster_signals()

# ---------------------------------------------------------------------------
# 1. Global disaster index metric cards
# ---------------------------------------------------------------------------

sev_counts = {"MINOR": 0, "MODERATE": 0, "SEVERE": 0, "CATASTROPHIC": 0}
for s in signals:
    ds = s.get("disaster_score", 0)
    if ds >= 75:
        sev_counts["CATASTROPHIC"] += 1
    elif ds >= 50:
        sev_counts["SEVERE"] += 1
    elif ds >= 25:
        sev_counts["MODERATE"] += 1
    else:
        sev_counts["MINOR"] += 1

c1, c2, c3, c4 = st.columns(4)
c1.markdown(render_metric_card("MINOR", str(sev_counts["MINOR"]), "Low-impact events", "#22c55e"), unsafe_allow_html=True)
c2.markdown(render_metric_card("MODERATE", str(sev_counts["MODERATE"]), "Moderate-impact events", "#eab308"), unsafe_allow_html=True)
c3.markdown(render_metric_card("SEVERE", str(sev_counts["SEVERE"]), "Severe disaster events", "#f97316"), unsafe_allow_html=True)
c4.markdown(render_metric_card("CATASTROPHIC", str(sev_counts["CATASTROPHIC"]), "Catastrophic events", "#ef4444"), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Disaster Globe
# ---------------------------------------------------------------------------

st.markdown("### 🌍 Global Disaster Signal Map")

fig_globe = go.Figure()
for dtype, color in _DISASTER_COLORS.items():
    subset = [s for s in signals if s.get("disaster_type") == dtype]
    if not subset:
        continue
    fig_globe.add_trace(go.Scattergeo(
        lat=[s.get("latitude", 0) for s in subset],
        lon=[s.get("longitude", 0) for s in subset],
        mode="markers",
        marker=dict(
            size=[max(6, min(20, s["disaster_score"] / 5)) for s in subset],
            color=color,
            opacity=0.8,
            line=dict(color="white", width=0.5),
        ),
        text=[f"{s['location']}<br>{dtype.title()}<br>Score: {s['disaster_score']}" for s in subset],
        hoverinfo="text",
        name=dtype.title(),
    ))

fig_globe.update_layout(
    geo=dict(
        showland=True, landcolor="#1f2937",
        showocean=True, oceancolor="#0a0e1a",
        showcoastlines=True, coastlinecolor="#374151",
        showcountries=True, countrycolor="#374151",
        bgcolor="#0a0e1a",
        projection_type="orthographic",
    ),
    paper_bgcolor="#0a0e1a",
    font_color="#e5e7eb",
    height=500,
    legend=dict(bgcolor="#111827", bordercolor="#374151", borderwidth=1),
)
st.plotly_chart(fig_globe, use_container_width=True)

# ---------------------------------------------------------------------------
# 3. Type breakdown pie + top hotspots
# ---------------------------------------------------------------------------

col_left, col_right = st.columns([1, 1])

with col_left:
    st.markdown("### 📊 Disaster Type Breakdown")
    type_counts = {}
    for s in signals:
        dt = s.get("disaster_type", "humanitarian")
        type_counts[dt] = type_counts.get(dt, 0) + 1

    fig_pie = go.Figure(go.Pie(
        labels=[k.title() for k in type_counts.keys()],
        values=list(type_counts.values()),
        marker=dict(colors=[_DISASTER_COLORS.get(k, "#6b7280") for k in type_counts.keys()]),
        hole=0.4,
        textinfo="label+percent",
    ))
    fig_pie.update_layout(**_CHART_LAYOUT, height=350, showlegend=True)
    st.plotly_chart(fig_pie, use_container_width=True)

with col_right:
    st.markdown("### 🔥 Top 5 Disaster Hotspots")
    region_max: dict[str, float] = {}
    region_dtype: dict[str, str] = {}
    for s in signals:
        loc = s.get("location", "Unknown")
        ds = s.get("disaster_score", 0)
        if ds > region_max.get(loc, 0):
            region_max[loc] = ds
            region_dtype[loc] = s.get("disaster_type", "humanitarian")

    top5 = sorted(region_max.items(), key=lambda x: x[1], reverse=True)[:5]
    for region, score in top5:
        dtype = region_dtype.get(region, "humanitarian")
        color = _DISASTER_COLORS.get(dtype, "#6b7280")
        st.markdown(render_safety_score_card(
            region, score, dtype.title(),
            [f"Disaster score: {score:.0f}", f"Type: {dtype.title()}"]
        ), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# 4. Disaster signal feed table
# ---------------------------------------------------------------------------

st.markdown("### 📋 Disaster Signal Feed")
if signals:
    df = pd.DataFrame([{
        "Region": s.get("location", ""),
        "Type": s.get("disaster_type", "").title(),
        "Disaster Score": s.get("disaster_score", 0),
        "Severity": s.get("severity", ""),
        "Source": s.get("source", ""),
        "Title": (s.get("title") or "")[:80],
        "Timestamp": (s.get("timestamp") or "")[:19],
    } for s in signals[:30]])

    st.dataframe(df.astype(str), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 5. WHO Disease Outbreaks
# ---------------------------------------------------------------------------

st.markdown("### 🦠 WHO Disease Outbreak Monitor")
outbreaks = _mock_disease_outbreaks()
df_disease = pd.DataFrame(outbreaks)
st.dataframe(df_disease.astype(str), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 6. USGS Earthquake Feed
# ---------------------------------------------------------------------------

st.markdown("### 🌐 USGS Earthquake Activity (Last 7 Days)")
eq_df = _mock_earthquake_feed()
if not eq_df.empty:
    fig_eq = go.Figure()
    mag_bins = {"≥7.0": (7.0, 10), "5.0–6.9": (5.0, 7.0), "3.5–4.9": (3.5, 5.0)}
    colors_eq = {"≥7.0": "#ef4444", "5.0–6.9": "#f97316", "3.5–4.9": "#eab308"}
    days_order = eq_df["Day"].unique().tolist()
    for label, (lo, hi) in mag_bins.items():
        counts = []
        for day in days_order:
            d = eq_df[(eq_df["Day"] == day) & (eq_df["Magnitude"] >= lo) & (eq_df["Magnitude"] < hi)]
            counts.append(len(d))
        fig_eq.add_trace(go.Bar(x=days_order, y=counts, name=label, marker_color=colors_eq[label]))

    fig_eq.update_layout(**_CHART_LAYOUT, barmode="stack", height=300,
                         title="Earthquakes by Magnitude (Last 7 Days)")
    st.plotly_chart(fig_eq, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 7. Resource deployment for disaster regions
# ---------------------------------------------------------------------------

st.markdown("### 📦 Resource Deployment for Disaster Regions")

_RESOURCES = ["Medical Teams", "Emergency Food", "Water Purification", "Search & Rescue", "Field Hospitals"]
deployed_regions = [r for r, sc in top5 if sc >= 40]
if deployed_regions:
    deploy_rows = []
    random.seed(42)
    for region in deployed_regions:
        res = random.choice(_RESOURCES)
        qty = random.randint(2, 15)
        deploy_rows.append({"Region": region, "Resource": res, "Units": qty, "Status": "Deployed"})
    st.dataframe(pd.DataFrame(deploy_rows).astype(str), use_container_width=True)
else:
    st.info("No major disaster regions requiring deployment at this time.")

st.divider()

# ---------------------------------------------------------------------------
# 8. Evacuation recommendations
# ---------------------------------------------------------------------------

st.markdown("### 🚨 Evacuation Recommendations")
evac_regions = [(r, sc) for r, sc in top5 if sc >= 50]
if evac_regions:
    for region, score in evac_regions:
        sev = "CATASTROPHIC" if score >= 75 else "SEVERE"
        st.markdown(render_severity_badge(sev), unsafe_allow_html=True)
        st.markdown(f"**{region}** — Disaster Score: `{score:.0f}`")
        st.markdown(
            f"⚠️ **Recommendation:** Immediate evacuation of affected zones in {region}. "
            f"Deploy emergency response teams. Coordinate with local authorities."
        )
        st.markdown("---")
else:
    st.success("✅ No evacuation-level disaster events detected at this time.")

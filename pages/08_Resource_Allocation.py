"""
08_Resource_Allocation.py — ORRAS v3.0 Resource Allocation Command Center

Global inventory, regional needs, deployment orders, coverage map,
shortfall alerts, simulation, manual override, historical deployments.
"""

import streamlit as st
import plotly.graph_objects as go
import plotly.express as px
import pandas as pd
import random
import json
import os
from datetime import datetime, timezone

st.set_page_config(
    page_title="Resource Allocation",
    page_icon="📦",
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
    from action_engine import ActionEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from ui_components import render_metric_card, render_alert_banner, render_severity_badge
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from utils import classify_severity, load_json, save_json, now_iso
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

_CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#111827",
    font_color="#e5e7eb",
    margin=dict(l=40, r=20, t=50, b=40),
)

_RESOURCE_TYPES = [
    "Medical Teams", "Emergency Food", "Water Purification",
    "Search & Rescue", "Field Hospitals", "Security Personnel",
    "Communications Equipment", "Logistics Vehicles",
]

_SCENARIOS = {
    "Baseline": {"multiplier": 1.0, "description": "Current deployment posture"},
    "Major Conflict": {"multiplier": 2.5, "description": "Full conflict escalation, surge demand"},
    "Mass Casualty Event": {"multiplier": 3.0, "description": "Large-scale medical emergency"},
    "Natural Disaster": {"multiplier": 2.0, "description": "Earthquake/flood response"},
    "Regional Pandemic": {"multiplier": 1.8, "description": "Outbreak containment mode"},
}

_OVERRIDES_FILE = "data/resource_overrides.json"

# ---------------------------------------------------------------------------
# Data helpers
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_signals() -> list:
    try:
        return ThreatEngine().score_all(generate_all_mock_signals())
    except Exception as e:
        st.warning(f"⚠️ {e}")
        return []


def _build_inventory(seed: int = 1) -> pd.DataFrame:
    random.seed(seed)
    rows = []
    for res in _RESOURCE_TYPES:
        total = random.randint(50, 200)
        deployed = random.randint(10, total - 5)
        available = total - deployed
        pct = round(available / total * 100, 1)
        rows.append({
            "Resource": res,
            "Total": total,
            "Deployed": deployed,
            "Available": available,
            "% Available": pct,
        })
    return pd.DataFrame(rows)


def _build_region_needs(signals: list) -> pd.DataFrame:
    region_score: dict[str, float] = {}
    for s in signals:
        loc = s.get("location", "Unknown")
        sc = float(s.get("raw_score") or 0)
        region_score[loc] = max(region_score.get(loc, 0), sc)

    rows = []
    random.seed(2)
    for region, score in sorted(region_score.items(), key=lambda x: x[1], reverse=True)[:15]:
        demand = min(100, int(score * 3.5))
        resource = random.choice(_RESOURCE_TYPES)
        rows.append({
            "Region": region,
            "Threat Score": round(score, 1),
            "Demand Level": demand,
            "Priority Resource": resource,
            "Severity": classify_severity(score),
        })
    return pd.DataFrame(rows)


def _build_deployment_orders(region_needs: pd.DataFrame) -> pd.DataFrame:
    random.seed(3)
    rows = []
    priorities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    statuses = ["In Transit", "Deployed", "Pending", "Scheduled"]
    for i, row in region_needs.head(10).iterrows():
        eta_days = random.randint(1, 5)
        rows.append({
            "Order ID": f"ORD-{1000 + i}",
            "Region": row["Region"],
            "Resource": row["Priority Resource"],
            "Qty": random.randint(2, 20),
            "Priority": random.choice(priorities),
            "ETA (days)": eta_days,
            "Status": random.choice(statuses),
        })
    return pd.DataFrame(rows)


def _build_coverage(region_needs: pd.DataFrame) -> pd.DataFrame:
    random.seed(4)
    cov = region_needs.copy()
    cov["Coverage %"] = [random.randint(20, 95) for _ in range(len(cov))]
    return cov


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown("# 📦 Resource Allocation Command Center")
st.divider()

with st.spinner("Loading resource data…"):
    signals = load_signals()
    inventory_df = _build_inventory()
    region_needs_df = _build_region_needs(signals)
    deployment_df = _build_deployment_orders(region_needs_df)
    coverage_df = _build_coverage(region_needs_df)

# ---------------------------------------------------------------------------
# 1. Global Inventory Table
# ---------------------------------------------------------------------------

st.markdown("### 🗃️ Global Resource Inventory")


def _color_pct(val: float) -> str:
    if val > 70:
        return "color: #22c55e"
    elif val > 40:
        return "color: #eab308"
    else:
        return "color: #ef4444"


def _style_inventory(df: pd.DataFrame) -> pd.io.formats.style.Styler:
    return df.style.applymap(_color_pct, subset=["% Available"])


st.dataframe(_style_inventory(inventory_df), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Resource needs by region
# ---------------------------------------------------------------------------

st.markdown("### 🎯 Resource Needs by Region")

_SEV_COLORS = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#22c55e"}


def _color_sev(val: str) -> str:
    return f"color: {_SEV_COLORS.get(val, '#e5e7eb')}"


styled_needs = region_needs_df.style.applymap(_color_sev, subset=["Severity"])
st.dataframe(styled_needs, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 3. Deployment Orders
# ---------------------------------------------------------------------------

st.markdown("### 📋 Active Deployment Orders")

_PRIORITY_COLORS = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#22c55e"}


def _color_priority(val: str) -> str:
    return f"color: {_PRIORITY_COLORS.get(val, '#e5e7eb')}"


styled_orders = deployment_df.style.applymap(_color_priority, subset=["Priority"])
st.dataframe(styled_orders, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 4. Coverage Map
# ---------------------------------------------------------------------------

st.markdown("### 🗺️ Regional Coverage Map")

fig_cov = px.choropleth(
    coverage_df,
    locations="Region",
    locationmode="country names",
    color="Coverage %",
    color_continuous_scale=["#ef4444", "#eab308", "#22c55e"],
    range_color=[0, 100],
    title="Resource Coverage by Region (%)",
)
fig_cov.update_layout(
    **_CHART_LAYOUT,
    height=420,
    coloraxis_colorbar=dict(title="Coverage %"),
)
st.plotly_chart(fig_cov, use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 5. Shortfall Alerts
# ---------------------------------------------------------------------------

st.markdown("### 🚨 Shortfall Alerts")
shortfall_regions = coverage_df[coverage_df["Coverage %"] < 50]["Region"].tolist()
if shortfall_regions:
    alerts = [f"⚠️ {r} — coverage below 50%" for r in shortfall_regions]
    st.markdown(render_alert_banner(alerts, "HIGH"), unsafe_allow_html=True)
else:
    st.success("✅ All regions above 50% coverage threshold.")

st.divider()

# ---------------------------------------------------------------------------
# 6. Resource Simulation
# ---------------------------------------------------------------------------

st.markdown("### 🔬 Resource Scenario Simulation")
col_s1, col_s2 = st.columns([2, 1])
with col_s1:
    scenario_name = st.selectbox("Select Scenario", list(_SCENARIOS.keys()))
with col_s2:
    st.markdown(f"**{_SCENARIOS[scenario_name]['description']}**")

if st.button("▶️ Run Simulation", use_container_width=True):
    mult = _SCENARIOS[scenario_name]["multiplier"]
    sim_df = region_needs_df.copy()
    sim_df["Simulated Demand"] = (sim_df["Demand Level"] * mult).clip(0, 100).astype(int)
    sim_df["Gap"] = (sim_df["Simulated Demand"] - sim_df["Demand Level"]).astype(int)

    st.markdown(f"**Scenario: {scenario_name}** — Demand multiplier: `{mult}x`")
    st.dataframe(sim_df[["Region", "Demand Level", "Simulated Demand", "Gap", "Priority Resource"]],
                 use_container_width=True)

    total_gap = sim_df["Gap"].sum()
    st.metric("Total Resource Gap (simulated)", total_gap, delta=f"+{total_gap} units needed")

st.divider()

# ---------------------------------------------------------------------------
# 7. Manual Override Form
# ---------------------------------------------------------------------------

st.markdown("### ✍️ Manual Resource Override")
with st.form("override_form"):
    ov_region = st.text_input("Region")
    ov_resource = st.selectbox("Resource Type", _RESOURCE_TYPES)
    ov_qty = st.number_input("Quantity", min_value=1, max_value=500, value=10)
    ov_reason = st.text_area("Reason / Justification")
    submitted = st.form_submit_button("📤 Submit Override")

if submitted and ov_region:
    override_entry = {
        "timestamp": now_iso(),
        "region": ov_region,
        "resource": ov_resource,
        "quantity": int(ov_qty),
        "reason": ov_reason,
    }
    try:
        existing = load_json(_OVERRIDES_FILE) if os.path.exists(_OVERRIDES_FILE) else []
        existing.append(override_entry)
        save_json(_OVERRIDES_FILE, existing)
        st.success(f"✅ Override logged: {int(ov_qty)} × {ov_resource} → {ov_region}")
    except Exception as e:
        st.warning(f"⚠️ Could not save override: {e}")
        st.json(override_entry)

st.divider()

# ---------------------------------------------------------------------------
# 8. Historical Deployments
# ---------------------------------------------------------------------------

st.markdown("### 📜 Historical Deployment Log")
try:
    overrides = load_json(_OVERRIDES_FILE) if os.path.exists(_OVERRIDES_FILE) else []
    if overrides:
        st.dataframe(pd.DataFrame(overrides), use_container_width=True)
    else:
        st.info("No manual overrides logged yet.")
except Exception:
    st.info("No deployment history available.")

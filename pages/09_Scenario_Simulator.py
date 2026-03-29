"""
09_Scenario_Simulator.py — ORRAS v3.0 Crisis Scenario Simulator

5 preset scenario cards, region selector, before/after comparison,
hour-by-hour escalation chart, compound events, resource impact,
multi-scenario compare, worst-case analysis, JSON export, custom builder.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
import random
from datetime import datetime, timezone

st.set_page_config(
    page_title="Scenario Simulator",
    page_icon="🎮",
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
    from ui_components import render_metric_card, render_severity_badge
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
# Preset scenarios
# ---------------------------------------------------------------------------

PRESET_SCENARIOS = {
    "Full-Scale Invasion": {
        "description": "Large-scale military incursion with rapid territorial gains.",
        "duration_hours": 72,
        "conflict_delta": 18.0,
        "disaster_delta": 4.0,
        "signal_surge": 3.5,
        "color": "#ef4444",
        "compound_events": ["Mass Casualty", "Infrastructure Collapse", "Refugee Exodus"],
    },
    "Cyber-Physical Attack": {
        "description": "Coordinated cyber attacks targeting critical infrastructure.",
        "duration_hours": 48,
        "conflict_delta": 8.0,
        "disaster_delta": 6.0,
        "signal_surge": 2.0,
        "color": "#3b82f6",
        "compound_events": ["Power Grid Failure", "Communications Blackout", "Financial System Disruption"],
    },
    "Major Natural Disaster": {
        "description": "Category-5 hurricane or 7.5+ magnitude earthquake.",
        "duration_hours": 96,
        "conflict_delta": 2.0,
        "disaster_delta": 22.0,
        "signal_surge": 2.8,
        "color": "#f97316",
        "compound_events": ["Mass Displacement", "Supply Chain Breakdown", "Disease Outbreak"],
    },
    "Regional Pandemic Surge": {
        "description": "Rapid spread of high-mortality infectious disease across region.",
        "duration_hours": 168,
        "conflict_delta": 1.5,
        "disaster_delta": 12.0,
        "signal_surge": 1.5,
        "color": "#ec4899",
        "compound_events": ["Healthcare System Overload", "Border Closures", "Civil Unrest"],
    },
    "Political Coup": {
        "description": "Government overthrow with violent suppression of opposition.",
        "duration_hours": 36,
        "conflict_delta": 14.0,
        "disaster_delta": 3.0,
        "signal_surge": 2.2,
        "color": "#9333ea",
        "compound_events": ["Internet Shutdown", "Mass Arrests", "Foreign Intervention Risk"],
    },
}

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_signals() -> list:
    try:
        return ThreatEngine().score_all(generate_all_mock_signals())
    except Exception as e:
        st.warning(f"⚠️ {e}")
        return []


def _region_baseline(signals: list, region: str) -> dict:
    region_sigs = [s for s in signals if s.get("location") == region]
    if not region_sigs:
        return {"conflict_score": 5.0, "disaster_score": 3.0, "combined": 8.0, "severity": "LOW", "signal_count": 0}
    scores = [float(s.get("raw_score") or 0) for s in region_sigs]
    max_sc = max(scores)
    avg_sc = sum(scores) / len(scores)
    conflict = round(min(30, max_sc), 1)
    disaster = round(min(30, avg_sc * 1.2), 1)
    combined = round(conflict + disaster, 1)
    return {
        "conflict_score": conflict,
        "disaster_score": disaster,
        "combined": combined,
        "severity": classify_severity(max_sc),
        "signal_count": len(region_sigs),
    }


def _run_scenario(baseline: dict, scenario: dict) -> dict:
    new_conflict = min(30, baseline["conflict_score"] + scenario["conflict_delta"])
    new_disaster = min(30, baseline["disaster_score"] + scenario["disaster_delta"])
    new_combined = round(new_conflict + new_disaster, 1)
    new_severity = classify_severity(new_combined / 2)
    return {
        "conflict_score": round(new_conflict, 1),
        "disaster_score": round(new_disaster, 1),
        "combined": new_combined,
        "severity": new_severity,
        "signal_count": int(baseline["signal_count"] * scenario["signal_surge"]),
    }


def _hour_by_hour(baseline: dict, scenario: dict) -> pd.DataFrame:
    hours = scenario["duration_hours"]
    random.seed(99)
    scores = []
    base = baseline["combined"]
    peak = base + scenario["conflict_delta"] + scenario["disaster_delta"]
    for h in range(hours + 1):
        t = h / hours
        # S-curve escalation
        progress = 1 / (1 + 2.718 ** (-10 * (t - 0.5)))
        noise = random.uniform(-0.5, 0.5)
        scores.append(round(base + (peak - base) * progress + noise, 2))
    return pd.DataFrame({"Hour": list(range(hours + 1)), "Combined Score": scores})


# ---------------------------------------------------------------------------
# Session state
# ---------------------------------------------------------------------------

if "sim_results" not in st.session_state:
    st.session_state.sim_results = {}

if "custom_result" not in st.session_state:
    st.session_state.custom_result = None

# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown("# 🎮 Crisis Scenario Simulator")
st.divider()

with st.spinner("Loading intelligence baseline…"):
    signals = load_signals()

regions = sorted(set(s.get("location", "Unknown") for s in signals if s.get("location")))

# ---------------------------------------------------------------------------
# 1. Preset Scenario Cards (2 columns + 1)
# ---------------------------------------------------------------------------

st.markdown("### 📋 Preset Crisis Scenarios")
cols = st.columns(3)
col_idx = 0
for sname, sdata in PRESET_SCENARIOS.items():
    with cols[col_idx % 3]:
        st.markdown(f"""
<div style="background:#111827;border:1px solid {sdata['color']};border-radius:8px;padding:12px;margin-bottom:8px">
<h4 style="color:{sdata['color']};margin:0">{sname}</h4>
<p style="color:#9ca3af;font-size:0.85em;margin:4px 0">{sdata['description']}</p>
<p style="color:#6b7280;font-size:0.8em">⏱ Duration: {sdata['duration_hours']}h</p>
</div>
""", unsafe_allow_html=True)
    col_idx += 1

st.divider()

# ---------------------------------------------------------------------------
# 2. Simulation Controls
# ---------------------------------------------------------------------------

st.markdown("### ▶️ Run Simulation")
col_reg, col_scen = st.columns(2)
with col_reg:
    selected_region = st.selectbox("Target Region", regions if regions else ["Unknown"])
with col_scen:
    selected_scenario = st.selectbox("Crisis Scenario", list(PRESET_SCENARIOS.keys()))

run_sim = st.button("🚀 Run Scenario", use_container_width=True, type="primary")

if run_sim:
    baseline = _region_baseline(signals, selected_region)
    scenario = PRESET_SCENARIOS[selected_scenario]
    result = _run_scenario(baseline, scenario)
    timeline_df = _hour_by_hour(baseline, scenario)

    st.session_state.sim_results[selected_scenario] = {
        "region": selected_region,
        "scenario": selected_scenario,
        "baseline": baseline,
        "result": result,
        "timeline": timeline_df.to_dict("records"),
        "scenario_data": scenario,
    }

    # Before / After
    st.markdown("### 📊 Before vs After")
    colB, colA = st.columns(2)
    with colB:
        st.markdown("#### 🔵 Before (Baseline)")
        st.metric("Conflict Score", baseline["conflict_score"])
        st.metric("Disaster Score", baseline["disaster_score"])
        st.metric("Combined Score", baseline["combined"])
        st.markdown(render_severity_badge(baseline["severity"]), unsafe_allow_html=True)
        st.metric("Signal Count", baseline["signal_count"])
    with colA:
        st.markdown("#### 🔴 After (Scenario)")
        delta_c = round(result["conflict_score"] - baseline["conflict_score"], 1)
        delta_d = round(result["disaster_score"] - baseline["disaster_score"], 1)
        delta_comb = round(result["combined"] - baseline["combined"], 1)
        st.metric("Conflict Score", result["conflict_score"], delta=f"+{delta_c}")
        st.metric("Disaster Score", result["disaster_score"], delta=f"+{delta_d}")
        st.metric("Combined Score", result["combined"], delta=f"+{delta_comb}")
        st.markdown(render_severity_badge(result["severity"]), unsafe_allow_html=True)
        st.metric("Signal Count", result["signal_count"], delta=f"+{result['signal_count'] - baseline['signal_count']}")

    # Hour-by-hour chart
    st.markdown("### ⏱️ Hour-by-Hour Escalation")
    fig_time = go.Figure()
    fig_time.add_trace(go.Scatter(
        x=timeline_df["Hour"],
        y=timeline_df["Combined Score"],
        mode="lines",
        line=dict(color=scenario["color"], width=2),
        fill="tozeroy",
        fillcolor=f"rgba({int(scenario['color'][1:3],16)},{int(scenario['color'][3:5],16)},{int(scenario['color'][5:7],16)},0.15)",
        name="Combined Score",
    ))
    fig_time.add_hline(y=baseline["combined"], line_dash="dash", line_color="#6b7280",
                       annotation_text="Baseline")
    fig_time.update_layout(**_CHART_LAYOUT, height=350,
                           title=f"{selected_scenario} — {selected_region}",
                           xaxis_title="Hour", yaxis_title="Score")
    st.plotly_chart(fig_time, use_container_width=True)

    # Compound events
    st.markdown("### 💥 Compound Events Detected")
    for evt in scenario["compound_events"]:
        st.markdown(f"🔴 **{evt}**")

    # Resource impact
    st.markdown("### 📦 Resource Impact Assessment")
    resource_rows = []
    _res = ["Medical Teams", "Emergency Food", "Water Purification", "Search & Rescue", "Field Hospitals"]
    for res in _res:
        base_need = random.randint(5, 20)
        surge = int(base_need * (1 + delta_comb / 20))
        resource_rows.append({"Resource": res, "Baseline Need": base_need, "Scenario Need": surge,
                               "Additional Required": surge - base_need})
    st.dataframe(pd.DataFrame(resource_rows), use_container_width=True)

    # JSON export
    st.markdown("### 💾 Export Results")
    export_data = {
        "region": selected_region,
        "scenario": selected_scenario,
        "baseline": baseline,
        "result": result,
        "compound_events": scenario["compound_events"],
    }
    st.download_button(
        "⬇️ Download Results as JSON",
        data=json.dumps(export_data, indent=2),
        file_name=f"scenario_{selected_region}_{selected_scenario.replace(' ', '_')}.json",
        mime="application/json",
    )

st.divider()

# ---------------------------------------------------------------------------
# 3. Compare Multiple Scenarios
# ---------------------------------------------------------------------------

st.markdown("### 🆚 Compare Multiple Scenarios")
compare_scenarios = st.multiselect("Select scenarios to compare", list(PRESET_SCENARIOS.keys()),
                                   default=list(PRESET_SCENARIOS.keys())[:3])
compare_region = st.selectbox("Region for comparison", regions if regions else ["Unknown"], key="compare_region")

if st.button("📊 Run Comparison", use_container_width=True):
    baseline = _region_baseline(signals, compare_region)
    comp_rows = []
    for sname in compare_scenarios:
        scenario = PRESET_SCENARIOS[sname]
        result = _run_scenario(baseline, scenario)
        comp_rows.append({
            "Scenario": sname,
            "Conflict Score": result["conflict_score"],
            "Disaster Score": result["disaster_score"],
            "Combined Score": result["combined"],
            "Severity": result["severity"],
            "Duration (h)": scenario["duration_hours"],
        })
    st.dataframe(pd.DataFrame(comp_rows), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 4. Worst-case analysis
# ---------------------------------------------------------------------------

st.markdown("### ☠️ Worst-Case Analysis")
wc_region = st.selectbox("Run worst-case for region", regions if regions else ["Unknown"], key="wc_region")

if st.button("⚠️ Run All 5 Scenarios (Worst-Case)", use_container_width=True):
    baseline = _region_baseline(signals, wc_region)
    wc_rows = []
    worst_combined = 0
    worst_name = ""
    for sname, scenario in PRESET_SCENARIOS.items():
        result = _run_scenario(baseline, scenario)
        wc_rows.append({
            "Scenario": sname,
            "Combined Score": result["combined"],
            "Severity": result["severity"],
            "Conflict Δ": f"+{scenario['conflict_delta']}",
            "Disaster Δ": f"+{scenario['disaster_delta']}",
        })
        if result["combined"] > worst_combined:
            worst_combined = result["combined"]
            worst_name = sname

    st.dataframe(pd.DataFrame(wc_rows), use_container_width=True)
    st.error(f"🔴 **Worst-case scenario for {wc_region}: {worst_name}** — Combined Score: `{worst_combined}`")

st.divider()

# ---------------------------------------------------------------------------
# 5. Custom Scenario Builder
# ---------------------------------------------------------------------------

st.markdown("### 🛠️ Custom Scenario Builder")
c1, c2, c3 = st.columns(3)
with c1:
    custom_signals = st.slider("Signal Count Surge (×)", 1.0, 5.0, 2.0, 0.5)
    custom_intensity = st.slider("Score Intensity (+)", 0.0, 25.0, 8.0, 0.5)
with c2:
    custom_duration = st.slider("Duration (hours)", 6, 168, 48, 6)
    custom_region = st.selectbox("Region", regions if regions else ["Unknown"], key="custom_region")
with c3:
    st.markdown("**Signal Types**")
    inc_conflict = st.checkbox("Conflict signals", value=True)
    inc_disaster = st.checkbox("Disaster signals", value=True)
    inc_cyber = st.checkbox("Cyber signals", value=False)
    inc_disease = st.checkbox("Disease signals", value=False)

if st.button("🔧 Run Custom Scenario", use_container_width=True):
    baseline = _region_baseline(signals, custom_region)
    type_mult = sum([inc_conflict, inc_disaster, inc_cyber, inc_disease]) * 0.3 + 0.4
    custom_scen = {
        "conflict_delta": custom_intensity * (0.6 if inc_conflict else 0.1),
        "disaster_delta": custom_intensity * (0.4 if inc_disaster else 0.1),
        "signal_surge": custom_signals,
        "duration_hours": custom_duration,
        "color": "#06b6d4",
        "compound_events": [],
    }
    result = _run_scenario(baseline, custom_scen)
    timeline_df = _hour_by_hour(baseline, custom_scen)

    st.markdown("#### Custom Scenario Results")
    colB2, colA2 = st.columns(2)
    with colB2:
        st.markdown("**Before**")
        st.metric("Combined Score", baseline["combined"])
        st.markdown(render_severity_badge(baseline["severity"]), unsafe_allow_html=True)
    with colA2:
        st.markdown("**After**")
        delta = round(result["combined"] - baseline["combined"], 1)
        st.metric("Combined Score", result["combined"], delta=f"+{delta}")
        st.markdown(render_severity_badge(result["severity"]), unsafe_allow_html=True)

    fig_custom = go.Figure()
    fig_custom.add_trace(go.Scatter(
        x=timeline_df["Hour"], y=timeline_df["Combined Score"],
        mode="lines", line=dict(color="#06b6d4", width=2), name="Score",
    ))
    fig_custom.update_layout(**_CHART_LAYOUT, height=300,
                              title=f"Custom Scenario — {custom_region}",
                              xaxis_title="Hour", yaxis_title="Score")
    st.plotly_chart(fig_custom, use_container_width=True)

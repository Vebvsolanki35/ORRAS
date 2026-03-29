"""
10_Explainability.py — ORRAS v3.0 Intelligence Explainability Center

Region explainer, signal-level explainer, anomaly explanations,
prediction reasoning, resource allocation reasoning, full audit trail.
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Explainability",
    page_icon="🔍",
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
    from prediction_engine import PredictionEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from escalation_tracker import EscalationTracker
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from ui_components import render_severity_badge
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from utils import classify_severity
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from config import KEYWORD_WEIGHTS, SOURCE_MULTIPLIERS
except ImportError:
    KEYWORD_WEIGHTS = {}
    SOURCE_MULTIPLIERS = {}

# ---------------------------------------------------------------------------
# Data
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_all_data() -> dict:
    try:
        signals = ThreatEngine().score_all(generate_all_mock_signals())
        anomalies = AnomalyEngine().detect_anomalies(signals)
        tracker = EscalationTracker()
        esc_result = tracker.run(signals)
        escalations = esc_result.get("escalation_alerts", [])
        try:
            pe = PredictionEngine()
            history = tracker.load_history()
            forecasts = pe.forecast_all_regions(history)
        except Exception:
            forecasts = {}
        return {"signals": signals, "anomalies": anomalies,
                "escalations": escalations, "forecasts": forecasts}
    except Exception as e:
        st.warning(f"⚠️ {e}")
        return {"signals": [], "anomalies": [], "escalations": [], "forecasts": {}}


# ---------------------------------------------------------------------------
# Explanation helpers
# ---------------------------------------------------------------------------

def _explain_region(signals: list, region: str) -> tuple[str, list[str]]:
    sigs = [s for s in signals if s.get("location") == region]
    if not sigs:
        return f"No signals found for {region}.", []
    scores = [float(s.get("raw_score") or 0) for s in sigs]
    max_sc = max(scores)
    avg_sc = sum(scores) / len(scores)
    severity = classify_severity(max_sc)
    sources = list(set(s.get("source", "Unknown") for s in sigs))
    all_kw: list[str] = []
    for s in sigs:
        all_kw.extend(s.get("keywords_matched") or [])
    kw_freq: dict[str, int] = {}
    for k in all_kw:
        kw_freq[k] = kw_freq.get(k, 0) + 1
    top_kw = sorted(kw_freq.items(), key=lambda x: x[1], reverse=True)[:5]

    explanation = (
        f"**{region}** was flagged with severity **{severity}** based on {len(sigs)} signals "
        f"from {len(sources)} source(s): {', '.join(sources)}. "
        f"The maximum threat score recorded was **{max_sc:.1f}** (average: {avg_sc:.1f}). "
        f"The primary threat indicators driving this assessment are high-weight keywords "
        f"detected in signal text content."
    )
    drivers = [
        f"Signal count: {len(sigs)} signals active in region",
        f"Peak score: {max_sc:.1f} → severity {severity}",
        f"Top keyword: '{top_kw[0][0]}' (matched {top_kw[0][1]}x)" if top_kw else "No keywords matched",
        f"Sources corroborating: {', '.join(sources[:3])}",
        f"Average score across all signals: {avg_sc:.1f}",
    ]
    return explanation, drivers


def _explain_signal(signal: dict) -> str:
    title = signal.get("title") or "Untitled"
    source = signal.get("source") or "Unknown"
    score = float(signal.get("raw_score") or 0)
    severity = signal.get("severity") or classify_severity(score)
    kws = signal.get("keywords_matched") or []
    src_weight = SOURCE_MULTIPLIERS.get(source, 1.0)
    kw_explain = ", ".join([f"'{k}' (weight: {KEYWORD_WEIGHTS.get(k, '?')})" for k in kws[:5]])

    return (
        f"**Signal:** {title}\n\n"
        f"**Source:** {source} — reliability multiplier: `{src_weight}×`\n\n"
        f"**Track classification:** Based on keyword content — "
        f"{'disaster-related' if any(k in ['flood','earthquake','fire','disease'] for k in kws) else 'conflict-related'}\n\n"
        f"**Raw score:** {score:.1f} (calculated as keyword weight sum × source multiplier, clamped to 30)\n\n"
        f"**Keywords matched:** {kw_explain or 'None'}\n\n"
        f"**Severity assigned:** {severity}"
    )


def _explain_anomaly(anomaly: dict) -> str:
    region = anomaly.get("region") or anomaly.get("location") or "Unknown"
    z = anomaly.get("z_score") or anomaly.get("zscore") or 0
    count = anomaly.get("signal_count") or anomaly.get("count") or 0
    return (
        f"A statistical anomaly was detected in **{region}**. "
        f"The signal count spiked to **{count}** — a Z-score of **{float(z):.2f}σ** "
        f"above the 7-day rolling mean. This indicates an unusual surge in threat activity "
        f"that warrants immediate analyst review."
    )


def _explain_forecast(region: str, forecast_data: dict) -> str:
    trend = forecast_data.get("trend_direction", "stable")
    conf = forecast_data.get("confidence", 0.5)
    points = forecast_data.get("forecast_points") or []
    direction_text = {
        "escalating": "an upward trend in threat scores",
        "de-escalating": "a downward trend, suggesting improving conditions",
        "stable": "a stable threat environment with minimal change expected",
    }.get(trend, "an uncertain outlook")

    pts_text = ""
    if points:
        vals = [p.get("score", 0) for p in points[:3]]
        pts_text = f" Projected 3-day scores: {', '.join(f'{v:.1f}' for v in vals)}."

    return (
        f"The forecast for **{region}** indicates {direction_text}. "
        f"Model confidence: **{conf*100:.0f}%** (based on historical variance and recency weighting).{pts_text} "
        f"The prediction uses a weighted linear regression over available history snapshots."
    )


def _explain_resource_allocation(region: str, score: float) -> str:
    severity = classify_severity(score)
    resources = []
    if score >= 20:
        resources.extend(["Medical Teams", "Security Personnel"])
    if score >= 15:
        resources.extend(["Emergency Food", "Field Hospitals"])
    if score >= 10:
        resources.append("Communications Equipment")
    resources = resources or ["Logistics Vehicles"]

    return (
        f"Resources were allocated to **{region}** because its threat score of **{score:.1f}** "
        f"places it in the **{severity}** severity band. "
        f"Under ORRAS allocation rules, {severity} regions receive: {', '.join(set(resources))}. "
        f"Allocation priority is computed by normalizing threat scores across all active regions."
    )


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown("# 🔍 Intelligence Explainability Center")
st.divider()

with st.spinner("Loading intelligence data…"):
    data = load_all_data()

signals = data["signals"]
anomalies = data["anomalies"]
escalations = data["escalations"]
forecasts = data["forecasts"]

regions = sorted(set(s.get("location", "Unknown") for s in signals if s.get("location")))

# ---------------------------------------------------------------------------
# 1. Region Explainer
# ---------------------------------------------------------------------------

st.markdown("### 🗺️ Region Threat Explainer")
selected_region = st.selectbox("Select Region to Explain", regions if regions else ["Unknown"])

if selected_region:
    explanation, drivers = _explain_region(signals, selected_region)
    sigs_for_region = [s for s in signals if s.get("location") == selected_region]
    if sigs_for_region:
        sev = sigs_for_region[0].get("severity", "LOW")
        st.markdown(render_severity_badge(sev), unsafe_allow_html=True)
    st.markdown(explanation)
    if drivers:
        st.markdown("**Top Drivers:**")
        for d in drivers:
            st.markdown(f"• {d}")

st.divider()

# ---------------------------------------------------------------------------
# 2. Signal-Level Explainer
# ---------------------------------------------------------------------------

st.markdown("### 📡 Signal-Level Explainer")
signal_titles = [f"{s.get('title', 'Untitled')[:70]} [{s.get('source','')}]" for s in signals[:50]]
if signal_titles:
    sel_idx = st.selectbox("Select Signal", range(len(signal_titles)),
                           format_func=lambda i: signal_titles[i])
    sel_signal = signals[sel_idx]
    with st.expander("📄 Signal Details", expanded=True):
        st.markdown(_explain_signal(sel_signal))
        st.markdown(f"**Full description:** {sel_signal.get('description','')[:300]}")

st.divider()

# ---------------------------------------------------------------------------
# 3. Anomaly Explanations
# ---------------------------------------------------------------------------

st.markdown("### ⚠️ Anomaly Explanations")
if anomalies:
    for i, anom in enumerate(anomalies[:10]):
        with st.expander(f"Anomaly {i+1}: {anom.get('region') or anom.get('location','Unknown')}"):
            st.markdown(_explain_anomaly(anom))
            st.json({k: v for k, v in anom.items() if k not in ("signals",)})
else:
    st.info("No anomalies detected in current signal set.")

st.divider()

# ---------------------------------------------------------------------------
# 4. Prediction Reasoning
# ---------------------------------------------------------------------------

st.markdown("### 📈 Prediction Reasoning")
if forecasts:
    forecast_regions = list(forecasts.keys())[:15]
    sel_fc_region = st.selectbox("Select Region for Forecast Explanation", forecast_regions, key="fc_region")
    if sel_fc_region:
        fc_data = forecasts.get(sel_fc_region, {})
        st.markdown(_explain_forecast(sel_fc_region, fc_data))
        with st.expander("Raw forecast data"):
            st.json(fc_data)
else:
    st.info("Insufficient history for prediction reasoning. Run the app to build history.")

st.divider()

# ---------------------------------------------------------------------------
# 5. Resource Allocation Reasoning
# ---------------------------------------------------------------------------

st.markdown("### 📦 Resource Allocation Reasoning")
region_scores: dict[str, float] = {}
for s in signals:
    loc = s.get("location", "Unknown")
    sc = float(s.get("raw_score") or 0)
    region_scores[loc] = max(region_scores.get(loc, 0), sc)

alloc_regions = sorted(region_scores.items(), key=lambda x: x[1], reverse=True)[:10]
for region, score in alloc_regions:
    if score >= 8:
        with st.expander(f"{region} — score {score:.1f}"):
            st.markdown(_explain_resource_allocation(region, score))

st.divider()

# ---------------------------------------------------------------------------
# 6. Audit Trail
# ---------------------------------------------------------------------------

st.markdown("### 📋 Decision Audit Trail")

pipeline_steps = [
    {"Step": "1. Data Collection", "Input": "13 data sources (mock/live)", "Output": f"{len(signals)} raw signals", "Key Decision": "Sources polled; failed sources skipped gracefully"},
    {"Step": "2. ThreatEngine.score_all()", "Input": f"{len(signals)} raw signals", "Output": f"{len(signals)} scored signals", "Key Decision": "Keyword matching + source multiplier applied; clamped to [0,30]"},
    {"Step": "3. AnomalyEngine.detect_anomalies()", "Input": f"{len(signals)} scored signals", "Output": f"{len(anomalies)} anomalies", "Key Decision": "Z-score > 2.0 threshold; rolling 7-day window"},
    {"Step": "4. EscalationTracker.run()", "Input": f"{len(signals)} signals", "Output": f"{len(escalations)} escalation alerts", "Key Decision": "Region score delta > threshold triggers escalation"},
    {"Step": "5. PredictionEngine.forecast_all_regions()", "Input": "History snapshots", "Output": f"{len(forecasts)} region forecasts", "Key Decision": "Weighted linear regression; 3-day horizon"},
    {"Step": "6. ActionEngine.generate_region_actions()", "Input": "Scored signals", "Output": "Resource recommendations", "Key Decision": "Severity-based action mapping; CRITICAL → immediate deployment"},
    {"Step": "7. UI Rendering", "Input": "All processed data", "Output": "12 dashboard pages", "Key Decision": "Session state caching; TTL=60s refresh"},
]

with st.expander("🕵️ Full Pipeline Audit (chronological)", expanded=False):
    st.dataframe(pd.DataFrame(pipeline_steps).astype(str), use_container_width=True)

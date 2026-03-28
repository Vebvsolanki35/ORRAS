"""
02_Predictions.py — ORRAS v2.0 Predictive Risk Forecasting Page

Displays 3-day ahead risk projections using linear trend analysis,
with per-region drill-down charts and escalation outlook.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd

st.set_page_config(
    page_title="ORRAS Predictions",
    page_icon="📈",
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
    from escalation_tracker import EscalationTracker
except ImportError as e:
    st.error(f"❌ Failed to import escalation_tracker: {e}")
    st.stop()

try:
    from prediction_engine import PredictionEngine
except ImportError as e:
    st.error(f"❌ Failed to import prediction_engine: {e}")
    st.stop()

try:
    from ui_components import (
        render_metric_card,
        render_prediction_card,
        render_severity_badge,
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
def load_forecasts(signal_count: int) -> dict:
    try:
        tracker = EscalationTracker()
        history = tracker.load_history()
        if not history:
            # Build minimal history from signals for forecasting
            tracker.run(load_signals())
            history = tracker.load_history()
        return PredictionEngine().forecast_all_regions(history)
    except Exception as e:
        st.warning(f"⚠️ Forecast load error: {e}")
        return {}


@st.cache_data(ttl=60)
def load_history(signal_count: int) -> list:
    try:
        return EscalationTracker().load_history()
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

with st.spinner("Loading forecast data…"):
    signals = load_signals()
    forecasts = load_forecasts(len(signals))
    history = load_history(len(signals))

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown("# 📈 Predictive Risk Forecasting")
st.markdown("*3-day ahead risk projections using trend analysis*")
st.divider()

if not forecasts:
    st.warning(
        "⚠️ Insufficient historical data for forecasting. "
        "At least 3 days of escalation history is required."
    )
    st.info(
        "Run the main dashboard to generate escalation snapshots, "
        "then return here for predictions."
    )
    st.stop()

# ---------------------------------------------------------------------------
# Summary metrics
# ---------------------------------------------------------------------------

directions = [d.get("direction", "STABLE") for d in forecasts.values()]
escalating = sum(1 for d in directions if d in ("ESCALATING", "VOLATILE"))
de_escalating = sum(1 for d in directions if d == "DE-ESCALATING")
stable = len(directions) - escalating - de_escalating

col1, col2, col3 = st.columns(3)
with col1:
    st.markdown(
        render_metric_card(
            title="Regions Escalating",
            value=str(escalating),
            delta=f"{escalating} of {len(forecasts)} tracked",
            icon="📈",
            color="#ef4444",
        ),
        unsafe_allow_html=True,
    )
with col2:
    st.markdown(
        render_metric_card(
            title="Regions Stable",
            value=str(stable),
            delta=f"{stable} of {len(forecasts)} tracked",
            icon="📊",
            color="#9ca3af",
        ),
        unsafe_allow_html=True,
    )
with col3:
    st.markdown(
        render_metric_card(
            title="Regions De-escalating",
            value=str(de_escalating),
            delta=f"{de_escalating} of {len(forecasts)} tracked",
            icon="📉",
            color="#22c55e",
        ),
        unsafe_allow_html=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# All-regions forecast table
# ---------------------------------------------------------------------------

st.markdown("### 📋 Regional Forecast Overview")

if forecasts:
    table_rows = []
    for region, data in sorted(forecasts.items()):
        current = data.get("current", 0.0)
        predicted = data.get("predicted_3day", 0.0)
        direction = data.get("direction", "STABLE")
        confidence = data.get("confidence", 0.0)
        delta = predicted - current

        direction_emoji = {
            "ESCALATING": "📈 Escalating",
            "DE-ESCALATING": "📉 De-escalating",
            "VOLATILE": "⚡ Volatile",
            "STABLE": "➡️ Stable",
        }.get(direction, "➡️ Stable")

        table_rows.append({
            "Region": region,
            "Current Score": round(current, 1),
            "Predicted (3-day)": round(predicted, 1),
            "Δ Change": f"{delta:+.1f}",
            "Direction": direction_emoji,
            "Confidence": f"{confidence * 100:.0f}%",
            "Severity (Now)": classify_severity(current),
        })

    df_table = pd.DataFrame(table_rows)

    def _color_row(row):
        sev = row.get("Severity (Now)", "LOW")
        colors = {
            "CRITICAL": "background-color: rgba(239,68,68,0.12)",
            "HIGH": "background-color: rgba(249,115,22,0.12)",
            "MEDIUM": "background-color: rgba(234,179,8,0.08)",
            "LOW": "background-color: rgba(34,197,94,0.05)",
        }
        c = colors.get(sev, "")
        return [c] * len(row)

    styled = df_table.style.apply(_color_row, axis=1)
    st.dataframe(styled, use_container_width=True, hide_index=True)
else:
    st.info("No forecast data available.")

st.divider()

# ---------------------------------------------------------------------------
# High-risk outlook cards
# ---------------------------------------------------------------------------

try:
    high_risk = PredictionEngine().get_high_risk_outlook(forecasts)
except Exception:
    high_risk = [
        {"region": r, **d}
        for r, d in forecasts.items()
        if d.get("predicted_3day", 0) >= 11
    ]
    high_risk.sort(key=lambda x: x.get("predicted_3day", 0), reverse=True)

if high_risk:
    st.markdown("### ⚠️ Regions Predicted to Escalate")
    st.markdown(
        f"*{len(high_risk)} region(s) forecast to reach HIGH or CRITICAL risk within 3 days.*"
    )

    cols_per_row = 3
    for row_start in range(0, len(high_risk), cols_per_row):
        row_items = high_risk[row_start : row_start + cols_per_row]
        cols = st.columns(len(row_items))
        for col, item in zip(cols, row_items):
            with col:
                direction_label = item.get("direction", "STABLE").lower()
                if direction_label in ("escalating", "volatile"):
                    direction_label = "increasing"
                elif direction_label == "de-escalating":
                    direction_label = "decreasing"
                else:
                    direction_label = "stable"

                st.markdown(
                    render_prediction_card(
                        region=item["region"],
                        current=item.get("current", 0.0),
                        predicted=item.get("predicted_3day", 0.0),
                        direction=direction_label,
                        confidence=item.get("confidence", 0.5) * 100,
                    ),
                    unsafe_allow_html=True,
                )
else:
    st.success("✅ No regions are currently forecast to reach HIGH or CRITICAL risk.")

st.divider()

# ---------------------------------------------------------------------------
# Region drill-down chart
# ---------------------------------------------------------------------------

st.markdown("### 🔭 Region Drill-Down")

all_forecast_regions = sorted(forecasts.keys())

if all_forecast_regions:
    selected_region = st.selectbox(
        "Select a region to view detailed forecast",
        options=all_forecast_regions,
        key="prediction_region_select",
    )

    region_data = forecasts.get(selected_region, {})
    forecast_points = region_data.get("forecast_points", [])

    # Build historical time series
    engine = PredictionEngine()
    try:
        hist_df = engine.prepare_time_series(history, selected_region)
    except Exception:
        hist_df = pd.DataFrame(columns=["date", "score"])

    fig = go.Figure()

    # Historical line
    if not hist_df.empty and "date" in hist_df.columns and "score" in hist_df.columns:
        hist_dates = hist_df["date"].astype(str).tolist()
        hist_scores = hist_df["score"].tolist()

        fig.add_trace(
            go.Scatter(
                x=hist_dates,
                y=hist_scores,
                mode="lines+markers",
                name="Historical",
                line=dict(color="#3b82f6", width=2),
                marker=dict(size=6, color="#3b82f6"),
            )
        )

        # Anchor forecast from last historical point
        if forecast_points and hist_dates:
            anchor_date = hist_dates[-1]
            anchor_score = float(hist_scores[-1]) if hist_scores else 0.0

            forecast_dates = [anchor_date] + [
                p.get("date", "") for p in forecast_points
            ]
            forecast_scores = [anchor_score] + [
                p.get("predicted_score", 0.0) for p in forecast_points
            ]
            confidence_val = region_data.get("confidence", 0.5)
            upper_band = [s * (1 + 0.15 * (1 - confidence_val)) for s in forecast_scores]
            lower_band = [max(0, s * (1 - 0.15 * (1 - confidence_val))) for s in forecast_scores]

            # Confidence band
            fig.add_trace(
                go.Scatter(
                    x=forecast_dates + forecast_dates[::-1],
                    y=upper_band + lower_band[::-1],
                    fill="toself",
                    fillcolor="rgba(249,115,22,0.10)",
                    line=dict(color="rgba(0,0,0,0)"),
                    hoverinfo="skip",
                    name="Confidence Band",
                    showlegend=True,
                )
            )

            # Forecast dashed line
            fig.add_trace(
                go.Scatter(
                    x=forecast_dates,
                    y=forecast_scores,
                    mode="lines+markers",
                    name="Forecast",
                    line=dict(color="#f97316", width=2, dash="dash"),
                    marker=dict(size=6, color="#f97316", symbol="diamond"),
                )
            )
    else:
        # No history available — plot forecast only
        if forecast_points:
            forecast_dates = [p.get("date", f"Day {i+1}") for i, p in enumerate(forecast_points)]
            forecast_scores = [p.get("predicted_score", 0.0) for p in forecast_points]

            fig.add_trace(
                go.Scatter(
                    x=forecast_dates,
                    y=forecast_scores,
                    mode="lines+markers",
                    name="Forecast",
                    line=dict(color="#f97316", width=2, dash="dash"),
                    marker=dict(size=6, color="#f97316"),
                )
            )
        else:
            st.info(f"No time-series data available for **{selected_region}**.")

    fig.update_layout(
        title=f"Risk Forecast — {selected_region}",
        xaxis_title="Date",
        yaxis_title="Risk Score (0–30)",
        yaxis=dict(range=[0, 30]),
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
        **_CHART_LAYOUT,
    )

    # Threshold lines
    fig.add_hline(y=11, line_dash="dot", line_color="#eab308", annotation_text="HIGH threshold")
    fig.add_hline(y=21, line_dash="dot", line_color="#ef4444", annotation_text="CRITICAL threshold")

    st.plotly_chart(fig, use_container_width=True)

    # Region forecast summary
    if region_data:
        direction_label = region_data.get("direction", "STABLE")
        confidence_pct = region_data.get("confidence", 0.5) * 100
        c1, c2, c3 = st.columns(3)
        with c1:
            st.metric("Current Score", f"{region_data.get('current', 0):.1f} / 30")
        with c2:
            st.metric(
                "3-Day Forecast",
                f"{region_data.get('predicted_3day', 0):.1f} / 30",
                delta=f"{region_data.get('predicted_3day', 0) - region_data.get('current', 0):+.1f}",
            )
        with c3:
            st.metric("Model Confidence", f"{confidence_pct:.0f}%")
else:
    st.info("No regions available for drill-down analysis.")

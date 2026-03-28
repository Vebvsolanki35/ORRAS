"""
04_Timeline.py — ORRAS v2.0 Historical Event Timeline Page

Visualises global and per-region threat timelines with filtering,
turning point detection, and annotated time-series charts.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="Event Timeline",
    page_icon="📅",
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
    from timeline_engine import TimelineEngine
except ImportError as e:
    st.error(f"❌ Failed to import timeline_engine: {e}")
    st.stop()

try:
    from ui_components import render_timeline_event, render_severity_badge
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

_SEVERITY_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH": "#f97316",
    "MEDIUM": "#eab308",
    "LOW": "#22c55e",
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
def load_history(signal_count: int) -> list:
    try:
        tracker = EscalationTracker()
        tracker.run(load_signals())
        return tracker.load_history()
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_global_timeline(signal_count: int) -> list:
    try:
        return TimelineEngine().build_global_timeline(load_signals())
    except Exception as e:
        st.warning(f"⚠️ Timeline build error: {e}")
        return []


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

with st.spinner("Building event timeline…"):
    signals = load_signals()
    history = load_history(len(signals))
    global_timeline = load_global_timeline(len(signals))

all_regions = sorted({s.get("location", "") for s in signals if s.get("location")})

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown("# 📅 Historical Event Timeline")
st.divider()

# ---------------------------------------------------------------------------
# Filters
# ---------------------------------------------------------------------------

st.markdown("### 🔧 Filters")
filter_col1, filter_col2, filter_col3 = st.columns([2, 2, 2])

with filter_col1:
    region_options = ["All Regions"] + all_regions
    selected_region = st.selectbox("Filter by Region", options=region_options, key="tl_region")

with filter_col2:
    severity_options = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
    selected_severities = st.multiselect(
        "Filter by Severity",
        options=severity_options,
        default=severity_options,
        key="tl_severity",
    )

with filter_col3:
    today = datetime.now(timezone.utc).date()
    date_range = st.date_input(
        "Date Range",
        value=(today - timedelta(days=30), today),
        key="tl_dates",
    )

# Parse date range safely
try:
    if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
        date_start, date_end = str(date_range[0]), str(date_range[1])
    else:
        date_start = str(today - timedelta(days=30))
        date_end = str(today)
except Exception:
    date_start = str(today - timedelta(days=30))
    date_end = str(today)

st.divider()

# ---------------------------------------------------------------------------
# Global average risk score chart
# ---------------------------------------------------------------------------

st.markdown("### 📊 Global Average Risk Score Over Time")

if global_timeline:
    # Apply date and severity filters
    filtered_tl = [
        e for e in global_timeline
        if date_start <= e.get("date", "") <= date_end
        and e.get("peak_severity", "LOW") in selected_severities
    ]

    if filtered_tl:
        dates = [e["date"] for e in filtered_tl]
        avg_scores = []
        colors = []
        hover_texts = []

        for e in filtered_tl:
            events = e.get("events", [])
            if events:
                avg = sum(float(ev.get("raw_score") or 0) for ev in events) / len(events)
            else:
                avg = 0.0
            avg_scores.append(round(avg, 2))
            colors.append(_SEVERITY_COLORS.get(e.get("peak_severity", "LOW"), "#22c55e"))
            hover_texts.append(
                f"Date: {e['date']}<br>"
                f"Signals: {e.get('total_signals', 0)}<br>"
                f"Peak: {e.get('peak_severity', 'N/A')}<br>"
                f"Top Region: {e.get('top_region', 'N/A')}"
            )

        fig_global = go.Figure()

        # Coloured scatter points
        for sev, sev_color in _SEVERITY_COLORS.items():
            sev_dates = [d for d, e in zip(dates, filtered_tl) if e.get("peak_severity") == sev]
            sev_scores = [s for s, e in zip(avg_scores, filtered_tl) if e.get("peak_severity") == sev]
            if sev_dates:
                fig_global.add_trace(
                    go.Scatter(
                        x=sev_dates,
                        y=sev_scores,
                        mode="markers",
                        name=sev,
                        marker=dict(color=sev_color, size=8, symbol="circle"),
                        hoverinfo="skip",
                    )
                )

        # Main line
        fig_global.add_trace(
            go.Scatter(
                x=dates,
                y=avg_scores,
                mode="lines",
                name="Avg Risk Score",
                line=dict(color="#3b82f6", width=2),
                hovertext=hover_texts,
                hoverinfo="text",
            )
        )

        fig_global.add_hline(y=11, line_dash="dot", line_color="#eab308",
                              annotation_text="HIGH threshold")
        fig_global.add_hline(y=21, line_dash="dot", line_color="#ef4444",
                              annotation_text="CRITICAL threshold")

        fig_global.update_layout(
            title="Global Average Risk Score",
            xaxis_title="Date",
            yaxis_title="Avg Risk Score (0–30)",
            yaxis=dict(range=[0, 30]),
            **_CHART_LAYOUT,
        )
        st.plotly_chart(fig_global, use_container_width=True)
    else:
        st.info("No events match the current filters.")
else:
    st.info("No global timeline data available.")

st.divider()

# ---------------------------------------------------------------------------
# Scrollable event cards
# ---------------------------------------------------------------------------

st.markdown("### 📋 Event Feed")
st.markdown("*Showing most recent events first*")

if global_timeline:
    # Build flat event list from timeline entries
    all_events = []
    for entry in global_timeline:
        for sig in entry.get("events", []):
            event_date = entry.get("date", "")
            if not (date_start <= event_date <= date_end):
                continue
            sev = sig.get("severity") or classify_severity(float(sig.get("raw_score") or 0))
            if sev not in selected_severities:
                continue
            location = sig.get("location") or "Unknown"
            if selected_region != "All Regions" and location != selected_region:
                continue
            all_events.append({
                "date": f"{event_date} UTC",
                "location": location,
                "description": sig.get("title") or sig.get("description") or "No description",
                "severity": sev,
                "type": sig.get("type") or sig.get("source") or "Signal",
            })

    # Sort newest first
    all_events.sort(key=lambda e: e.get("date", ""), reverse=True)

    if all_events:
        # Pagination: show 20 events at a time
        page_size = 20
        if "timeline_page" not in st.session_state:
            st.session_state.timeline_page = 0

        total_pages = max(1, (len(all_events) + page_size - 1) // page_size)
        page = st.session_state.timeline_page
        page_events = all_events[page * page_size : (page + 1) * page_size]

        for event in page_events:
            st.markdown(render_timeline_event(event), unsafe_allow_html=True)

        # Pagination controls
        pg_col1, pg_col2, pg_col3 = st.columns([1, 2, 1])
        with pg_col1:
            if st.button("← Previous", disabled=(page == 0)):
                st.session_state.timeline_page = max(0, page - 1)
                st.rerun()
        with pg_col2:
            st.markdown(
                f"<div style='text-align:center;color:#9ca3af;'>"
                f"Page {page + 1} of {total_pages} &nbsp;|&nbsp; "
                f"{len(all_events)} total events"
                f"</div>",
                unsafe_allow_html=True,
            )
        with pg_col3:
            if st.button("Next →", disabled=(page >= total_pages - 1)):
                st.session_state.timeline_page = min(total_pages - 1, page + 1)
                st.rerun()
    else:
        st.info("No events match the current filters.")
else:
    st.info("No event data available.")

st.divider()

# ---------------------------------------------------------------------------
# Major Escalation Events (turning points)
# ---------------------------------------------------------------------------

st.markdown("### 🚨 Major Escalation Events")
st.markdown("*Significant severity-level transitions detected in historical data*")

if selected_region != "All Regions":
    with st.spinner(f"Analysing turning points for {selected_region}…"):
        try:
            turning_points = TimelineEngine().find_turning_points(history, selected_region)
        except Exception:
            turning_points = []

    if turning_points:
        for tp in turning_points:
            from_sev = tp.get("from_severity", "LOW")
            to_sev = tp.get("to_severity", "LOW")
            tp_date = tp.get("date", "Unknown")
            from_badge = render_severity_badge(from_sev)
            to_badge = render_severity_badge(to_sev)

            tp_event = {
                "date": tp_date,
                "location": selected_region,
                "description": f"Severity transition: {from_sev} → {to_sev}",
                "severity": to_sev,
                "type": "Escalation Turning Point",
            }
            st.markdown(render_timeline_event(tp_event), unsafe_allow_html=True)
    else:
        st.info(f"No turning points detected for **{selected_region}** in available history.")
else:
    st.info("Select a specific region above to view its escalation turning points.")

st.divider()

# ---------------------------------------------------------------------------
# Region-specific chart with annotations
# ---------------------------------------------------------------------------

st.markdown("### 📍 Region-Specific Timeline")

if all_regions:
    chart_region = st.selectbox(
        "Select region for detailed chart",
        options=all_regions,
        key="tl_chart_region",
    )

    with st.spinner(f"Building timeline for {chart_region}…"):
        try:
            region_tl = TimelineEngine().build_region_timeline(signals, history, chart_region)
        except Exception as e:
            region_tl = []
            st.warning(f"Could not build region timeline: {e}")

    if region_tl:
        # Apply date filter
        region_tl_filtered = [
            e for e in region_tl
            if date_start <= e.get("date", "") <= date_end
        ]

        if region_tl_filtered:
            r_dates = [e["date"] for e in region_tl_filtered]
            r_scores = [e.get("score", 0.0) for e in region_tl_filtered]
            r_escalations = [e.get("escalation_event", False) for e in region_tl_filtered]

            fig_region = go.Figure()

            # Main score line
            fig_region.add_trace(
                go.Scatter(
                    x=r_dates,
                    y=r_scores,
                    mode="lines+markers",
                    name="Risk Score",
                    line=dict(color="#06b6d4", width=2),
                    marker=dict(size=6, color="#06b6d4"),
                )
            )

            # Annotate escalation events
            esc_dates = [d for d, esc in zip(r_dates, r_escalations) if esc]
            esc_scores = [s for s, esc in zip(r_scores, r_escalations) if esc]
            if esc_dates:
                fig_region.add_trace(
                    go.Scatter(
                        x=esc_dates,
                        y=esc_scores,
                        mode="markers",
                        name="Escalation Event",
                        marker=dict(
                            size=12,
                            color="#ef4444",
                            symbol="triangle-up",
                            line=dict(color="#fca5a5", width=1),
                        ),
                    )
                )

            # Shaded severity bands
            fig_region.add_hrect(y0=21, y1=30, fillcolor="rgba(239,68,68,0.07)",
                                  line_width=0, annotation_text="CRITICAL", annotation_position="right")
            fig_region.add_hrect(y0=11, y1=21, fillcolor="rgba(249,115,22,0.05)",
                                  line_width=0, annotation_text="HIGH", annotation_position="right")
            fig_region.add_hrect(y0=6, y1=11, fillcolor="rgba(234,179,8,0.05)",
                                  line_width=0, annotation_text="MEDIUM", annotation_position="right")

            fig_region.update_layout(
                title=f"Risk Score Timeline — {chart_region}",
                xaxis_title="Date",
                yaxis_title="Risk Score (0–30)",
                yaxis=dict(range=[0, 30]),
                **_CHART_LAYOUT,
            )
            st.plotly_chart(fig_region, use_container_width=True)
        else:
            st.info(f"No data for **{chart_region}** in the selected date range.")
    else:
        st.info(f"No timeline data available for **{chart_region}**.")
else:
    st.info("No regions available.")

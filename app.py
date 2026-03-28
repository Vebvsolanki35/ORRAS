"""
app.py — ORRAS Streamlit Dashboard.

Orchestrates the full data pipeline and presents results through an
interactive, dark-themed real-time risk assessment dashboard.
"""

import time
import traceback
from datetime import datetime, timezone

import pandas as pd
import plotly.express as px
import plotly.graph_objects as go
import streamlit as st

# ── Page config must be the first Streamlit call ────────────────────────────
st.set_page_config(
    page_title="ORRAS — Risk Assessment System",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Engine imports (after page config) ──────────────────────────────────────
from action_engine import ActionEngine
from anomaly_engine import AnomalyEngine
from confidence_engine import ConfidenceEngine
from config import DASHBOARD_REFRESH_SECONDS
from correlation_engine import CorrelationEngine
from data_collector import DataCollectionOrchestrator
from data_processor import DataProcessor
from escalation_tracker import EscalationTracker
from threat_engine import ThreatEngine

# ── Custom CSS ───────────────────────────────────────────────────────────────
CUSTOM_CSS = """
<style>
  /* Dark background */
  [data-testid="stAppViewContainer"] { background-color: #0d1117; }
  [data-testid="stSidebar"]          { background-color: #161b22; }

  /* Cards */
  .risk-card {
    background-color: #161b22;
    border-radius: 8px;
    padding: 16px;
    margin-bottom: 10px;
    border-left: 4px solid #58a6ff;
  }
  .risk-card.CRITICAL {
    border-left: 4px solid #ff4444;
    box-shadow: 0 0 12px #ff444466;
  }
  .risk-card.HIGH    { border-left: 4px solid #ff8c00; }
  .risk-card.MEDIUM  { border-left: 4px solid #ffd700; }
  .risk-card.LOW     { border-left: 4px solid #00cc66; }

  /* Severity badges */
  .badge {
    display: inline-block;
    padding: 2px 8px;
    border-radius: 4px;
    font-size: 0.75rem;
    font-weight: bold;
    color: #fff;
  }
  .badge.CRITICAL { background-color: #ff4444; }
  .badge.HIGH     { background-color: #ff8c00; }
  .badge.MEDIUM   { background-color: #b8860b; color: #fff; }
  .badge.LOW      { background-color: #006633; }

  /* Signal feed monospace */
  [data-testid="stDataFrame"] { font-family: 'Courier New', monospace; font-size: 0.82rem; }

  /* Headings */
  h1, h2, h3, h4 { color: #e6edf3 !important; }
  p, li, label   { color: #c9d1d9 !important; }
</style>
"""

st.markdown(CUSTOM_CSS, unsafe_allow_html=True)

# ── Severity colour helpers ──────────────────────────────────────────────────
SEV_COLOURS = {
    "CRITICAL": "#ff4444",
    "HIGH": "#ff8c00",
    "MEDIUM": "#ffd700",
    "LOW": "#00cc66",
}
SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ── Pipeline ─────────────────────────────────────────────────────────────────

def run_pipeline() -> dict:
    """
    Execute the full ORRAS data pipeline.

    Stages: Collect → Process → Score → Correlate → Anomaly →
            Escalation → Confidence → Actions

    Returns:
        Dict containing all pipeline outputs, keyed for the dashboard.
    """
    collector = DataCollectionOrchestrator()
    raw = collector.collect_all()
    status_map = raw.pop("_status", {})

    processor = DataProcessor()
    signals = processor.process_all(raw)

    threat = ThreatEngine()
    signals = threat.score_all(signals)
    top_keywords = threat.get_top_keywords(signals, n=15)

    corr = CorrelationEngine()
    signals = corr.correlate_all(signals)

    anomaly = AnomalyEngine()
    anomalies = anomaly.detect_anomalies(signals)
    anomaly_summary = anomaly.summarize_anomalies(anomalies)

    tracker = EscalationTracker()
    escalation_result = tracker.run(signals)

    conf = ConfidenceEngine()
    conf_map = conf.score_confidence(signals)
    signals = conf.annotate_signals(signals, conf_map)

    action = ActionEngine()
    actions = action.generate_region_actions(signals)
    action.log_alerts(actions)

    return {
        "signals": signals,
        "status_map": status_map,
        "top_keywords": top_keywords,
        "anomalies": anomalies,
        "anomaly_summary": anomaly_summary,
        "region_risk": escalation_result["region_risk"],
        "escalation_alerts": escalation_result["escalation_alerts"],
        "conf_map": conf_map,
        "actions": actions,
        "tracker": tracker,
    }


def _should_refresh() -> bool:
    """Return True if the pipeline cache has expired."""
    last = st.session_state.get("last_run")
    if last is None:
        return True
    elapsed = (datetime.now(timezone.utc) - last).total_seconds()
    return elapsed >= DASHBOARD_REFRESH_SECONDS


def _get_pipeline_data() -> dict:
    """Return cached pipeline data, refreshing when necessary."""
    if _should_refresh() or "pipeline_data" not in st.session_state:
        with st.spinner("⚙️ Running ORRAS pipeline…"):
            try:
                data = run_pipeline()
                st.session_state["pipeline_data"] = data
                st.session_state["last_run"] = datetime.now(timezone.utc)
            except Exception:
                st.error(f"Pipeline failed:\n```\n{traceback.format_exc()}\n```")
                st.stop()
    return st.session_state["pipeline_data"]


# ── Sidebar ──────────────────────────────────────────────────────────────────

def render_sidebar(data: dict) -> dict:
    """Render sidebar and return active filter settings."""
    st.sidebar.markdown("## 🛡️ ORRAS v1.0")
    st.sidebar.markdown("*Open-source Real-time Risk Assessment System*")
    st.sidebar.divider()

    if st.sidebar.button("🔄 Refresh Now", use_container_width=True):
        # Force pipeline re-run
        st.session_state.pop("pipeline_data", None)
        st.session_state.pop("last_run", None)
        st.rerun()

    last = st.session_state.get("last_run")
    if last:
        st.sidebar.caption(f"Last updated: {last.strftime('%Y-%m-%d %H:%M:%S UTC')}")

    st.sidebar.divider()
    st.sidebar.markdown("### 🔍 Filters")

    signals = data.get("signals", [])
    all_regions = sorted({s.get("location", "Unknown") for s in signals})
    all_sources = sorted({s.get("source", "Unknown") for s in signals})
    severity_opts = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    regions = st.sidebar.multiselect(
        "Regions", options=all_regions, default=all_regions, key="filter_regions"
    )
    sources = st.sidebar.multiselect(
        "Sources", options=all_sources, default=all_sources, key="filter_sources"
    )
    severities = st.sidebar.multiselect(
        "Severity", options=severity_opts, default=severity_opts, key="filter_sev"
    )
    days_back = st.sidebar.slider(
        "Days of history", min_value=1, max_value=7, value=2, key="filter_days"
    )

    st.sidebar.divider()
    st.sidebar.markdown("### 📡 Source Health")
    status_map = data.get("status_map", {})
    for src_name in ["NewsAPI", "GDELT", "OpenSky", "NASA FIRMS", "Cloudflare Radar",
                     "NetBlocks", "Social/Mock"]:
        status = status_map.get(src_name, "UNKNOWN")
        badge = "🟢 LIVE" if status == "LIVE" else "🔴 MOCK/OFFLINE"
        st.sidebar.markdown(f"`{src_name}` {badge}")

    return {
        "regions": regions,
        "sources": sources,
        "severities": severities,
        "days_back": days_back,
    }


def _apply_filters(signals: list[dict], filters: dict) -> list[dict]:
    """Filter signals according to sidebar selections."""
    regions = set(filters.get("regions") or [])
    sources = set(filters.get("sources") or [])
    sevs = set(filters.get("severities") or [])
    days = filters.get("days_back", 7)

    cutoff = pd.Timestamp.utcnow() - pd.Timedelta(days=days)
    result = []
    for sig in signals:
        loc = sig.get("location", "Unknown")
        src = sig.get("source", "Unknown")
        sev = sig.get("severity", "LOW")
        ts_str = sig.get("timestamp", "")
        try:
            ts = pd.Timestamp(ts_str, tz="UTC")
        except Exception:
            ts = cutoff  # include on parse failure

        if regions and loc not in regions:
            continue
        if sources and src not in sources:
            continue
        if sevs and sev not in sevs:
            continue
        if ts < cutoff:
            continue
        result.append(sig)
    return result


# ── World Map ─────────────────────────────────────────────────────────────────

def render_map(signals: list[dict]) -> None:
    """Render an interactive Folium world map with signal markers and heatmap."""
    try:
        import folium
        from folium.plugins import HeatMap
        from streamlit_folium import st_folium

        m = folium.Map(
            location=[20, 0],
            zoom_start=2,
            tiles="CartoDB dark_matter",
        )

        marker_group = folium.FeatureGroup(name="Signal Markers")
        heat_data = []

        colour_map = {
            "CRITICAL": "red",
            "HIGH": "orange",
            "MEDIUM": "yellow",
            "LOW": "green",
        }

        for sig in signals:
            lat = sig.get("latitude") or 0.0
            lon = sig.get("longitude") or 0.0
            if lat == 0.0 and lon == 0.0:
                continue

            sev = sig.get("severity", "LOW")
            colour = colour_map.get(sev, "blue")
            radius = max(4, min(20, sig.get("raw_score", 1) * 0.7))
            recommendation = sig.get("recommendation", "")

            popup_html = (
                f"<b>{sig.get('title', '')[:80]}</b><br>"
                f"<b>Severity:</b> {sev}<br>"
                f"<b>Source:</b> {sig.get('source', '')}<br>"
                f"<b>Score:</b> {sig.get('raw_score', 0):.1f}<br>"
                f"<b>Time:</b> {sig.get('timestamp', '')[:19]}<br>"
                f"<i>{recommendation}</i>"
            )

            folium.CircleMarker(
                location=[lat, lon],
                radius=radius,
                color=colour,
                fill=True,
                fill_color=colour,
                fill_opacity=0.6,
                popup=folium.Popup(popup_html, max_width=300),
                tooltip=sig.get("location", ""),
            ).add_to(marker_group)

            heat_data.append([lat, lon, sig.get("raw_score", 1) / 30.0])

        marker_group.add_to(m)

        heat_group = folium.FeatureGroup(name="Heat Map", show=False)
        if heat_data:
            HeatMap(heat_data, radius=20, blur=15).add_to(heat_group)
        heat_group.add_to(m)

        folium.LayerControl().add_to(m)
        st_folium(m, width="100%", height=450, returned_objects=[])

    except ImportError:
        st.info("Install `folium` and `streamlit-folium` to see the map.")


# ── Charts ────────────────────────────────────────────────────────────────────

def render_escalation_chart(signals: list[dict], tracker: EscalationTracker) -> None:
    """Render a 7-day risk escalation timeline for the top 5 regions."""
    # Compute top 5 regions by current avg score
    from collections import defaultdict
    region_scores: dict[str, list] = defaultdict(list)
    for sig in signals:
        region_scores[sig.get("location", "Unknown")].append(sig.get("raw_score", 0))
    top5 = sorted(
        region_scores.items(), key=lambda x: sum(x[1]) / len(x[1]), reverse=True
    )[:5]

    fig = go.Figure()
    for region, _ in top5:
        df = tracker.get_trend_data(region, days=7)
        if df.empty:
            continue
        fig.add_trace(go.Scatter(
            x=df["date"],
            y=df["avg_score"],
            mode="lines+markers",
            name=region,
        ))

    fig.update_layout(
        title="7-Day Risk Escalation Timeline",
        xaxis_title="Date",
        yaxis_title="Avg Risk Score (0–30)",
        yaxis=dict(range=[0, 30]),
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


def render_keyword_chart(top_keywords: dict[str, int]) -> None:
    """Render a horizontal bar chart of the top threat keywords."""
    if not top_keywords:
        st.info("No keywords to display.")
        return

    kws = list(top_keywords.keys())[:15]
    counts = [top_keywords[k] for k in kws]
    max_c = max(counts) if counts else 1

    colours = [
        f"rgb({int(255 * (c / max_c))}, {int(100 * (1 - c / max_c))}, 50)"
        for c in counts
    ]

    fig = go.Figure(go.Bar(
        x=counts,
        y=kws,
        orientation="h",
        marker_color=colours,
    ))
    fig.update_layout(
        title="Top Threat Keywords",
        xaxis_title="Occurrences",
        yaxis=dict(autorange="reversed"),
        template="plotly_dark",
        paper_bgcolor="#0d1117",
        plot_bgcolor="#161b22",
        height=350,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Main dashboard ────────────────────────────────────────────────────────────

def main() -> None:
    """Main entry point for the ORRAS Streamlit dashboard."""
    data = _get_pipeline_data()
    filters = render_sidebar(data)

    all_signals = data.get("signals", [])
    filtered_signals = _apply_filters(all_signals, filters)
    actions = data.get("actions", [])
    anomalies = data.get("anomalies", [])
    escalation_alerts = data.get("escalation_alerts", [])
    conf_map = data.get("conf_map", {})
    top_keywords = data.get("top_keywords", {})
    tracker = data.get("tracker")

    st.title("🛡️ ORRAS — Open-source Real-time Risk Assessment System")

    # ── Row 1: Alert Banner ──────────────────────────────────────────────────
    anomaly_summary = data.get("anomaly_summary", "")
    if anomalies:
        st.error(anomaly_summary or "⚠️ Anomalies detected.")
    if escalation_alerts:
        esc_msg = "🔺 RAPID ESCALATION: " + ", ".join(
            f"{a['region']} ({a['from_level']}→{a['to_level']})"
            for a in escalation_alerts
        )
        st.warning(esc_msg)
    if not anomalies and not escalation_alerts:
        st.success("✅ All systems nominal — No anomalies detected")

    # ── Row 2: KPI Metrics ───────────────────────────────────────────────────
    col1, col2, col3, col4 = st.columns(4)
    critical_regions = sum(
        1 for v in data.get("region_risk", {}).values() if v.get("severity") == "CRITICAL"
    )
    avg_conf = (
        sum(v["confidence_score"] for v in conf_map.values()) / len(conf_map)
        if conf_map else 0.0
    )

    col1.metric("Total Signals", len(filtered_signals), delta=f"{len(all_signals)} total")
    col2.metric("Critical Regions", critical_regions)
    col3.metric("Active Anomalies", len(anomalies))
    col4.metric("Avg Confidence", f"{avg_conf * 100:.0f}%")

    # ── Row 3: World Map ─────────────────────────────────────────────────────
    st.subheader("🌍 Global Signal Map")
    render_map(filtered_signals)

    # ── Row 4: Signal Feed + Action Panel ────────────────────────────────────
    col_left, col_right = st.columns([6, 4])

    with col_left:
        st.subheader("📡 Live Signal Feed")
        if filtered_signals:
            df_signals = pd.DataFrame([
                {
                    "Timestamp": s.get("timestamp", "")[:19],
                    "Location": s.get("location", ""),
                    "Source": s.get("source", ""),
                    "Title": s.get("title", "")[:60],
                    "Score": round(s.get("raw_score", 0), 1),
                    "Severity": s.get("severity", "LOW"),
                    "Confidence": s.get("confidence", "Low"),
                }
                for s in filtered_signals
            ])
            st.dataframe(df_signals, use_container_width=True, height=350)

            csv = df_signals.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download CSV",
                data=csv,
                file_name="orras_signals.csv",
                mime="text/csv",
            )
        else:
            st.info("No signals match the current filters.")

    with col_right:
        st.subheader("🎯 Action Recommendations")
        # Filter actions to regions visible in current filter
        visible_regions = {s.get("location") for s in filtered_signals}
        visible_actions = [a for a in actions if a["region"] in visible_regions][:6]

        for action in visible_actions:
            sev = action["max_severity"]
            colour = SEV_COLOURS.get(sev, "#58a6ff")
            st.markdown(
                f"""
                <div class="risk-card {sev}">
                  <b>{action['region']}</b>
                  <span class="badge {sev}" style="margin-left:8px">{sev}</span>
                  <br><small>Signals: {action['signal_count']}</small>
                  <br><i>{action['recommendation']}</i>
                  <ul style="margin:4px 0 0 12px; padding:0">
                    {''.join(f"<li><small>{t[:60]}</small></li>" for t in action['top_signals'])}
                  </ul>
                </div>
                """,
                unsafe_allow_html=True,
            )

    # ── Row 5: Escalation Timeline + Keywords ────────────────────────────────
    col_l, col_r = st.columns(2)
    with col_l:
        if tracker:
            render_escalation_chart(filtered_signals, tracker)
        else:
            st.info("Escalation timeline not available.")
    with col_r:
        render_keyword_chart(top_keywords)

    # ── Row 6: Region Drill-Down ─────────────────────────────────────────────
    st.subheader("🔬 Region Drill-Down")
    all_region_names = sorted({s.get("location", "Unknown") for s in all_signals})
    if all_region_names:
        selected_region = st.selectbox(
            "Select a region:", options=all_region_names, key="region_drilldown"
        )
        region_sigs = [s for s in all_signals if s.get("location") == selected_region]

        if region_sigs:
            dr_col1, dr_col2 = st.columns([3, 2])

            with dr_col1:
                st.markdown(f"**Signals in {selected_region}:** {len(region_sigs)}")
                df_region = pd.DataFrame([
                    {
                        "Timestamp": s.get("timestamp", "")[:19],
                        "Source": s.get("source", ""),
                        "Title": s.get("title", "")[:60],
                        "Score": round(s.get("raw_score", 0), 1),
                        "Severity": s.get("severity", "LOW"),
                    }
                    for s in region_sigs
                ])
                st.dataframe(df_region, use_container_width=True)

            with dr_col2:
                conf_data = conf_map.get(selected_region, {})
                st.markdown(
                    f"**Confidence:** {conf_data.get('confidence', 'Low')} "
                    f"({conf_data.get('confidence_score', 0.33):.0%})"
                )
                st.markdown(f"**Sources:** {', '.join(conf_data.get('sources', []))}")

                # 7-day mini-chart
                if tracker:
                    trend_df = tracker.get_trend_data(selected_region, days=7)
                    if not trend_df.empty:
                        mini_fig = px.line(
                            trend_df, x="date", y="avg_score",
                            title=f"7-Day Trend: {selected_region}",
                            template="plotly_dark",
                        )
                        mini_fig.update_layout(
                            paper_bgcolor="#0d1117",
                            plot_bgcolor="#161b22",
                            height=250,
                        )
                        st.plotly_chart(mini_fig, use_container_width=True)

                # Recommendation
                region_action = next(
                    (a for a in actions if a["region"] == selected_region), None
                )
                if region_action:
                    sev = region_action["max_severity"]
                    st.markdown(
                        f"<div class='risk-card {sev}'>"
                        f"<b>{sev}</b><br>{region_action['recommendation']}"
                        f"</div>",
                        unsafe_allow_html=True,
                    )

    # ── Auto-refresh ─────────────────────────────────────────────────────────
    st.caption(
        f"Auto-refreshes every {DASHBOARD_REFRESH_SECONDS}s. "
        "Use 🔄 in the sidebar to refresh immediately."
    )

    # Trigger a rerun after the refresh interval expires
    time.sleep(1)
    if _should_refresh():
        st.rerun()


if __name__ == "__main__":
    main()

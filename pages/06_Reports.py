"""
06_Reports.py — ORRAS v2.0 Intelligence Reports & Exports Page

Provides four tabs: Daily PDF report generation, signal export with filters,
alert history browser, and custom report builder.
"""

import json
import io
from datetime import datetime, timedelta, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="Reports",
    page_icon="📄",
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
    from anomaly_engine import AnomalyEngine
except ImportError as e:
    st.error(f"❌ Failed to import anomaly_engine: {e}")
    st.stop()

try:
    from prediction_engine import PredictionEngine
except ImportError as e:
    st.error(f"❌ Failed to import prediction_engine: {e}")
    st.stop()

try:
    from safety_engine import SafetyEngine
except ImportError as e:
    st.error(f"❌ Failed to import safety_engine: {e}")
    st.stop()

try:
    from report_engine import ReportEngine
except ImportError as e:
    st.error(f"❌ Failed to import report_engine: {e}")
    st.stop()

try:
    from utils import classify_severity, load_json
    from config import ALERT_LOG_FILE
except ImportError as e:
    st.error(f"❌ Failed to import utils/config: {e}")
    st.stop()

try:
    from ui_components import render_severity_badge, render_metric_card
except ImportError as e:
    st.error(f"❌ Failed to import ui_components: {e}")
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
def load_anomalies(signal_count: int) -> list:
    try:
        return AnomalyEngine().detect_anomalies(load_signals())
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_escalations(signal_count: int) -> list:
    try:
        tracker = EscalationTracker()
        result = tracker.run(load_signals())
        return result.get("escalation_alerts", [])
    except Exception:
        return []


@st.cache_data(ttl=60)
def load_forecasts(signal_count: int) -> dict:
    try:
        tracker = EscalationTracker()
        history = tracker.load_history()
        if not history:
            tracker.run(load_signals())
            history = tracker.load_history()
        return PredictionEngine().forecast_all_regions(history)
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_safety(signal_count: int) -> dict:
    try:
        engine = SafetyEngine()
        signals = load_signals()
        scores = engine.score_all_categories(signals)
        return engine.compute_overall_safety_index(scores)
    except Exception:
        return {}


@st.cache_data(ttl=60)
def load_alert_log() -> list:
    try:
        return load_json(ALERT_LOG_FILE)
    except Exception:
        return []


# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown("# 📄 Intelligence Reports & Exports")
st.divider()

# Load base data
with st.spinner("Loading report data…"):
    signals = load_signals()
    anomalies = load_anomalies(len(signals))
    escalations = load_escalations(len(signals))

all_regions = sorted({s.get("location", "") for s in signals if s.get("location")})
all_severities = ["CRITICAL", "HIGH", "MEDIUM", "LOW"]
today = datetime.now(timezone.utc).date()

# ---------------------------------------------------------------------------
# Tabs
# ---------------------------------------------------------------------------

tab1, tab2, tab3, tab4 = st.tabs([
    "📊 Daily Report",
    "📤 Signal Export",
    "🔔 Alert History",
    "🛠️ Custom Report",
])

# ============================================================================
# TAB 1: Daily Report
# ============================================================================

with tab1:
    st.markdown("### 📊 Daily Intelligence Report")
    st.markdown(
        "Generate a comprehensive PDF intelligence report covering threats, "
        "anomalies, escalations, forecasts, and safety assessments."
    )

    col_info, col_btn = st.columns([3, 1])
    with col_info:
        st.markdown(
            f'<div style="background:#111827;border:1px solid #1f2937;border-radius:12px;'
            f'padding:1rem;">'
            f'<b style="color:#f9fafb;">Report will include:</b>'
            f'<ul style="color:#d1d5db;margin:0.5rem 0;">'
            f'<li>Executive Summary & KPIs</li>'
            f'<li>Top 10 threat regions</li>'
            f'<li>Signal breakdown by source</li>'
            f'<li>Anomaly & escalation alerts</li>'
            f'<li>3-day predictive forecast</li>'
            f'<li>Safety intelligence scorecard</li>'
            f'<li>CRITICAL/HIGH signal appendix</li>'
            f'</ul>'
            f'<small style="color:#9ca3af;">Signals: {len(signals)} | '
            f'Anomalies: {len(anomalies)} | '
            f'Escalations: {len(escalations)}</small>'
            f'</div>',
            unsafe_allow_html=True,
        )

    with col_btn:
        st.markdown("<br>", unsafe_allow_html=True)
        generate_report = st.button(
            "📊 Generate PDF Report",
            use_container_width=True,
            key="gen_daily_report",
        )

    if generate_report:
        with st.spinner("Generating PDF report… this may take a moment."):
            try:
                forecasts = load_forecasts(len(signals))
                safety = load_safety(len(signals))
                engine = ReportEngine()
                pdf_bytes = engine.generate_daily_report(
                    signals=signals,
                    anomalies=anomalies,
                    escalations=escalations,
                    forecasts=forecasts,
                    safety=safety,
                )
                filename = engine.get_report_filename()
                st.session_state.daily_report_bytes = pdf_bytes
                st.session_state.daily_report_filename = filename
                st.success(f"✅ Report generated: **{filename}**")
            except Exception as e:
                st.error(f"❌ Report generation failed: {e}")

    # Preview section
    if "daily_report_bytes" in st.session_state and st.session_state.daily_report_bytes:
        st.markdown("---")
        st.markdown("#### 📋 Report Preview")
        size_kb = len(st.session_state.daily_report_bytes) / 1024
        st.markdown(
            f'<div style="background:#111827;border:1px solid #22c55e44;border-radius:12px;'
            f'padding:1.2rem;">'
            f'<b style="color:#86efac;">✅ Report Ready</b><br>'
            f'<span style="color:#d1d5db;">Filename: '
            f'{st.session_state.get("daily_report_filename", "report.pdf")}</span><br>'
            f'<span style="color:#9ca3af;">Size: {size_kb:.1f} KB</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)
        st.download_button(
            label="⬇️ Download PDF Report",
            data=st.session_state.daily_report_bytes,
            file_name=st.session_state.get("daily_report_filename", "ORRAS_Report.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )

# ============================================================================
# TAB 2: Signal Export
# ============================================================================

with tab2:
    st.markdown("### 📤 Signal Export")
    st.markdown("Filter and download signal data in CSV or JSON format.")

    # Filters
    f_col1, f_col2, f_col3 = st.columns(3)

    with f_col1:
        region_filter = st.multiselect(
            "Filter by Region",
            options=["All Regions"] + all_regions,
            default=["All Regions"],
            key="export_region_filter",
        )

    with f_col2:
        severity_filter = st.multiselect(
            "Filter by Severity",
            options=all_severities,
            default=all_severities,
            key="export_severity_filter",
        )

    with f_col3:
        date_range = st.date_input(
            "Date Range",
            value=(today - timedelta(days=7), today),
            key="export_date_range",
        )

    # Apply filters
    try:
        if isinstance(date_range, (list, tuple)) and len(date_range) == 2:
            start_date, end_date = str(date_range[0]), str(date_range[1])
        else:
            start_date = str(today - timedelta(days=7))
            end_date = str(today)
    except Exception:
        start_date = str(today - timedelta(days=7))
        end_date = str(today)

    use_all_regions = "All Regions" in region_filter or not region_filter

    filtered_signals = []
    for sig in signals:
        sig_date = (sig.get("timestamp") or "")[:10]
        sig_region = sig.get("location", "")
        sig_severity = sig.get("severity") or classify_severity(float(sig.get("raw_score") or 0))

        if not (start_date <= sig_date <= end_date):
            continue
        if not use_all_regions and sig_region not in region_filter:
            continue
        if sig_severity not in severity_filter:
            continue

        filtered_signals.append(sig)

    st.markdown(f"**{len(filtered_signals)}** signals match filters.")

    if filtered_signals:
        # Build preview DataFrame
        preview_rows = []
        for sig in filtered_signals[:100]:  # Limit preview to 100 rows
            preview_rows.append({
                "Timestamp": sig.get("timestamp", "")[:19],
                "Region": sig.get("location", "Unknown"),
                "Source": sig.get("source", "Unknown"),
                "Type": sig.get("type", "Unknown"),
                "Score": round(float(sig.get("raw_score") or 0), 1),
                "Severity": sig.get("severity") or classify_severity(float(sig.get("raw_score") or 0)),
                "Title": (sig.get("title") or sig.get("description") or "")[:80],
            })

        df_preview = pd.DataFrame(preview_rows)
        if len(filtered_signals) > 100:
            st.info(f"Showing first 100 of {len(filtered_signals)} signals in preview.")
        st.dataframe(df_preview, use_container_width=True, hide_index=True)

        # Export buttons
        dl_col1, dl_col2 = st.columns(2)

        with dl_col1:
            df_export = pd.DataFrame(preview_rows)
            csv_data = df_export.to_csv(index=False)
            st.download_button(
                label="⬇️ Download as CSV",
                data=csv_data,
                file_name=f"orras_signals_{today}.csv",
                mime="text/csv",
                use_container_width=True,
            )

        with dl_col2:
            # Export as JSON (full signal data for matching signals)
            json_export_data = []
            for sig in filtered_signals:
                json_export_data.append({
                    "id": sig.get("id"),
                    "timestamp": sig.get("timestamp"),
                    "location": sig.get("location"),
                    "source": sig.get("source"),
                    "type": sig.get("type"),
                    "raw_score": sig.get("raw_score"),
                    "severity": sig.get("severity"),
                    "title": sig.get("title"),
                    "description": sig.get("description"),
                    "keywords_matched": sig.get("keywords_matched", []),
                })
            json_str = json.dumps(json_export_data, indent=2, ensure_ascii=False)
            st.download_button(
                label="⬇️ Download as JSON",
                data=json_str,
                file_name=f"orras_signals_{today}.json",
                mime="application/json",
                use_container_width=True,
            )
    else:
        st.warning("⚠️ No signals match the current filters.")

# ============================================================================
# TAB 3: Alert History
# ============================================================================

with tab3:
    st.markdown("### 🔔 Alert History")

    alert_log = load_alert_log()

    if not alert_log:
        st.info(
            "📭 No alert history found. "
            "Run the main dashboard to generate alerts, then return here."
        )
    else:
        # Filters
        ah_col1, ah_col2, ah_col3 = st.columns(3)

        with ah_col1:
            ah_region_filter = st.multiselect(
                "Filter by Region",
                options=["All"] + sorted({a.get("region", "Unknown") for a in alert_log}),
                default=["All"],
                key="ah_region",
            )
        with ah_col2:
            ah_severity_filter = st.multiselect(
                "Filter by Severity",
                options=all_severities,
                default=all_severities,
                key="ah_severity",
            )
        with ah_col3:
            ah_date_range = st.date_input(
                "Date Range",
                value=(today - timedelta(days=30), today),
                key="ah_date_range",
            )

        try:
            if isinstance(ah_date_range, (list, tuple)) and len(ah_date_range) == 2:
                ah_start, ah_end = str(ah_date_range[0]), str(ah_date_range[1])
            else:
                ah_start = str(today - timedelta(days=30))
                ah_end = str(today)
        except Exception:
            ah_start = str(today - timedelta(days=30))
            ah_end = str(today)

        use_all_ah_regions = "All" in ah_region_filter or not ah_region_filter

        filtered_alerts = []
        for alert in alert_log:
            a_date = (alert.get("timestamp") or "")[:10]
            a_region = alert.get("region", "Unknown")
            a_severity = alert.get("max_severity") or alert.get("severity") or "LOW"

            if not (ah_start <= a_date <= ah_end):
                continue
            if not use_all_ah_regions and a_region not in ah_region_filter:
                continue
            if a_severity not in ah_severity_filter:
                continue

            filtered_alerts.append(alert)

        # Stats bar
        st.markdown(f"**{len(filtered_alerts)}** alerts match filters (of {len(alert_log)} total)")
        sev_counts = {}
        for a in filtered_alerts:
            sev = a.get("max_severity") or a.get("severity") or "LOW"
            sev_counts[sev] = sev_counts.get(sev, 0) + 1

        if sev_counts:
            stat_cols = st.columns(4)
            sev_colors = {"CRITICAL": "#ef4444", "HIGH": "#f97316", "MEDIUM": "#eab308", "LOW": "#22c55e"}
            for i, sev in enumerate(["CRITICAL", "HIGH", "MEDIUM", "LOW"]):
                with stat_cols[i]:
                    count = sev_counts.get(sev, 0)
                    st.markdown(
                        render_metric_card(
                            title=sev,
                            value=str(count),
                            subtitle="alerts",
                            color=sev_colors.get(sev, "#9ca3af"),
                        ),
                        unsafe_allow_html=True,
                    )

        # Bar chart: alerts by severity
        if sev_counts:
            fig_bar = go.Figure(
                go.Bar(
                    x=list(sev_counts.keys()),
                    y=list(sev_counts.values()),
                    marker_color=[sev_colors.get(s, "#9ca3af") for s in sev_counts],
                    text=list(sev_counts.values()),
                    textposition="auto",
                )
            )
            fig_bar.update_layout(
                title="Alert Distribution by Severity",
                xaxis_title="Severity",
                yaxis_title="Count",
                **_CHART_LAYOUT,
            )
            st.plotly_chart(fig_bar, use_container_width=True)

        # Alert table
        if filtered_alerts:
            alert_rows = []
            for a in sorted(filtered_alerts, key=lambda x: x.get("timestamp", ""), reverse=True):
                alert_rows.append({
                    "Timestamp": (a.get("timestamp") or "")[:19],
                    "Region": a.get("region", "Unknown"),
                    "Severity": a.get("max_severity") or a.get("severity") or "LOW",
                    "Recommendation": a.get("recommendation") or a.get("action", "—"),
                    "Signal Count": a.get("signal_count", "—"),
                })
            df_alerts = pd.DataFrame(alert_rows)
            st.dataframe(df_alerts, use_container_width=True, hide_index=True)

            # Export
            csv_alerts = df_alerts.to_csv(index=False)
            st.download_button(
                label="⬇️ Export Alert History as CSV",
                data=csv_alerts,
                file_name=f"orras_alerts_{today}.csv",
                mime="text/csv",
            )
        else:
            st.warning("No alerts match the current filters.")

# ============================================================================
# TAB 4: Custom Report
# ============================================================================

with tab4:
    st.markdown("### 🛠️ Custom Report Builder")
    st.markdown("Select report sections, region scope, and date range to generate a tailored PDF.")

    cr_col1, cr_col2 = st.columns(2)

    with cr_col1:
        st.markdown("**📋 Report Sections**")
        inc_executive = st.checkbox("Executive Summary", value=True, key="cr_exec")
        inc_top_regions = st.checkbox("Top Threat Regions", value=True, key="cr_top")
        inc_sources = st.checkbox("Signal Source Breakdown", value=True, key="cr_src")
        inc_anomalies = st.checkbox("Anomaly Alerts", value=True, key="cr_anom")
        inc_escalations = st.checkbox("Escalation Events", value=True, key="cr_esc")
        inc_forecast = st.checkbox("3-Day Forecast", value=False, key="cr_fore")
        inc_safety = st.checkbox("Safety Intelligence Scorecard", value=False, key="cr_safe")
        inc_appendix = st.checkbox("Signal Appendix (CRITICAL/HIGH)", value=True, key="cr_app")

    with cr_col2:
        st.markdown("**🌍 Scope**")
        cr_region_options = ["All Regions"] + all_regions
        cr_regions = st.multiselect(
            "Include Regions (leave blank for all)",
            options=cr_region_options,
            default=["All Regions"],
            key="cr_regions",
        )

        cr_date_range = st.date_input(
            "Report Date Range",
            value=(today - timedelta(days=7), today),
            key="cr_date_range",
        )

        cr_min_severity = st.selectbox(
            "Minimum Severity",
            options=["LOW", "MEDIUM", "HIGH", "CRITICAL"],
            index=1,
            key="cr_min_sev",
        )

    st.markdown("---")
    generate_custom = st.button(
        "🛠️ Generate Custom PDF Report",
        use_container_width=True,
        key="gen_custom_report",
    )

    if generate_custom:
        # Apply regional and date scope filters
        try:
            if isinstance(cr_date_range, (list, tuple)) and len(cr_date_range) == 2:
                cr_start, cr_end = str(cr_date_range[0]), str(cr_date_range[1])
            else:
                cr_start = str(today - timedelta(days=7))
                cr_end = str(today)
        except Exception:
            cr_start = str(today - timedelta(days=7))
            cr_end = str(today)

        use_all_cr_regions = "All Regions" in cr_regions or not cr_regions
        _sev_order = {"LOW": 0, "MEDIUM": 1, "HIGH": 2, "CRITICAL": 3}
        min_sev_rank = _sev_order.get(cr_min_severity, 1)

        custom_signals = [
            s for s in signals
            if (use_all_cr_regions or s.get("location") in cr_regions)
            and cr_start <= (s.get("timestamp") or "")[:10] <= cr_end
            and _sev_order.get(
                s.get("severity") or classify_severity(float(s.get("raw_score") or 0)), 0
            ) >= min_sev_rank
        ]

        if not custom_signals:
            st.warning("⚠️ No signals match the selected scope. Widening scope to all signals.")
            custom_signals = signals

        with st.spinner("Building custom PDF report…"):
            try:
                cr_forecasts = load_forecasts(len(signals)) if inc_forecast else {}
                cr_safety_data = load_safety(len(signals)) if inc_safety else {}

                # Use escalations only if requested
                cr_escalations = escalations if inc_escalations else []
                cr_anomalies = anomalies if inc_anomalies else []

                report_engine = ReportEngine()
                pdf_bytes = report_engine.generate_daily_report(
                    signals=custom_signals,
                    anomalies=cr_anomalies,
                    escalations=cr_escalations,
                    forecasts=cr_forecasts,
                    safety=cr_safety_data,
                )
                cr_filename = report_engine.get_report_filename().replace(
                    "ORRAS_Report", "ORRAS_Custom_Report"
                )

                st.session_state.custom_report_bytes = pdf_bytes
                st.session_state.custom_report_filename = cr_filename
                st.success(f"✅ Custom report generated: **{cr_filename}**")

            except Exception as e:
                st.error(f"❌ Custom report generation failed: {e}")

    if "custom_report_bytes" in st.session_state and st.session_state.custom_report_bytes:
        size_kb = len(st.session_state.custom_report_bytes) / 1024
        st.markdown(
            f'<div style="background:#111827;border:1px solid #3b82f644;border-radius:12px;'
            f'padding:1rem;margin:1rem 0;">'
            f'<b style="color:#93c5fd;">📄 Custom Report Ready</b><br>'
            f'<span style="color:#d1d5db;">File: '
            f'{st.session_state.get("custom_report_filename", "report.pdf")}</span><br>'
            f'<span style="color:#9ca3af;">Size: {size_kb:.1f} KB</span>'
            f'</div>',
            unsafe_allow_html=True,
        )
        st.download_button(
            label="⬇️ Download Custom PDF Report",
            data=st.session_state.custom_report_bytes,
            file_name=st.session_state.get("custom_report_filename", "ORRAS_Custom_Report.pdf"),
            mime="application/pdf",
            use_container_width=True,
        )

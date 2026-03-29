"""
app.py — ORRAS v2.0 Advanced Dashboard.

Orchestrates the full data pipeline and renders an advanced, dark-themed
real-time risk assessment dashboard with 3D globe, AI SITREP, safety
index, forecasting, and live signal feed.
"""

from __future__ import annotations

import traceback
from datetime import datetime, timezone

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

# ── Page config must be the first Streamlit call ────────────────────────────
st.set_page_config(
    page_title="ORRAS v2.0",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Load custom CSS ──────────────────────────────────────────────────────────
try:
    with open("assets/custom.css", "r", encoding="utf-8") as _css_file:
        st.markdown(f"<style>{_css_file.read()}</style>", unsafe_allow_html=True)
except FileNotFoundError:
    pass  # CSS is cosmetic; proceed without it

# ── Severity helpers ─────────────────────────────────────────────────────────
SEV_COLORS = {
    "CRITICAL": "#ef4444",
    "HIGH":     "#f97316",
    "MEDIUM":   "#eab308",
    "LOW":      "#22c55e",
}
SEV_ORDER = {"CRITICAL": 0, "HIGH": 1, "MEDIUM": 2, "LOW": 3}


# ── Data pipeline ─────────────────────────────────────────────────────────────

@st.cache_data(ttl=60)
def run_pipeline():
    """
    Execute the full ORRAS data pipeline.

    Returns:
        Tuple: (signals, anomalies, escalation_data, actions, status_map, conf_map,
                active_alerts)
    """
    from data_collector import DataCollectionOrchestrator
    from data_processor import DataProcessor
    from threat_engine import ThreatEngine
    from correlation_engine import CorrelationEngine
    from anomaly_engine import AnomalyEngine
    from escalation_tracker import EscalationTracker
    from confidence_engine import ConfidenceEngine
    from action_engine import ActionEngine
    from classifier_engine import ClassifierEngine
    from weight_engine import WeightEngine
    from disaster_engine import DisasterEngine
    from fusion_engine import FusionEngine
    from geofence_engine import GeofenceEngine
    from alert_engine import AlertEngine

    raw = DataCollectionOrchestrator().collect_all()
    status_map = raw.pop("_status", {})

    signals = DataProcessor().process_all(raw)
    signals = ThreatEngine().score_all(signals)
    signals = CorrelationEngine().correlate_all(signals)
    anomalies = AnomalyEngine().detect_anomalies(signals)
    escalation_data = EscalationTracker().run(signals)

    # Part 2 enrichment engines
    signals = ClassifierEngine().classify_all(signals)
    signals = WeightEngine().apply_weights(signals)
    signals = DisasterEngine().score_all(signals)
    signals = FusionEngine().fuse_all(signals)
    signals = GeofenceEngine().tag_all(signals)

    conf_engine = ConfidenceEngine()
    conf_map = conf_engine.score_confidence(signals)
    signals = conf_engine.annotate_signals(signals, conf_map)

    actions = ActionEngine().generate_region_actions(signals)

    active_alerts = AlertEngine().generate_alerts(signals)

    return signals, anomalies, escalation_data, actions, status_map, conf_map, active_alerts


@st.cache_data(ttl=60)
def run_safety_pipeline(signals_tuple):
    """
    Score all safety categories and compute the overall safety index.

    Args:
        signals_tuple: Tuple-converted signals for cache-key hashing.

    Returns:
        Tuple: (category_scores dict, overall_index dict)
    """
    from safety_engine import SafetyEngine

    signals = list(signals_tuple)
    se = SafetyEngine()
    scores = se.score_all_categories(signals)
    overall = se.compute_overall_safety_index(scores)
    return scores, overall


@st.cache_data(ttl=300)
def run_forecast_pipeline():
    """
    Generate risk forecasts for all tracked regions.

    Returns:
        Tuple: (forecasts dict, high_risk_outlook list)
    """
    from escalation_tracker import EscalationTracker
    from prediction_engine import PredictionEngine

    history = EscalationTracker().load_history()
    pe = PredictionEngine()
    forecasts = pe.forecast_all_regions(history)
    outlook = pe.get_high_risk_outlook(forecasts)
    return forecasts, outlook


@st.cache_data(ttl=120)
def run_disaster_pipeline(signals_tuple):
    """
    Compute disaster hotspots and a composite disaster index.

    Args:
        signals_tuple: Tuple-converted signals for cache-key hashing.

    Returns:
        Tuple: (hotspots list, disaster_index dict)
    """
    from disaster_engine import DisasterEngine

    signals = list(signals_tuple)
    de = DisasterEngine()
    hotspots = de.get_disaster_hotspots(signals)
    disaster_index = de.compute_disaster_index(signals)
    return hotspots, disaster_index


# ── Sidebar ───────────────────────────────────────────────────────────────────

def _render_sidebar(status_map: dict, last_updated: str) -> tuple[str, bool]:
    """
    Render the sidebar and return (theme, auto_refresh_enabled).
    """
    with st.sidebar:
        st.markdown(
            '<div style="text-align:center;padding:1rem 0 0.5rem;">'
            '<span style="font-size:2.5rem;">🛡️</span>'
            '<div style="font-size:1.4rem;font-weight:800;color:#f9fafb;'
            'letter-spacing:-0.02em;margin-top:0.2rem;">ORRAS v2.0</div>'
            '<div style="font-size:0.75rem;color:#6b7280;letter-spacing:0.08em;'
            'text-transform:uppercase;">Operational Risk Assessment</div>'
            '</div>',
            unsafe_allow_html=True,
        )
        st.divider()

        theme = st.radio(
            "🎨 Theme",
            options=["Dark", "Light"],
            horizontal=True,
            index=0,
        )

        auto_refresh = st.toggle("🔄 Auto-refresh (60 s)", value=False)

        st.divider()
        st.markdown(
            '<div style="font-size:0.75rem;font-weight:700;text-transform:uppercase;'
            'letter-spacing:0.08em;color:#9ca3af;margin-bottom:0.5rem;">'
            '📡 Data Sources</div>',
            unsafe_allow_html=True,
        )

        _source_labels = {
            "newsapi":   "NewsAPI",
            "gdelt":     "GDELT",
            "opensky":   "OpenSky Network",
            "firms":     "NASA FIRMS",
            "netblocks": "NetBlocks",
            "social":    "Social Media",
        }

        try:
            from ui_components import render_source_health_badge

            if status_map:
                for key, label in _source_labels.items():
                    is_live = status_map.get(key, False)
                    st.markdown(
                        render_source_health_badge(label, bool(is_live)),
                        unsafe_allow_html=True,
                    )
            else:
                for label in _source_labels.values():
                    st.markdown(
                        render_source_health_badge(label, True),
                        unsafe_allow_html=True,
                    )
        except Exception:
            for label in _source_labels.values():
                color = "#22c55e"
                st.markdown(
                    f'<div style="display:flex;align-items:center;gap:8px;'
                    f'padding:4px 0;font-size:0.82rem;color:#d1d5db;">'
                    f'<span style="width:8px;height:8px;border-radius:50%;'
                    f'background:{color};display:inline-block;"></span>'
                    f'{label}</div>',
                    unsafe_allow_html=True,
                )

        st.divider()
        st.markdown(
            f'<div style="font-size:0.72rem;color:#6b7280;">'
            f'🕐 Last updated<br>'
            f'<span style="color:#9ca3af;">{last_updated}</span></div>',
            unsafe_allow_html=True,
        )

    return theme, auto_refresh


# ── KPI row ───────────────────────────────────────────────────────────────────

def _render_kpi_row(
    signals: list,
    anomalies: list,
    overall_safety: dict,
    conf_map: dict,
) -> None:
    """Render the six headline KPI metric cards."""
    total_signals = len(signals)
    critical_regions = len({
        s.get("location", "") for s in signals
        if str(s.get("severity", "")).upper() == "CRITICAL"
    })
    active_anomalies = len(anomalies) if anomalies else 0
    safety_grade = overall_safety.get("safety_grade", "N/A") if overall_safety else "N/A"
    safety_score = overall_safety.get("overall_score", 0.0) if overall_safety else 0.0

    if conf_map:
        avg_conf = sum(
            v.get("confidence_score", 0.0) for v in conf_map.values()
        ) / len(conf_map) * 100
    else:
        avg_conf = 0.0

    regions_monitored = len({s.get("location", "") for s in signals})

    try:
        from ui_components import render_metric_card

        cols = st.columns(6)
        metrics = [
            ("Total Signals", str(total_signals), "Live feed", "#3b82f6"),
            ("Critical Regions", str(critical_regions), "Active warnings", "#ef4444"),
            ("Active Anomalies", str(active_anomalies), "Detected", "#f97316"),
            ("Safety Grade", f"Grade {safety_grade}", f"{safety_score:.0f}/100", "#22c55e"),
            ("Avg Confidence", f"{avg_conf:.0f}%", "Multi-source", "#8b5cf6"),
            ("Regions Monitored", str(regions_monitored), "Worldwide", "#06b6d4"),
        ]
        for col, (title, value, subtitle, color) in zip(cols, metrics):
            with col:
                st.markdown(
                    render_metric_card(title, value, subtitle, color),
                    unsafe_allow_html=True,
                )
    except Exception:
        cols = st.columns(6)
        with cols[0]:
            st.metric("📡 Total Signals", total_signals)
        with cols[1]:
            st.metric("🚨 Critical Regions", critical_regions)
        with cols[2]:
            st.metric("⚡ Anomalies", active_anomalies)
        with cols[3]:
            st.metric("🔒 Safety Grade", f"Grade {safety_grade}")
        with cols[4]:
            st.metric("🎯 Avg Confidence", f"{avg_conf:.0f}%")
        with cols[5]:
            st.metric("🌍 Regions", regions_monitored)


# ── 3-D Globe ─────────────────────────────────────────────────────────────────

def _render_globe(signals: list) -> None:
    """Render the orthographic 3D globe with signal markers."""
    from mock_data_generator import COUNTRY_COORDS

    lats, lons, sizes, colors, hover_texts = [], [], [], [], []

    for sig in signals:
        location = sig.get("location", "")
        coords = COUNTRY_COORDS.get(location)
        if coords is None:
            continue
        lat, lon = coords
        raw_score = float(sig.get("raw_score") or 0.0)
        severity = str(sig.get("severity", "LOW")).upper()
        title = sig.get("title", "No title")

        # Normalise score to marker size [5, 30]
        size = max(5.0, min(30.0, 5.0 + (raw_score / 30.0) * 25.0))

        lats.append(lat)
        lons.append(lon)
        sizes.append(size)
        colors.append(SEV_COLORS.get(severity, "#22c55e"))
        hover_texts.append(
            f"<b>{location}</b><br>"
            f"Severity: {severity}<br>"
            f"Score: {raw_score:.1f}<br>"
            f"{title[:80]}"
        )

    if not lats:
        st.info("No georeferenced signals to display on the globe.")
        return

    fig = go.Figure(
        go.Scattergeo(
            lat=lats,
            lon=lons,
            mode="markers",
            marker=dict(
                size=sizes,
                color=colors,
                opacity=0.8,
                line=dict(color="white", width=0.5),
            ),
            text=hover_texts,
            hoverinfo="text",
        )
    )
    fig.update_geos(
        projection_type="orthographic",
        showland=True,
        landcolor="#1a2332",
        showocean=True,
        oceancolor="#0d1b2a",
        showlakes=True,
        lakecolor="#0d1b2a",
        showcountries=True,
        countrycolor="#2d3748",
        bgcolor="#0a0e1a",
    )
    fig.update_layout(
        paper_bgcolor="#0a0e1a",
        plot_bgcolor="#0a0e1a",
        margin=dict(l=0, r=0, t=0, b=0),
        height=600,
    )
    st.plotly_chart(fig, use_container_width=True)


# ── Risk cards row ────────────────────────────────────────────────────────────

def _render_risk_cards(signals: list) -> None:
    """Render the top-6 risk region cards."""
    try:
        from ui_components import render_region_card
    except Exception:
        st.warning("ui_components unavailable — skipping region cards.")
        return

    region_map: dict[str, dict] = {}
    for sig in signals:
        loc = sig.get("location") or "Unknown"
        score = float(sig.get("raw_score") or 0.0)
        sev = str(sig.get("severity", "LOW")).upper()
        entry = region_map.setdefault(
            loc, {"scores": [], "severity": sev, "confidence": "LOW (50%)"}
        )
        entry["scores"].append(score)
        # Promote severity if higher
        if SEV_ORDER.get(sev, 3) < SEV_ORDER.get(entry["severity"], 3):
            entry["severity"] = sev
        if sig.get("confidence"):
            entry["confidence"] = str(sig["confidence"])

    top_regions = sorted(
        [
            {
                "region": r,
                "score": sum(d["scores"]) / len(d["scores"]),
                "severity": d["severity"],
                "confidence": d["confidence"],
            }
            for r, d in region_map.items()
        ],
        key=lambda x: x["score"],
        reverse=True,
    )[:6]

    cols = st.columns(min(len(top_regions), 6))
    for col, reg in zip(cols, top_regions):
        with col:
            trend = "rising" if reg["score"] > 15 else "stable"
            st.markdown(
                render_region_card(
                    region=reg["region"],
                    score=reg["score"],
                    severity=reg["severity"],
                    trend=trend,
                    confidence=reg["confidence"],
                ),
                unsafe_allow_html=True,
            )


# ── Signal feed + Safety index ────────────────────────────────────────────────

def _render_signal_feed(signals: list) -> None:
    """Render the filterable live signal feed dataframe."""
    st.markdown(
        '<div style="font-size:1rem;font-weight:700;color:#f9fafb;margin-bottom:0.5rem;">'
        "📡 Live Signal Feed</div>",
        unsafe_allow_html=True,
    )

    sev_filter = st.multiselect(
        "Filter by severity",
        options=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        default=["CRITICAL", "HIGH", "MEDIUM", "LOW"],
        key="sig_feed_filter",
    )

    rows = []
    for s in signals:
        sev = str(s.get("severity", "LOW")).upper()
        if sev not in sev_filter:
            continue
        rows.append(
            {
                "Location": s.get("location", "Unknown"),
                "Severity": sev,
                "Score": round(float(s.get("raw_score") or 0.0), 1),
                "Source": s.get("source_type", s.get("source", "—")),
                "Title": (s.get("title") or "")[:80],
                "Confidence": s.get("confidence", "—"),
            }
        )

    if not rows:
        st.info("No signals match the selected filters.")
        return

    df = pd.DataFrame(rows).sort_values("Score", ascending=False).reset_index(drop=True)

    def _color_row(row):
        color_map = {
            "CRITICAL": "background-color:#ef444422;color:#fca5a5",
            "HIGH":     "background-color:#f9731622;color:#fdba74",
            "MEDIUM":   "background-color:#eab30822;color:#fde047",
            "LOW":      "background-color:#22c55e22;color:#86efac",
        }
        sev = row.get("Severity", "LOW")
        style = color_map.get(sev, "")
        return [style] * len(row)

    styled = df.style.apply(_color_row, axis=1)
    st.dataframe(styled, use_container_width=True, height=400)


def _render_safety_index(scores: dict, overall: dict) -> None:
    """Render the safety index panel with per-category cards."""
    st.markdown(
        '<div style="font-size:1rem;font-weight:700;color:#f9fafb;margin-bottom:0.5rem;">'
        "🔒 Safety Index</div>",
        unsafe_allow_html=True,
    )

    if overall:
        grade = overall.get("safety_grade", "N/A")
        idx = overall.get("overall_score", 0.0)
        summary = overall.get("summary", "")
        st.markdown(
            f'<div style="background:#111827;border:1px solid #3b82f644;'
            f'border-radius:12px;padding:1rem 1.2rem;margin-bottom:0.8rem;">'
            f'<span style="font-size:1.5rem;font-weight:800;color:#3b82f6;">'
            f'Grade {grade}</span>'
            f'<span style="font-size:0.9rem;color:#9ca3af;margin-left:8px;">'
            f'({idx:.0f}/100)</span>'
            f'<div style="font-size:0.78rem;color:#9ca3af;margin-top:0.3rem;">'
            f'{summary}</div></div>',
            unsafe_allow_html=True,
        )

    try:
        from ui_components import render_safety_score_card
        from safety_engine import SAFETY_CATEGORIES

        for cat_key, cat_data in scores.items():
            cat_name = SAFETY_CATEGORIES.get(cat_key, {}).get("name", cat_key)
            score = float(cat_data.get("score") or 0.0)
            status = str(cat_data.get("status") or "SECURE")
            regions = cat_data.get("regions_affected") or []
            details = (
                [f"Regions affected: {', '.join(regions[:3])}" if regions else "No regions affected"]
                + [f"Signal count: {cat_data.get('signal_count', 0)}"]
                + [f"Trend: {cat_data.get('trend', 'STABLE')}"]
            )
            st.markdown(
                render_safety_score_card(cat_name, score, status, details),
                unsafe_allow_html=True,
            )
    except Exception as exc:
        st.warning(f"Safety index cards unavailable: {exc}")
        if scores:
            for cat_key, cat_data in scores.items():
                st.write(f"**{cat_key}**: {cat_data.get('score', 0):.1f} — {cat_data.get('status', '?')}")


# ── Action panel ──────────────────────────────────────────────────────────────

def _render_action_panel(actions: list) -> None:
    """Render recommended actions grouped by region with severity expanders."""
    st.markdown("### ⚡ Recommended Actions")

    try:
        from ui_components import render_alert_banner

        high_critical = [
            a for a in actions
            if str(a.get("severity", "")).upper() in ("HIGH", "CRITICAL")
        ]
        if high_critical:
            alert_texts = [
                f"{a.get('region', '?')}: {a.get('recommendation', '')}"
                for a in high_critical[:5]
            ]
            top_sev = "CRITICAL" if any(
                str(a.get("severity", "")).upper() == "CRITICAL" for a in high_critical
            ) else "HIGH"
            st.markdown(
                render_alert_banner(alert_texts, top_sev),
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    region_actions: dict[str, list] = {}
    for action in actions:
        region = action.get("region") or "Unknown"
        region_actions.setdefault(region, []).append(action)

    for region, region_acts in sorted(
        region_actions.items(),
        key=lambda x: SEV_ORDER.get(
            str(x[1][0].get("severity", "LOW")).upper(), 3
        ),
    ):
        top_sev = str(region_acts[0].get("severity", "LOW")).upper()
        color = SEV_COLORS.get(top_sev, "#9ca3af")
        label = f"{region} [{top_sev}]"
        with st.expander(label):
            for act in region_acts:
                sev = str(act.get("severity", "LOW")).upper()
                rec = act.get("recommendation") or act.get("action") or str(act)
                st.markdown(
                    f'<div style="border-left:3px solid {SEV_COLORS.get(sev, color)}; '
                    f'padding:6px 10px;margin:4px 0;font-size:0.85rem;">'
                    f'<b style="color:{SEV_COLORS.get(sev, color)};">[{sev}]</b> {rec}'
                    f'</div>',
                    unsafe_allow_html=True,
                )


# ── AI Global SITREP ──────────────────────────────────────────────────────────

def _render_ai_sitrep(signals: list, anomalies: list) -> None:
    """Render the AI SITREP generator section."""
    st.markdown("### 🤖 AI Global Situation Report")

    if "last_sitrep" not in st.session_state:
        st.session_state["last_sitrep"] = None

    col_btn, col_info = st.columns([1, 4])
    with col_btn:
        generate = st.button("🤖 Generate AI Situation Report", type="primary")

    if generate:
        with st.spinner("Generating SITREP…"):
            try:
                from ai_assistant import generate_global_sitrep

                sitrep = generate_global_sitrep(signals, anomalies)
                st.session_state["last_sitrep"] = sitrep
            except Exception as exc:
                st.error(f"SITREP generation failed: {exc}")

    if st.session_state["last_sitrep"]:
        ts = datetime.now(timezone.utc).strftime("%d %b %Y %H%MZ")
        st.markdown(
            f'<div style="background:#0d1117;border:1px solid #3b82f644;'
            f'border-radius:16px;padding:1.5rem 1.8rem;margin-top:0.8rem;'
            f'font-family:\'JetBrains Mono\',\'Fira Code\',monospace;'
            f'font-size:0.85rem;line-height:1.7;color:#e2e8f0;'
            f'white-space:pre-wrap;">'
            f'<div style="font-size:0.7rem;color:#6b7280;margin-bottom:0.8rem;'
            f'text-transform:uppercase;letter-spacing:0.1em;">ORRAS-AI • {ts}</div>'
            f'{st.session_state["last_sitrep"]}'
            f'</div>',
            unsafe_allow_html=True,
        )


# ── Footer ────────────────────────────────────────────────────────────────────

def _render_footer(signals: list, anomalies: list, escalation_data: dict) -> None:
    """Render the page footer with download button and metadata."""
    st.divider()
    col_sources, col_dl, col_info = st.columns([2, 1, 1])

    with col_sources:
        st.markdown(
            '<div style="font-size:0.78rem;color:#6b7280;">'
            "<b style='color:#9ca3af;'>Data Sources:</b> NewsAPI · GDELT · "
            "OpenSky Network · NASA FIRMS · NetBlocks · Social Media Feeds"
            "</div>",
            unsafe_allow_html=True,
        )

    with col_dl:
        try:
            from report_engine import ReportEngine
            from safety_engine import SafetyEngine

            if st.button("📥 Download Full Report"):
                with st.spinner("Generating report…"):
                    try:
                        se = SafetyEngine()
                        safety_scores = se.score_all_categories(signals)
                        overall = se.compute_overall_safety_index(safety_scores)

                        from escalation_tracker import EscalationTracker
                        from prediction_engine import PredictionEngine

                        history = EscalationTracker().load_history()
                        forecasts = PredictionEngine().forecast_all_regions(history)

                        report_bytes = ReportEngine().generate_daily_report(
                            signals=signals,
                            anomalies=anomalies or [],
                            escalations=escalation_data.get("escalation_alerts", []),
                            safety={"scores": safety_scores, "overall": overall},
                            forecasts=forecasts,
                        )
                        filename = ReportEngine().get_report_filename()
                        st.download_button(
                            label="💾 Save PDF",
                            data=report_bytes,
                            file_name=filename,
                            mime="application/pdf",
                        )
                    except Exception as exc:
                        st.error(f"Report generation failed: {exc}")
        except Exception:
            st.caption("Report engine unavailable.")

    with col_info:
        st.markdown(
            '<div style="font-size:0.78rem;color:#6b7280;text-align:right;">'
            '<a href="https://github.com/your-org/ORRAS" '
            'style="color:#3b82f6;text-decoration:none;">🔗 GitHub</a>'
            " · ORRAS v2.0"
            "</div>",
            unsafe_allow_html=True,
        )


# ── Fusion & Alerts panel ─────────────────────────────────────────────────────

def _render_fusion_and_alerts_panel(signals: list, active_alerts: list) -> None:
    """Render the Active Alerts and Geofence Triggers sections."""
    col_alerts, col_geo = st.columns(2)

    with col_alerts:
        st.markdown("#### 🚨 Active Alerts")
        if active_alerts:
            total = len(active_alerts)
            critical = sum(1 for a in active_alerts if a.get("severity") == "CRITICAL")
            high = sum(1 for a in active_alerts if a.get("severity") == "HIGH")
            st.markdown(
                f'<div style="padding:0.6rem 1rem;border-radius:8px;'
                f'background:#1f2937;border:1px solid #374151;margin-bottom:0.5rem;">'
                f'<span style="color:#f9fafb;font-weight:700;">{total}</span>'
                f'<span style="color:#9ca3af;"> total · </span>'
                f'<span style="color:#ef4444;font-weight:700;">{critical} CRITICAL</span>'
                f'<span style="color:#9ca3af;"> · </span>'
                f'<span style="color:#f97316;font-weight:700;">{high} HIGH</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            for alert in active_alerts[:5]:
                sev = alert.get("severity", "LOW")
                color = SEV_COLORS.get(sev, "#6b7280")
                title = alert.get("title", alert.get("region", "Unknown"))
                st.markdown(
                    f'<div style="padding:0.4rem 0.8rem;border-left:3px solid {color};'
                    f'margin-bottom:4px;font-size:0.82rem;color:#e2e8f0;">'
                    f'<b style="color:{color};">[{sev}]</b> {title}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No active alerts.")

    with col_geo:
        st.markdown("#### 🌐 Geofence Triggers")
        critical_zone_signals = [s for s in signals if s.get("in_critical_zone")]
        if critical_zone_signals:
            st.caption(f"{len(critical_zone_signals)} signal(s) inside critical zones")
            for sig in critical_zone_signals[:5]:
                zones = ", ".join(sig.get("geofence_zones", []))
                region = sig.get("region", "Unknown")
                sev = sig.get("severity", "LOW")
                color = SEV_COLORS.get(sev, "#6b7280")
                st.markdown(
                    f'<div style="padding:0.4rem 0.8rem;border-left:3px solid {color};'
                    f'margin-bottom:4px;font-size:0.82rem;color:#e2e8f0;">'
                    f'<b>{region}</b>'
                    f'<span style="color:#9ca3af;font-size:0.75rem;"> · {zones}</span>'
                    f'</div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No signals in critical zones.")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    """Entry point — assembles the full ORRAS v2.0 dashboard."""

    last_updated = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

    # ── Run core pipeline ────────────────────────────────────────────────────
    signals: list = []
    anomalies: list = []
    escalation_data: dict = {}
    actions: list = []
    status_map: dict = {}
    conf_map: dict = {}
    active_alerts: list = []
    pipeline_error: str | None = None

    try:
        signals, anomalies, escalation_data, actions, status_map, conf_map, active_alerts = run_pipeline()
        # Persist outside the cached function to avoid duplicate insertions
        try:
            from database_engine import DatabaseEngine
            db = DatabaseEngine()
            db.insert_signals(signals)
            for _alert in active_alerts:
                db.insert_alert(_alert)
        except Exception as db_exc:  # noqa: BLE001
            st.warning(f"DB persistence skipped: {db_exc}")
    except Exception:
        pipeline_error = traceback.format_exc()

    # ── Run safety pipeline ──────────────────────────────────────────────────
    safety_scores: dict = {}
    overall_safety: dict = {}

    try:
        safety_scores, overall_safety = run_safety_pipeline(tuple(
            tuple(sorted(s.items())) for s in signals
        ))
    except Exception:
        pass

    # ── Sidebar ──────────────────────────────────────────────────────────────
    theme, auto_refresh = _render_sidebar(status_map, last_updated)

    # ── Auto-refresh ─────────────────────────────────────────────────────────
    if auto_refresh:
        try:
            from streamlit_autorefresh import st_autorefresh

            st_autorefresh(interval=60_000, limit=None, key="orras_autorefresh")
        except ImportError:
            st.sidebar.warning("streamlit-autorefresh not installed.")

    # ── Page header ──────────────────────────────────────────────────────────
    st.markdown(
        """
<div style="margin-bottom:1rem;">
  <!-- Classification banner -->
  <div style="
      background:#0a0000;
      border:1px solid #1a0000;
      text-align:center;
      padding:4px;
      font-family:'Courier New',monospace;
      font-size:0.65rem;
      letter-spacing:4px;
      text-transform:uppercase;
      color:#ff4444;
      margin-bottom:8px;
  ">UNCLASSIFIED // OPEN SOURCE INTELLIGENCE</div>

  <!-- Main header bar -->
  <div style="
      background:linear-gradient(135deg,#000000,#050510);
      border:1px solid #1a3a5c;
      border-left:4px solid #00d4ff;
      padding:16px 20px;
      display:flex;align-items:center;justify-content:space-between;
  ">
    <div style="display:flex;align-items:center;gap:12px;">
      <span style="
          display:inline-block;width:10px;height:10px;
          border-radius:50%;background:#00ff88;
          box-shadow:0 0 10px #00ff88;
          animation:blink 1s infinite;
          flex-shrink:0;
      "></span>
      <div>
        <div style="
            font-family:'Courier New',monospace;
            font-size:1.5rem;font-weight:700;
            color:#00d4ff;
            text-shadow:0 0 20px rgba(0,212,255,0.6);
            letter-spacing:2px;
        ">ORRAS INTELLIGENCE SYSTEM v3.0</div>
        <div style="
            font-family:'Courier New',monospace;
            font-size:0.65rem;
            color:#7090a0;
            letter-spacing:3px;
            text-transform:uppercase;
            margin-top:2px;
        ">Operational Risk &amp; Resilience Assessment System</div>
      </div>
    </div>
    <div id="orras-clock" style="
        font-family:'Courier New',monospace;
        font-size:0.75rem;
        color:#7090a0;
        letter-spacing:1px;
        text-align:right;
    ">
      <div style="color:#4a6a7a;font-size:0.6rem;letter-spacing:2px;text-transform:uppercase;">Last Updated</div>
      <div style="color:#00d4ff;" id="orras-ts">""" + last_updated + """</div>
    </div>
  </div>
</div>
<script>
(function() {
  function pad(n){return n<10?'0'+n:n;}
  function tick(){
    var d=new Date();
    var ts=pad(d.getUTCHours())+':'+pad(d.getUTCMinutes())+':'+pad(d.getUTCSeconds())+' UTC';
    var el=document.getElementById('orras-ts');
    if(el){el.textContent=ts;}
  }
  tick();
  setInterval(tick,1000);
})();
</script>
""",
        unsafe_allow_html=True,
    )

    # ── Pipeline error banner ─────────────────────────────────────────────────
    if pipeline_error:
        with st.expander("⚠️ Pipeline error — showing partial data", expanded=False):
            st.code(pipeline_error)

    # ── News Ticker ───────────────────────────────────────────────────────────
    try:
        from news_ticker import NewsTicker

        ticker = NewsTicker()
        headlines = ticker.get_ticker_headlines(signals)
        if headlines:
            st.markdown(ticker.format_ticker_html(headlines), unsafe_allow_html=True)
    except Exception:
        pass

    # ── Critical alert banner ─────────────────────────────────────────────────
    try:
        from ui_components import render_alert_banner

        critical_alerts = [
            s["title"] for s in signals if s.get("severity") == "CRITICAL"
        ][:5]
        if critical_alerts:
            st.markdown(
                render_alert_banner(critical_alerts, "CRITICAL"),
                unsafe_allow_html=True,
            )
    except Exception:
        pass

    st.markdown("<br>", unsafe_allow_html=True)

    # ── KPI row ──────────────────────────────────────────────────────────────
    _render_kpi_row(signals, anomalies, overall_safety, conf_map)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── 3D Globe ─────────────────────────────────────────────────────────────
    st.markdown("### 🌍 Global Risk Map")
    _render_globe(signals)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Top risk region cards ─────────────────────────────────────────────────
    st.markdown("### 🗺️ Top Risk Regions")
    _render_risk_cards(signals)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Signal feed + Safety index ────────────────────────────────────────────
    col_left, col_right = st.columns([3, 2])
    with col_left:
        _render_signal_feed(signals)
    with col_right:
        _render_safety_index(safety_scores, overall_safety)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Action panel ──────────────────────────────────────────────────────────
    if actions:
        _render_action_panel(actions)
        st.markdown("<br>", unsafe_allow_html=True)

    # ── Fusion & alerts panel ─────────────────────────────────────────────────
    st.markdown("### 🔔 Alerts & Geofence")
    _render_fusion_and_alerts_panel(signals, active_alerts)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── AI Global SITREP ──────────────────────────────────────────────────────
    _render_ai_sitrep(signals, anomalies)

    st.markdown("<br>", unsafe_allow_html=True)

    # ── Footer ────────────────────────────────────────────────────────────────
    _render_footer(signals, anomalies, escalation_data)


if __name__ == "__main__":
    main()

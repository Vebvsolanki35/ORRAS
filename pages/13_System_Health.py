"""
13_System_Health.py — ORRAS System Health & Data Quality

Answers "can I trust what this dashboard is telling me?".

Surfaces:
  - Live source health (LIVE / MOCK / FAILED per collector)
  - A composite data-quality score with per-dimension breakdown
  - Actionable data-quality findings
  - Per-source signal census and severity mix
  - Forecast readiness and escalation-history depth
  - SQLite database statistics and schema integrity
"""

import os

import pandas as pd
import plotly.graph_objects as go
import streamlit as st

st.set_page_config(
    page_title="System Health",
    page_icon="🩺",
    layout="wide",
)

# ---------------------------------------------------------------------------
# Imports
# ---------------------------------------------------------------------------
try:
    from data_collector import DataCollectionOrchestrator
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from data_processor import DataProcessor
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
    from quality_engine import QualityEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from escalation_tracker import EscalationTracker
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from prediction_engine import PredictionEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from database_engine import DatabaseEngine
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from ui_components import render_metric_card
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from config import DB_PATH, MAX_HISTORY_SNAPSHOTS, VERSION_LABEL
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

_CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#111827",
    font_color="#e5e7eb",
    margin=dict(l=40, r=20, t=50, b=40),
)

_Q_COLOR = {
    "A": "#22c55e", "B": "#84cc16", "C": "#eab308",
    "D": "#f97316", "F": "#ef4444", "N/A": "#6b7280",
}


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

@st.cache_data(ttl=60)
def load_health() -> dict:
    """
    Run collection + scoring + quality assessment once and return everything
    the page needs.
    """
    orchestrator = DataCollectionOrchestrator()
    raw = orchestrator.collect_all()
    status = raw.pop("_status", {})

    signals = ThreatEngine().score_all(DataProcessor().process_all(raw))
    quality = QualityEngine().assess(signals)
    anomalies = AnomalyEngine().detect_anomalies(signals)

    return {
        "signals": signals,
        "status": status,
        "quality": quality,
        "anomalies": anomalies,
        "raw_counts": {k: len(v) for k, v in raw.items() if isinstance(v, list)},
    }


@st.cache_data(ttl=120)
def load_forecast_state() -> dict:
    """Report escalation-history depth and forecasting readiness."""
    try:
        history = EscalationTracker().load_history()
        return {
            "history": len(history),
            "readiness": PredictionEngine().forecast_readiness(history),
        }
    except Exception as e:  # noqa: BLE001
        return {"history": 0, "readiness": {}, "error": str(e)}


@st.cache_data(ttl=120)
def load_db_state() -> dict:
    """Report database size, table row counts and schema integrity."""
    try:
        db = DatabaseEngine()
        tables = db.list_tables()
        counts = {t: db.count_rows(t) for t in tables}
        size = os.path.getsize(DB_PATH) if os.path.exists(DB_PATH) else 0
        expected = set(DatabaseEngine.TABLE_SCHEMAS)
        missing_tables = sorted(expected - set(tables))
        return {
            "tables": tables,
            "counts": counts,
            "size_bytes": size,
            "missing_tables": missing_tables,
        }
    except Exception as e:  # noqa: BLE001
        return {"error": str(e)}


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

with st.spinner("Assessing system health…"):
    health = load_health()
    forecast_state = load_forecast_state()
    db_state = load_db_state()

signals = health["signals"]
quality = health["quality"]
status = health["status"]

st.markdown("# 🩺 System Health & Data Quality")
st.markdown(
    "*Trust indicators for the current intelligence picture — "
    "source liveness, signal quality, and pipeline completeness*"
)
st.divider()

# ---------------------------------------------------------------------------
# 1. Headline metrics
# ---------------------------------------------------------------------------

live_count = sum(1 for v in status.values() if str(v).upper() == "LIVE")

m1, m2, m3, m4, m5 = st.columns(5)
with m1:
    st.markdown(render_metric_card(
        "Signals", str(len(signals)), "in current picture", "#3b82f6"
    ), unsafe_allow_html=True)
with m2:
    grade = quality["grade"]
    st.markdown(render_metric_card(
        "Quality Grade", f"Grade {grade}",
        f"{quality['score']:.0f}/100", _Q_COLOR.get(grade, "#6b7280")
    ), unsafe_allow_html=True)
with m3:
    st.markdown(render_metric_card(
        "Live Sources", f"{live_count}/{len(status)}",
        "upstream feeds", "#22c55e" if live_count else "#f97316"
    ), unsafe_allow_html=True)
with m4:
    st.markdown(render_metric_card(
        "Findings", str(len(quality["findings"])),
        "data-quality issues", "#ef4444" if quality["findings"] else "#22c55e"
    ), unsafe_allow_html=True)
with m5:
    st.markdown(render_metric_card(
        "Anomalies", str(len(health["anomalies"])),
        "statistical outliers", "#f97316"
    ), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Source health
# ---------------------------------------------------------------------------

st.markdown("### 📡 Source Health")

if status:
    rows = []
    for source, state in status.items():
        rows.append({
            "Source": source,
            "Status": str(state).upper(),
            "Raw Records": health["raw_counts"].get(source.lower().replace("/mock", ""), 0),
            "Signals": next(
                (v["count"] for k, v in quality["by_source"].items()
                 if k.lower() == source.lower()),
                0,
            ),
        })
    st.dataframe(pd.DataFrame(rows), use_container_width=True, hide_index=True)

    if live_count == 0:
        st.info(
            "ℹ️ No upstream feeds are live — every source is serving synthetic "
            "data. Add API keys to `.env` (see `.env.example`) to switch a "
            "source to LIVE. The platform is fully functional either way."
        )
    elif live_count < len(status):
        st.caption(
            f"{len(status) - live_count} source(s) are on synthetic data. "
            "Configure their API keys to improve fidelity."
        )
else:
    st.warning("Source health report unavailable.")

st.divider()

# ---------------------------------------------------------------------------
# 3. Data quality dimensions
# ---------------------------------------------------------------------------

st.markdown("### 🔬 Data Quality Dimensions")

dims = quality["dimensions"]
if dims:
    labels = {
        "completeness": "Completeness",
        "geolocation": "Geolocation",
        "freshness": "Freshness",
        "uniqueness": "Uniqueness",
        "diversity": "Source Diversity",
    }
    names = [labels.get(k, k.title()) for k in dims]
    values = [dims[k]["score"] for k in dims]
    weights = [QualityEngine.WEIGHTS[k] for k in dims]

    fig = go.Figure(go.Bar(
        x=names,
        y=values,
        marker_color=[
            "#22c55e" if v >= 80 else "#eab308" if v >= 60 else "#ef4444"
            for v in values
        ],
        text=[f"{v:.0f}" for v in values],
        textposition="outside",
        hovertext=[f"weight {w:.0%}" for w in weights],
        hoverinfo="text",
    ))
    fig.update_layout(
        **_CHART_LAYOUT, height=320,
        title="Quality score by dimension (0–100)",
        yaxis=dict(range=[0, 105]),
    )
    st.plotly_chart(fig, use_container_width=True)

    detail_rows = []
    for key, data in dims.items():
        row = {"Dimension": labels.get(key, key.title()), "Score": data["score"]}
        for sub_key, sub_val in data.items():
            if sub_key == "score":
                continue
            if isinstance(sub_val, dict):
                sub_val = ", ".join(f"{k}: {v}" for k, v in sub_val.items()) or "—"
            row[sub_key.replace("_", " ").title()] = sub_val
        detail_rows.append(row)
    st.dataframe(pd.DataFrame(detail_rows), use_container_width=True, hide_index=True)
else:
    st.info("No signals to assess.")

st.divider()

# ---------------------------------------------------------------------------
# 4. Findings
# ---------------------------------------------------------------------------

st.markdown("### 🚩 Findings")

if quality["findings"]:
    for finding in quality["findings"]:
        st.markdown(
            f'<div style="border-left:3px solid #f97316;padding:6px 12px;'
            f'margin:5px 0;font-size:0.88rem;color:#e5e7eb;">'
            f'{finding}</div>',
            unsafe_allow_html=True,
        )
else:
    st.success("✅ No data-quality issues detected in the current signal set.")

st.divider()

# ---------------------------------------------------------------------------
# 5. Per-source census
# ---------------------------------------------------------------------------

st.markdown("### 📊 Source Census")

by_source = quality["by_source"]
if by_source:
    census = pd.DataFrame([
        {
            "Source": source,
            "Signals": data["count"],
            "Share": f"{data['count'] / max(quality['total_signals'], 1):.1%}",
            "Critical": data["critical"],
            "High": data["high"],
            "Unresolved Loc": data["unresolved"],
            "Mean Score": data["mean_score"],
        }
        for source, data in by_source.items()
    ])
    st.dataframe(census, use_container_width=True, hide_index=True)
else:
    st.info("No source data available.")

st.divider()

# ---------------------------------------------------------------------------
# 6. Pipeline readiness
# ---------------------------------------------------------------------------

st.markdown("### ⚙️ Pipeline Readiness")

readiness = forecast_state.get("readiness", {})
r1, r2 = st.columns(2)

with r1:
    st.markdown("**Forecasting**")
    if readiness:
        days_have = readiness.get("days_available", 0)
        days_need = readiness.get("days_required", 3)
        st.progress(
            min(1.0, days_have / max(days_need, 1)),
            text=f"History: {days_have}/{days_need} days",
        )
        st.caption(
            f"{readiness.get('mature', 0)} region(s) have full history · "
            f"{readiness.get('cold_start', 0)} forecasting from thin history · "
            f"{readiness.get('regions', 0)} regions tracked"
        )
        if days_have < days_need:
            st.caption(
                "Run the main dashboard and use **⚡ Backfill history** in the "
                "sidebar to derive history from existing signal timestamps."
            )
    else:
        st.caption("Forecast readiness unavailable.")

with r2:
    st.markdown("**Storage**")
    if db_state.get("error"):
        st.error(f"Database unavailable: {db_state['error']}")
    else:
        st.caption(
            f"SQLite: {db_state['size_bytes'] / 1024:.1f} KB · "
            f"{len(db_state['tables'])} tables"
        )
        if db_state.get("missing_tables"):
            st.error(
                "Missing tables: " + ", ".join(db_state["missing_tables"])
            )
        else:
            st.success("✅ All canonical tables present — schema is current.")
        counts = db_state.get("counts", {})
        if counts:
            st.dataframe(
                pd.DataFrame(
                    [{"Table": t, "Rows": c} for t, c in counts.items()]
                ),
                use_container_width=True,
                hide_index=True,
            )

    esc_n = forecast_state.get("history", 0)
    st.caption(
        f"Escalation snapshots: {esc_n} / {MAX_HISTORY_SNAPSHOTS} (capped)"
    )

st.divider()

# ---------------------------------------------------------------------------
# 7. Maintenance
# ---------------------------------------------------------------------------

st.markdown("### 🧰 Maintenance")

mc1, mc2 = st.columns(2)

with mc1:
    if st.button("⚡ Backfill escalation history", use_container_width=True):
        with st.spinner("Deriving history from signal timestamps…"):
            try:
                added = EscalationTracker().backfill_from_signals(signals)
                if added:
                    st.success(f"Added {added} day-snapshot(s).")
                else:
                    st.info("History already covers every day in the signal set.")
                st.cache_data.clear()
            except Exception as e:  # noqa: BLE001
                st.error(f"Backfill failed: {e}")

with mc2:
    if st.button("🔄 Refresh health assessment", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

st.caption(
    f"{VERSION_LABEL} · Quality weights: "
    + ", ".join(f"{k} {v:.0%}" for k, v in QualityEngine.WEIGHTS.items())
)

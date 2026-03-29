"""
12_Database_Explorer.py — ORRAS v3.0 Database Explorer

DB statistics, raw signal browser, alert history, escalation chart,
resource log, DB health, full export, data cleanup, raw SQL query.
"""

import streamlit as st
import plotly.graph_objects as go
import pandas as pd
import json
import os
import sqlite3
import io
from datetime import datetime, timedelta, timezone

st.set_page_config(
    page_title="Database Explorer",
    page_icon="🗄️",
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
    from escalation_tracker import EscalationTracker
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from ui_components import render_metric_card
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

try:
    from utils import load_json, save_json, classify_severity
except ImportError as e:
    st.error(f"❌ {e}"); st.stop()

_CHART_LAYOUT = dict(
    template="plotly_dark",
    paper_bgcolor="#0a0e1a",
    plot_bgcolor="#111827",
    font_color="#e5e7eb",
    margin=dict(l=40, r=20, t=50, b=40),
)

_ALERT_LOG = "data/alert_log.json"
_ESC_HISTORY = "data/escalation_history.json"
_OVERRIDES_FILE = "data/resource_overrides.json"
_DB_FILE = "data/orras.db"

# ---------------------------------------------------------------------------
# SQLite helpers
# ---------------------------------------------------------------------------

def _get_db() -> sqlite3.Connection:
    """Return SQLite connection, creating tables if needed."""
    os.makedirs("data", exist_ok=True)
    conn = sqlite3.connect(_DB_FILE, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("""
        CREATE TABLE IF NOT EXISTS signals (
            id TEXT PRIMARY KEY,
            timestamp TEXT,
            type TEXT,
            source TEXT,
            location TEXT,
            latitude REAL,
            longitude REAL,
            title TEXT,
            description TEXT,
            raw_score REAL,
            severity TEXT,
            keywords_matched TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS alerts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            region TEXT,
            severity TEXT,
            recommendation TEXT,
            signal_count INTEGER,
            acknowledged INTEGER DEFAULT 0
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS escalations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            region TEXT,
            score REAL,
            severity TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS deployments (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            region TEXT,
            resource TEXT,
            quantity INTEGER,
            reason TEXT
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS scenarios (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TEXT,
            region TEXT,
            scenario_name TEXT,
            baseline_score REAL,
            result_score REAL
        )
    """)
    conn.commit()
    return conn


def _seed_db(conn: sqlite3.Connection, signals: list, alerts: list, escalations: list) -> None:
    """Seed DB with current data if tables are empty."""
    cur = conn.cursor()
    # Signals
    if cur.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0:
        for s in signals:
            kw = json.dumps(s.get("keywords_matched") or [])
            try:
                cur.execute(
                    "INSERT OR IGNORE INTO signals VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (s.get("id", ""), s.get("timestamp", ""), s.get("type", ""),
                     s.get("source", ""), s.get("location", ""),
                     s.get("latitude"), s.get("longitude"),
                     (s.get("title") or "")[:200], (s.get("description") or "")[:400],
                     s.get("raw_score"), s.get("severity", ""), kw),
                )
            except Exception:
                pass
    # Alerts
    if cur.execute("SELECT COUNT(*) FROM alerts").fetchone()[0] == 0:
        for a in alerts:
            cur.execute(
                "INSERT INTO alerts (timestamp, region, severity, recommendation, signal_count) VALUES (?,?,?,?,?)",
                (a.get("timestamp", ""), a.get("region", ""), a.get("max_severity", ""),
                 a.get("recommendation", ""), a.get("signal_count", 0)),
            )
    # Escalations (from escalation_history.json)
    if cur.execute("SELECT COUNT(*) FROM escalations").fetchone()[0] == 0:
        for snap in escalations[:50]:
            ts = snap.get("timestamp", "")
            for region, info in (snap.get("regions") or {}).items():
                cur.execute(
                    "INSERT INTO escalations (timestamp, region, score, severity) VALUES (?,?,?,?)",
                    (ts, region, info.get("score", 0), info.get("severity", "")),
                )
    conn.commit()


@st.cache_data(ttl=60)
def load_signals() -> list:
    try:
        return ThreatEngine().score_all(generate_all_mock_signals())
    except Exception as e:
        st.warning(f"⚠️ {e}")
        return []


def _cleanup_old(conn: sqlite3.Connection, days: int) -> int:
    cutoff = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat()
    cur = conn.cursor()
    cur.execute("DELETE FROM signals WHERE timestamp < ?", (cutoff,))
    deleted = cur.rowcount
    cur.execute("DELETE FROM alerts WHERE timestamp < ?", (cutoff,))
    deleted += cur.rowcount
    conn.commit()
    return deleted


# ---------------------------------------------------------------------------
# Page
# ---------------------------------------------------------------------------

st.markdown("# 🗄️ ORRAS Database Explorer")
st.divider()

with st.spinner("Initialising database…"):
    signals = load_signals()
    alerts_raw = load_json(_ALERT_LOG) if os.path.exists(_ALERT_LOG) else []
    esc_history = load_json(_ESC_HISTORY) if os.path.exists(_ESC_HISTORY) else []
    overrides = load_json(_OVERRIDES_FILE) if os.path.exists(_OVERRIDES_FILE) else []

    try:
        conn = _get_db()
        _seed_db(conn, signals, alerts_raw, esc_history)
    except Exception as e:
        st.warning(f"⚠️ DB init error: {e}")
        conn = None

# ---------------------------------------------------------------------------
# 1. DB Statistics Cards
# ---------------------------------------------------------------------------

def _db_count(table: str) -> int:
    if conn is None:
        return 0
    try:
        return conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    except Exception:
        return 0


total_signals = _db_count("signals")
total_alerts = _db_count("alerts")
total_esc = _db_count("escalations")
total_deploy = _db_count("deployments")
total_scenarios = _db_count("scenarios")

c1, c2, c3, c4, c5 = st.columns(5)
c1.markdown(render_metric_card("Total Signals", str(total_signals), "In DB", "#3b82f6"), unsafe_allow_html=True)
c2.markdown(render_metric_card("Active Alerts", str(total_alerts), "Alert log", "#ef4444"), unsafe_allow_html=True)
c3.markdown(render_metric_card("Escalation Records", str(total_esc), "History snapshots", "#f97316"), unsafe_allow_html=True)
c4.markdown(render_metric_card("Deployments", str(total_deploy + len(overrides)), "Resource log", "#22c55e"), unsafe_allow_html=True)
c5.markdown(render_metric_card("Scenarios", str(total_scenarios), "Simulations run", "#9333ea"), unsafe_allow_html=True)

st.divider()

# ---------------------------------------------------------------------------
# 2. Raw Signal Browser
# ---------------------------------------------------------------------------

st.markdown("### 📡 Raw Signal Browser")
PAGE_SIZE = 50

# Filters
f1, f2, f3 = st.columns(3)
with f1:
    type_filter = st.selectbox("Filter by Type", ["All"] + sorted(set(s.get("type","") for s in signals)))
with f2:
    source_filter = st.selectbox("Filter by Source", ["All"] + sorted(set(s.get("source","") for s in signals)))
with f3:
    sev_filter = st.selectbox("Filter by Severity", ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"])

filtered = signals
if type_filter != "All":
    filtered = [s for s in filtered if s.get("type") == type_filter]
if source_filter != "All":
    filtered = [s for s in filtered if s.get("source") == source_filter]
if sev_filter != "All":
    filtered = [s for s in filtered if s.get("severity") == sev_filter]

total_pages = max(1, (len(filtered) + PAGE_SIZE - 1) // PAGE_SIZE)
if "signal_page" not in st.session_state:
    st.session_state.signal_page = 0

col_prev, col_info, col_next = st.columns([1, 3, 1])
with col_prev:
    if st.button("◀ Prev") and st.session_state.signal_page > 0:
        st.session_state.signal_page -= 1
with col_next:
    if st.button("Next ▶") and st.session_state.signal_page < total_pages - 1:
        st.session_state.signal_page += 1
with col_info:
    st.caption(f"Page {st.session_state.signal_page + 1} of {total_pages} — {len(filtered)} signals")

page_signals = filtered[st.session_state.signal_page * PAGE_SIZE:(st.session_state.signal_page + 1) * PAGE_SIZE]
if page_signals:
    df_sigs = pd.DataFrame([{
        "ID": s.get("id","")[:12],
        "Timestamp": (s.get("timestamp",""))[:19],
        "Type": s.get("type",""),
        "Source": s.get("source",""),
        "Location": s.get("location",""),
        "Score": s.get("raw_score",0),
        "Severity": s.get("severity",""),
        "Title": (s.get("title",""))[:60],
    } for s in page_signals])
    st.dataframe(df_sigs.astype(str), use_container_width=True)

st.divider()

# ---------------------------------------------------------------------------
# 3. Alert History Browser
# ---------------------------------------------------------------------------

st.markdown("### 🚨 Alert History Browser")

if alerts_raw:
    af1, af2, af3 = st.columns(3)
    with af1:
        alert_sev_filter = st.selectbox("Severity", ["All", "CRITICAL", "HIGH", "MEDIUM", "LOW"], key="asf")
    with af2:
        ack_filter = st.selectbox("Acknowledged", ["All", "Yes", "No"], key="ackf")
    with af3:
        if conn and st.button("✅ Acknowledge All"):
            conn.execute("UPDATE alerts SET acknowledged = 1")
            conn.commit()
            st.success("All alerts acknowledged.")

    df_alerts = pd.DataFrame(alerts_raw)
    if "max_severity" in df_alerts.columns:
        df_alerts = df_alerts.rename(columns={"max_severity": "severity"})
    if alert_sev_filter != "All" and "severity" in df_alerts.columns:
        df_alerts = df_alerts[df_alerts["severity"] == alert_sev_filter]

    st.dataframe(df_alerts.astype(str), use_container_width=True)

    # Bar chart
    if "severity" in df_alerts.columns:
        sev_counts = df_alerts["severity"].value_counts()
        fig_alert = go.Figure(go.Bar(
            x=sev_counts.index.tolist(),
            y=sev_counts.values.tolist(),
            marker_color=["#ef4444", "#f97316", "#eab308", "#22c55e"][:len(sev_counts)],
        ))
        fig_alert.update_layout(**_CHART_LAYOUT, height=260, title="Alert Counts by Severity")
        st.plotly_chart(fig_alert, use_container_width=True)

    csv_alerts = df_alerts.to_csv(index=False).encode("utf-8")
    st.download_button("⬇️ Export Alert Log CSV", csv_alerts, "alert_log.csv", "text/csv")
else:
    st.info("No alert log data found.")

st.divider()

# ---------------------------------------------------------------------------
# 4. Escalation History Chart
# ---------------------------------------------------------------------------

st.markdown("### 📈 Escalation History Chart")

esc_regions = sorted(set(
    region for snap in esc_history for region in (snap.get("regions") or {}).keys()
))

if esc_regions and esc_history:
    sel_esc_region = st.selectbox("Select Region", esc_regions, key="esc_region")
    esc_rows = []
    for snap in esc_history:
        ts = snap.get("timestamp", "")[:19]
        region_data = (snap.get("regions") or {}).get(sel_esc_region)
        if region_data:
            esc_rows.append({"timestamp": ts, "score": region_data.get("score", 0)})

    if esc_rows:
        esc_df = pd.DataFrame(esc_rows).sort_values("timestamp")
        fig_esc = go.Figure(go.Scatter(
            x=esc_df["timestamp"], y=esc_df["score"],
            mode="lines+markers", line=dict(color="#3b82f6", width=2),
        ))
        fig_esc.update_layout(**_CHART_LAYOUT, height=300,
                              title=f"Escalation History — {sel_esc_region}",
                              xaxis_title="Time", yaxis_title="Score")
        st.plotly_chart(fig_esc, use_container_width=True)
    else:
        st.info(f"No escalation history for {sel_esc_region}.")
else:
    st.info("No escalation history data available.")

st.divider()

# ---------------------------------------------------------------------------
# 5. Resource Deployment Log
# ---------------------------------------------------------------------------

st.markdown("### 📦 Resource Deployment Log")
if overrides:
    st.dataframe(pd.DataFrame(overrides).astype(str), use_container_width=True)
else:
    st.info("No resource deployment records. Use the Resource Allocation page to log overrides.")

st.divider()

# ---------------------------------------------------------------------------
# 6. DB Health Info
# ---------------------------------------------------------------------------

st.markdown("### 💻 Database Health")
col_h1, col_h2, col_h3 = st.columns(3)

db_size = os.path.getsize(_DB_FILE) if os.path.exists(_DB_FILE) else 0
with col_h1:
    st.metric("DB File Size", f"{db_size / 1024:.1f} KB")
with col_h2:
    if esc_history:
        oldest = min(snap.get("timestamp","") for snap in esc_history)[:10]
        st.metric("Oldest Record", oldest)
    else:
        st.metric("Oldest Record", "N/A")
with col_h3:
    if esc_history:
        newest = max(snap.get("timestamp","") for snap in esc_history)[:10]
        st.metric("Newest Record", newest)
    else:
        st.metric("Newest Record", "N/A")

st.divider()

# ---------------------------------------------------------------------------
# 7. Export Full DB
# ---------------------------------------------------------------------------

st.markdown("### 💾 Export Full Database")
if signals:
    all_df = pd.DataFrame([{
        "id": s.get("id",""),
        "timestamp": s.get("timestamp",""),
        "type": s.get("type",""),
        "source": s.get("source",""),
        "location": s.get("location",""),
        "latitude": s.get("latitude"),
        "longitude": s.get("longitude"),
        "title": s.get("title",""),
        "description": s.get("description",""),
        "raw_score": s.get("raw_score"),
        "severity": s.get("severity",""),
        "keywords_matched": json.dumps(s.get("keywords_matched",[])),
    } for s in signals])
    csv_all = all_df.to_csv(index=False).encode("utf-8")
    st.download_button(
        "⬇️ Export Full DB as CSV",
        data=csv_all,
        file_name="orras_full_export.csv",
        mime="text/csv",
        use_container_width=True,
    )

st.divider()

# ---------------------------------------------------------------------------
# 8. Cleanup Old Data
# ---------------------------------------------------------------------------

st.markdown("### 🧹 Cleanup Old Data")
days_thresh = st.slider("Delete records older than (days)", 1, 365, 30)
st.warning(f"⚠️ This will delete all DB records older than **{days_thresh} days**.")
if st.button("🗑️ Confirm Cleanup", type="primary"):
    if conn:
        deleted = _cleanup_old(conn, days_thresh)
        st.success(f"✅ Cleanup complete. {deleted} records deleted.")
    else:
        st.error("Database not available.")

st.divider()

# ---------------------------------------------------------------------------
# 9. Raw SQL Query
# ---------------------------------------------------------------------------

st.markdown("### 🔬 Advanced: Raw SQL Query")
st.caption("Only SELECT queries are allowed for safety.")
raw_sql = st.text_area("SQL Query", value="SELECT id, location, severity, raw_score FROM signals ORDER BY raw_score DESC LIMIT 20;", height=100)

if st.button("▶️ Run Query"):
    if not raw_sql.strip().upper().startswith("SELECT"):
        st.error("❌ Only SELECT queries are permitted.")
    elif conn is None:
        st.error("Database not available.")
    else:
        try:
            df_query = pd.read_sql_query(raw_sql, conn)
            st.dataframe(df_query.astype(str), use_container_width=True)
            st.caption(f"Returned {len(df_query)} rows.")
        except Exception as e:
            st.error(f"Query error: {e}")

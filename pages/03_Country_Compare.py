"""
03_Country_Compare.py — ORRAS v2.0 Country Threat Comparison Page

Side-by-side threat comparison between any two regions, global ranking,
and similar-region discovery.
"""

import streamlit as st
import pandas as pd

st.set_page_config(
    page_title="Country Comparison",
    page_icon="⚖️",
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
    from comparison_engine import ComparisonEngine
except ImportError as e:
    st.error(f"❌ Failed to import comparison_engine: {e}")
    st.stop()

try:
    from ui_components import (
        render_comparison_bar,
        render_severity_badge,
        render_metric_card,
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
def load_ranking(signal_count: int) -> list:
    try:
        signals = load_signals()
        return ComparisonEngine().rank_all_regions(signals)
    except Exception as e:
        st.warning(f"⚠️ Ranking load error: {e}")
        return []


# ---------------------------------------------------------------------------
# Load data
# ---------------------------------------------------------------------------

with st.spinner("Loading comparison data…"):
    signals = load_signals()
    ranking = load_ranking(len(signals))

all_regions = sorted({s.get("location", "") for s in signals if s.get("location")})

# ---------------------------------------------------------------------------
# Page header
# ---------------------------------------------------------------------------

st.markdown("# ⚖️ Country Threat Comparison")
st.divider()

# ---------------------------------------------------------------------------
# Comparison selector
# ---------------------------------------------------------------------------

st.markdown("### 🔍 Head-to-Head Comparison")

if len(all_regions) < 2:
    st.warning("⚠️ Not enough regions in signal data for comparison.")
else:
    sel_col1, sel_col2, btn_col = st.columns([2, 2, 1])

    with sel_col1:
        country1 = st.selectbox(
            "Country / Region 1",
            options=all_regions,
            index=0,
            key="compare_c1",
        )
    with sel_col2:
        default_idx = 1 if len(all_regions) > 1 else 0
        country2 = st.selectbox(
            "Country / Region 2",
            options=all_regions,
            index=default_idx,
            key="compare_c2",
        )
    with btn_col:
        st.markdown("<br>", unsafe_allow_html=True)
        compare_clicked = st.button("⚖️ Compare", use_container_width=True)

    if "comparison_result" not in st.session_state:
        st.session_state.comparison_result = None
    if "comparison_pair" not in st.session_state:
        st.session_state.comparison_pair = (None, None)

    if compare_clicked:
        if country1 == country2:
            st.warning("⚠️ Please select two different regions to compare.")
        else:
            with st.spinner(f"Comparing {country1} vs {country2}…"):
                try:
                    result = ComparisonEngine().compare_regions(signals, country1, country2)
                    st.session_state.comparison_result = result
                    st.session_state.comparison_pair = (country1, country2)
                except Exception as e:
                    st.error(f"Comparison failed: {e}")

    # Display comparison results
    result = st.session_state.comparison_result
    c1_name, c2_name = st.session_state.comparison_pair

    if result and c1_name and c2_name:
        p1 = result.get(c1_name, {})
        p2 = result.get(c2_name, {})
        score1 = p1.get("current_score", 0.0)
        score2 = p2.get("current_score", 0.0)
        score_delta = result.get("score_delta", abs(score1 - score2))
        winner = result.get("winner_score", "TIE")

        st.markdown("---")

        # Comparison bar
        st.markdown(
            render_comparison_bar(c1_name, score1, c2_name, score2),
            unsafe_allow_html=True,
        )

        # Score delta badge
        st.markdown("<br>", unsafe_allow_html=True)
        delta_color = "#ef4444" if score_delta > 5 else "#eab308" if score_delta > 2 else "#22c55e"
        winner_label = (
            f"**{winner}** leads by `{score_delta:.1f}` points"
            if winner != "TIE"
            else "**TIE** — both regions have equal scores"
        )
        st.markdown(
            f'<div style="text-align:center;font-size:1rem;color:{delta_color};">'
            f"🏆 {winner_label}"
            f"</div>",
            unsafe_allow_html=True,
        )
        st.markdown("<br>", unsafe_allow_html=True)

        # Side-by-side stat tables
        stat_col1, stat_col2 = st.columns(2)

        def _render_stat_table(profile: dict, label: str, col):
            with col:
                st.markdown(f"#### 📍 {label}")
                sev_badge = render_severity_badge(profile.get("severity", "LOW"))
                st.markdown(sev_badge, unsafe_allow_html=True)
                stats = {
                    "Score": f"{profile.get('current_score', 0):.1f} / 30",
                    "Severity": profile.get("severity", "N/A"),
                    "Signal Count": str(profile.get("signal_count", 0)),
                    "Confidence": profile.get("confidence", "N/A"),
                    "Trend": profile.get("trend", "N/A"),
                }
                for k, v in stats.items():
                    st.markdown(f"**{k}:** {v}")

                top_kw = profile.get("top_keywords", [])
                if top_kw:
                    st.markdown("**Top Keywords:**")
                    st.markdown(", ".join(f"`{kw}`" for kw in top_kw))

                src_bd = profile.get("source_breakdown", {})
                if src_bd:
                    st.markdown("**Sources:**")
                    for src, cnt in src_bd.items():
                        st.markdown(f"- {src}: {cnt}")

        _render_stat_table(p1, c1_name, stat_col1)
        _render_stat_table(p2, c2_name, stat_col2)

        # Keyword overlap section
        st.markdown("---")
        st.markdown("#### 🔑 Keyword Analysis")
        kw_col1, kw_col2, kw_col3 = st.columns(3)

        common = result.get("common_keywords", [])
        unique_r1 = result.get("unique_to_r1", [])
        unique_r2 = result.get("unique_to_r2", [])

        with kw_col1:
            st.markdown(f"**🔗 Shared Threats ({len(common)})**")
            if common:
                for kw in common:
                    st.markdown(f"- `{kw}`")
            else:
                st.markdown("*No shared keywords*")

        with kw_col2:
            st.markdown(f"**📍 Unique to {c1_name} ({len(unique_r1)})**")
            if unique_r1:
                for kw in unique_r1:
                    st.markdown(f"- `{kw}`")
            else:
                st.markdown("*None*")

        with kw_col3:
            st.markdown(f"**📍 Unique to {c2_name} ({len(unique_r2)})**")
            if unique_r2:
                for kw in unique_r2:
                    st.markdown(f"- `{kw}`")
            else:
                st.markdown("*None*")

        # Summary
        st.markdown("---")
        summary_text = result.get("summary", "")
        if summary_text:
            st.info(f"📋 **Analysis Summary:** {summary_text}")

st.divider()

# ---------------------------------------------------------------------------
# Global ranking table
# ---------------------------------------------------------------------------

st.markdown("### 🌍 Global Threat Ranking")

if ranking:
    rank_rows = []
    for item in ranking:
        rank_rows.append({
            "Rank": item.get("rank", "—"),
            "Region": item.get("region", "Unknown"),
            "Score": round(item.get("current_score", 0.0), 1),
            "Severity": item.get("severity", "LOW"),
            "Signals": item.get("signal_count", 0),
            "Trend": item.get("trend", "STABLE"),
            "Confidence": item.get("confidence", "LOW"),
        })

    df_rank = pd.DataFrame(rank_rows)

    def _color_severity(val):
        colors = {
            "CRITICAL": "color: #fca5a5; font-weight: bold",
            "HIGH": "color: #fdba74; font-weight: bold",
            "MEDIUM": "color: #fde047",
            "LOW": "color: #86efac",
        }
        return colors.get(val, "")

    def _color_row(row):
        sev = row.get("Severity", "LOW")
        bg = {
            "CRITICAL": "background-color: rgba(239,68,68,0.10)",
            "HIGH": "background-color: rgba(249,115,22,0.08)",
            "MEDIUM": "background-color: rgba(234,179,8,0.06)",
            "LOW": "background-color: rgba(34,197,94,0.04)",
        }.get(sev, "")
        return [bg] * len(row)

    styled_rank = df_rank.style.apply(_color_row, axis=1).applymap(
        _color_severity, subset=["Severity"]
    )

    st.dataframe(styled_rank, use_container_width=True, hide_index=True)

    # CSV download
    csv_data = df_rank.to_csv(index=False)
    st.download_button(
        label="⬇️ Download Ranking as CSV",
        data=csv_data,
        file_name="orras_global_ranking.csv",
        mime="text/csv",
    )
else:
    st.info("No ranking data available. Signals may not have loaded correctly.")

st.divider()

# ---------------------------------------------------------------------------
# Similar regions section
# ---------------------------------------------------------------------------

st.markdown("### 🔗 Find Similar Regions")
st.markdown("*Discover regions with similar threat profiles*")

if all_regions:
    similar_target = st.selectbox(
        "Select a region to find similar regions",
        options=all_regions,
        key="similar_target_select",
    )

    if st.button("🔍 Find Similar Regions", key="find_similar_btn"):
        with st.spinner(f"Finding regions similar to {similar_target}…"):
            try:
                similar = ComparisonEngine().find_similar_regions(
                    signals, similar_target, n=3
                )
                st.session_state.similar_results = similar
                st.session_state.similar_target = similar_target
            except Exception as e:
                st.error(f"Similar region search failed: {e}")
                st.session_state.similar_results = []

    if "similar_results" in st.session_state and st.session_state.similar_results:
        target_label = st.session_state.get("similar_target", similar_target)
        st.markdown(f"**Regions most similar to {target_label}:**")
        sim_cols = st.columns(min(3, len(st.session_state.similar_results)))
        for col, item in zip(sim_cols, st.session_state.similar_results):
            with col:
                region_name = item.get("region", "Unknown")
                score = item.get("current_score", 0.0)
                severity = item.get("severity", "LOW")
                sev_badge = render_severity_badge(severity)
                similarity = item.get("similarity_score", 0.0)

                st.markdown(
                    f'<div style="background:#111827;border:1px solid #1f2937;'
                    f'border-radius:12px;padding:1rem;">'
                    f"<b>{region_name}</b><br>"
                    f"Score: {score:.1f} / 30<br>"
                    f"{sev_badge}<br>"
                    f"<small style='color:#9ca3af;'>Similarity: {similarity:.0%}</small>"
                    f"</div>",
                    unsafe_allow_html=True,
                )
else:
    st.info("No region data available for similarity analysis.")

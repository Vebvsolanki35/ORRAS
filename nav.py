"""
nav.py — Application-wide navigation for ORRAS.

Streamlit renders multipage navigation inside the sidebar. That is fragile:
when the sidebar is collapsed (narrow viewport, or a user preference stored
in the browser) the navigation disappears with it, and the control that
reopens the sidebar lives in the toolbar, which custom CSS or a Streamlit
DOM change can easily hide.

This module provides a navigation bar rendered in the *main* content area of
every page, so the dashboard is always switchable — independent of sidebar
state, theme CSS, or Streamlit version.

Usage:
    from nav import render_top_nav
    render_top_nav(__file__)
"""

from __future__ import annotations

from pathlib import Path

import streamlit as st

# Every page in display order: (file path, short label, icon)
PAGES: list[tuple[str, str, str]] = [
    ("app.py",                        "Dashboard",     "🛡️"),
    ("pages/01_AI_Assistant.py",      "AI Assistant",  "🤖"),
    ("pages/02_Predictions.py",       "Predictions",   "📈"),
    ("pages/03_Country_Compare.py",   "Compare",       "🌍"),
    ("pages/04_Timeline.py",          "Timeline",      "🕐"),
    ("pages/05_Safety_Monitor.py",    "Safety",        "🔒"),
    ("pages/06_Reports.py",           "Reports",       "📄"),
    ("pages/07_Disaster_Response.py", "Disaster",      "🌋"),
    ("pages/08_Resource_Allocation.py", "Resources",   "📦"),
    ("pages/09_Scenario_Simulator.py", "Scenarios",    "🎮"),
    ("pages/10_Explainability.py",    "Explain",       "🔍"),
    ("pages/11_Fusion_Center.py",     "Fusion",        "⚡"),
    ("pages/12_Database_Explorer.py", "Database",      "🗄️"),
    ("pages/13_System_Health.py",     "Health",        "🩺"),
]

# Styling for the nav bar — scoped with a class so it cannot affect anything else.
_NAV_CSS = """
<style>
  .orras-nav {
      display: flex;
      flex-wrap: wrap;
      gap: 6px;
      align-items: center;
      padding: 8px 10px;
      margin: 0 0 12px 0;
      background: linear-gradient(90deg, #050510, #0a1020);
      border: 1px solid #1a3a5c;
      border-radius: 6px;
  }
  .orras-nav a {
      font-family: "Courier New", monospace !important;
      font-size: 0.72rem !important;
      letter-spacing: 1px;
      text-transform: uppercase;
      text-decoration: none !important;
      padding: 5px 10px;
      border: 1px solid #1a3a5c;
      border-radius: 4px;
      color: #7090a0 !important;
      background: transparent;
      white-space: nowrap;
      transition: all 0.15s ease;
  }
  .orras-nav a:hover {
      color: #00d4ff !important;
      border-color: #00d4ff;
      background: rgba(0, 212, 255, 0.08);
  }
  .orras-nav a.orras-nav-active {
      color: #00d4ff !important;
      border-color: #00d4ff;
      background: rgba(0, 212, 255, 0.15);
      font-weight: 700;
  }
</style>
"""


def _current_page(current_file: str | None) -> str:
    """Normalise the calling file into a repo-relative page path."""
    if not current_file:
        return ""
    try:
        path = Path(current_file).resolve()
        for name in ("ORRAS",):  # repo root marker
            parts = path.parts
            if name in parts:
                return "/".join(parts[parts.index(name) + 1:])
        return path.name
    except Exception:  # noqa: BLE001
        return Path(str(current_file)).name


def render_top_nav(current_file: str | None = None) -> None:
    """
    Render the ORRAS page navigation bar in the main content area.

    Uses native ``st.page_link`` when available (Streamlit ≥ 1.30) and falls
    back to plain markdown links otherwise, so navigation works even if the
    sidebar is collapsed and unreachable.

    Args:
        current_file: ``__file__`` of the calling page, used to highlight the
                      active entry. Optional.
    """
    active = _current_page(current_file)

    st.markdown(_NAV_CSS, unsafe_allow_html=True)
    st.markdown('<div class="orras-nav">', unsafe_allow_html=True)

    # Build the links as HTML so the whole bar is one compact, scrollable row.
    links: list[str] = []
    for path, label, icon in PAGES:
        if not Path(path).exists():
            continue
        css = "orras-nav-active" if path == active else ""
        # Streamlit derives page URLs from the filename without the numeric
        # prefix or extension, e.g. pages/02_Predictions.py -> /Predictions
        slug = Path(path).stem
        if slug != "app":
            slug = slug.split("_", 1)[-1] if "_" in slug else slug
            href = f"/{slug}"
        else:
            href = "/"
        links.append(
            f'<a class="{css}" href="{href}" target="_self">'
            f"{icon} {label}</a>"
        )

    st.markdown("".join(links), unsafe_allow_html=True)
    st.markdown("</div>", unsafe_allow_html=True)

    # Native links are more reliable than hand-built URLs, but they render as
    # large cards. Keep them available in a collapsed "Jump to page" expander
    # so there is always a supported navigation path.
    if hasattr(st, "page_link"):
        with st.expander("📂 Jump to page", expanded=False):
            cols = st.columns(4)
            for idx, (path, label, icon) in enumerate(PAGES):
                if not Path(path).exists():
                    continue
                with cols[idx % 4]:
                    try:
                        st.page_link(path, label=label, icon=icon,
                                     width="stretch")
                    except Exception:  # noqa: BLE001 - never break the page
                        pass

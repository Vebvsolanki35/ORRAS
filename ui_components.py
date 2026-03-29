"""
ui_components.py — ORRAS v2.0 Reusable HTML Component Library
==============================================================
Every function returns an HTML string that can be rendered with:
    st.markdown(render_xxx(...), unsafe_allow_html=True)

All styling is inline so components work even without custom.css loaded.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from typing import Optional


# ─── Internal helpers ────────────────────────────────────────────────────────

# Maps severity level → (hex colour, text colour, glow CSS)
_SEVERITY_PALETTE: dict[str, tuple[str, str, str]] = {
    "CRITICAL": ("#ef4444", "#fca5a5", "0 0 16px rgba(239,68,68,0.45)"),
    "HIGH":     ("#f97316", "#fdba74", "0 0 12px rgba(249,115,22,0.35)"),
    "MEDIUM":   ("#eab308", "#fde047", "0 0 12px rgba(234,179,8,0.30)"),
    "LOW":      ("#22c55e", "#86efac", "0 0 12px rgba(34,197,94,0.30)"),
    "INFO":     ("#3b82f6", "#93c5fd", "0 0 12px rgba(59,130,246,0.30)"),
}

# Parses a hex colour string and returns (normalized_hex, r, g, b).
# Falls back to the provided default if the string is absent or malformed.
def _parse_color(color: str, default: str = "#00d4ff") -> tuple[str, int, int, int]:
    raw = color.strip() if color else ""
    if not raw:
        raw = default
    try:
        c = raw.lstrip("#")
        if len(c) == 3:
            c = "".join(ch * 2 for ch in c)
        if len(c) != 6:
            raise ValueError(f"Unexpected colour length: {raw!r}")
        return raw, int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)
    except (ValueError, IndexError):
        c = default.lstrip("#")
        return default, int(c[0:2], 16), int(c[2:4], 16), int(c[4:6], 16)


    return _SEVERITY_PALETTE.get(level.upper(), _SEVERITY_PALETTE["INFO"])

# Clamps a float value between lo and hi
def _clamp(value: float, lo: float = 0.0, hi: float = 100.0) -> float:
    return max(lo, min(hi, value))

# Safely escapes a string for use inside HTML text/attributes
def _esc(text: str) -> str:
    return html.escape(str(text))


# ─── 1. Severity Badge ────────────────────────────────────────────────────────

def render_severity_badge(severity: str) -> str:
    """Returns a colored pill-shaped badge HTML for LOW / MEDIUM / HIGH / CRITICAL.

    Args:
        severity: One of "LOW", "MEDIUM", "HIGH", "CRITICAL" (case-insensitive).

    Returns:
        HTML string containing a styled <span> badge.
    """
    border_color, text_color, glow = _severity(severity)
    label = severity.upper()

    # Background is the solid color at low opacity
    bg = f"{border_color}22"

    badge_html = (
        f'<span style="'
        f"display:inline-flex;align-items:center;gap:5px;"
        f"padding:3px 10px;"
        f"border-radius:99px;"
        f"background:{bg};"
        f"border:1px solid {border_color}88;"
        f"color:{text_color};"
        f"font-size:0.7rem;font-weight:700;"
        f"letter-spacing:0.07em;text-transform:uppercase;"
        f"box-shadow:{glow};"
        f"white-space:nowrap;"
        f'">'
        f'<span style="width:6px;height:6px;border-radius:50%;'
        f'background:{text_color};flex-shrink:0;display:inline-block;"></span>'
        f"{_esc(label)}"
        f"</span>"
    )
    return badge_html


# ─── 2. Metric / KPI Card ─────────────────────────────────────────────────────

def render_metric_card(
    title: str,
    value: str,
    subtitle: str,
    color: str,
) -> str:
    """Renders a dark intel-themed KPI card with large value, title, and subtitle.

    Args:
        title:    Short label shown below the value (e.g. "Active Threats").
        value:    The main display number or text (e.g. "142").
        subtitle: Descriptive note shown below the title (e.g. "In DB").
        color:    Hex accent colour for the left border and value glow (e.g. "#00d4ff").

    Returns:
        HTML string for the metric card.
    """
    # Parse colour to RGB for glow effects
    color, r, g, b = _parse_color(color)

    card = f"""
<div style="
    background:linear-gradient(135deg,#0a0a1a,#0d1525);
    border:1px solid #1a3a5c;
    border-left:3px solid {color};
    border-radius:4px;
    padding:16px;
    box-shadow:0 0 20px rgba({r},{g},{b},0.12);
    position:relative;overflow:hidden;
    animation:slide-in 0.4s ease both;
">
  <div style="
      font-size:2.5rem;font-weight:700;
      font-family:'Courier New',monospace;
      color:{color};
      text-shadow:0 0 10px rgba({r},{g},{b},0.5);
      line-height:1;margin-bottom:4px;">
    {_esc(value)}
  </div>
  <div style="
      font-family:'Courier New',monospace;
      font-size:0.65rem;font-weight:700;
      text-transform:uppercase;letter-spacing:3px;
      color:#7090a0;margin-top:2px;">
    {_esc(title)}
  </div>
  <div style="font-size:0.72rem;color:#4a6a7a;margin-top:4px;">
    {_esc(subtitle)}
  </div>
</div>
"""
    return card


# ─── 3. Alert Banner ──────────────────────────────────────────────────────────

def render_alert_banner(alerts: list[str], level: str) -> str:
    """Full-width alert banner with a scrolling list of alert messages.

    CRITICAL banners get a pulsing red border animation.

    Args:
        alerts: List of alert message strings to display.
        level:  Severity level — "CRITICAL", "HIGH", "MEDIUM", or "LOW".

    Returns:
        HTML string for the banner.
    """
    border_color, text_color, glow = _severity(level)
    bg_color = f"{border_color}18"
    label = level.upper()

    # CRITICAL gets the pulsing animation via an injected <style> block
    animation_style = ""
    extra_shadow = glow
    if label == "CRITICAL":
        animation_style = """
<style>
@keyframes _pulse_crit {
  0%,100%{box-shadow:0 0 20px rgba(239,68,68,0.4),0 0 6px rgba(239,68,68,0.2);
           border-color:rgba(239,68,68,1);}
  50%    {box-shadow:0 0 36px rgba(239,68,68,0.7),0 0 14px rgba(239,68,68,0.4);
           border-color:rgba(239,68,68,0.55);}
}
._orras_alert_critical{animation:_pulse_crit 2.4s ease-in-out infinite!important;}
</style>"""
        extra_shadow = "0 0 20px rgba(239,68,68,0.4)"

    # Icon per level
    icons = {"CRITICAL": "🔴", "HIGH": "🟠", "MEDIUM": "🟡", "LOW": "🟢"}
    icon = icons.get(label, "ℹ️")

    # Build the list of alert messages
    items_html = "".join(
        f'<li style="margin:2px 0;font-size:0.85rem;">'
        f'<span style="opacity:0.65;margin-right:4px;">▸</span>{_esc(a)}</li>'
        for a in alerts
    )

    css_class = f"_orras_alert_critical" if label == "CRITICAL" else ""

    banner = f"""
{animation_style}
<div class="{css_class}" style="
    background:{bg_color};
    border:2px solid {border_color};
    border-radius:14px;
    padding:0.9rem 1.2rem;
    margin-bottom:0.75rem;
    display:flex;align-items:flex-start;gap:0.7rem;
    box-shadow:{extra_shadow};
    animation:slide-in 0.3s ease both;
">
  <span style="font-size:1.3rem;flex-shrink:0;margin-top:1px;">{icon}</span>
  <div style="flex:1;">
    <div style="font-size:0.78rem;font-weight:700;text-transform:uppercase;
                letter-spacing:0.08em;color:{text_color};margin-bottom:0.3rem;">
      {label} ALERT — {len(alerts)} event(s)
    </div>
    <ul style="list-style:none;margin:0;padding:0;color:{text_color};">
      {items_html}
    </ul>
  </div>
</div>
"""
    return banner


# ─── 4. News Ticker ───────────────────────────────────────────────────────────

def render_news_ticker(headlines: list[str]) -> str:
    """CSS-animated horizontal scrolling news ticker that auto-loops continuously.

    Headlines are joined with red dividers (🔴). Hovering pauses the scroll.

    Args:
        headlines: List of headline strings to display.

    Returns:
        HTML string for the ticker.
    """
    # Join headlines with a divider
    divider = ' <span style="color:#ef4444;margin:0 0.6rem;user-select:none;">🔴</span> '
    content = divider.join(_esc(h) for h in headlines)

    # Duplicate content so the loop appears seamless
    ticker_html = f"""
<style>
@keyframes _ticker_scroll {{
  0%   {{ transform: translateX(0); }}
  100% {{ transform: translateX(-50%); }}
}}
._orras_ticker_track {{
  display:inline-flex;white-space:nowrap;
  animation:_ticker_scroll 50s linear infinite;
}}
._orras_ticker_track:hover {{ animation-play-state:paused; }}
</style>
<div style="
    background:#111827;
    border:1px solid #1f2937;
    border-radius:10px;
    padding:0.5rem 0;
    overflow:hidden;
    white-space:nowrap;
    position:relative;
">
  <!-- Gradient fade on the left edge -->
  <div style="position:absolute;top:0;left:0;bottom:0;width:3rem;
              background:linear-gradient(90deg,#111827,transparent);z-index:2;
              pointer-events:none;"></div>
  <!-- Label chip -->
  <span style="
      display:inline-block;vertical-align:middle;
      background:#3b82f6;color:#fff;
      font-size:0.68rem;font-weight:700;letter-spacing:0.08em;text-transform:uppercase;
      padding:0.15rem 0.55rem;border-radius:6px;
      margin-left:0.75rem;margin-right:0.25rem;
  ">LIVE FEED</span>
  <!-- Scrolling track (content doubled for seamless loop) -->
  <span class="_orras_ticker_track" style="font-size:0.82rem;color:#9ca3af;">
    {content} {divider} {content}
  </span>
  <!-- Gradient fade on the right edge -->
  <div style="position:absolute;top:0;right:0;bottom:0;width:3rem;
              background:linear-gradient(-90deg,#111827,transparent);z-index:2;
              pointer-events:none;"></div>
</div>
"""
    return ticker_html


# ─── 5. Region Card ───────────────────────────────────────────────────────────

def render_region_card(
    region: str,
    score: float,
    severity: str,
    trend: str,
    confidence: str,
) -> str:
    """Card showing region name, risk score, severity badge, trend arrow, and confidence bar.

    Args:
        region:     Region name (e.g. "Eastern Europe").
        score:      Risk score 0–30.
        severity:   "LOW", "MEDIUM", "HIGH", or "CRITICAL".
        trend:      "rising", "falling", or "stable".
        confidence: Label shown on the confidence bar (e.g. "HIGH (87%)").

    Returns:
        HTML string for the region card.
    """
    border_color, text_color, glow = _severity(severity)

    # Trend arrow: red up for rising, green down for falling, grey for stable
    trend_map = {
        "rising":  ("↑", "#fca5a5"),
        "falling": ("↓", "#86efac"),
        "stable":  ("→", "#9ca3af"),
    }
    trend_arrow, trend_color = trend_map.get(trend.lower(), ("→", "#9ca3af"))

    # Score gauge: clamp to 0-30 range, map to 0-100% for the bar
    score_clamped = _clamp(score, 0.0, 30.0)
    bar_pct = (score_clamped / 30.0) * 100

    badge_html = render_severity_badge(severity)

    # Parse confidence percentage from label if present (e.g. "HIGH (87%)" → 87)
    conf_pct = 75  # default
    for part in str(confidence).replace("(", "").replace(")", "").replace("%", "").split():
        try:
            conf_pct = int(part)
        except ValueError:
            pass

    card = f"""
<div style="
    background:#111827;border:1px solid {border_color}44;
    border-radius:20px;padding:1.2rem 1.3rem;
    box-shadow:0 4px 20px rgba(0,0,0,0.4),{glow};
    transition:transform 0.2s ease,box-shadow 0.2s ease;
    animation:slide-in 0.35s ease both;
">
  <div style="display:flex;justify-content:space-between;align-items:flex-start;margin-bottom:0.5rem;">
    <div style="font-size:0.95rem;font-weight:700;color:#f9fafb;">{_esc(region)}</div>
    <div style="color:{trend_color};font-size:1.1rem;font-weight:700;">{trend_arrow}</div>
  </div>

  <!-- Risk score -->
  <div style="font-size:2rem;font-weight:800;color:{text_color};
              letter-spacing:-0.04em;line-height:1;margin-bottom:0.4rem;">
    {score_clamped:.1f}
    <span style="font-size:0.85rem;font-weight:500;color:#9ca3af;">/ 30</span>
  </div>

  <!-- Score bar -->
  <div style="width:100%;height:5px;background:rgba(255,255,255,0.07);
              border-radius:99px;overflow:hidden;margin-bottom:0.6rem;">
    <div style="width:{bar_pct:.1f}%;height:100%;background:{border_color};
                border-radius:99px;"></div>
  </div>

  <!-- Severity badge -->
  <div style="margin-bottom:0.65rem;">{badge_html}</div>

  <!-- Confidence bar -->
  <div>
    <div style="display:flex;justify-content:space-between;
                font-size:0.7rem;color:#9ca3af;margin-bottom:3px;">
      <span>Confidence</span>
      <span>{_esc(confidence)}</span>
    </div>
    <div style="width:100%;height:4px;background:rgba(255,255,255,0.07);
                border-radius:99px;overflow:hidden;">
      <div style="width:{_clamp(conf_pct,0,100):.0f}%;height:100%;
                  background:linear-gradient(90deg,#3b82f6,#06b6d4);
                  border-radius:99px;"></div>
    </div>
  </div>
</div>
"""
    return card


# ─── 6. Source Health Badge ───────────────────────────────────────────────────

def render_source_health_badge(source: str, is_live: bool) -> str:
    """Renders a LIVE (green) or OFFLINE (red) status badge for a data source.

    Args:
        source:  Name of the data source (e.g. "GDELT News API").
        is_live: True → green LIVE badge, False → red OFFLINE badge.

    Returns:
        HTML string containing the badge.
    """
    if is_live:
        dot_color = "#22c55e"
        bg        = "rgba(34,197,94,0.12)"
        border    = "rgba(34,197,94,0.40)"
        text_col  = "#86efac"
        status    = "LIVE"
        # Blinking dot animation (injected once per call; browsers deduplicate)
        anim_style = (
            '<style>@keyframes _blink_live{'
            '0%,100%{opacity:1;}50%{opacity:0.3;}}'
            '._orras_dot_live{animation:_blink_live 1.6s ease-in-out infinite;}'
            '</style>'
        )
        dot_class = "_orras_dot_live"
    else:
        dot_color = "#ef4444"
        bg        = "rgba(239,68,68,0.10)"
        border    = "rgba(239,68,68,0.35)"
        text_col  = "#fca5a5"
        status    = "OFFLINE"
        anim_style = ""
        dot_class  = ""

    badge = (
        f'{anim_style}'
        f'<span style="'
        f"display:inline-flex;align-items:center;gap:6px;"
        f"padding:4px 10px;"
        f"border-radius:99px;"
        f"background:{bg};"
        f"border:1px solid {border};"
        f"color:{text_col};"
        f"font-size:0.72rem;font-weight:600;letter-spacing:0.06em;"
        f"text-transform:uppercase;white-space:nowrap;"
        f'">'
        f'<span class="{dot_class}" style="'
        f"width:7px;height:7px;border-radius:50%;"
        f"background:{dot_color};flex-shrink:0;display:inline-block;"
        f'"></span>'
        f"{_esc(source)} ● {status}"
        f"</span>"
    )
    return badge


# ─── 7. Threat Gauge (SVG circular) ──────────────────────────────────────────

def render_threat_gauge(score: float) -> str:
    """SVG circular gauge showing a 0–30 threat score.

    Colour transitions: green (0–8) → yellow (9–15) → orange (16–22) → red (23–30).
    Includes an animated fill drawn from 0 → current value on render.

    Args:
        score: Threat score between 0 and 30.

    Returns:
        HTML string containing the SVG gauge.
    """
    score = _clamp(score, 0.0, 30.0)
    pct   = score / 30.0  # 0.0 – 1.0

    # Pick colour based on score bands
    if score < 9:
        arc_color = "#22c55e"
        label_color = "#86efac"
    elif score < 16:
        arc_color = "#eab308"
        label_color = "#fde047"
    elif score < 23:
        arc_color = "#f97316"
        label_color = "#fdba74"
    else:
        arc_color = "#ef4444"
        label_color = "#fca5a5"

    # SVG circle math
    cx, cy, r = 60, 60, 50          # centre, radius
    circumference = 2 * 3.14159 * r  # ≈ 314.16
    dash_length   = circumference * pct
    dash_gap      = circumference - dash_length

    # Unique ID so multiple gauges on the same page don't conflict
    uid = f"g{int(score*100)}"

    gauge = f"""
<style>
@keyframes _gauge_draw_{uid} {{
  from {{ stroke-dasharray: 0 {circumference:.2f}; }}
  to   {{ stroke-dasharray: {dash_length:.2f} {dash_gap:.2f}; }}
}}
._{uid}_arc {{
  animation: _gauge_draw_{uid} 1.2s cubic-bezier(0.22,1,0.36,1) both;
  animation-delay: 0.15s;
}}
</style>
<div style="
    display:flex;flex-direction:column;align-items:center;
    background:#111827;border:1px solid #1f2937;
    border-radius:20px;padding:1.25rem;
    box-shadow:0 4px 20px rgba(0,0,0,0.4);
    width:fit-content;margin:0 auto;
">
  <svg width="120" height="120" viewBox="0 0 120 120"
       style="transform:rotate(-90deg);" aria-label="Threat score {score:.1f} out of 30">
    <!-- Background track -->
    <circle cx="{cx}" cy="{cy}" r="{r}"
            fill="none" stroke="rgba(255,255,255,0.07)" stroke-width="12"/>
    <!-- Filled arc -->
    <circle class="_{uid}_arc" cx="{cx}" cy="{cy}" r="{r}"
            fill="none"
            stroke="{arc_color}"
            stroke-width="12"
            stroke-linecap="round"
            stroke-dasharray="{dash_length:.2f} {dash_gap:.2f}"
            style="filter:drop-shadow(0 0 6px {arc_color}88);"/>
  </svg>
  <!-- Central label overlay (positioned over the SVG) -->
  <div style="margin-top:-84px;height:80px;width:120px;
              display:flex;flex-direction:column;align-items:center;justify-content:center;">
    <div style="font-size:1.7rem;font-weight:800;color:{label_color};
                letter-spacing:-0.04em;line-height:1;">{score:.1f}</div>
    <div style="font-size:0.62rem;color:#6b7280;text-transform:uppercase;
                letter-spacing:0.07em;">/ 30</div>
  </div>
  <div style="margin-top:0.5rem;font-size:0.75rem;font-weight:600;
              color:#9ca3af;text-transform:uppercase;letter-spacing:0.08em;">
    Threat Score
  </div>
</div>
"""
    return gauge


# ─── 8. Comparison Bar Chart ──────────────────────────────────────────────────

def render_comparison_bar(
    country1: str,
    score1: float,
    country2: str,
    score2: float,
) -> str:
    """Side-by-side horizontal bar chart for comparing two countries' risk scores.

    Bar colour is chosen from the severity palette based on score thresholds
    (same 0-30 scale as the gauge).

    Args:
        country1: Name of the first country.
        score1:   Risk score for country 1 (0–30).
        country2: Name of the second country.
        score2:   Risk score for country 2 (0–30).

    Returns:
        HTML string for the comparison bar chart.
    """
    def _bar_color(s: float) -> str:
        if s < 9:   return "#22c55e"
        if s < 16:  return "#eab308"
        if s < 23:  return "#f97316"
        return "#ef4444"

    def _row(label: str, score: float) -> str:
        s   = _clamp(score, 0.0, 30.0)
        pct = (s / 30.0) * 100
        col = _bar_color(s)
        return (
            f'<div style="display:flex;align-items:center;gap:10px;margin-bottom:10px;">'
            f'<div style="width:110px;font-size:0.8rem;font-weight:600;color:#f9fafb;'
            f'white-space:nowrap;overflow:hidden;text-overflow:ellipsis;">{_esc(label)}</div>'
            f'<div style="flex:1;height:22px;background:rgba(255,255,255,0.06);'
            f'border-radius:99px;overflow:hidden;">'
            f'<div style="width:{pct:.1f}%;height:100%;background:{col};'
            f'border-radius:99px;'
            f'transition:width 0.9s cubic-bezier(0.22,1,0.36,1);"></div>'
            f'</div>'
            f'<div style="width:34px;text-align:right;font-size:0.8rem;'
            f'font-weight:700;color:#f9fafb;">{s:.1f}</div>'
            f'</div>'
        )

    chart = f"""
<div style="
    background:#111827;border:1px solid #1f2937;
    border-radius:16px;padding:1.2rem 1.3rem;
    animation:slide-in 0.35s ease both;
">
  <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.08em;color:#9ca3af;margin-bottom:0.85rem;">
    Risk Score Comparison (0–30)
  </div>
  {_row(country1, score1)}
  {_row(country2, score2)}
</div>
"""
    return chart


# ─── 9. Timeline Event ────────────────────────────────────────────────────────

def render_timeline_event(event: dict) -> str:
    """Vertical timeline card with a colour-coded dot by severity.

    Expected keys in `event`:
        - ``date``        (str): Display date/time string.
        - ``location``    (str): Location or region name.
        - ``description`` (str): Event summary text.
        - ``severity``    (str): "LOW" | "MEDIUM" | "HIGH" | "CRITICAL".
        - ``type``        (str, optional): Event type label.

    Args:
        event: Dictionary with event data (see above).

    Returns:
        HTML string for a single timeline event card.
    """
    severity    = event.get("severity", "INFO")
    date        = event.get("date", "Unknown Date")
    location    = event.get("location", "Unknown Location")
    description = event.get("description", "")
    evt_type    = event.get("type", "")

    border_color, text_color, glow = _severity(severity)
    badge_html = render_severity_badge(severity)

    type_chip = ""
    if evt_type:
        type_chip = (
            f'<span style="display:inline-block;padding:2px 8px;'
            f'border-radius:6px;background:rgba(255,255,255,0.06);'
            f'color:#9ca3af;font-size:0.68rem;font-weight:500;'
            f'text-transform:uppercase;letter-spacing:0.06em;margin-bottom:4px;">'
            f'{_esc(evt_type)}</span>'
        )

    event_html = f"""
<div style="
    display:flex;gap:0.85rem;margin-bottom:1rem;
    animation:fadeIn 0.35s ease both;
">
  <!-- Timeline spine + dot -->
  <div style="display:flex;flex-direction:column;align-items:center;flex-shrink:0;">
    <div style="
        width:14px;height:14px;border-radius:50%;
        background:{border_color};
        box-shadow:{glow};
        border:2px solid #111827;
        flex-shrink:0;margin-top:3px;
    "></div>
    <div style="width:2px;flex:1;background:linear-gradient(to bottom,{border_color}44,transparent);
                margin-top:3px;min-height:20px;"></div>
  </div>

  <!-- Content card -->
  <div style="
      flex:1;background:#111827;
      border:1px solid {border_color}33;
      border-radius:14px;padding:0.85rem 1rem;
      margin-bottom:0.25rem;
  ">
    {type_chip}
    <div style="font-size:0.68rem;color:#6b7280;font-weight:500;
                text-transform:uppercase;letter-spacing:0.06em;margin-bottom:2px;">
      📅 {_esc(date)}
    </div>
    <div style="font-size:0.82rem;color:#06b6d4;font-weight:600;margin-bottom:0.4rem;">
      📍 {_esc(location)}
    </div>
    <div style="font-size:0.85rem;color:#d1d5db;line-height:1.5;margin-bottom:0.5rem;">
      {_esc(description)}
    </div>
    {badge_html}
  </div>
</div>
"""
    return event_html


# ─── 10. Confidence Breakdown ─────────────────────────────────────────────────

def render_confidence_breakdown(sources: list[str], confidence: str) -> str:
    """Shows each data source as an icon + name and an overall animated confidence bar.

    Args:
        sources:    List of source names (e.g. ["GDELT", "ACLED", "OSINT"]).
        confidence: Overall confidence label shown on the bar (e.g. "HIGH (92%)").

    Returns:
        HTML string for the breakdown panel.
    """
    # Icons for well-known source names; fall back to 📡
    source_icons: dict[str, str] = {
        "gdelt": "📰", "acled": "⚔️", "osint": "🔍", "twitter": "🐦",
        "reddit": "🟠", "news": "📺", "api": "🔌", "satellite": "🛰️",
        "military": "🎖️", "govt": "🏛️", "social": "💬", "economic": "📊",
        "weather": "🌦️", "seismic": "🌋",
    }

    def _icon(name: str) -> str:
        for key, ico in source_icons.items():
            if key in name.lower():
                return ico
        return "📡"

    # Parse confidence percentage
    conf_pct = 75
    for part in str(confidence).replace("(", "").replace(")", "").replace("%", "").split():
        try:
            conf_pct = int(part)
        except ValueError:
            pass
    conf_pct = _clamp(conf_pct, 0, 100)

    # Source chips
    chips_html = "".join(
        f'<div style="display:flex;align-items:center;gap:6px;'
        f'padding:5px 10px;border-radius:8px;'
        f'background:rgba(255,255,255,0.04);border:1px solid #1f2937;'
        f'margin-bottom:6px;">'
        f'<span style="font-size:1rem;">{_icon(s)}</span>'
        f'<span style="font-size:0.8rem;color:#d1d5db;font-weight:500;">{_esc(s)}</span>'
        f'<span style="margin-left:auto;font-size:0.65rem;color:#22c55e;'
        f'font-weight:600;">✓ ACTIVE</span>'
        f'</div>'
        for s in sources
    )

    breakdown = f"""
<div style="
    background:#111827;border:1px solid #1f2937;
    border-radius:16px;padding:1.2rem;
    animation:slide-in 0.35s ease both;
">
  <div style="font-size:0.72rem;font-weight:700;text-transform:uppercase;
              letter-spacing:0.08em;color:#9ca3af;margin-bottom:0.8rem;">
    📡 Intelligence Sources ({len(sources)})
  </div>
  {chips_html}
  <!-- Overall confidence bar -->
  <div style="margin-top:0.8rem;">
    <div style="display:flex;justify-content:space-between;
                font-size:0.72rem;color:#9ca3af;margin-bottom:4px;">
      <span>Overall Confidence</span>
      <span style="font-weight:700;color:#06b6d4;">{_esc(confidence)}</span>
    </div>
    <div style="width:100%;height:7px;background:rgba(255,255,255,0.07);
                border-radius:99px;overflow:hidden;">
      <div style="
          width:{conf_pct:.0f}%;height:100%;
          background:linear-gradient(90deg,#3b82f6,#06b6d4);
          border-radius:99px;
          box-shadow:0 0 10px rgba(6,182,212,0.45);
          transition:width 1s cubic-bezier(0.22,1,0.36,1);
      "></div>
    </div>
  </div>
</div>
"""
    return breakdown


# ─── 11. AI Chat Message ──────────────────────────────────────────────────────

def render_ai_message(role: str, content: str) -> str:
    """Renders a chat bubble styled differently for 'assistant' vs 'user' roles.

    Args:
        role:    "assistant" (blue accent bubble) or "user" (dark grey bubble).
        content: The message text. Newlines are preserved.

    Returns:
        HTML string for the chat message.
    """
    now = datetime.now(timezone.utc).strftime("%H:%M UTC")

    if role.lower() == "assistant":
        avatar       = "🤖"
        bubble_bg    = "rgba(59,130,246,0.14)"
        bubble_border= "rgba(59,130,246,0.30)"
        bubble_radius= "18px 18px 18px 4px"  # pointed top-left corner
        avatar_bg    = "linear-gradient(135deg,#3b82f6,#06b6d4)"
        name         = "ORRAS AI"
        name_color   = "#93c5fd"
        align_dir    = "flex-start"
        flex_dir     = "row"
    else:
        avatar       = "👤"
        bubble_bg    = "#1e2535"
        bubble_border= "#2d3748"
        bubble_radius= "18px 18px 4px 18px"  # pointed top-right corner
        avatar_bg    = "#1f2937"
        name         = "You"
        name_color   = "#9ca3af"
        align_dir    = "flex-end"
        flex_dir     = "row-reverse"

    # Replace newlines with <br> for HTML rendering, escape other HTML
    safe_content = _esc(content).replace("\n", "<br>")

    message = f"""
<div style="
    display:flex;flex-direction:{flex_dir};gap:10px;
    margin-bottom:1rem;
    justify-content:{align_dir};
    animation:fadeIn 0.3s ease both;
    max-width:85%;
    {'margin-left:auto;' if role.lower() != 'assistant' else ''}
">
  <!-- Avatar -->
  <div style="
      width:36px;height:36px;border-radius:50%;flex-shrink:0;
      background:{avatar_bg};border:1px solid rgba(255,255,255,0.1);
      display:flex;align-items:center;justify-content:center;font-size:1.1rem;
  ">{avatar}</div>

  <!-- Bubble -->
  <div style="flex:1;">
    <div style="font-size:0.7rem;font-weight:600;color:{name_color};
                margin-bottom:3px;{'text-align:right;' if role.lower()!='assistant' else ''}">
      {_esc(name)}
    </div>
    <div style="
        background:{bubble_bg};
        border:1px solid {bubble_border};
        border-radius:{bubble_radius};
        padding:0.7rem 0.95rem;
        font-size:0.87rem;line-height:1.55;color:#e5e7eb;
    ">
      {safe_content}
    </div>
    <div style="font-size:0.65rem;color:#6b7280;margin-top:3px;
                {'text-align:right;' if role.lower()!='assistant' else ''}">
      {now}
    </div>
  </div>
</div>
"""
    return message


# ─── 12. Prediction Card ──────────────────────────────────────────────────────

def render_prediction_card(
    region: str,
    current: float,
    predicted: float,
    direction: str,
    confidence: float,
) -> str:
    """Shows current risk → predicted risk with arrow, confidence %, and trend label.

    Args:
        region:     Region name.
        current:    Current risk score (0–30).
        predicted:  Predicted risk score (0–30).
        direction:  "increasing", "decreasing", or "stable".
        confidence: Confidence percentage 0–100.

    Returns:
        HTML string for the prediction card.
    """
    current   = _clamp(current,   0.0, 30.0)
    predicted = _clamp(predicted, 0.0, 30.0)
    conf_pct  = _clamp(confidence, 0.0, 100.0)

    # Arrow and colours based on direction
    dir_map = {
        "increasing": ("→", "#ef4444", "⚠️ Risk Increasing"),
        "decreasing": ("→", "#22c55e", "✅ Risk Decreasing"),
        "stable":     ("→", "#9ca3af", "📊 Situation Stable"),
    }
    arrow_char, arrow_color, dir_label = dir_map.get(
        direction.lower(), ("→", "#9ca3af", "📊 Situation Stable")
    )

    # Colour for current and predicted scores
    def _score_color(s: float) -> str:
        if s < 9:   return "#86efac"
        if s < 16:  return "#fde047"
        if s < 23:  return "#fdba74"
        return "#fca5a5"

    cur_col  = _score_color(current)
    pred_col = _score_color(predicted)

    # Big upward/downward indicator
    if direction.lower() == "increasing":
        big_arrow = "↑"
        big_arrow_color = "#fca5a5"
    elif direction.lower() == "decreasing":
        big_arrow = "↓"
        big_arrow_color = "#86efac"
    else:
        big_arrow = "⇌"
        big_arrow_color = "#9ca3af"

    card = f"""
<div style="
    background:#111827;border:1px solid #1f2937;
    border-radius:20px;padding:1.3rem 1.5rem;
    animation:slide-in 0.35s ease both;
">
  <!-- Header -->
  <div style="display:flex;justify-content:space-between;align-items:center;
              margin-bottom:0.85rem;">
    <div>
      <div style="font-size:0.68rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.08em;color:#9ca3af;">7-Day Forecast</div>
      <div style="font-size:1rem;font-weight:700;color:#f9fafb;">{_esc(region)}</div>
    </div>
    <div style="display:flex;flex-direction:column;align-items:flex-end;gap:2px;">
      <span style="font-size:2rem;line-height:1;">{big_arrow}</span>
      <span style="color:{big_arrow_color};font-size:0.78rem;font-weight:700;
                   white-space:nowrap;">{_esc(dir_label)}</span>
    </div>
  </div>

  <!-- Score flow: current → arrow → predicted -->
  <div style="display:flex;align-items:center;gap:0.75rem;margin:0.75rem 0;">
    <div style="flex:1;text-align:center;">
      <div style="font-size:0.65rem;color:#9ca3af;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:3px;">Current</div>
      <div style="font-size:2rem;font-weight:800;color:{cur_col};
                  letter-spacing:-0.04em;line-height:1;">{current:.1f}</div>
      <div style="font-size:0.65rem;color:#6b7280;">/ 30</div>
    </div>

    <div style="font-size:1.6rem;color:{arrow_color};flex-shrink:0;">
      {arrow_char}
    </div>

    <div style="flex:1;text-align:center;">
      <div style="font-size:0.65rem;color:#9ca3af;text-transform:uppercase;
                  letter-spacing:0.06em;margin-bottom:3px;">Predicted</div>
      <div style="font-size:2rem;font-weight:800;color:{pred_col};
                  letter-spacing:-0.04em;line-height:1;">{predicted:.1f}</div>
      <div style="font-size:0.65rem;color:#6b7280;">/ 30</div>
    </div>
  </div>

  <!-- Confidence -->
  <div style="margin-top:0.75rem;">
    <div style="display:flex;justify-content:space-between;
                font-size:0.72rem;color:#9ca3af;margin-bottom:4px;">
      <span>Model Confidence</span>
      <span style="font-weight:700;color:#06b6d4;">{conf_pct:.0f}%</span>
    </div>
    <div style="width:100%;height:6px;background:rgba(255,255,255,0.07);
                border-radius:99px;overflow:hidden;">
      <div style="width:{conf_pct:.0f}%;height:100%;
                  background:linear-gradient(90deg,#3b82f6,#06b6d4);
                  border-radius:99px;
                  box-shadow:0 0 8px rgba(6,182,212,0.4);"></div>
    </div>
  </div>
</div>
"""
    return card


# ─── 13. Safety Score Card ────────────────────────────────────────────────────

def render_safety_score_card(
    category: str,
    score: float,
    status: str,
    details: list[str],
) -> str:
    """Safety category card showing a score out of 100 with status badge and detail list.

    Args:
        category: Name of the safety category (e.g. "Infrastructure Security").
        score:    Numeric score 0–100.
        status:   "SECURE", "AT RISK", or "COMPROMISED".
        details:  List of detail strings (shown as a checklist).

    Returns:
        HTML string for the safety score card.
    """
    score = _clamp(score, 0.0, 100.0)

    # Map status to visual style
    status_upper = status.upper()
    status_styles: dict[str, tuple[str, str, str, str]] = {
        "SECURE":      ("#22c55e", "#86efac", "rgba(34,197,94,0.12)",  "✅"),
        "AT RISK":     ("#eab308", "#fde047", "rgba(234,179,8,0.12)",  "⚠️"),
        "COMPROMISED": ("#ef4444", "#fca5a5", "rgba(239,68,68,0.12)",  "🔴"),
    }
    border_color, text_color, bg_color, status_icon = status_styles.get(
        status_upper, ("#3b82f6", "#93c5fd", "rgba(59,130,246,0.12)", "ℹ️")
    )

    # Score ring percentage (visual only — approximated using border trick)
    bar_pct = score

    # Build detail checklist
    detail_items = "".join(
        f'<li style="display:flex;align-items:center;gap:6px;'
        f'font-size:0.78rem;color:#d1d5db;margin-bottom:4px;">'
        f'<span style="color:#22c55e;font-weight:700;flex-shrink:0;">✓</span>'
        f'{_esc(d)}</li>'
        for d in details
    )

    card = f"""
<div style="
    background:#111827;
    border:1px solid {border_color}44;
    border-radius:20px;padding:1.3rem 1.5rem;
    animation:slide-in 0.35s ease both;
    position:relative;overflow:hidden;
">
  <!-- Top accent line -->
  <div style="position:absolute;top:0;left:0;right:0;height:3px;
              background:linear-gradient(90deg,{border_color},{border_color}44);
              border-radius:20px 20px 0 0;"></div>

  <!-- Header row -->
  <div style="display:flex;justify-content:space-between;align-items:flex-start;
              margin-bottom:0.85rem;margin-top:0.2rem;">
    <div>
      <div style="font-size:0.7rem;font-weight:700;text-transform:uppercase;
                  letter-spacing:0.08em;color:#9ca3af;margin-bottom:2px;">
        Safety Assessment
      </div>
      <div style="font-size:0.95rem;font-weight:700;color:#f9fafb;">{_esc(category)}</div>
    </div>
    <!-- Status badge -->
    <span style="
        display:inline-flex;align-items:center;gap:5px;
        padding:3px 10px;border-radius:99px;
        background:{bg_color};border:1px solid {border_color}66;
        color:{text_color};font-size:0.7rem;font-weight:700;
        letter-spacing:0.06em;text-transform:uppercase;white-space:nowrap;
    ">{status_icon} {_esc(status_upper)}</span>
  </div>

  <!-- Score display -->
  <div style="display:flex;align-items:flex-end;gap:6px;margin-bottom:0.65rem;">
    <div style="font-size:2.5rem;font-weight:800;color:{text_color};
                letter-spacing:-0.04em;line-height:1;">{score:.0f}</div>
    <div style="font-size:1rem;color:#6b7280;padding-bottom:4px;">/ 100</div>
  </div>

  <!-- Score bar -->
  <div style="width:100%;height:8px;background:rgba(255,255,255,0.07);
              border-radius:99px;overflow:hidden;margin-bottom:1rem;">
    <div style="
        width:{bar_pct:.0f}%;height:100%;
        background:linear-gradient(90deg,{border_color},{border_color}bb);
        border-radius:99px;
        box-shadow:0 0 10px {border_color}55;
        transition:width 1s cubic-bezier(0.22,1,0.36,1);
    "></div>
  </div>

  <!-- Details list -->
  <ul style="list-style:none;margin:0;padding:0;">
    {detail_items}
  </ul>
</div>
"""
    return card



# ─── 14. Intel Card ──────────────────────────────────────────────────────────

def render_intel_card(title: str, content: str, accent_color: str = "#00d4ff") -> str:
    """Renders a professional intelligence-themed content card.

    Args:
        title:        Card header label (e.g. "THREAT ASSESSMENT").
        content:      Body text or HTML content to display inside the card.
        accent_color: Hex colour for the left border and header (default: #00d4ff).

    Returns:
        HTML string for the intel card.
    """
    accent_color, r, g, b = _parse_color(accent_color)

    card = f"""
<div class="intel-card" style="
    background:linear-gradient(135deg,#0a0a1a,#0d1525);
    border:1px solid #1a3a5c;
    border-left:3px solid {accent_color};
    border-radius:4px;
    padding:16px;
    box-shadow:0 0 20px rgba({r},{g},{b},0.1);
    margin-bottom:12px;
">
  <div class="section-header" style="
      font-family:'Courier New',monospace;
      color:{accent_color};
      font-size:0.7rem;
      letter-spacing:3px;
      text-transform:uppercase;
      border-bottom:1px solid #1a3a5c;
      padding-bottom:8px;
      margin-bottom:12px;
  ">{_esc(title)}</div>
  <div style="font-size:0.85rem;color:#e0f0ff;line-height:1.6;">
    {content}
  </div>
</div>
"""
    return card


# ─── 15. Status Bar ──────────────────────────────────────────────────────────

def render_status_bar(label: str, value: float, max_val: float, color: str = "#00d4ff") -> str:
    """Renders a labeled progress/status bar in intel style.

    Args:
        label:   Text label displayed above the bar (e.g. "Threat Level").
        value:   Current numeric value.
        max_val: Maximum value (100% of bar).
        color:   Hex colour for the filled portion (default: #00d4ff).

    Returns:
        HTML string for the status bar.
    """
    color, r, g, b = _parse_color(color)

    max_val = max_val if max_val > 0 else 1
    pct = max(0.0, min(100.0, (value / max_val) * 100))

    bar = f"""
<div style="margin-bottom:10px;">
  <div style="
      display:flex;justify-content:space-between;
      font-family:'Courier New',monospace;
      font-size:0.7rem;letter-spacing:1px;
      color:#7090a0;margin-bottom:4px;
  ">
    <span style="text-transform:uppercase;">{_esc(label)}</span>
    <span style="color:{color};">{value:.0f}/{max_val:.0f}</span>
  </div>
  <div style="
      width:100%;height:6px;
      background:rgba(255,255,255,0.05);
      border:1px solid #1a3a5c;
      border-radius:2px;overflow:hidden;
  ">
    <div style="
        width:{pct:.1f}%;height:100%;
        background:linear-gradient(90deg,{color},{color}88);
        box-shadow:0 0 8px rgba({r},{g},{b},0.6);
        transition:width 0.8s ease;
    "></div>
  </div>
</div>
"""
    return bar


# Run `python ui_components.py` directly to verify all functions return strings.

if __name__ == "__main__":
    print("Running ui_components smoke test…")

    checks = [
        ("render_severity_badge",    render_severity_badge("CRITICAL")),
        ("render_metric_card",       render_metric_card("Alerts", "142", "Active signals", "#ef4444")),
        ("render_alert_banner",      render_alert_banner(["Attack detected in Zone 4"], "CRITICAL")),
        ("render_news_ticker",       render_news_ticker(["Headline one", "Headline two", "Headline three"])),
        ("render_region_card",       render_region_card("Eastern Europe", 21.5, "HIGH", "rising", "HIGH (85%)")),
        ("render_source_health_badge", render_source_health_badge("GDELT API", True)),
        ("render_threat_gauge",      render_threat_gauge(24.7)),
        ("render_comparison_bar",    render_comparison_bar("Ukraine", 25.2, "Poland", 8.4)),
        ("render_timeline_event",    render_timeline_event({
            "date": "2024-11-15 08:32 UTC", "location": "Kyiv, Ukraine",
            "description": "Significant escalation reported near northern border.",
            "severity": "HIGH", "type": "Military Activity",
        })),
        ("render_confidence_breakdown", render_confidence_breakdown(
            ["GDELT", "ACLED", "OSINT", "Social Media"], "HIGH (91%)"
        )),
        ("render_ai_message",        render_ai_message("assistant", "Based on current data, risk levels are elevated.")),
        ("render_prediction_card",   render_prediction_card("South Asia", 14.2, 18.7, "increasing", 82.5)),
        ("render_safety_score_card", render_safety_score_card(
            "Cyber Infrastructure", 67.0, "AT RISK",
            ["Firewall active", "Intrusion detection online", "2 vulnerabilities patched"],
        )),
    ]

    all_ok = True
    for name, result in checks:
        if isinstance(result, str) and len(result) > 10:
            print(f"  ✓  {name}")
        else:
            print(f"  ✗  {name}  ← returned unexpected value: {result!r}")
            all_ok = False

    print("\n✅ All checks passed." if all_ok else "\n❌ Some checks failed.")

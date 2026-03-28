"""
news_ticker.py — Live news ticker for the ORRAS v2.0 dashboard.

Provides formatted headline strings from internal signals and optional
live NewsAPI headlines, plus an injectable HTML/CSS ticker animation.
"""

import requests
from typing import Any

from config import NEWSAPI_KEY, NEWSAPI_URL


class NewsTicker:
    """Formats risk signals and live news into scrolling ticker headlines."""

    # Severities that qualify for the ticker
    _TICKER_SEVERITIES: set[str] = {"HIGH", "CRITICAL"}

    def get_ticker_headlines(
        self, signals: list[dict[str, Any]], max: int = 20
    ) -> list[str]:
        """
        Filter HIGH and CRITICAL signals and return formatted headline strings.

        Each signal dict is expected to contain: title, location, raw_score,
        severity, and source.  Signals are sorted descending by raw_score so
        the most urgent items appear first in the ticker.

        Args:
            signals: List of signal dicts from the ORRAS signal pipeline.
            max:     Maximum number of headlines to return.

        Returns:
            List of formatted headline strings, e.g.
            "🔴 [Ukraine] — Missile strike reported | Score: 34"
        """
        filtered = [
            s for s in signals
            if str(s.get("severity", "")).upper() in self._TICKER_SEVERITIES
        ]

        # Most urgent first
        filtered.sort(key=lambda s: s.get("raw_score", 0), reverse=True)

        headlines: list[str] = []
        for signal in filtered[:max]:
            region = signal.get("location", "UNKNOWN").upper()
            title = signal.get("title", "No title")
            score = signal.get("raw_score", 0)
            headlines.append(f"🔴 [{region}] — {title} | Score: {score}")

        return headlines

    def get_live_headlines(self) -> list[str]:
        """
        Attempt to fetch breaking-news headlines from NewsAPI.

        Requires a valid NEWSAPI_KEY in the environment.  Any network or
        parsing error causes a silent fallback to an empty list so the
        dashboard never crashes due to a missing API key or connectivity issue.

        Returns:
            List of formatted headline strings, or [] on failure.
        """
        if not NEWSAPI_KEY:
            return []

        try:
            params = {
                "q": (
                    "war OR conflict OR attack OR missile OR military OR "
                    "protest OR riot OR sanctions OR nuclear OR troops"
                ),
                "language": "en",
                "sortBy": "publishedAt",
                "pageSize": 20,
                "apiKey": NEWSAPI_KEY,
            }
            response = requests.get(NEWSAPI_URL, params=params, timeout=8)
            response.raise_for_status()
            articles = response.json().get("articles", [])

            headlines: list[str] = []
            for article in articles:
                source = article.get("source", {}).get("name", "NEWS")
                title = article.get("title", "").strip()
                if title:
                    headlines.append(f"🔴 [{source.upper()}] — {title}")
            return headlines

        except Exception:
            # Silently degrade — the ticker is non-critical
            return []

    def format_ticker_html(self, headlines: list[str]) -> str:
        """
        Wrap headline strings in a self-contained CSS ticker animation div.

        The ticker scrolls from right to left continuously using a pure-CSS
        animation.  The returned string is safe to inject directly into a
        Streamlit ``st.markdown(..., unsafe_allow_html=True)`` call.

        Args:
            headlines: List of headline strings to display.

        Returns:
            An HTML string containing the ticker div and its <style> block.
        """
        if not headlines:
            headlines = ["🔴 [ORRAS] — No active HIGH/CRITICAL signals at this time"]

        divider = " &nbsp;🔴&nbsp; "
        ticker_text = divider.join(headlines)

        html = f"""
<style>
  .orras-ticker-wrapper {{
    width: 100%;
    overflow: hidden;
    background: #0d1117;
    border-top: 2px solid #e63946;
    border-bottom: 2px solid #e63946;
    padding: 6px 0;
    box-sizing: border-box;
  }}
  .orras-ticker-content {{
    display: inline-block;
    white-space: nowrap;
    animation: orras-scroll 60s linear infinite;
    color: #f1faee;
    font-size: 0.88rem;
    font-family: 'Courier New', Courier, monospace;
    letter-spacing: 0.03em;
  }}
  @keyframes orras-scroll {{
    0%   {{ transform: translateX(100vw); }}
    100% {{ transform: translateX(-100%); }}
  }}
</style>
<div class="orras-ticker-wrapper">
  <span class="orras-ticker-content">{ticker_text}</span>
</div>
"""
        return html


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    sample_signals = [
        {
            "title": "Large-scale troop mobilisation detected",
            "location": "Ukraine",
            "raw_score": 38,
            "severity": "CRITICAL",
            "source": "GDELT",
        },
        {
            "title": "Internet blackout reported across capital",
            "location": "Myanmar",
            "raw_score": 14,
            "severity": "HIGH",
            "source": "NetBlocks",
        },
        {
            "title": "Routine military exercise concluded",
            "location": "Germany",
            "raw_score": 3,
            "severity": "LOW",
            "source": "NewsAPI",
        },
        {
            "title": "Missile strike on civilian infrastructure",
            "location": "Yemen",
            "raw_score": 42,
            "severity": "CRITICAL",
            "source": "NASA FIRMS",
        },
    ]

    ticker = NewsTicker()

    headlines = ticker.get_ticker_headlines(sample_signals)
    print("=== Formatted headlines ===")
    for h in headlines:
        print(h)

    html = ticker.format_ticker_html(headlines)
    print("\n=== Ticker HTML (truncated) ===")
    print(html[:300], "...")

    live = ticker.get_live_headlines()
    print(f"\n=== Live headlines fetched: {len(live)} ===")
    for h in live[:3]:
        print(h)

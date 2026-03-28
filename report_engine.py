"""
report_engine.py — PDF report generator for ORRAS v2.0.

Produces a multi-section intelligence brief using ReportLab, covering the
executive summary, top-regions table, signal breakdown, anomaly alerts,
safety scorecard, 3-day forecast, and an appendix of critical signals.
"""

import os
from datetime import datetime
from io import BytesIO
from typing import Any

from reportlab.lib import colors
from reportlab.lib.pagesizes import letter
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import inch
from reportlab.lib.utils import ImageReader
from reportlab.platypus import (
    PageBreak,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)
from reportlab.lib.colors import HexColor

# ---------------------------------------------------------------------------
# Palette
# ---------------------------------------------------------------------------
_NAVY = HexColor("#1e3a5f")
_NAVY_LIGHT = HexColor("#2e5080")
_RED = HexColor("#c0392b")
_ORANGE = HexColor("#e67e22")
_GREEN = HexColor("#27ae60")
_YELLOW = HexColor("#f1c40f")
_ROW_ALT = HexColor("#eaf0fb")  # alternating table row tint
_ROW_HEAD = _NAVY


class ReportEngine:
    """Generates and persists professional PDF intelligence reports."""

    # Default output directory (relative to CWD)
    REPORTS_DIR: str = "data/reports"

    # ---------------------------------------------------------------------------
    # Public API
    # ---------------------------------------------------------------------------

    def generate_daily_report(
        self,
        signals: list[dict[str, Any]],
        anomalies: list[dict[str, Any]],
        escalations: list[dict[str, Any]],
        forecasts: dict[str, Any],
        safety: dict[str, Any],
    ) -> bytes:
        """
        Build a full-length intelligence PDF and return it as raw bytes.

        Sections produced:
          1. Cover page
          2. Executive Summary
          3. Top-10 regions table
          4. Signal breakdown by source
          5. Anomaly alerts
          6. Safety index scorecard  (omitted when safety is empty)
          7. 3-day forecast table    (omitted when forecasts is empty)
          8. Appendix — CRITICAL & HIGH signal list

        Args:
            signals:     List of signal dicts from the ORRAS pipeline.
            anomalies:   List of anomaly dicts from the anomaly engine.
            escalations: List of escalation event dicts.
            forecasts:   Dict of region → forecast payload (may be empty).
            safety:      Dict of safety index data (may be empty).

        Returns:
            PDF file contents as a ``bytes`` object.
        """
        buf = BytesIO()
        doc = SimpleDocTemplate(
            buf,
            pagesize=letter,
            leftMargin=0.85 * inch,
            rightMargin=0.85 * inch,
            topMargin=0.85 * inch,
            bottomMargin=0.85 * inch,
        )
        styles = self._build_styles()
        story: list = []

        # -- Cover ----------------------------------------------------------
        story += self._cover_page(styles)
        story.append(PageBreak())

        # -- Executive Summary ----------------------------------------------
        story += self._executive_summary(signals, anomalies, escalations, styles)
        story.append(PageBreak())

        # -- Top-10 Regions -------------------------------------------------
        story += self._top_regions_section(signals, styles)
        story.append(PageBreak())

        # -- Signal Breakdown by Source -------------------------------------
        story += self._source_breakdown_section(signals, styles)

        # -- Anomaly Alerts -------------------------------------------------
        story += self._anomaly_section(anomalies, styles)

        # -- Safety Scorecard (optional) ------------------------------------
        if safety:
            story.append(PageBreak())
            story += self._safety_section(safety, styles)

        # -- 3-Day Forecast (optional) --------------------------------------
        if forecasts:
            story.append(PageBreak())
            story += self._forecast_section(forecasts, styles)

        # -- Appendix -------------------------------------------------------
        story.append(PageBreak())
        story += self._appendix(signals, styles)

        doc.build(story)
        return buf.getvalue()

    def save_report(self, pdf_bytes: bytes, filename: str) -> None:
        """
        Write *pdf_bytes* to ``data/reports/<filename>``.

        Creates the directory tree if it does not already exist.

        Args:
            pdf_bytes: Raw PDF content returned by :meth:`generate_daily_report`.
            filename:  Destination file name (not a full path).
        """
        os.makedirs(self.REPORTS_DIR, exist_ok=True)
        path = os.path.join(self.REPORTS_DIR, filename)
        with open(path, "wb") as fh:
            fh.write(pdf_bytes)
        print(f"[ReportEngine] Saved: {path}")

    def get_report_filename(self) -> str:
        """
        Return a timestamp-stamped filename for today's report.

        Returns:
            String of the form ``ORRAS_Report_YYYY-MM-DD_HH-MM.pdf``.
        """
        return datetime.now().strftime("ORRAS_Report_%Y-%m-%d_%H-%M.pdf")

    # ---------------------------------------------------------------------------
    # Internal helpers — styles
    # ---------------------------------------------------------------------------

    def _build_styles(self) -> dict[str, ParagraphStyle]:
        """Construct and return a mapping of named ParagraphStyle objects."""
        base = getSampleStyleSheet()

        def ps(name: str, **kwargs) -> ParagraphStyle:
            return ParagraphStyle(name, parent=base["Normal"], **kwargs)

        return {
            "cover_title": ps(
                "cover_title",
                fontSize=48,
                textColor=_NAVY,
                spaceAfter=12,
                spaceBefore=80,
                fontName="Helvetica-Bold",
                alignment=1,  # centre
            ),
            "cover_subtitle": ps(
                "cover_subtitle",
                fontSize=16,
                textColor=_NAVY_LIGHT,
                spaceAfter=6,
                fontName="Helvetica",
                alignment=1,
            ),
            "cover_unclass": ps(
                "cover_unclass",
                fontSize=13,
                textColor=colors.white,
                fontName="Helvetica-Bold",
                alignment=1,
            ),
            "section_heading": ps(
                "section_heading",
                fontSize=15,
                textColor=_NAVY,
                fontName="Helvetica-Bold",
                spaceBefore=14,
                spaceAfter=6,
                borderPadding=(0, 0, 4, 0),
            ),
            "body": ps(
                "body",
                fontSize=10,
                textColor=colors.black,
                spaceAfter=4,
                leading=14,
            ),
            "kpi_label": ps(
                "kpi_label",
                fontSize=11,
                textColor=_NAVY,
                fontName="Helvetica-Bold",
            ),
            "critical": ps(
                "critical",
                fontSize=10,
                textColor=_RED,
                fontName="Helvetica-Bold",
            ),
            "high": ps(
                "high",
                fontSize=10,
                textColor=_ORANGE,
                fontName="Helvetica-Bold",
            ),
            "footer": ps(
                "footer",
                fontSize=8,
                textColor=colors.grey,
                alignment=1,
            ),
        }

    # ---------------------------------------------------------------------------
    # Internal helpers — sections
    # ---------------------------------------------------------------------------

    def _cover_page(self, styles: dict) -> list:
        """Return flowables for the report cover page."""
        now = datetime.now()
        elements: list = []

        elements.append(Spacer(1, 1.2 * inch))
        elements.append(Paragraph("ORRAS", styles["cover_title"]))
        elements.append(Paragraph(
            "Operational Risk &amp; Regional Alert System",
            styles["cover_subtitle"],
        ))
        elements.append(Spacer(1, 0.3 * inch))
        elements.append(Paragraph(
            f"Daily Intelligence Report — {now.strftime('%A, %d %B %Y')}",
            styles["cover_subtitle"],
        ))
        elements.append(Paragraph(
            f"Generated: {now.strftime('%H:%M UTC')}",
            styles["cover_subtitle"],
        ))
        elements.append(Spacer(1, 0.6 * inch))

        # UNCLASSIFIED banner
        banner_table = Table(
            [[Paragraph("✦  UNCLASSIFIED  ✦", styles["cover_unclass"])]],
            colWidths=[6.5 * inch],
        )
        banner_table.setStyle(TableStyle([
            ("BACKGROUND", (0, 0), (-1, -1), _GREEN),
            ("ALIGN", (0, 0), (-1, -1), "CENTER"),
            ("TOPPADDING", (0, 0), (-1, -1), 8),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 8),
            ("ROUNDEDCORNERS", [4, 4, 4, 4]),
        ]))
        elements.append(banner_table)
        elements.append(Spacer(1, 1.5 * inch))

        elements.append(Paragraph(
            "FOR AUTHORISED PERSONNEL ONLY",
            styles["footer"],
        ))
        return elements

    def _executive_summary(
        self,
        signals: list[dict],
        anomalies: list[dict],
        escalations: list[dict],
        styles: dict,
    ) -> list:
        """Return flowables for the Executive Summary page."""
        elements: list = []
        elements.append(Paragraph("Executive Summary", styles["section_heading"]))
        elements.append(self._divider())

        critical = [s for s in signals if s.get("severity", "").upper() == "CRITICAL"]
        high = [s for s in signals if s.get("severity", "").upper() == "HIGH"]
        medium = [s for s in signals if s.get("severity", "").upper() == "MEDIUM"]
        low = [s for s in signals if s.get("severity", "").upper() == "LOW"]

        avg_score = (
            sum(s.get("raw_score", 0) for s in signals) / len(signals)
            if signals else 0
        )

        summary_text = (
            f"As of {datetime.now().strftime('%d %B %Y %H:%M UTC')}, the ORRAS system "
            f"has processed <b>{len(signals)}</b> signals across all monitored regions. "
            f"The global threat landscape presents <b>{len(critical)} CRITICAL</b> and "
            f"<b>{len(high)} HIGH</b> alerts requiring immediate analyst attention. "
            f"<b>{len(anomalies)}</b> statistical anomalies and "
            f"<b>{len(escalations)}</b> active escalation events are also recorded. "
            f"The mean composite risk score across all signals is "
            f"<b>{avg_score:.1f}</b>."
        )
        elements.append(Paragraph(summary_text, styles["body"]))
        elements.append(Spacer(1, 0.25 * inch))

        # KPI table
        kpi_data = [
            ["Metric", "Count"],
            ["Total Signals Processed", str(len(signals))],
            ["CRITICAL Alerts", str(len(critical))],
            ["HIGH Alerts", str(len(high))],
            ["MEDIUM Alerts", str(len(medium))],
            ["LOW Alerts", str(len(low))],
            ["Statistical Anomalies", str(len(anomalies))],
            ["Active Escalations", str(len(escalations))],
            ["Mean Risk Score", f"{avg_score:.1f}"],
        ]
        kpi_table = Table(kpi_data, colWidths=[4 * inch, 2 * inch])
        kpi_table.setStyle(self._base_table_style(len(kpi_data)))

        # Colour-code critical and high rows
        kpi_table.setStyle(TableStyle([
            ("TEXTCOLOR", (0, 2), (1, 2), _RED),
            ("TEXTCOLOR", (0, 3), (1, 3), _ORANGE),
        ]))
        elements.append(kpi_table)
        return elements

    def _top_regions_section(self, signals: list[dict], styles: dict) -> list:
        """Return flowables for the Top-10 Regions table."""
        elements: list = []
        elements.append(Paragraph("Top 10 Regions by Risk Score", styles["section_heading"]))
        elements.append(self._divider())

        # Aggregate max score per region
        region_scores: dict[str, dict] = {}
        for s in signals:
            loc = s.get("location", "Unknown")
            score = s.get("raw_score", 0)
            sev = s.get("severity", "LOW").upper()
            if loc not in region_scores or score > region_scores[loc]["score"]:
                region_scores[loc] = {"score": score, "severity": sev}

        top10 = sorted(region_scores.items(), key=lambda x: x[1]["score"], reverse=True)[:10]

        table_data = [["#", "Region", "Max Risk Score", "Severity"]]
        for rank, (region, info) in enumerate(top10, start=1):
            table_data.append([str(rank), region, str(info["score"]), info["severity"]])

        tbl = Table(table_data, colWidths=[0.5 * inch, 2.5 * inch, 1.8 * inch, 1.5 * inch])
        tbl.setStyle(self._base_table_style(len(table_data)))

        # Colour-code severity cells
        for row_idx, (_, info) in enumerate(top10, start=1):
            sev = info["severity"]
            color = _RED if sev == "CRITICAL" else _ORANGE if sev == "HIGH" else colors.black
            tbl.setStyle(TableStyle([("TEXTCOLOR", (3, row_idx), (3, row_idx), color)]))

        elements.append(tbl)
        return elements

    def _source_breakdown_section(self, signals: list[dict], styles: dict) -> list:
        """Return flowables for the Signal Breakdown by Source table."""
        elements: list = []
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph("Signal Breakdown by Source", styles["section_heading"]))
        elements.append(self._divider())

        source_counts: dict[str, int] = {}
        for s in signals:
            src = s.get("source", "Unknown")
            source_counts[src] = source_counts.get(src, 0) + 1

        table_data = [["Source", "Signal Count", "% of Total"]]
        total = len(signals) or 1
        for src, count in sorted(source_counts.items(), key=lambda x: x[1], reverse=True):
            pct = (count / total) * 100
            table_data.append([src, str(count), f"{pct:.1f}%"])

        tbl = Table(table_data, colWidths=[3 * inch, 1.8 * inch, 1.8 * inch])
        tbl.setStyle(self._base_table_style(len(table_data)))
        elements.append(tbl)
        return elements

    def _anomaly_section(self, anomalies: list[dict], styles: dict) -> list:
        """Return flowables for the Anomaly Alerts section."""
        elements: list = []
        elements.append(Spacer(1, 0.15 * inch))
        elements.append(Paragraph("Anomaly Alerts", styles["section_heading"]))
        elements.append(self._divider())

        if not anomalies:
            elements.append(Paragraph("No statistical anomalies detected.", styles["body"]))
            return elements

        table_data = [["Region", "Signal Type", "Z-Score", "Description"]]
        for a in anomalies[:20]:
            table_data.append([
                a.get("location", "N/A"),
                a.get("signal_type", "N/A"),
                f"{a.get('z_score', 0):.2f}",
                (a.get("description") or a.get("title", "—"))[:60],
            ])

        tbl = Table(
            table_data,
            colWidths=[1.4 * inch, 1.4 * inch, 1 * inch, 3 * inch],
        )
        tbl.setStyle(self._base_table_style(len(table_data)))
        elements.append(tbl)
        return elements

    def _safety_section(self, safety: dict[str, Any], styles: dict) -> list:
        """Return flowables for the Safety Index Scorecard."""
        elements: list = []
        elements.append(Paragraph("Safety Index Scorecard", styles["section_heading"]))
        elements.append(self._divider())

        if not safety:
            elements.append(Paragraph("No safety data available.", styles["body"]))
            return elements

        table_data = [["Region / Metric", "Safety Index", "Status"]]
        for region, data in safety.items():
            if isinstance(data, dict):
                index = data.get("safety_index", data.get("score", "N/A"))
                status = data.get("status", "—")
            else:
                index = str(data)
                status = "—"
            table_data.append([region, str(index), status])

        tbl = Table(table_data, colWidths=[3 * inch, 1.8 * inch, 1.8 * inch])
        tbl.setStyle(self._base_table_style(len(table_data)))
        elements.append(tbl)
        return elements

    def _forecast_section(self, forecasts: dict[str, Any], styles: dict) -> list:
        """Return flowables for the 3-Day Forecast table."""
        elements: list = []
        elements.append(Paragraph("3-Day Risk Forecast", styles["section_heading"]))
        elements.append(self._divider())
        elements.append(Paragraph(
            "Projected risk scores for the next three days based on trend analysis.",
            styles["body"],
        ))
        elements.append(Spacer(1, 0.1 * inch))

        table_data = [["Region", "Day 1", "Day 2", "Day 3", "Trend"]]
        for region, fc in list(forecasts.items())[:15]:
            if isinstance(fc, dict):
                days = fc.get("forecast", [None, None, None])
                trend = fc.get("trend", "—")
            elif isinstance(fc, (list, tuple)):
                days = list(fc) + [None] * 3
                trend = "—"
            else:
                days = [None, None, None]
                trend = "—"

            def _fmt(v: Any) -> str:
                return f"{v:.1f}" if isinstance(v, (int, float)) else str(v or "—")

            table_data.append([
                region,
                _fmt(days[0] if len(days) > 0 else None),
                _fmt(days[1] if len(days) > 1 else None),
                _fmt(days[2] if len(days) > 2 else None),
                trend,
            ])

        tbl = Table(
            table_data,
            colWidths=[2.2 * inch, 1 * inch, 1 * inch, 1 * inch, 1.4 * inch],
        )
        tbl.setStyle(self._base_table_style(len(table_data)))
        elements.append(tbl)
        return elements

    def _appendix(self, signals: list[dict], styles: dict) -> list:
        """Return flowables for the Appendix listing all CRITICAL and HIGH signals."""
        elements: list = []
        elements.append(Paragraph("Appendix — Critical &amp; High Signals", styles["section_heading"]))
        elements.append(self._divider())
        elements.append(Paragraph(
            "Full list of CRITICAL and HIGH severity signals included in this report.",
            styles["body"],
        ))
        elements.append(Spacer(1, 0.1 * inch))

        priority = [
            s for s in signals
            if s.get("severity", "").upper() in {"CRITICAL", "HIGH"}
        ]
        priority.sort(key=lambda s: s.get("raw_score", 0), reverse=True)

        if not priority:
            elements.append(Paragraph("No CRITICAL or HIGH signals to display.", styles["body"]))
            return elements

        table_data = [["#", "Title", "Region", "Score", "Severity", "Source"]]
        for idx, s in enumerate(priority, start=1):
            table_data.append([
                str(idx),
                (s.get("title", "—"))[:45],
                s.get("location", "—"),
                str(s.get("raw_score", 0)),
                s.get("severity", "—").upper(),
                s.get("source", "—"),
            ])

        tbl = Table(
            table_data,
            colWidths=[0.4 * inch, 2.6 * inch, 1.2 * inch, 0.6 * inch, 0.85 * inch, 1.1 * inch],
        )
        tbl.setStyle(self._base_table_style(len(table_data)))

        # Colour-code CRITICAL / HIGH severity cells
        for row_idx, s in enumerate(priority, start=1):
            sev = s.get("severity", "").upper()
            color = _RED if sev == "CRITICAL" else _ORANGE
            tbl.setStyle(TableStyle([("TEXTCOLOR", (4, row_idx), (4, row_idx), color)]))

        elements.append(tbl)
        return elements

    # ---------------------------------------------------------------------------
    # Shared table style
    # ---------------------------------------------------------------------------

    @staticmethod
    def _base_table_style(row_count: int) -> TableStyle:
        """
        Return a TableStyle with header formatting, gridlines, and alternating
        row shading for a table of *row_count* rows (including the header).
        """
        cmds = [
            # Header row
            ("BACKGROUND", (0, 0), (-1, 0), _ROW_HEAD),
            ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
            ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
            ("FONTSIZE", (0, 0), (-1, 0), 10),
            ("ALIGN", (0, 0), (-1, 0), "CENTER"),
            ("BOTTOMPADDING", (0, 0), (-1, 0), 7),
            ("TOPPADDING", (0, 0), (-1, 0), 7),
            # Body rows
            ("FONTNAME", (0, 1), (-1, -1), "Helvetica"),
            ("FONTSIZE", (0, 1), (-1, -1), 9),
            ("TOPPADDING", (0, 1), (-1, -1), 5),
            ("BOTTOMPADDING", (0, 1), (-1, -1), 5),
            ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            # Grid
            ("GRID", (0, 0), (-1, -1), 0.4, HexColor("#cccccc")),
            ("LINEBELOW", (0, 0), (-1, 0), 1.5, _NAVY),
        ]
        # Alternating row shading (skip header row 0)
        for row in range(1, row_count):
            if row % 2 == 0:
                cmds.append(("BACKGROUND", (0, row), (-1, row), _ROW_ALT))
        return TableStyle(cmds)

    @staticmethod
    def _divider() -> Table:
        """Return a thin navy-coloured horizontal rule as a single-cell Table."""
        tbl = Table([[""]], colWidths=[6.8 * inch], rowHeights=[2])
        tbl.setStyle(TableStyle([
            ("LINEBELOW", (0, 0), (-1, -1), 1.5, _NAVY),
            ("TOPPADDING", (0, 0), (-1, -1), 0),
            ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
        ]))
        return tbl


# ---------------------------------------------------------------------------
# Quick smoke-test
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    import random

    random.seed(0)

    REGIONS = [
        "Ukraine", "Russia", "Syria", "Iran", "North Korea",
        "Myanmar", "Yemen", "Sudan", "Taiwan", "Israel",
    ]
    SOURCES = ["GDELT", "NewsAPI", "NASA FIRMS", "NetBlocks", "OpenSky"]
    SEVERITIES = ["LOW", "MEDIUM", "HIGH", "CRITICAL"]

    def _rand_signal(i: int) -> dict:
        sev = random.choice(SEVERITIES)
        score = {"LOW": 3, "MEDIUM": 8, "HIGH": 15, "CRITICAL": 30}[sev] + random.randint(0, 10)
        return {
            "id": f"SIG-{i:04d}",
            "title": f"Sample signal event #{i} — {random.choice(REGIONS)}",
            "location": random.choice(REGIONS),
            "raw_score": score,
            "severity": sev,
            "source": random.choice(SOURCES),
        }

    sample_signals = [_rand_signal(i) for i in range(1, 61)]
    sample_anomalies = [
        {
            "location": "Ukraine",
            "signal_type": "troop_movement",
            "z_score": 3.4,
            "description": "Abnormal spike in troop-movement signals vs 7-day baseline",
        },
        {
            "location": "Taiwan",
            "signal_type": "aircraft_anomaly",
            "z_score": 2.8,
            "description": "Elevated ADIZ incursions beyond rolling average",
        },
    ]
    sample_escalations = [
        {"region": "Ukraine", "level": 4, "description": "Escalation to level 4"},
        {"region": "Taiwan", "level": 3, "description": "Escalation to level 3"},
    ]
    sample_forecasts = {
        "Ukraine": {"forecast": [38.2, 41.0, 44.5], "trend": "↑ Rising"},
        "Taiwan": {"forecast": [22.1, 20.8, 19.4], "trend": "↓ Falling"},
        "Myanmar": {"forecast": [16.0, 16.5, 17.0], "trend": "→ Stable"},
    }
    sample_safety = {
        "Ukraine": {"safety_index": 12, "status": "Critical"},
        "Taiwan": {"safety_index": 45, "status": "Moderate"},
        "Germany": {"safety_index": 88, "status": "Safe"},
    }

    engine = ReportEngine()
    pdf_bytes = engine.generate_daily_report(
        signals=sample_signals,
        anomalies=sample_anomalies,
        escalations=sample_escalations,
        forecasts=sample_forecasts,
        safety=sample_safety,
    )

    filename = engine.get_report_filename()
    engine.save_report(pdf_bytes, filename)
    print(f"[ReportEngine] Test report size: {len(pdf_bytes):,} bytes")
    print(f"[ReportEngine] Filename: {filename}")

```
  ██████╗ ██████╗ ██████╗  █████╗ ███████╗
 ██╔═══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝
 ██║   ██║██████╔╝██████╔╝███████║███████╗
 ██║   ██║██╔══██╗██╔══██╗██╔══██╗╚════██║
 ╚██████╔╝██║  ██║██║  ██║██║  ██║███████║
  ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝
  v3.0 — Integrated Intelligence Fusion & Disaster Response System
```

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-FF4B4B?logo=streamlit)
![Plotly](https://img.shields.io/badge/Plotly-5.20%2B-3F4F75?logo=plotly)
![Claude AI](https://img.shields.io/badge/Claude-AI%20Powered-8A2BE2?logo=anthropic)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

---

## What is ORRAS?

**ORRAS** (Operational Risk & Regional Alert System) v3.0 is a production-grade, multi-source OSINT intelligence fusion and disaster response platform. It ingests signals from up to 13 real-time data sources, correlates them using statistical and AI-powered engines, and surfaces actionable risk alerts through a 12-page interactive Streamlit dashboard.

ORRAS features dual-track threat analysis (conflict + disaster), AI-powered decision support via the Claude API, geofence monitoring, automated PDF reporting, resource allocation intelligence, crisis scenario simulation, SQLite persistence, and a fully explainable intelligence pipeline. It is designed for analysts, researchers, emergency management professionals, and security teams who need a single pane of glass across military movements, cyber threats, humanitarian crises, natural disasters, and more.

---

## ✨ v3.0 Features (30+)

| Feature | Description |
|---|---|
| 🤖 AI Assistant | Claude-powered natural-language Q&A over live signal data |
| 📈 Prediction Engine | Weighted linear regression 3-day forecasts with confidence scoring |
| 🌍 Country Comparator | Side-by-side risk comparison, keyword overlap, global ranking table |
| 🕐 Timeline View | Chronological signal replay with turning points and region drill-down |
| 🛡️ Safety Monitor | 6-domain safety scores (cyber, nuclear, infrastructure, maritime, economic, humanitarian) |
| 📄 Report Engine | One-click PDF reports and multi-format exports (CSV/JSON) |
| 🔴 Live News Ticker | Auto-scrolling headlines from the signal feed |
| 🌐 3D Globe View | Interactive Plotly globe with risk heat-overlay |
| 📊 Anomaly Detection | Z-score rolling-window outlier detection per region |
| 🔗 Correlation Engine | Cross-source signal correlation with configurable bonuses |
| ⚡ Escalation Tracker | 72-hour escalation window with jump-level alerting |
| 🔒 Confidence Engine | Per-signal confidence scoring with source reliability weights |
| 🌋 Disaster Response | Dual-track disaster monitoring: globe, type breakdown, WHO feeds, USGS earthquakes |
| 📦 Resource Allocation | Inventory tracking, deployment orders, scenario simulation, manual overrides |
| 🎮 Scenario Simulator | 5 preset crisis scenarios + custom builder, before/after comparison, JSON export |
| 🔍 Explainability Center | Full reasoning chain for every region, signal, anomaly, forecast, and allocation |
| ⚡ Fusion Center | Fusion matrix heatmap, compound event detection, source corroboration analysis |
| 🗄️ Database Explorer | SQLite browser, alert history, escalation chart, raw SQL query, data cleanup |
| 🔒 Geofence Monitoring | Network/internet shutdown detection mapped by region |
| 📍 Choropleth Coverage | Resource coverage percentage mapped by country |
| 🤝 Source Corroboration | Cross-source region overlap analysis for intelligence validation |
| 🎯 Fusion Confidence | Per-region confidence scoring based on multi-source corroboration |
| 💥 Compound Events | Automatic detection of multi-domain event combinations |
| 📋 Audit Trail | Full chronological pipeline decision log |
| ⚙️ Offline Mock Mode | Complete functionality without any API keys via synthetic data |
| 🗃️ SQLite Persistence | All signals, alerts, deployments, and scenarios stored in local DB |
| 📥 Multi-format Export | Download signals, alerts, scenarios as CSV or JSON |
| 🔬 Custom Scenarios | Build and run custom crisis scenarios with configurable parameters |
| 📊 Worst-Case Analysis | Automated worst-case assessment across all 5 preset scenarios |
| 🌡️ Safety SVG Gauge | Circular SVG safety score gauge with letter grades (A–F) |

---

## Architecture

```
┌──────────────────────────────────────────────────────────────────┐
│                         app.py  (Streamlit)                      │
│   Main Dashboard: Globe · Ticker · Alert Feed · Refresh Timer    │
└────────────────────────┬─────────────────────────────────────────┘
                         │  shared data layer
        ┌────────────────▼────────────────┐
        │         data_processor.py        │
        │   normalise · score · aggregate  │
        └──┬──────────┬──────────┬────────┘
           │          │          │
    ┌──────▼──┐  ┌────▼────┐  ┌──▼───────┐
    │data_    │  │mock_    │  │data_     │
    │collector│  │data_    │  │dir       │
    │.py      │  │generator│  │(JSON)    │
    │(6 APIs) │  │.py      │  │          │
    └─────────┘  └─────────┘  └──────────┘

  ┌───────────────────── Engine Layer ──────────────────────────┐
  │  anomaly_engine.py      correlation_engine.py               │
  │  prediction_engine.py   confidence_engine.py                │
  │  safety_engine.py       escalation_tracker.py               │
  │  threat_engine.py       timeline_engine.py                  │
  │  action_engine.py       report_engine.py                    │
  └──────────────────────────────────────────────────────────────┘

  ┌───────────────────── Pages Layer ───────────────────────────┐
  │  01_AI_Assistant.py     02_Predictions.py                   │
  │  03_Country_Compare.py  04_Timeline.py                      │
  │  05_Safety_Monitor.py   06_Reports.py                       │
  │  07_Disaster_Response.py  08_Resource_Allocation.py         │
  │  09_Scenario_Simulator.py 10_Explainability.py              │
  │  11_Fusion_Center.py    12_Database_Explorer.py             │
  └──────────────────────────────────────────────────────────────┘

  ┌───────────────────── Support Layer ─────────────────────────┐
  │  ai_assistant.py   news_ticker.py   ui_components.py        │
  │  utils.py          config.py                                │
  └──────────────────────────────────────────────────────────────┘
```

---

## 🚀 Installation

```bash
# 1. Clone the repository
git clone https://github.com/your-org/ORRAS.git
cd ORRAS

# 2. Create and activate a virtual environment (recommended)
python -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Configure environment variables
cp .env.example .env
# Edit .env and fill in your API keys (see Configuration below)

# 5. Launch the dashboard
streamlit run app.py
```

The dashboard will open at **http://localhost:8501** in your browser.

---

## ⚙️ Configuration

All configuration is handled through environment variables in your `.env` file.

| Variable | Required | Default | Description |
|---|---|---|---|
| `NEWSAPI_KEY` | Optional | `""` | NewsAPI.org key for live headlines |
| `NASA_FIRMS_KEY` | Optional | `""` | NASA FIRMS key for satellite fire data |
| `ANTHROPIC_API_KEY` | Optional | `""` | Anthropic key for Claude AI features |
| `AI_FEATURES_ENABLED` | No | `true` | Set `false` to disable all AI features |
| `OFFLINE_MODE` | No | `false` | Set `true` to use only mock data (no API calls) |

> **Tip:** GDELT, OpenSky Network, and Cloudflare Radar are free and require no API key.

### Advanced constants (config.py)

| Constant | Default | Description |
|---|---|---|
| `Z_SCORE_THRESHOLD` | `2.0` | Anomaly detection sensitivity |
| `ROLLING_WINDOW_DAYS` | `7` | Rolling window for baseline calculation |
| `FORECAST_DAYS` | `3` | Days ahead to forecast |
| `FORECAST_CONFIDENCE_THRESHOLD` | `0.6` | Minimum confidence to display a forecast |
| `ESCALATION_WINDOW_HOURS` | `72` | Sliding window for escalation detection |
| `ESCALATION_LEVEL_JUMP` | `2` | Minimum risk-level delta to trigger an alert |
| `DASHBOARD_REFRESH_SECONDS` | `60` | Auto-refresh interval for the main dashboard |
| `TICKER_SPEED_SECONDS` | `30` | News ticker scroll interval |

---

## 📂 Module Reference (25+ modules)

### Core

| File | Purpose |
|---|---|
| `app.py` | Main Streamlit entry point; renders the globe, ticker, and alert feed |
| `config.py` | Single source of truth for all constants, thresholds, and env-var bindings |
| `utils.py` | Shared utilities: formatting, date helpers, severity classification, JSON I/O |

### Data Layer

| File | Purpose |
|---|---|
| `data_collector.py` | Fetches raw signals from 13 live APIs (NewsAPI, GDELT, OpenSky, NASA FIRMS, Cloudflare Radar, NetBlocks, WHO, USGS…) |
| `data_processor.py` | Normalises raw API responses, applies keyword scoring, builds the unified signal schema |
| `mock_data_generator.py` | Generates realistic synthetic signals for offline / demo / test mode |

### Engine Layer

| File | Purpose |
|---|---|
| `anomaly_engine.py` | Z-score anomaly detection with configurable rolling 7-day window |
| `correlation_engine.py` | Cross-source signal correlation with bonus scoring for co-occurring event types |
| `prediction_engine.py` | Weighted linear regression forecasting with confidence intervals and trend detection |
| `confidence_engine.py` | Per-signal confidence scoring based on source reliability weights |
| `safety_engine.py` | 6-domain safety index (cyber, nuclear, infrastructure, maritime, economic, humanitarian) |
| `escalation_tracker.py` | Tracks risk-level trajectories and fires escalation alerts within a 72-hour window |
| `threat_engine.py` | Keyword-based scoring engine: raw_score = Σ(keyword_weights) × source_multiplier |
| `timeline_engine.py` | Builds time-ordered signal sequences and detects turning points |
| `action_engine.py` | Recommends actions based on current threat level and domain |
| `report_engine.py` | Generates professional multi-section PDF intelligence reports via ReportLab |
| `ai_assistant.py` | Claude API wrapper providing natural-language analysis over live signal data |
| `news_ticker.py` | Filters and formats headlines for the auto-scrolling ticker component |
| `ui_components.py` | 12+ reusable Streamlit HTML components (gauges, badges, cards, comparison bars, timeline events) |
| `comparison_engine.py` | Region-vs-region comparison with keyword overlap, score delta, and global ranking |

---

## 🖥️ Dashboard Pages (12 Pages)

| Page | File | Description |
|---|---|---|
| **Main Dashboard** | `app.py` | Live 3D globe with risk heat-overlay, scrolling news ticker, and alert feed |
| **AI Assistant** | `pages/01_AI_Assistant.py` | Chat interface powered by Claude; ask questions about current signals in plain English |
| **Predictions** | `pages/02_Predictions.py` | 3-day risk forecasts per region with confidence bands and trend indicators |
| **Country Compare** | `pages/03_Country_Compare.py` | Side-by-side comparison of risk scores, signal counts, keyword overlap, global ranking |
| **Timeline** | `pages/04_Timeline.py` | Chronological event replay with escalation overlays and filterable signal types |
| **Safety Monitor** | `pages/05_Safety_Monitor.py` | 6-domain safety scores (cyber, nuclear, infrastructure, maritime, economic, humanitarian) with SVG gauge |
| **Reports** | `pages/06_Reports.py` | Generate/download PDF reports; export signals as CSV/JSON; alert history; custom report builder |
| **Disaster Response** | `pages/07_Disaster_Response.py` | Disaster globe, type breakdown pie, top hotspots, WHO disease feed, USGS earthquakes, evacuation recommendations |
| **Resource Allocation** | `pages/08_Resource_Allocation.py` | Global inventory, regional demand table, deployment orders, coverage map, scenario simulation, manual overrides |
| **Scenario Simulator** | `pages/09_Scenario_Simulator.py` | 5 preset crisis scenarios + custom builder; before/after comparison; hour-by-hour escalation chart; JSON export |
| **Explainability** | `pages/10_Explainability.py` | Full reasoning chain for regions, signals, anomalies, forecasts, resource allocations, and pipeline audit trail |
| **Fusion Center** | `pages/11_Fusion_Center.py` | Fusion matrix heatmap, compound event cards, dual-track bar chart, source corroboration, AI SITREP, alert feed |
| **Database Explorer** | `pages/12_Database_Explorer.py` | SQLite browser with pagination/filters, escalation chart, deployment log, DB health, cleanup slider, raw SQL input |

---

## 🔌 Offline / Mock Mode

Set `OFFLINE_MODE=true` in your `.env` to run ORRAS entirely on synthetic data with no external API calls. This is useful for:

- Development and UI work without API quotas
- Demos in air-gapped or restricted environments
- Automated testing pipelines

Mock data is generated by `mock_data_generator.py` using `faker` and mirrors the structure of real signals, including realistic region distribution, keyword scoring, and escalation patterns.

---

## 🔑 API Keys Guide

All keys are **free** at the links below. ORRAS degrades gracefully when keys are missing — that source is simply skipped.

| Source | Key Required | How to Get |
|---|---|---|
| **NewsAPI** | Yes (free tier) | [newsapi.org/register](https://newsapi.org/register) — 100 req/day free |
| **NASA FIRMS** | Yes (free) | [firms.modaps.eosdis.nasa.gov](https://firms.modaps.eosdis.nasa.gov/api/area/) — instant approval |
| **Anthropic (Claude)** | Yes (free tier) | [console.anthropic.com](https://console.anthropic.com) — free credits on sign-up |
| **GDELT** | No | Fully open, no key needed |
| **OpenSky Network** | No | Fully open, no key needed |
| **Cloudflare Radar** | No | Fully open, no key needed |

---

## 👨‍💻 Resume Line

> **Developed ORRAS v3.0** — a production-grade multi-source OSINT intelligence fusion and disaster response platform featuring dual-track threat analysis (conflict + disaster), AI-powered decision support via Claude API, geofence monitoring, resource allocation engine, scenario simulation with 5 crisis presets, SQLite persistence, and a 12-page interactive Streamlit dashboard processing 13 real-time data sources.

---

## 🤝 Contributing

Contributions are welcome! Please follow these steps:

1. Fork the repository and create a feature branch (`git checkout -b feature/your-feature`)
2. Make your changes, ensuring all existing behaviour is preserved
3. Run a quick sanity check: `python -c "import app"` and `streamlit run app.py --server.headless true &`
4. Open a pull request with a clear description of the changes and motivation

### Code Style
- Python 3.11+ with type hints throughout
- Single source of truth for constants in `config.py` — never hard-code thresholds in engine files
- Streamlit pages must be self-contained under `pages/` and import from the engine layer only

---

## 📄 License

This project is licensed under the **MIT License**.

```
MIT License

Copyright (c) 2024 ORRAS Contributors

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
```

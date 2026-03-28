```
 ██████╗ ██████╗ ██████╗  █████╗ ███████╗
██╔═══██╗██╔══██╗██╔══██╗██╔══██╗██╔════╝
██║   ██║██████╔╝██████╔╝███████║███████╗
██║   ██║██╔══██╗██╔══██╗██╔══██║╚════██║
╚██████╔╝██║  ██║██║  ██║██║  ██║███████║
 ╚═════╝ ╚═╝  ╚═╝╚═╝  ╚═╝╚═╝  ╚═╝╚══════╝

  Operational Risk & Regional Alert System  ·  v2.0
```

![Python 3.11+](https://img.shields.io/badge/Python-3.11%2B-blue?logo=python)
![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-FF4B4B?logo=streamlit)
![Plotly](https://img.shields.io/badge/Plotly-5.20%2B-3F4F75?logo=plotly)
![Claude AI](https://img.shields.io/badge/Claude-AI%20Powered-8A2BE2?logo=anthropic)
![License: MIT](https://img.shields.io/badge/License-MIT-green)

---

## Overview

**ORRAS** (Operational Risk & Regional Alert System) is a real-time geopolitical intelligence dashboard that ingests signals from six live data sources, correlates them using statistical and ML-based engines, and surfaces actionable risk alerts with AI-powered analysis.

It is designed for analysts, researchers, and security professionals who need a single pane of glass across military movements, cyber threats, humanitarian crises, infrastructure disruptions, and more. ORRAS v2.0 adds Claude AI integration, automated PDF reporting, multi-domain safety scoring, and six dedicated dashboard pages.

---

## ✨ v2.0 Features

| Feature | Description |
|---|---|
| 🤖 AI Assistant | Claude-powered natural-language Q&A over live signal data |
| 📈 Prediction Engine | ARIMA-style 3-day forecasts with confidence scoring |
| 🌍 Country Comparator | Side-by-side risk comparison across regions |
| 🕐 Timeline View | Chronological signal replay with escalation overlays |
| 🛡️ Safety Monitor | Multi-domain safety scores (cyber, nuclear, infrastructure, maritime, economic, humanitarian) |
| 📄 Report Engine | One-click PDF reports with charts and signal tables |
| 🔴 Live News Ticker | Auto-scrolling headlines from the signal feed |
| 🌐 3D Globe View | Interactive Plotly globe with risk heat-overlay |
| 📊 Anomaly Detection | Z-score rolling-window outlier detection per region |
| 🔗 Correlation Engine | Cross-source signal correlation with configurable bonuses |
| ⚡ Escalation Tracker | 72-hour escalation window with jump-level alerting |
| 🔒 Confidence Engine | Per-signal confidence scoring with source reliability weights |

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

## 📂 Module Reference

### Core

| File | Purpose |
|---|---|
| `app.py` | Main Streamlit application entry point; renders the globe, ticker, and alert feed |
| `config.py` | Single source of truth for all constants, thresholds, and env-var bindings |
| `utils.py` | Shared utility functions (formatting, date helpers, risk colour mapping) |

### Data Layer

| File | Purpose |
|---|---|
| `data_collector.py` | Fetches raw signals from six live APIs (NewsAPI, GDELT, OpenSky, NASA FIRMS, Cloudflare Radar, NetBlocks) |
| `data_processor.py` | Normalises raw API responses, applies keyword scoring, and builds the unified signal list |
| `mock_data_generator.py` | Generates realistic synthetic signals for offline / demo mode |

### Engine Layer

| File | Purpose |
|---|---|
| `anomaly_engine.py` | Z-score anomaly detection with configurable rolling window |
| `correlation_engine.py` | Cross-source signal correlation with bonus scoring for co-occurring event types |
| `prediction_engine.py` | Short-range risk forecasting (ARIMA-inspired) with confidence intervals |
| `confidence_engine.py` | Per-signal confidence scoring based on source reliability weights |
| `safety_engine.py` | Multi-domain safety index (cyber, nuclear, infrastructure, maritime, economic, humanitarian) |
| `escalation_tracker.py` | Tracks risk-level trajectories and fires escalation alerts within a 72-hour window |
| `threat_engine.py` | Aggregates engine outputs into a unified threat picture per region |
| `timeline_engine.py` | Builds time-ordered signal sequences for the Timeline page |
| `action_engine.py` | Suggests recommended actions based on current threat level and domain |
| `report_engine.py` | Renders PDF intelligence reports via ReportLab |
| `ai_assistant.py` | Claude API wrapper that provides natural-language analysis over signal data |
| `news_ticker.py` | Filters and formats headlines for the auto-scrolling ticker component |
| `ui_components.py` | Reusable Streamlit UI widgets (risk gauges, signal cards, map overlays) |

---

## 🖥️ Dashboard Pages

| Page | File | Description |
|---|---|---|
| **Main Dashboard** | `app.py` | Live 3D globe with risk heat-overlay, scrolling news ticker, and alert feed |
| **AI Assistant** | `pages/01_AI_Assistant.py` | Chat interface powered by Claude; ask questions about current signals in plain English |
| **Predictions** | `pages/02_Predictions.py` | 3-day risk forecasts per region with confidence bands and trend indicators |
| **Country Compare** | `pages/03_Country_Compare.py` | Side-by-side comparison of risk scores, signal counts, and domain breakdowns for any two regions |
| **Timeline** | `pages/04_Timeline.py` | Chronological event replay with escalation overlays and filterable signal types |
| **Safety Monitor** | `pages/05_Safety_Monitor.py` | Domain-level safety scores (cyber, nuclear, infrastructure, maritime, economic, humanitarian) with gauge charts |
| **Reports** | `pages/06_Reports.py` | Generate and download PDF intelligence reports for any region and time range |

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

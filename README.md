# ORRAS — Open-source Real-time Risk Assessment System

[![Python 3.11+](https://img.shields.io/badge/python-3.11%2B-blue.svg)](https://www.python.org/)
[![Streamlit](https://img.shields.io/badge/Streamlit-1.32%2B-red.svg)](https://streamlit.io/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](LICENSE)

ORRAS is a real-time geopolitical risk intelligence dashboard. It collects
signals from six independent data sources, scores them with a keyword-weight
model, detects statistical anomalies, tracks regional escalation trends, and
presents everything through an interactive dark-themed Streamlit dashboard.

---

## ✨ Features

- **Multi-source intelligence** — NewsAPI, GDELT, OpenSky, NASA FIRMS,
  Cloudflare Radar, and social/mock signals
- **Automatic mock fallback** — works 100% offline with realistic synthetic data
- **Threat scoring** — keyword-weight model with per-source reliability multipliers
- **Correlation bonuses** — compound risk score when multiple signal types
  co-occur in the same region
- **Z-score anomaly detection** — flags regional spikes vs. 7-day baseline
- **Escalation tracking** — alerts when a region's severity jumps ≥ 2 levels
  within 72 hours
- **Confidence scoring** — rates reliability based on number of independent sources
- **Action recommendations** — LOW → CRITICAL response playbooks per region
- **Interactive world map** — Folium markers + heatmap layer (dark tile)
- **Live signal feed** — filterable table with CSV export
- **Auto-refresh** — pipeline re-runs every 60 seconds

---

## 🏗️ Architecture

```
┌─────────────────────────────────────────────────────┐
│                     app.py (Streamlit UI)            │
│  Sidebar filters │ Map │ KPIs │ Feed │ Charts │ Drill │
└────────────────────────┬────────────────────────────┘
                         │ run_pipeline()
         ┌───────────────▼────────────────┐
         │   DataCollectionOrchestrator   │
         │  NewsAPI │ GDELT │ OpenSky     │
         │  FIRMS   │ Cloudflare │ Mock   │
         └───────────────┬────────────────┘
                         │ raw dict
         ┌───────────────▼────────────────┐
         │         DataProcessor          │
         │  normalise → deduplicate →     │
         │  validate → unified schema     │
         └───────────────┬────────────────┘
                         │ signals[]
         ┌───────────────▼────────────────┐
         │          ThreatEngine          │
         │  keyword scoring + multipliers │
         └───────────────┬────────────────┘
                         │
         ┌───────────────▼────────────────┐
         │       CorrelationEngine        │
         │  cross-source correlation bonus│
         └───────────────┬────────────────┘
                         │
     ┌───────────────────┼──────────────────────┐
     │                   │                      │
┌────▼─────┐    ┌────────▼──────┐    ┌──────────▼──────┐
│ Anomaly  │    │  Escalation   │    │   Confidence     │
│ Engine   │    │   Tracker     │    │   Engine         │
│ (Z-score)│    │ (72h window)  │    │ (source count)   │
└────┬─────┘    └───────┬───────┘    └──────────┬───────┘
     └──────────────────┴──────────────────────┘
                         │
                ┌────────▼────────┐
                │  ActionEngine   │
                │ recommendations │
                │  + alert log    │
                └─────────────────┘
```

---

## 📦 Installation

```bash
# 1. Clone the repository
git clone https://github.com/Vebvsolanki35/ORRAS.git
cd ORRAS

# 2. Create and activate a virtual environment (recommended)
python -m venv venv
source venv/bin/activate        # macOS/Linux
venv\Scripts\activate.bat       # Windows

# 3. Install dependencies
pip install -r requirements.txt

# 4. Set up environment variables
cp .env.example .env
# Edit .env and add your API keys (optional — works without them)
```

---

## 🚀 Running the Dashboard

```bash
streamlit run app.py
```

The dashboard opens at `http://localhost:8501`.

---

## 🔑 API Keys (Optional)

ORRAS runs fully offline with mock data when keys are absent. To enable live feeds:

### NewsAPI
1. Register at <https://newsapi.org/register>
2. Copy your free API key
3. Add to `.env`: `NEWSAPI_KEY=your_key_here`

### NASA FIRMS
1. Visit <https://firms.modaps.eosdis.nasa.gov/api/>
2. Click **Get FIRMS API Key** (free, instant)
3. Add to `.env`: `NASA_FIRMS_KEY=your_key_here`

### GDELT, OpenSky, Cloudflare Radar
These sources require **no API key** — they are called freely by default.

---

## 🔌 Offline / Mock Mode

To run entirely on synthetic data (no network calls):

```bash
# In .env
OFFLINE_MODE=true
```

Or run `mock_data_generator.py` standalone to pre-populate `data/signals.json`:

```bash
python mock_data_generator.py
```

---

## 📁 Module Descriptions

| Module | Purpose |
|--------|---------|
| `config.py` | All constants, thresholds, weights, and file paths |
| `utils.py` | Shared utilities: IDs, logging, JSON I/O, geo, text |
| `mock_data_generator.py` | Realistic synthetic signals for all 6 source types |
| `data_collector.py` | Live HTTP collectors with automatic mock fallback |
| `data_processor.py` | Normalises raw data into the unified signal schema |
| `threat_engine.py` | Keyword scoring with source reliability multipliers |
| `correlation_engine.py` | Cross-source compound signal correlation bonuses |
| `anomaly_engine.py` | Z-score statistical anomaly detection |
| `escalation_tracker.py` | Time-series risk escalation tracking and alerting |
| `confidence_engine.py` | Multi-source confidence scoring per region |
| `action_engine.py` | Action recommendations and alert logging |
| `app.py` | Streamlit dashboard orchestrating the full pipeline |

---

## 📸 Dashboard

*(Screenshot coming soon — run `streamlit run app.py` to see the live dashboard)*

---

## 📄 License

MIT License — see [LICENSE](LICENSE) for details.

---

## 🤝 Contributing

Pull requests are welcome. For major changes, please open an issue first to
discuss what you would like to change.

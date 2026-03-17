# DiseaseWatch
### Real-time Intelligent Disease Surveillance Dashboard

**Team CellStack** — Padma Saathvika, Vishrutha Udandra, Snigdha Naithani
**Hackathon:** Medfusion Hackfest
**Problem Statement:** Design and develop a functional prototype of an interactive intelligent dashboard for disease surveillance that integrates real-time and historical data from approved public health surveillance sources into a unified, analytical and visually interpretable web platform.

---

## What it does

DiseaseWatch is a real-time global disease surveillance platform that:

- Pulls live and historical data from **6 free public health APIs** simultaneously
- Covers **28 diseases** with species-level pathogen detail (COVID-19, Malaria, Cholera, TB, HIV, Dengue, Ebola, Mpox and more)
- Calculates epidemiological indicators automatically — R_t, CFR, case velocity, outbreak risk score, doubling time
- Explains every number in plain language so non-technical users can understand and trust the data
- Detects anomalies and fires alerts only when multiple risk signals align simultaneously
- Provides an AI chatbot (Groq + Llama 3.3 70B) that answers questions grounded in live surveillance data

---

## Features

| Feature | Description |
|---|---|
| Global threat thermometer | Animated 0–100 risk gauge aggregated across 20 highest-burden countries |
| Multi-disease world map | Choropleth map switchable across 28 diseases with pathogen names |
| Disease intelligence cards | Per-disease cards with AI-generated plain-language summary, R_t, CFR, trend |
| What changed today | Delta-first feed showing % change across all diseases, sorted by magnitude |
| Transparent math | Every formula explained in plain English — no black boxes |
| Early outbreak detection | 3-condition alert logic: fires only when case velocity + R_t + climate all align |
| AI chatbot | Groq-powered Q&A grounded in live data, ~0.3s response time |
| Data confidence score | Honest uncertainty metric shown on every stat |
| ProMED live alerts | Real-time outbreak signals from the WHO-validated ProMED RSS feed |

---

## Architecture

```
Data Sources (6 APIs, parallel async fetch)
    WHO GHO · disease.sh · CMU Delphi · ProMED RSS · GBIF · Open Meteo
            ↓
Ingestion Layer
    fetchers.py → normalizer.py → scispaCy NLP
            ↓
DuckDB + Polars processing bus
            ↓
Analytics Layer
    epi_engine.py (R_t, CFR, outbreak score)
    pipeline.py (orchestrator)
    store.py (DuckDB + Parquet)
            ↓
AI Layer
    chatbot.py (Groq + Llama 3.3 70B RAG)
            ↓
Streamlit Dashboard (app.py)
    World map · Disease cards · Alerts · How it works · AI chat
```

---

## Backend — core files

| File | Role |
|---|---|
| `ingestion/fetchers.py` | Async parallel HTTP fetcher for all 6 APIs. Fetches 28 WHO disease indicators concurrently. ~3s total vs 18s sequential |
| `ingestion/normalizer.py` | Unifies all API formats into one standard schema: disease, species, country, cases, deaths, cfr, source |
| `analytics/epi_engine.py` | All epidemiology math — R_t with 95% CI, CFR, case velocity, outbreak risk score, global threat score, confidence scorer |
| `analytics/store.py` | DuckDB storage layer — upserts records, runs SQL queries, writes daily Parquet snapshots |
| `analytics/chatbot.py` | Groq + Llama 3.3 70B integration — live data context injection, disease card sentence generation |
| `analytics/pipeline.py` | Master orchestrator — fetch, normalize, score, store, return dashboard payload in one call |

---

## Data Sources (all free, no paid APIs)

| API | Data | Update frequency |
|---|---|---|
| disease.sh | COVID-19 real-time by country | Every 10 min |
| WHO GHO | 28 disease indicators, 180+ countries | Annual (historical) |
| CMU Delphi Epidata | US influenza ILI rates | Weekly |
| Open Meteo | Climate/rainfall for risk scoring | Hourly |
| ProMED RSS | Outbreak alerts, all diseases | ~15 min |
| GBIF | Disease vector species locations | Updated regularly |

---

## Tech stack

**Backend:** Python · httpx async · DuckDB · Polars · scikit-learn · XGBoost · Prophet · scispaCy
**AI:** Groq API · Llama 3.3 70B · LangChain
**Frontend:** Streamlit · Plotly · Pandas
**Storage:** DuckDB · Parquet

---

## Epidemiology — how the math works

**R_t (reproduction number)**
R_t = cases(this week) / cases(prior week)
Tells you: is each infected person spreading to more or less than 1 other person right now?

**Outbreak risk score (0–100)**
Risk = 0.40 x case_velocity + 0.30 x R_t_score + 0.20 x climate_index + 0.10 x reporting_lag

**CFR (case fatality rate)**
CFR = (deaths / confirmed cases) x 100

**Data confidence**
Confidence = 0.4 x data_completeness + 0.4 x model_accuracy + 0.2 x signal_consistency
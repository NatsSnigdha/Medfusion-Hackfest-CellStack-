<<<<<<< HEAD
# DiseaseWatch — Real-time Disease Surveillance Dashboard

## Setup (5 minutes)

```bash
# 1. Clone and enter project
cd disease_surveillance

# 2. Create virtual environment
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate

# 3. Install dependencies
pip install -r requirements.txt

# 4. Add your Groq API key (free at console.groq.com — no credit card)
cp .env.example .env
# Edit .env and add: GROQ_API_KEY=your_key_here

# 5. Run
streamlit run app.py
```

## APIs used (all free, no key needed except Groq)

| API | Data | Key needed? |
|-----|------|-------------|
| disease.sh | COVID-19 by country, real-time | No |
| WHO GHO | Malaria, cholera, TB historical | No |
| CMU Delphi Epidata | US influenza ILI rates | No |
| Open Meteo | Climate/rainfall for risk scoring | No |
| ProMED RSS | Real-time outbreak alerts | No |
| GBIF | Disease vector species locations | No |
| Groq (Llama 3.3 70B) | AI chatbot + disease card sentences | Yes (free) |

## Project structure

```
disease_surveillance/
├── app.py                    # Streamlit UI — all tabs
├── requirements.txt
├── .env.example
├── ingestion/
│   ├── fetchers.py           # Async HTTP fetchers for all 6 APIs
│   └── normalizer.py         # Unified schema {disease, species, country, cases...}
├── analytics/
│   ├── epi_engine.py         # R_t, CFR, outbreak score, velocity, threat thermometer
│   ├── store.py              # DuckDB + Parquet storage layer
│   ├── chatbot.py            # Groq-powered AI chat
│   └── pipeline.py           # Master orchestrator
└── data/
    ├── surveillance.duckdb   # Live data store (auto-created)
    └── snapshots/            # Daily Parquet snapshots
```

## Key features

- **Threat thermometer** — animated 0-100 global risk gauge in sidebar
- **Disease cards** — per-disease with Groq-generated aha sentence, R_t, CFR, velocity
- **What changed today** — delta-first feed sorted by % change
- **Plain-language math** — every formula explained in plain English with step-by-step
- **AI chatbot** — Groq Llama 3.3 70B grounded in live data, ~0.3s response time
- **Math sandbox** — interactive R_t and outbreak score sliders
- **World map** — choropleth with hover details
- **Progressive disclosure** — show number → plain English → full formula on demand
=======
# Medfusion-Hackfest-CellStack-
Team:
Padma Saathvika,
Vishrutha Udandra,
Snigdha Naithani
>>>>>>> f978995ac82634045d61317537f3a3be667b6926

# MetroMorph

Metamorphic testing of a multi-agent Dallas–Fort Worth housing-trends application.

## Stack

- **Backend:** FastAPI + 5 Python agents (Criteria → Scanner → Analyst → Critic → Report)
- **Frontend (primary):** Next.js / React + Recharts analytics dashboard
- **Optional:** Streamlit UI under `app/streamlit_app.py`
- **LLM:** Mock mode or Ollama
- **Data:** Real Zillow ZHVI (ZIP) + Redfin Dallas metro aggregates only

## Quick start — React UI

### 1. Python API
```bash
cd lotline
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
PYTHONPATH=src uvicorn api.server:app --reload --port 8000
```

### 2. React frontend
```bash
cd lotline/frontend
npm install
npm run dev
```

Open **http://localhost:3000**

## Data

Real public sources (no Kaggle login):
- Zillow Research ZHVI ZIP/metro
- Redfin Data Center Dallas metro tracker

Committed freeze files:
- `data/dallas_zhvi_zip_frozen.csv`
- `data/dallas_redfin_metro_frozen.csv`
- `data/SOURCES.md`

Rebuild from `data/raw/` downloads:
```bash
python data/build_from_public.py
```

## MR harness
```bash
# All 8 MRs (assignment results table)
PYTHONPATH=src python harness/run_harness.py --n 30 --seed 7

# List ids
PYTHONPATH=src python harness/run_harness.py --list

# One MR (or a few) with per-case pass/fail
PYTHONPATH=src python harness/run_harness.py --mr MR3_duplicate --n 30 --seed 7 -v
PYTHONPATH=src python harness/run_harness.py --mr MR1 --mr MR5 --n 15
```

## Teammate with Ollama
```bash
export METROMORPH_MODE=ollama
export OLLAMA_MODEL=llama3.2
```

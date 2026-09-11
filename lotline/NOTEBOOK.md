# NOTEBOOK.md — How to run MetroMorph

## Prerequisites
- Python 3.10+ (tested path: 3.14)
- Optional: [Ollama](https://ollama.com) + a small model for live LLM agents

## 1. Setup

```bash
cd lotline
python3 -m venv .venv
source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements.txt
python data/build_from_public.py  # rebuilds data/frozen_listings.csv from Zillow/Redfin
```

## 2. Launch React UI (primary)

Terminal A — API:
```bash
PYTHONPATH=src uvicorn api.server:app --host 127.0.0.1 --port 8000
```

Terminal B — React:
```bash
cd frontend && npm install && npm run dev -- --hostname 127.0.0.1 --port 3000
```

Open **http://127.0.0.1:3000**

- Type a question in chat (or click an example)
- Use tabs: Trends · Agents · Breakdown · Listings · Market
- Agent mode: auto / mock / ollama in the header

### Optional Streamlit UI
```bash
PYTHONPATH=src streamlit run app/streamlit_app.py
```


## 3. Launch with local LLM (teammate)

```bash
ollama serve   # if not already running
ollama pull llama3.2
export METROMORPH_MODE=ollama
export OLLAMA_MODEL=llama3.2
PYTHONPATH=src streamlit run app/streamlit_app.py
```

Criteria / Critic / Report will call Ollama JSON generation. Scanner + Analyst remain deterministic pandas tools.

## 4. Reproduce MR results table

```bash
PYTHONPATH=src python harness/run_harness.py --n 30 --seed 7
```

Outputs:
- Console table: MR id, n, violations, rate, 95% CI
- `harness/results_table.json`

## 5. Agents & loop (for design note)

```text
Criteria → Scanner → Analyst → Critic
                              ├─ PASS → Report
                              └─ REVISE → Criteria (cycle)
```

Evidence: UI trace lines containing `critic → REVISE` then a later `criteria →` with widened bounds.

## 6. Assumptions to document
- Zero-price listings are dropped as invalid
- Coverage threshold ~0.72 / min ~12 listings per month drives Critic
- Zillow/Redfin-calibrated DFW listings (see `data/SOURCES.md`)

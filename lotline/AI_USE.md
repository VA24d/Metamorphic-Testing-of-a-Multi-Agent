# AI_USE.md

Disclose substantive AI assistance for the TSE assignment.

## Tools used
- **Cursor (Composer)** — scaffolded the MetroMorph application structure, UI, agent orchestration, Zillow/Redfin data builder, and metamorphic harness from the assignment brief and team action plan.

## What AI produced
- Project layout and typed Pydantic contracts (`QueryPlan`, `TrendOutput`, `Critique`, …)
- Five-agent pipeline with Critic feedback loop
- Mock + Ollama dual mode so UI works without a local LLM
- React + Streamlit analytics UIs
- Eight MR checkers + Wilson CI harness runner
- **Zillow/Redfin public aggregate freeze** (`data/build_from_public.py`) — ZIP ZHVI + Dallas metro metrics only (no synthetic MLS rows)

## What we verified / own
- [ ] Re-ran UI in mock mode end-to-end
- [ ] Re-ran `harness/run_harness.py --n 30` and saved results
- [ ] Confirmed Critic loop fires under tight filters (trace shows REVISE)
- [ ] Checked MR definitions against our output contract
- [ ] Teammate validated Ollama mode on their machine

## Cases where the tool was wrong / incomplete
- Dual-axis Plotly subplot wiring needed manual correction for secondary `$/sqft` axis.
- Import paths (`PYTHONPATH=src`) must be set explicitly; AI initially assumed an installed package.
- Harness initially mixed agent non-determinism with MR checks — we keep Scanner/Analyst deterministic for measurement trust.

## Human decisions
- Brand/visual direction (MetroMorph slate/teal), not purple “AI default”
- Pydantic-style agents + Python orchestrator loop (instead of LangGraph)
- Public Zillow/Redfin freeze for reproducibility (not live scraping)

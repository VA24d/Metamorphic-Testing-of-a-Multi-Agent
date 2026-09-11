.PHONY: data api ui react install-frontend harness

install:
	python3 -m venv .venv
	.venv/bin/pip install -r requirements.txt

data:
	.venv/bin/python data/build_from_public.py

api:
	PYTHONPATH=src .venv/bin/uvicorn api.server:app --reload --port 8000

install-frontend:
	cd frontend && npm install

react:
	cd frontend && npm run dev

ui:
	PYTHONPATH=src .venv/bin/streamlit run app/streamlit_app.py

harness:
	PYTHONPATH=src .venv/bin/python harness/run_harness.py --n 30 --seed 7

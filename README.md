# Bus Charging Scheduler

Electric bus charging planner for the Bengaluru–Kochi corridor. Assigns where each bus charges and resolves charger conflicts when multiple buses share stations A–D.

## Stack

- Python scheduler (`scheduler/`)
- Scenario data (`scenarios/*.json`)
- Streamlit UI (`app.py`)

## Run locally

```bash
pip install -r requirements.txt
streamlit run app.py
```

## Project layout

- `app.py` — Streamlit entry point
- `scheduler/` — models, planner, dispatcher, cost
- `scenarios/` — five test scenarios
- `ARCHITECTURE.md` — design notes

See [ARCHITECTURE.md](ARCHITECTURE.md) for details.

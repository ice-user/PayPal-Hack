# Precedent

An operations consultant for PayPal merchants that cites past cases before it acts.

It detects a dispute spike, retrieves similar past cases, explains why they match and
where they differ, proposes typed actions, and only after a deterministic policy gate
and a human click, executes them through the PayPal Sandbox. The same symptom
(an item-not-received spike) leads to three different plans depending on the signals.

Built for the PayPal AI Hackathon. **Work in progress.**

## Honest labels

- The demo merchant's order feed is **synthetic**. Detection statistics run on it for real.
- The case library is currently **authored** playbook cases, labelled `illustrative`.
  None of them carries outcome numbers, so the app shows **no numeric forecast**.
  Numeric effects are only ever computed from `measured_observational` cases.
- PayPal: token, payments and dispute reads are **real sandbox calls**. Seller actions on
  our sandbox dispute are currently refused by PayPal (`UNDER_PAYPAL_REVIEW`), so
  execution is **simulated** and labelled. See [docs/SPIKE1_RESULT.md](docs/SPIKE1_RESULT.md).
- Outcomes are "observed" or "followed", never "caused". Not financial advice.

## Layout

| Path | What |
|---|---|
| `contracts/` | JSON schemas, shared thresholds, fixtures (the contract between frontend and backend) |
| `cases/` | Case library (authored now; public cases next) |
| `intelligence/` | Consultant, baseline retriever, effects rule, reference policy gate, stats |
| `scripts/build_fixtures.py` | Builds and validates the demo fixtures from the pipeline |
| `frontend/` | React + Vite dashboard (runs on fixtures, or a real API via `VITE_API_BASE`) |
| `backend/spike1/` | PayPal sandbox spike scripts (credentials in `backend/.env`, never committed) |
| `docs/` | Brief, design, handoffs, spike results |

## Run

```bash
pip install jsonschema pytest
python scripts/build_fixtures.py
python -m pytest -q
cd frontend && npm install && npm run dev
```

Then open http://localhost:5173.

## Licence

MIT, see [LICENSE](LICENSE).

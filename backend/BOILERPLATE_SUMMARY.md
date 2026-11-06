"""
PayPal Hack — Person B Backend Boilerplate
===========================================

Minimal FastAPI application with the core Person B infrastructure:

1. Situation Builder — binomial test + Wilson CI for anomaly detection
2. Hybrid Retriever — structured + text similarity, RRF fuse
3. Policy Gate — 3 approval tiers (AUTO / NEEDS_APPROVAL / BLOCKED)
4. Executor — state machine + idempotency + dispute re-check
5. Outcome Tracker — simulated clock
6. API routes matching the proposed contract
7. PayPal sandbox adapter (Spike 1)

RUN:
    uvicorn backend.app:app --reload --host 127.0.0.1 --port 8765

DEPS:
    pip install fastapi uvicorn requests

See README.md in the project root for contract schemas and fixtures.
"""

# Minimal check: only include what's absolutely needed for the boilerplate
# Full app.py is the complete version; this is a lightweight summary
print("Person B backend boilerplate loaded. See backend/app.py for full implementation.")
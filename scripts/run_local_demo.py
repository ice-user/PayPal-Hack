"""Serve the built dashboard and API locally with isolated, simulated execution.

Build frontend first with VITE_API_BASE=/, then run:
    python scripts/run_local_demo.py
No credentials, PayPal requests, LLM requests or persistent database writes.
"""
import argparse
import os
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    args = parser.parse_args()
    dashboard = ROOT / "frontend/dist"
    if not (dashboard / "index.html").exists():
        parser.error("Build frontend with VITE_API_BASE=/ before running the local demo (see README).")
    os.environ["PRECEDENT_STATIC_DIR"] = str(dashboard)
    os.environ["PRECEDENT_LLM_WRITER"] = "0"
    import uvicorn
    from intelligence.retrieve_hybrid import retrieve
    from precedent import api
    from precedent.paypal_adapter import PayPalAdapter
    from precedent.service import Service
    from precedent.store import Store

    api._service = Service(Store(":memory:"), PayPalAdapter(env={"PRECEDENT_REAL_EXECUTION": "0"}),
                           retriever=retrieve)
    uvicorn.run(api.app, host="127.0.0.1", port=args.port)


if __name__ == "__main__":
    main()

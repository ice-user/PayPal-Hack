"""HTTP API for the dashboard. Run from the repo root:

    python -m uvicorn precedent.api:app --app-dir backend --port 8000

Then start the frontend with VITE_API_BASE=http://localhost:8000.
"""
from __future__ import annotations

import os

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field

from .executor import ActionError
from .paypal_adapter import PayPalError
from .scenarios import DEMO
from .service import MODES, Service

app = FastAPI(title="Precedent API", version="0.1.0",
              description="Dispute consultant for PayPal merchants. Synthetic order feed; PayPal sandbox only.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "PRECEDENT_CORS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    ).split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type"],
)

_service: Service | None = None


def service() -> Service:
    global _service
    if _service is None:
        _service = Service()
    return _service


def _guard(fn, *args):
    try:
        return fn(*args)
    except ActionError as e:
        raise HTTPException(status_code=e.status, detail=str(e)) from e


class ActionRequest(BaseModel):
    situation: str = Field(examples=["A"])
    mode: str = Field(default="with_precedent", examples=["with_precedent"])
    action_id: str = Field(examples=["act_1"])


class AdvanceRequest(BaseModel):
    situation: str
    mode: str = "with_precedent"
    days: int = Field(default=14, ge=1, le=60)


@app.get("/api/health")
def health() -> dict:
    s = service()
    return {"ok": True, "cases": len(s.cases), "paypal_configured": s.adapter.configured,
            "paypal_host": s.adapter.base, "webhook_configured": bool(s.adapter.webhook_id)}


@app.get("/api/situations")
def situations() -> dict:
    return {"situations": [{"key": k, "situation_id": f"sit_demo_{k}", "label": v.name} for k, v in DEMO.items()],
            "modes": list(MODES)}


@app.get("/api/bundles/{key}")
def bundle(key: str, mode: str = "with_precedent") -> dict:
    return _guard(service().bundle, key, mode)


@app.post("/api/actions/approve")
def approve(req: ActionRequest) -> dict:
    return _guard(service().approve, req.situation, req.mode, req.action_id)


@app.post("/api/actions/reject")
def reject(req: ActionRequest) -> dict:
    return _guard(service().reject, req.situation, req.mode, req.action_id)


@app.post("/api/sim/advance")
def advance(req: AdvanceRequest) -> dict:
    return _guard(service().advance, req.situation, req.mode, req.days)


@app.post("/api/demo/reset")
def demo_reset() -> dict:
    """Clear approvals, outcomes and pending cases (not the audit log). Does not touch PayPal."""
    s = service()
    s.store.reset_demo()
    s.store.audit("operator", "demo_reset", {})
    return {"ok": True}


@app.get("/api/cases/{case_id}")
def case(case_id: str) -> dict:
    s = service()
    for c in s.cases + s.store.pending_cases():
        if c["case_id"] == case_id:
            return c
    raise HTTPException(404, f"No case {case_id}")


@app.get("/api/cases")
def cases(include_pending: bool = False) -> dict:
    s = service()
    out = [{"case_id": c["case_id"], "title": c["title"], "provenance": c["provenance"],
            "evidence_quality": c["evidence_quality"], "review_status": c["review_status"]} for c in s.cases]
    if include_pending:
        out += [{"case_id": c["case_id"], "title": c["title"], "provenance": c["provenance"],
                 "evidence_quality": c["evidence_quality"], "review_status": c["review_status"]}
                for c in s.store.pending_cases()]
    return {"cases": out}


@app.get("/api/audit")
def audit(limit: int = 50) -> dict:
    return {"events": service().store.audit_tail(min(limit, 500))}


@app.get("/api/paypal/disputes/{dispute_id}")
def paypal_dispute(dispute_id: str) -> dict:
    s = service()
    if not s.adapter.configured:
        raise HTTPException(503, "PayPal sandbox credentials are not configured.")
    try:
        return {"source": "paypal_sandbox", "dispute": s.adapter.get_dispute(dispute_id)}
    except PayPalError as e:
        raise HTTPException(502 if e.status >= 500 else e.status, f"PayPal said {e.status}") from e


def _mount_dashboard() -> None:
    """In the deployed container the built dashboard is served from the same origin."""
    static_dir = os.environ.get("PRECEDENT_STATIC_DIR")
    if static_dir and os.path.isdir(static_dir):
        from fastapi.staticfiles import StaticFiles
        app.mount("/", StaticFiles(directory=static_dir, html=True), name="dashboard")


@app.post("/api/paypal/webhook")
async def paypal_webhook(request: Request) -> dict:
    s = service()
    event = await request.json()
    if not s.adapter.verify_webhook(dict(request.headers), event):
        s.store.audit("paypal", "webhook_rejected", {"event_type": event.get("event_type")})
        raise HTTPException(400, "Webhook signature could not be verified.")
    tid = request.headers.get("paypal-transmission-id", "")
    if s.store.seen_webhook(tid, event.get("event_type", "")):
        return {"ok": True, "replay": True}
    s.store.audit("paypal", "webhook_received", {"event_type": event.get("event_type"),
                                                 "resource_id": (event.get("resource") or {}).get("dispute_id")})
    return {"ok": True, "replay": False}


_mount_dashboard()  # last, so /api routes take precedence

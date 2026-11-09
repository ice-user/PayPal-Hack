"""HTTP API for the dashboard. Run from the repo root:

    python -m uvicorn precedent.api:app --app-dir backend --port 8000

Then start the frontend with VITE_API_BASE=http://localhost:8000.
"""
from __future__ import annotations

import json
import os
import re
import threading
import time
from collections import OrderedDict

from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from starlette.concurrency import run_in_threadpool
from pydantic import BaseModel, Field

from .executor import ActionError
from .paypal_adapter import PayPalError
from .scenarios import DEMO
from .techkart import TECHKART  # noqa: E402
from .service import MODES, Service
from .webhooks import MAX_BODY_BYTES, metadata

app = FastAPI(title="MediateAI API", version="0.1.0",
              description="Dispute consultant for PayPal merchants. Synthetic order feed; PayPal sandbox only.")
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.environ.get(
        "PRECEDENT_CORS", "http://localhost:5173,http://127.0.0.1:5173,http://localhost:5174,http://127.0.0.1:5174"
    ).split(","),
    allow_methods=["GET", "POST"], allow_headers=["Content-Type", "X-Demo-Session"],
)

_service: Service | None = None


def service() -> Service:
    global _service
    if _service is None:
        _service = Service()
    return _service


# Public deployments (PRECEDENT_PER_VISITOR=1) give every browser its own demo workspace, keyed by
# the random X-Demo-Session id the dashboard sends, so one judge's approvals, simulated clock and
# case reviews never show up for another. Workspaces live in memory; the least recently used ones
# are dropped past the cap or after the idle limit. PayPal reads and webhooks stay on the shared service.
_VISITOR_ID = re.compile(r"[A-Za-z0-9-]{8,64}")
_visitors: OrderedDict[str, tuple[Service, float]] = OrderedDict()
_visitors_lock = threading.Lock()


def workspace(x_demo_session: str | None = Header(default=None)) -> Service:
    base = service()
    if os.environ.get("PRECEDENT_PER_VISITOR") != "1":
        return base
    vid = x_demo_session if x_demo_session and _VISITOR_ID.fullmatch(x_demo_session) else "anonymous"
    cap = int(os.environ.get("PRECEDENT_MAX_VISITORS", "500"))
    idle = float(os.environ.get("PRECEDENT_VISITOR_IDLE_HOURS", "12")) * 3600
    now = time.monotonic()
    with _visitors_lock:
        while _visitors:
            oldest, (_, seen) = next(iter(_visitors.items()))
            if len(_visitors) < cap and now - seen < idle:
                break
            del _visitors[oldest]
        ws = _visitors.pop(vid, (None, 0.0))[0] or base.fork()
        _visitors[vid] = (ws, now)
    return ws


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
    labels = {k: v.name for k, v in DEMO.items()} | {"T": TECHKART.name}
    return {"situations": [{"key": k, "situation_id": f"sit_demo_{k}", "label": v} for k, v in labels.items()],
            "modes": list(MODES)}


@app.get("/api/bundles/{key}")
def bundle(key: str, mode: str = "with_precedent", ws: Service = Depends(workspace)) -> dict:
    return _guard(ws.bundle, key, mode)


@app.post("/api/actions/approve")
def approve(req: ActionRequest, ws: Service = Depends(workspace)) -> dict:
    return _guard(ws.approve, req.situation, req.mode, req.action_id)


@app.post("/api/actions/reject")
def reject(req: ActionRequest, ws: Service = Depends(workspace)) -> dict:
    return _guard(ws.reject, req.situation, req.mode, req.action_id)


@app.post("/api/sim/advance")
def advance(req: AdvanceRequest, ws: Service = Depends(workspace)) -> dict:
    return _guard(ws.advance, req.situation, req.mode, req.days)


class ReviewRequest(BaseModel):
    decision: str = Field(examples=["approved"])


@app.post("/api/cases/{case_id}/review")
def review_case(case_id: str, req: ReviewRequest, ws: Service = Depends(workspace)) -> dict:
    """A human approves or rejects a live_simulated case before it can be retrieved."""
    return _guard(ws.review_case, case_id, req.decision)


@app.post("/api/demo/reset")
def demo_reset(s: Service = Depends(workspace)) -> dict:
    """Clear approvals, outcomes and pending cases (not the audit log). Does not touch PayPal.
    On a public deployment this resets only the caller's own workspace."""
    s.store.reset_demo()
    s._plans.clear()
    s.store.audit("operator", "demo_reset", {})
    return {"ok": True}


@app.get("/api/cases/{case_id}")
def case(case_id: str, s: Service = Depends(workspace)) -> dict:
    for c in s.cases + s.store.pending_cases():
        if c["case_id"] == case_id:
            return c
    raise HTTPException(404, f"No case {case_id}")


@app.get("/api/cases")
def cases(include_pending: bool = False, s: Service = Depends(workspace)) -> dict:
    out = [{"case_id": c["case_id"], "title": c["title"], "provenance": c["provenance"],
            "evidence_quality": c["evidence_quality"], "review_status": c["review_status"]} for c in s.cases]
    if include_pending:
        out += [{"case_id": c["case_id"], "title": c["title"], "provenance": c["provenance"],
                 "evidence_quality": c["evidence_quality"], "review_status": c["review_status"]}
                for c in s.store.pending_cases()]
    return {"cases": out}


@app.get("/api/audit")
def audit(limit: int = 50, s: Service = Depends(workspace)) -> dict:
    return {"events": s.store.audit_tail(min(limit, 500))}


_last_refresh = [0.0]


@app.get("/api/paypal/account")
def paypal_account() -> dict:
    """The connected sandbox account as MediateAI sees it: imported disputes, PayPal status,
    allowed seller actions and trackers. Cached and shared by all visitors."""
    return service().feed.public()


@app.post("/api/paypal/refresh")
def paypal_refresh() -> dict:
    """Re-import disputes from PayPal now (at most once every 10 seconds across all visitors)."""
    s = service()
    force = time.monotonic() - _last_refresh[0] >= 10
    if force:
        _last_refresh[0] = time.monotonic()
    return s.feed.public(s.feed.snapshot(force=force))


@app.get("/api/paypal/activity")
def paypal_activity(limit: int = Query(default=25, ge=1, le=60)) -> dict:
    """The latest requests this deployment made to PayPal: method, path, HTTP status, latency.
    Paths contain sandbox IDs only; no tokens, bodies or personal data are recorded."""
    a = service().adapter
    return {"host": a.base, "calls": list(a.activity)[:limit]}


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
    body = bytearray()
    async for chunk in request.stream():
        body.extend(chunk)
        if len(body) > MAX_BODY_BYTES:
            raise HTTPException(413, "Webhook body exceeds 1 MiB.")
    try:
        event = json.loads(body)
        projected = metadata(event)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise HTTPException(400, "Malformed webhook envelope.") from exc
    return await run_in_threadpool(_ingest_webhook, dict(request.headers), event, projected)


def _ingest_webhook(headers: dict, event: dict, projected: dict) -> dict:
    s = service()
    if not (s.adapter.configured and s.adapter.webhook_id):
        raise HTTPException(503, "Webhook verification is not configured.")
    try:
        verified = s.adapter.verify_webhook(headers, event)
    except PayPalError as exc:
        raise HTTPException(503, "Webhook verification unavailable; retry delivery.") from exc
    if not verified:
        s.store.audit("paypal", "webhook_rejected", {"event_type": projected["event_type"]})
        raise HTTPException(400, "Webhook signature could not be verified.")
    replay = s.store.record_webhook(projected, headers["paypal-transmission-id"])
    return {"ok": True, "replay": replay}


@app.get("/api/paypal/disputes/{dispute_id}/events")
def paypal_dispute_events(dispute_id: str, limit: int = Query(default=50, ge=1, le=500)) -> dict:
    """Local verified history; no PayPal read or seller action is triggered."""
    return service().store.webhook_history(dispute_id, limit)


_mount_dashboard()  # last, so /api routes take precedence

"""Import the connected PayPal sandbox account's disputes into the TechKart triage.

PayPal is the input as well as the output:
1. Disputes API, list disputes: every dispute on the account.
2. Disputes API, show dispute details: reason, amount, deadline, disputed transaction, and
   which seller actions PayPal allows right now.
3. Add Tracking API, list trackers for the disputed transaction: the parcel's shipment state.

Disputes waiting for the seller's response are triaged with the same dispute-level cases
as the synthetic TechKart disputes (intelligence/triage.py). Approving one of their actions
calls PayPal on that exact dispute. Everything else on the account is listed, not triaged.

Reads are cached for `ttl` seconds and shared by every visitor, so a busy public demo makes
at most a handful of PayPal calls a minute.
"""
from __future__ import annotations

import threading
import time
from datetime import datetime, timezone

from .paypal_adapter import PayPalAdapter, PayPalError

NEEDS_SELLER = {"WAITING_FOR_SELLER_RESPONSE"}
REASONS = {"MERCHANDISE_OR_SERVICE_NOT_RECEIVED": "ITEM_NOT_RECEIVED"}
# PayPal tracker status -> (shipment state, proof level) in the dispute cases' terms. A tracker
# marked DELIVERED is the carrier's delivery confirmation; SHIPPED / ON_HOLD only show a parcel
# in transit. PayPal has no "lost" tracker status, so a lost parcel is never inferred from PayPal.
TRACKER_STATE = {"DELIVERED": ("delivered", "confirmation"), "SHIPPED": ("in_transit", "tracking"),
                 "ON_HOLD": ("in_transit", "tracking")}
MAX_DETAILS = 10


def _day(ts: str | None) -> str | None:
    return ts[:10] if ts else None


def to_dispute(detail: dict, trackers: list[dict]) -> dict:
    """One PayPal dispute (plus its trackers) in the triage's dispute shape."""
    tx = (detail.get("disputed_transactions") or [{}])[0]
    item = (tx.get("items") or [{}])[0]
    tracker = next((t for t in trackers if (t.get("status") or "").upper() in TRACKER_STATE), trackers[0] if trackers else None)
    status, proof = TRACKER_STATE.get(((tracker or {}).get("status") or "").upper(), ("unknown", "none"))
    due = _day(detail.get("seller_response_due_date")) or _day(detail.get("buyer_response_due_date")) \
        or _day(detail.get("create_time")) or datetime.now(timezone.utc).date().isoformat()
    return {
        "dispute_id": detail["dispute_id"], "order_id": tx.get("seller_transaction_id") or "",
        "carrier": (tracker or {}).get("carrier_name_other") or (tracker or {}).get("carrier") or "no tracker in PayPal",
        "sku": item.get("item_name") or "Item", "amount": float((detail.get("dispute_amount") or {}).get("value") or 0),
        "reason": REASONS.get(detail.get("reason"), detail.get("reason") or "OTHER"),
        "shipment_status": status, "proof": proof, "expected_delivery": None, "response_due": due,
        "opened": _day(detail.get("create_time")), "true_state": None,
        "paypal": True, "tracking_number": (tracker or {}).get("tracking_number"),
        "tracker_status": (tracker or {}).get("status"),
    }


def summary(detail: dict, dispute: dict, triaged: bool) -> dict:
    return {
        "dispute_id": detail["dispute_id"], "reason": detail.get("reason"), "status": detail.get("status"),
        "stage": detail.get("dispute_life_cycle_stage"), "amount": detail.get("dispute_amount"),
        "created": detail.get("create_time"), "response_due": dispute["response_due"],
        "allowed": sorted(l.get("rel") for l in detail.get("links", []) if l.get("rel") not in (None, "self")),
        "item": dispute["sku"], "transaction_id": dispute["order_id"],
        "shipment_status": dispute["shipment_status"], "tracker_status": dispute["tracker_status"],
        "tracking_number": dispute["tracking_number"], "triaged": triaged,
    }


class PayPalFeed:
    def __init__(self, adapter: PayPalAdapter, ttl: float = 60.0):
        self.adapter, self.ttl = adapter, ttl
        self._snap: dict | None = None
        self._at = 0.0
        self._sig: tuple = ()
        self.version = 0
        self._lock = threading.Lock()

    def snapshot(self, force: bool = False) -> dict:
        """The cached import, refreshed when older than ttl (or on force)."""
        if not self.adapter.configured:
            return {"connected": False, "version": 0, "disputes": [], "triage": [], "fetched_at": None,
                    "error": "PayPal sandbox credentials are not configured on this deployment."}
        fresh = self._snap is not None and time.monotonic() - self._at < self.ttl
        if fresh and not force:
            return self._snap
        if not self._lock.acquire(blocking=self._snap is None):
            return self._snap  # another request is refreshing: serve the previous import
        try:
            self._snap = self._fetch()
            self._at = time.monotonic()
            return self._snap
        finally:
            self._lock.release()

    def _fetch(self) -> dict:
        now = datetime.now(timezone.utc).isoformat(timespec="seconds")
        try:
            items = self.adapter.list_disputes(page_size=20)
            rows, triage = [], []
            for it in items[:MAX_DETAILS]:
                detail = self.adapter.dispute_details(it["dispute_id"])
                tx = (detail.get("disputed_transactions") or [{}])[0].get("seller_transaction_id")
                trackers = self.adapter.trackers(tx) if tx else []
                d = to_dispute(detail, trackers)
                needs = detail.get("status") in NEEDS_SELLER
                if needs:
                    triage.append(d)
                rows.append(summary(detail, d, needs))
        except PayPalError as e:
            prev = self._snap or {"disputes": [], "triage": [], "version": self.version}
            return dict(prev, connected=True, fetched_at=now, error=f"PayPal returned {e.status} while importing disputes.")
        sig = tuple((r["dispute_id"], r["status"], r["tracker_status"], tuple(r["allowed"])) for r in rows)
        if sig != self._sig:
            self._sig, self.version = sig, self.version + 1
        return {"connected": True, "version": self.version, "disputes": rows, "triage": triage,
                "fetched_at": now, "error": None, "total_listed": len(items)}

    def public(self, snap: dict | None = None) -> dict:
        """What the dashboard shows (no internal triage records)."""
        s = snap or self.snapshot()
        a = self.adapter
        return {"connected": s["connected"], "fetched_at": s["fetched_at"], "error": s["error"],
                "host": a.base, "disputes": s["disputes"],
                "real_actions": None if not (a.configured and a.real_execution) else sorted(a.real_types or ["ALL"]),
                "real_calls_per_hour": a.max_real_per_hour or None}

"""Executor: the state machine between an approved recommendation action and PayPal.

States: PROPOSED -> GATED -> AWAITING_APPROVAL -> EXECUTING -> SUCCEEDED | FAILED,
or AWAITING_APPROVAL -> CANCELLED (rejected). AUTO actions go GATED -> SUCCEEDED
(prepare-only, nothing leaves the system). BLOCKED actions never leave GATED.

- One row per (recommendation, action), keyed by an idempotency key: a duplicate
  approval cannot execute twice (compare-and-set on the state column).
- The policy gate is re-run at approval time, not trusted from the client.
- Success is recorded from the adapter's response, never from the client.
"""
from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

from .paypal_adapter import PayPalAdapter
from .store import Store

CLIENT_STATE = {  # server state -> what the UI shows
    "GATED": "proposed", "AWAITING_APPROVAL": "proposed", "EXECUTING": "executing",
    "SUCCEEDED": "succeeded", "FAILED": "failed", "CANCELLED": "rejected",
}


class ActionError(Exception):
    def __init__(self, status: int, message: str):
        super().__init__(message)
        self.status = status


def idempotency_key(rec_id: str, action: dict) -> str:
    raw = json.dumps([rec_id, action["action_id"], action["type"], action["params"]], sort_keys=True)
    return hashlib.sha256(raw.encode()).hexdigest()[:32]


class Executor:
    def __init__(self, store: Store, adapter: PayPalAdapter, *, max_external_per_hour: int = 20):
        self.store, self.adapter, self.max_per_hour = store, adapter, max_external_per_hour

    def register(self, rec: dict, decisions: list[dict]) -> None:
        """Record every proposed action once, with its gate decision."""
        by_id = {d["action_id"]: d for d in decisions}
        for a in rec["actions"]:
            d = by_id[a["action_id"]]
            state = {"AUTO": "SUCCEEDED", "NEEDS_APPROVAL": "AWAITING_APPROVAL", "BLOCKED": "GATED"}[d["decision"]]
            key = idempotency_key(rec["recommendation_id"], a)
            if self.store.insert_action({"idempotency_key": key, "recommendation_id": rec["recommendation_id"],
                                         "action_id": a["action_id"], "type": a["type"], "params": a["params"],
                                         "decision": d["decision"], "state": state}):
                if state == "SUCCEEDED":
                    self.store.transition(key, ("SUCCEEDED",), "SUCCEEDED", execution_mode="real",
                                          detail="Prepared automatically. Nothing left the system.")
                self.store.audit("system", "action_registered", {"recommendation_id": rec["recommendation_id"],
                                 "action_id": a["action_id"], "decision": d["decision"], "rules": d["rules_hit"]})

    def approve(self, rec: dict, decisions: list[dict], action_id: str, actor: str = "merchant") -> dict:
        action = next((a for a in rec["actions"] if a["action_id"] == action_id), None)
        if action is None:
            raise ActionError(404, f"No action {action_id} in {rec['recommendation_id']}.")
        decision = next(d for d in decisions if d["action_id"] == action_id)  # fresh gate result
        key = idempotency_key(rec["recommendation_id"], action)
        row = self.store.get_action(rec["recommendation_id"], action_id)
        if decision["decision"] == "BLOCKED":
            self.store.audit(actor, "approval_refused", {"action_id": action_id, "rules": decision["rules_hit"]})
            raise ActionError(409, f"Blocked by policy: {decision['explanation']}")
        if row and row["state"] in ("EXECUTING", "SUCCEEDED", "FAILED", "CANCELLED"):
            self.store.audit(actor, "duplicate_approval_ignored", {"action_id": action_id, "state": row["state"]})
            return row
        since = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat(timespec="seconds")
        if self.store.count_executed_since(since) >= self.max_per_hour:
            raise ActionError(429, "Rate limit: too many executed actions in the last hour.")
        if not self.store.transition(key, ("AWAITING_APPROVAL",), "EXECUTING",
                                     approved_at=datetime.now(timezone.utc).isoformat(timespec="seconds")):
            return self.store.get_action(rec["recommendation_id"], action_id)  # lost the race: someone else is executing
        self.store.audit(actor, "action_approved", {"action_id": action_id, "type": action["type"]})
        try:
            result = self.adapter.execute(action)
            self.store.transition(key, ("EXECUTING",), "SUCCEEDED", execution_mode=result["mode"],
                                  paypal_ref=result.get("paypal_ref"), detail=result["detail"])
            self.store.audit("executor", "action_succeeded", {"action_id": action_id, **result})
        except Exception as e:  # noqa: BLE001 - any adapter failure is recorded, never swallowed silently
            self.store.transition(key, ("EXECUTING",), "FAILED", detail=f"Execution failed: {e}")
            self.store.audit("executor", "action_failed", {"action_id": action_id, "error": str(e)})
        return self.store.get_action(rec["recommendation_id"], action_id)

    def reject(self, rec: dict, action_id: str, actor: str = "merchant") -> dict:
        action = next((a for a in rec["actions"] if a["action_id"] == action_id), None)
        if action is None:
            raise ActionError(404, f"No action {action_id}.")
        key = idempotency_key(rec["recommendation_id"], action)
        if self.store.transition(key, ("AWAITING_APPROVAL",), "CANCELLED", detail="Rejected by the merchant. Nothing sent."):
            self.store.audit(actor, "action_rejected", {"action_id": action_id})
        return self.store.get_action(rec["recommendation_id"], action_id)

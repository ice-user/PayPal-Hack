"""API, executor and PayPal adapter tests. No network: PayPal is a fake transport."""
import sys
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from intelligence.schema import errors  # noqa: E402
from precedent import api as api_module  # noqa: E402
from precedent.paypal_adapter import PayPalAdapter  # noqa: E402
from precedent.service import Service  # noqa: E402
from precedent.store import Store  # noqa: E402

ENV = {"PAYPAL_CLIENT_ID": "test-id", "PAYPAL_CLIENT_SECRET": "test-secret",
       "PAYPAL_BASE_URL": "https://api-m.sandbox.paypal.com", "PAYPAL_WEBHOOK_ID": "WH-TEST"}


class FakePayPal:
    """Records calls; dispute allows whatever `allowed` lists."""

    def __init__(self, allowed=(), verify="SUCCESS"):
        self.calls, self.allowed, self.verify = [], list(allowed), verify

    def __call__(self, method, path, *, headers, data):
        self.calls.append((method, path))
        if path == "/v1/oauth2/token":
            return 200, {"access_token": "tok", "expires_in": 3600}
        if path.endswith("verify-webhook-signature"):
            return 200, {"verification_status": self.verify}
        if method == "GET" and "/v1/customer/disputes/" in path:
            return 200, {"dispute_id": path.rsplit("/", 1)[-1], "status": "OPEN", "dispute_state": "UNDER_PAYPAL_REVIEW",
                         "links": [{"rel": "self"}] + [{"rel": r} for r in self.allowed]}
        if method == "POST" and "/v1/customer/disputes/" in path:
            return 200, {"links": []}
        return 404, {"name": "NOT_FOUND"}

    def writes(self):
        return [c for c in self.calls if c[0] == "POST" and "/disputes/" in c[1]]


def make_client(fake):
    svc = Service(store=Store(":memory:"), adapter=PayPalAdapter(env=ENV, transport=fake))
    api_module._service = svc
    return TestClient(api_module.app), svc


@pytest.fixture
def blocked_pp():
    return FakePayPal(allowed=())


def first_needs_approval(bundle):
    return next(d["action_id"] for d in bundle["policy_decisions"] if d["decision"] == "NEEDS_APPROVAL")


def test_bundle_is_contract_valid(blocked_pp):
    client, _ = make_client(blocked_pp)
    b = client.get("/api/bundles/A?mode=with_precedent").json()
    assert errors("bundle", b) == []
    assert all(v["state"] in ("proposed", "succeeded") for v in b["action_states"].values())


def test_approve_falls_back_to_labelled_simulation_when_paypal_blocks(blocked_pp):
    client, _ = make_client(blocked_pp)
    b = client.get("/api/bundles/A").json()
    aid = first_needs_approval(b)
    b2 = client.post("/api/actions/approve", json={"situation": "A", "action_id": aid}).json()
    st = b2["action_states"][aid]
    assert st["state"] == "succeeded" and st["execution_mode"] == "simulated"
    assert "does not allow" in st["detail"]
    assert blocked_pp.writes() == []  # never wrote to PayPal
    assert any(e["step"] == "executed" and e["status"] == "done" and e["simulated"] for e in b2["timeline"])


def test_real_call_when_paypal_allows_and_no_double_execution():
    fake = FakePayPal(allowed=["provide_evidence", "send_message"])
    client, _ = make_client(fake)
    aid = first_needs_approval(client.get("/api/bundles/A").json())
    for _ in range(3):  # double and triple clicks
        b = client.post("/api/actions/approve", json={"situation": "A", "action_id": aid}).json()
    assert b["action_states"][aid]["execution_mode"] == "real"
    assert len(fake.writes()) == 1


def test_blocked_action_cannot_be_approved(blocked_pp):
    client, _ = make_client(blocked_pp)
    b = client.get("/api/bundles/A?mode=no_precedent").json()
    r = client.post("/api/actions/approve", json={"situation": "A", "mode": "no_precedent", "action_id": "act_3"})
    assert r.status_code == 409 and "Blocked by policy" in r.json()["detail"]
    assert b["policy_decisions"][2]["decision"] == "BLOCKED"


def test_reject_then_approve_does_nothing(blocked_pp):
    client, _ = make_client(blocked_pp)
    aid = first_needs_approval(client.get("/api/bundles/B").json())
    client.post("/api/actions/reject", json={"situation": "B", "action_id": aid})
    b = client.post("/api/actions/approve", json={"situation": "B", "action_id": aid}).json()
    assert b["action_states"][aid]["state"] == "rejected"


def test_simulated_clock_requires_an_executed_action_and_records_pending_case(blocked_pp):
    client, svc = make_client(blocked_pp)
    assert client.post("/api/sim/advance", json={"situation": "A"}).status_code == 409
    aid = first_needs_approval(client.get("/api/bundles/A").json())
    client.post("/api/actions/approve", json={"situation": "A", "action_id": aid})
    b = client.post("/api/sim/advance", json={"situation": "A", "days": 14}).json()
    assert b["outcome"]["simulated"] is True and b["outcome"]["after"] < b["outcome"]["before"]
    pending = svc.store.pending_cases()
    assert len(pending) == 1 and pending[0]["evidence_quality"] == "simulated" and pending[0]["review_status"] == "pending"
    assert pending[0]["case_id"] not in {c["case_id"] for c in svc.cases}  # never retrievable until reviewed


def test_reviewed_simulated_case_joins_library_but_never_drives_numbers(blocked_pp):
    client, svc = make_client(blocked_pp)
    aid = first_needs_approval(client.get("/api/bundles/A").json())
    client.post("/api/actions/approve", json={"situation": "A", "action_id": aid})
    b = client.post("/api/sim/advance", json={"situation": "A"}).json()
    cid = b["outcome"]["new_case_id"]
    assert b["outcome"]["case_review_status"] == "pending"
    assert client.post(f"/api/cases/{cid}/review", json={"decision": "maybe"}).status_code == 400
    r = client.post(f"/api/cases/{cid}/review", json={"decision": "approved"})
    assert r.status_code == 200 and r.json()["review_status"] == "approved"
    b2 = client.get("/api/bundles/A").json()
    assert b2["outcome"]["case_review_status"] == "approved"
    sim = [p for p in b2["recommendation"]["precedents"] if p["case_id"] == cid]
    assert sim and sim[0]["provenance"] == "live_simulated" and sim[0]["evidence_quality"] == "simulated"
    assert b2["recommendation"]["predicted_effect"] is None  # simulated cases never produce numbers
    assert any(e["event"] == "case_reviewed" for e in client.get("/api/audit").json()["events"])


def test_webhook_bad_signature_rejected_and_replay_ignored():
    bad = FakePayPal(verify="FAILURE")
    client, _ = make_client(bad)
    hdrs = {"paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
            "paypal-transmission-id": "T-1", "paypal-transmission-sig": "sig", "paypal-transmission-time": "2026-11-07T00:00:00Z"}
    event = {"event_type": "CUSTOMER.DISPUTE.UPDATED", "resource": {"dispute_id": "PP-R-1"}}
    assert client.post("/api/paypal/webhook", json=event, headers=hdrs).status_code == 400
    good = FakePayPal(verify="SUCCESS")
    client, _ = make_client(good)
    assert client.post("/api/paypal/webhook", json=event, headers=hdrs).json() == {"ok": True, "replay": False}
    assert client.post("/api/paypal/webhook", json=event, headers=hdrs).json() == {"ok": True, "replay": True}
    assert client.post("/api/paypal/webhook", json=event, headers={}).status_code == 400  # missing headers


def test_adapter_refuses_live_host():
    with pytest.raises(ValueError):
        PayPalAdapter(env=dict(ENV, PAYPAL_BASE_URL="https://api-m.paypal.com"))


def test_unknown_situation_is_404(blocked_pp):
    client, _ = make_client(blocked_pp)
    assert client.get("/api/bundles/Z").status_code == 404

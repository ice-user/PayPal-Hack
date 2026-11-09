"""TechKart dispute-level triage: shipment-state paths, warnings, deadlines, money batching,
the gate's triage rules, System A, and the API path for situation T. No network."""
import sys
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from intelligence.gate_reference import decide as gate  # noqa: E402
from intelligence.schema import errors  # noqa: E402
from intelligence.triage import (MONEY_BATCH_CAP, decide, fingerprint, generic_plan,  # noqa: E402
                                 load_dispute_cases, triage)
from precedent import api as api_module  # noqa: E402
from precedent.paypal_adapter import PayPalAdapter  # noqa: E402
from precedent.service import Service  # noqa: E402
from precedent.store import Store  # noqa: E402
from precedent.techkart import TECHKART, generate  # noqa: E402

TODAY = date(2026, 11, 8)
CASES = load_dispute_cases()


def dispute(status, proof, due="2026-11-15", expected=None, amount=79.0, did="TKD-1"):
    return {"dispute_id": did, "order_id": "TK-1", "carrier": "Carrier X", "sku": "VX-200 wireless earbuds",
            "amount": amount, "reason": "ITEM_NOT_RECEIVED", "shipment_status": status, "proof": proof,
            "expected_delivery": expected, "response_due": due, "opened": "2026-11-05", "true_state": None}


def test_deadline_first_only_when_delivery_misses_the_window():
    assert fingerprint(dispute("in_transit", "tracking", due="2026-11-15", expected="2026-11-11"), TODAY)["deadline_first"] == 0
    assert fingerprint(dispute("in_transit", "tracking", due="2026-11-15", expected="2026-11-15"), TODAY)["deadline_first"] == 1
    assert fingerprint(dispute("delivered", "confirmation"), TODAY)["deadline_first"] == 0


def test_each_shipment_state_gets_its_spec_path():
    cases = {
        ("delivered", "confirmation", None): "evidence_delivery",
        ("delivered", "gps", None): "evidence_delivery_documented",
        ("delivered", "signature", None): "evidence_delivery_documented",
        ("in_transit", "tracking", "2026-11-10"): "message_eta",
        ("in_transit", "tracking", "2026-11-20"): "evidence_in_transit",
        ("lost", "tracking", None): "refund_lost",
        ("unknown", "none", None): "gather_info",
    }
    for (status, proof, expected), path in cases.items():
        assert decide(dispute(status, proof, expected=expected), CASES, TODAY)["response"] == path, (status, proof)


def test_backfired_cases_warn_but_never_vote():
    dec = decide(dispute("in_transit", "tracking", due="2026-11-11", expected="2026-11-20"), CASES, TODAY)
    assert dec["response"] == "evidence_in_transit"
    assert {"dc_t05_claimed_delivered_early", "dc_t06_waited_past_deadline"} <= set(dec["warnings"])
    by_id = {c["case_id"]: c for c in CASES}
    assert all(by_id[b]["appropriate"] for b in dec["backers"])


def test_no_close_case_means_manual_review():
    dec = decide(dispute("delivered", "confirmation"), [c for c in CASES if c["fingerprint"]["status"] != "delivered"], TODAY)
    assert dec["response"] == "manual_review" and dec["backers"] == []


def test_only_delivered_parcels_are_claimed_delivered():
    _, disputes = generate(TECHKART)
    t = triage(disputes, TECHKART.end, cases=CASES)
    states = {d["dispute_id"]: d["shipment_status"] for d in disputes}
    for a in t["actions"]:
        if a["params"]["asserts_delivery"]:
            assert {states[i] for i in a["params"]["synthetic_dispute_ids"]} == {"delivered"}


def test_refunds_are_batched_under_the_cap():
    lost = [dispute("lost", "tracking", amount=189.0, did=f"TKD-{i}") for i in range(6)]
    t = triage(lost, TODAY, cases=CASES)
    refunds = [a for a in t["actions"] if a["type"] == "ACCEPT_CLAIM"]
    assert len(refunds) > 1
    assert all(a["params"]["amount"]["value"] <= MONEY_BATCH_CAP for a in refunds)
    assert sum(a["params"]["dispute_count"] for a in refunds) == 6


def _rec(actions, abstain=False):
    return {"actions": actions, "precedents": [], "abstain": abstain, "confidence": 0.3}


def test_gate_triage_rules():
    _, disputes = generate(TECHKART)
    t = triage(disputes, TECHKART.end, cases=CASES)
    decisions = {d["action_id"]: d for d in gate(_rec(t["actions"], abstain=True))}
    for a in t["actions"]:
        d = decisions[a["action_id"]]
        if a["type"] == "FLAG_ONLY":
            assert d["decision"] == "AUTO"
        else:  # the spike-level abstention does not block dispute handling
            assert d["decision"] == "NEEDS_APPROVAL", (a["title"], d)
        if a["type"] == "ACCEPT_CLAIM":
            assert "money_requires_approval" in d["rules_hit"]
    weak = dict(t["actions"][0], supporting_cases=t["actions"][0]["supporting_cases"][:1])
    assert gate(_rec([weak]))[0]["decision"] == "BLOCKED"


def test_generic_plan_ignores_shipment_state():
    ds = [dispute("lost", "tracking", did="a"), dispute("in_transit", "tracking", did="b"),
          dispute("delivered", "gps", did="c"), dispute("unknown", "none", did="d")]
    assert generic_plan(ds) == {"a": "generic_tracking", "b": "generic_tracking", "c": "generic_tracking",
                                "d": "generic_refund"}


def test_api_serves_techkart_and_simulates_without_sandbox_mapping():
    calls = []

    def transport(method, path, *, headers, data):
        calls.append((method, path))
        return (200, {"access_token": "t", "expires_in": 3600}) if path == "/v1/oauth2/token" else (404, {})

    env = {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": "s", "PAYPAL_BASE_URL": "https://api-m.sandbox.paypal.com"}
    svc = Service(store=Store(":memory:"), adapter=PayPalAdapter(env=env, transport=transport))
    api_module._service = svc
    client = TestClient(api_module.app)
    assert "T" in [s["key"] for s in client.get("/api/situations").json()["situations"]]
    b = client.get("/api/bundles/T?mode=with_precedent").json()
    assert not errors("bundle", b)
    assert b["recommendation"]["triage"]["groups"]
    target = next(d["action_id"] for d in b["policy_decisions"] if d["decision"] == "NEEDS_APPROVAL")
    after = client.post("/api/actions/approve", json={"situation": "T", "mode": "with_precedent", "action_id": target}).json()
    st = after["action_states"][target]
    assert st["state"] == "succeeded" and st["execution_mode"] == "simulated"
    assert not [c for c in calls if c[0] == "POST" and "/disputes/" in c[1]]  # nothing reached PayPal
    adv = client.post("/api/sim/advance", json={"situation": "T", "mode": "with_precedent", "days": 14}).json()
    assert adv["outcome"] and "new_case_id" not in adv["outcome"]  # dispute-level only: no case to learn from
    blocked = client.get("/api/bundles/T?mode=no_precedent").json()
    assert all(d["decision"] == "BLOCKED" for d in blocked["policy_decisions"] if d["tier"] != "PREPARE")

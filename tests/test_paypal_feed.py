"""PayPal as input and output: disputes and trackers imported from the sandbox account are
triaged, their actions target those exact disputes, and a public deployment can allow only
some real action types under an hourly cap. A fake PayPal transport; no network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient  # noqa: E402

from precedent import api as api_module  # noqa: E402
from precedent.paypal_adapter import PayPalAdapter  # noqa: E402
from precedent.paypal_feed import PayPalFeed, to_dispute  # noqa: E402
from precedent.service import Service  # noqa: E402
from precedent.store import Store  # noqa: E402

ENV = {"PAYPAL_CLIENT_ID": "id", "PAYPAL_CLIENT_SECRET": "s", "PAYPAL_BASE_URL": "https://api-m.sandbox.paypal.com"}
SELLER_LINKS = [{"rel": "self"}, {"rel": "provide_evidence"}, {"rel": "send_message"}, {"rel": "accept_claim"}]


def detail(did, status, tx, amount="79.00", links=SELLER_LINKS):
    return {"dispute_id": did, "reason": "MERCHANDISE_OR_SERVICE_NOT_RECEIVED", "status": status,
            "dispute_life_cycle_stage": "INQUIRY", "dispute_amount": {"currency_code": "USD", "value": amount},
            "create_time": "2026-11-08T10:00:00Z", "seller_response_due_date": "2026-11-18T10:00:00Z",
            "disputed_transactions": [{"seller_transaction_id": tx, "items": [{"item_name": "VX-200 wireless earbuds"}]}],
            "links": links}


class FakePayPal:
    def __init__(self):
        self.calls = []
        self.disputes = {
            "PP-D-1": detail("PP-D-1", "WAITING_FOR_SELLER_RESPONSE", "TX1"),
            "PP-D-2": detail("PP-D-2", "WAITING_FOR_SELLER_RESPONSE", "TX2"),
            "PP-D-3": detail("PP-D-3", "WAITING_FOR_BUYER_RESPONSE", "TX3", links=[{"rel": "accept_claim"}]),
        }
        self.trackers = {"TX1": [{"transaction_id": "TX1", "tracking_number": "1Z1", "status": "DELIVERED", "carrier": "UPS"}],
                         "TX2": [{"transaction_id": "TX2", "tracking_number": "1Z2", "status": "SHIPPED", "carrier": "UPS"}]}

    def __call__(self, method, path, *, headers, data):
        self.calls.append((method, path))
        if path == "/v1/oauth2/token":
            return 200, {"access_token": "t", "expires_in": 3600}
        if path.startswith("/v1/customer/disputes?"):
            return 200, {"items": [{"dispute_id": k} for k in self.disputes]}
        if path.startswith("/v1/shipping/trackers?"):
            tx = path.split("transaction_id=")[1]
            return 200, {"trackers": self.trackers.get(tx, [])}
        if path.startswith("/v1/customer/disputes/"):
            did = path.split("/")[4]
            if method == "POST":
                return 200, {"links": []}
            return 200, self.disputes[did]
        return 404, {}


def svc(fake, **env):
    adapter = PayPalAdapter(env={**ENV, **env}, transport=fake)
    return Service(store=Store(":memory:"), adapter=adapter)


def test_tracker_status_maps_to_shipment_state_and_response():
    delivered = to_dispute(detail("A", "WAITING_FOR_SELLER_RESPONSE", "T"), [{"status": "DELIVERED", "tracking_number": "1"}])
    shipped = to_dispute(detail("B", "WAITING_FOR_SELLER_RESPONSE", "T"), [{"status": "SHIPPED"}])
    none = to_dispute(detail("C", "WAITING_FOR_SELLER_RESPONSE", "T"), [])
    assert (delivered["shipment_status"], delivered["proof"]) == ("delivered", "confirmation")
    assert (shipped["shipment_status"], shipped["expected_delivery"]) == ("in_transit", None)
    assert (none["shipment_status"], none["proof"]) == ("unknown", "none")
    assert delivered["reason"] == "ITEM_NOT_RECEIVED" and delivered["response_due"] == "2026-11-18"
    assert delivered["amount"] == 79.0 and delivered["paypal"] is True


def test_feed_imports_triages_only_disputes_waiting_for_the_seller_and_caches():
    fake = FakePayPal()
    feed = PayPalFeed(PayPalAdapter(env=ENV, transport=fake), ttl=60)
    snap = feed.snapshot()
    assert [d["dispute_id"] for d in snap["triage"]] == ["PP-D-1", "PP-D-2"]
    assert {r["dispute_id"]: r["triaged"] for r in snap["disputes"]} == {"PP-D-1": True, "PP-D-2": True, "PP-D-3": False}
    n = len(fake.calls)
    feed.snapshot()
    assert len(fake.calls) == n  # cached
    fake.trackers["TX2"][0]["status"] = "DELIVERED"
    v = snap["version"]
    assert feed.snapshot(force=True)["version"] == v + 1  # PayPal data changed: new version


def test_feed_without_credentials_makes_no_calls():
    fake = FakePayPal()
    snap = PayPalFeed(PayPalAdapter(env={}, transport=fake)).snapshot()
    assert snap["connected"] is False and fake.calls == []


def test_techkart_triages_live_disputes_with_their_own_paypal_targets():
    s = svc(FakePayPal(), PRECEDENT_REAL_EXECUTION="0")
    b = s.bundle("T", "with_precedent")
    live_groups = [g for g in b["recommendation"]["triage"]["groups"] if g.get("paypal")]
    assert {g["response"] for g in live_groups} == {"evidence_delivery", "evidence_in_transit"}
    acts = {a["action_id"]: a for a in b["recommendation"]["actions"]}
    for g in live_groups:
        for aid in g["action_ids"]:
            p = acts[aid]["params"]
            assert p["dispute_ids"] and set(p["dispute_ids"]) <= {"PP-D-1", "PP-D-2"} and p["synthetic_dispute_ids"] == []
    assert not any(set(a["params"].get("dispute_ids") or []) & {"PP-D-1", "PP-D-2"}
                   for a in acts.values() if a["params"].get("synthetic_dispute_ids"))
    assert b["paypal"]["connected"] and len(b["paypal"]["disputes"]) == 3
    assert b["recommendation"]["recommendation_id"].endswith("_pp1")


def _live_action(b, response):
    g = next(g for g in b["recommendation"]["triage"]["groups"] if g.get("paypal") and g["response"] == response)
    return g["action_ids"][0]


def test_public_allowlist_runs_evidence_for_real_on_the_right_dispute():
    fake = FakePayPal()
    s = svc(fake, PRECEDENT_REAL_EXECUTION="1", PRECEDENT_REAL_ACTIONS="SEND_MESSAGE,PROVIDE_EVIDENCE")
    b = s.bundle("T", "with_precedent")
    aid = _live_action(b, "evidence_delivery")
    after = s.approve("T", "with_precedent", aid)
    st = after["action_states"][aid]
    assert st["execution_mode"] == "real", st
    assert ("POST", "/v1/customer/disputes/PP-D-1/provide-evidence") in fake.calls
    assert not [c for c in fake.calls if c[0] == "POST" and "PP-D-2" in c[1]]


def test_types_outside_the_allowlist_stay_simulated():
    fake = FakePayPal()
    adapter = PayPalAdapter(env={**ENV, "PRECEDENT_REAL_ACTIONS": "SEND_MESSAGE"}, transport=fake)
    out = adapter.execute({"type": "PROVIDE_EVIDENCE", "title": "t", "rationale": "r", "params": {"dispute_ids": ["PP-D-1"]}})
    assert out["mode"] == "simulated" and "keeps PROVIDE_EVIDENCE simulated" in out["detail"]
    assert not [c for c in fake.calls if c[0] == "POST" and "/disputes/" in c[1]]


def test_hourly_cap_on_real_actions():
    fake = FakePayPal()
    adapter = PayPalAdapter(env={**ENV, "PRECEDENT_REAL_CALLS_PER_HOUR": "1"}, transport=fake)
    act = {"type": "SEND_MESSAGE", "title": "t", "rationale": "r", "params": {"dispute_ids": ["PP-D-1"]}}
    assert adapter.execute(act)["mode"] == "real"
    second = adapter.execute(act)
    assert second["mode"] == "simulated" and "limit of 1 real PayPal actions an hour" in second["detail"]


def test_activity_log_and_endpoints_carry_no_secrets():
    fake = FakePayPal()
    api_module._service = svc(fake, PRECEDENT_REAL_EXECUTION="0")
    c = TestClient(api_module.app)
    acct = c.get("/api/paypal/account").json()
    assert acct["connected"] and acct["real_actions"] is None
    calls = c.get("/api/paypal/activity").json()["calls"]
    assert calls and {"method", "path", "status", "ms", "at"} == set(calls[0])
    assert "secret" not in str(calls).lower() and "Bearer" not in str(calls)
    assert c.post("/api/paypal/refresh").json()["connected"]

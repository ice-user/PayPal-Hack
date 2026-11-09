"""Public deployment: each browser (X-Demo-Session) gets its own demo workspace. No network."""
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from precedent import api as api_module  # noqa: E402
from precedent.paypal_adapter import PayPalAdapter  # noqa: E402
from precedent.service import Service  # noqa: E402
from precedent.store import Store  # noqa: E402

JUDGE_1 = {"X-Demo-Session": "judge-one-0001"}
JUDGE_2 = {"X-Demo-Session": "judge-two-0002"}


@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("PRECEDENT_PER_VISITOR", "1")
    api_module._service = Service(store=Store(":memory:"), adapter=PayPalAdapter(env={"PRECEDENT_REAL_EXECUTION": "0"}))
    api_module._visitors.clear()
    yield TestClient(api_module.app)
    api_module._visitors.clear()


def _approve_first(client, headers, key="B"):
    b = client.get(f"/api/bundles/{key}", headers=headers).json()
    target = next(d["action_id"] for d in b["policy_decisions"] if d["decision"] == "NEEDS_APPROVAL")
    after = client.post("/api/actions/approve", headers=headers,
                        json={"situation": key, "mode": "with_precedent", "action_id": target}).json()
    return target, after


def test_one_visitors_approval_is_invisible_to_another(client):
    target, after = _approve_first(client, JUDGE_1)
    assert after["action_states"][target]["state"] == "succeeded"
    assert after["action_states"][target]["execution_mode"] == "simulated"
    other = client.get("/api/bundles/B", headers=JUDGE_2).json()
    assert other["action_states"][target]["state"] == "proposed"
    mine = client.get("/api/bundles/B", headers=JUDGE_1).json()
    assert mine["action_states"][target]["state"] == "succeeded"


def test_reset_clears_only_the_callers_workspace(client):
    target, _ = _approve_first(client, JUDGE_1)
    _approve_first(client, JUDGE_2)
    assert client.post("/api/demo/reset", headers=JUDGE_1).json() == {"ok": True}
    assert client.get("/api/bundles/B", headers=JUDGE_1).json()["action_states"][target]["state"] == "proposed"
    assert client.get("/api/bundles/B", headers=JUDGE_2).json()["action_states"][target]["state"] == "succeeded"


def test_visitors_share_one_plan_but_not_the_audit_log(client):
    a = client.get("/api/bundles/T", headers=JUDGE_1).json()
    b = client.get("/api/bundles/T", headers=JUDGE_2).json()
    assert a["recommendation"] == b["recommendation"]
    _approve_first(client, JUDGE_1, key="T")
    events = lambda h: [e["event"] for e in client.get("/api/audit", headers=h).json()["events"]]  # noqa: E731
    assert "action_approved" in events(JUDGE_1)
    assert "action_approved" not in events(JUDGE_2)


def test_missing_or_bad_session_ids_share_an_anonymous_workspace(client):
    target, _ = _approve_first(client, {})
    weird = client.get("/api/bundles/B", headers={"X-Demo-Session": "../../etc"}).json()
    assert weird["action_states"][target]["state"] == "succeeded"  # same "anonymous" workspace
    assert client.get("/api/bundles/B", headers=JUDGE_1).json()["action_states"][target]["state"] == "proposed"


def test_workspace_cap_drops_the_least_recently_used(client, monkeypatch):
    monkeypatch.setenv("PRECEDENT_MAX_VISITORS", "2")
    for i in range(4):
        client.get("/api/bundles/A", headers={"X-Demo-Session": f"visitor-{i:04d}"})
    assert list(api_module._visitors) == ["visitor-0002", "visitor-0003"]


def test_without_the_flag_everyone_shares_the_service(monkeypatch):
    monkeypatch.delenv("PRECEDENT_PER_VISITOR", raising=False)
    api_module._service = Service(store=Store(":memory:"), adapter=PayPalAdapter(env={"PRECEDENT_REAL_EXECUTION": "0"}))
    c = TestClient(api_module.app)
    target, _ = _approve_first(c, JUDGE_1)
    assert c.get("/api/bundles/B", headers=JUDGE_2).json()["action_states"][target]["state"] == "succeeded"

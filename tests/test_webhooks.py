"""Verified event ingestion: retries, ordering, persistence and action isolation."""
import copy
import json
import sqlite3
from concurrent.futures import ThreadPoolExecutor
from urllib.error import URLError

import pytest

from test_api import ENV, FakePayPal, make_client
from precedent.paypal_adapter import PayPalAdapter
from precedent.store import Store
from precedent.webhooks import metadata

HEADERS = {"paypal-auth-algo": "SHA256withRSA", "paypal-cert-url": "https://api.sandbox.paypal.com/cert",
           "paypal-transmission-id": "T-1", "paypal-transmission-sig": "sig",
           "paypal-transmission-time": "2026-11-08T12:00:00Z"}
EVENT = {"id": "WH-1", "event_type": "CUSTOMER.DISPUTE.UPDATED", "create_time": "2026-11-08T12:00:00Z",
         "resource": {"dispute_id": "PP-R-1", "status": "OPEN", "dispute_state": "UNDER_REVIEW",
                      "update_time": "2026-11-08T11:00:00Z", "buyer": {"email": "private@example.com"}}}


def post(client, event=None, headers=None):
    return client.post("/api/paypal/webhook", json=EVENT if event is None else event,
                       headers=HEADERS if headers is None else headers)


def history(client):
    response = client.get("/api/paypal/disputes/PP-R-1/events")
    assert response.status_code == 200
    return response.json()


def test_dedup_uses_event_id_and_verifies_even_replays():
    fake = FakePayPal()
    client, svc = make_client(fake)
    assert post(client).json() == {"ok": True, "replay": False}
    assert post(client, headers=dict(HEADERS, **{"paypal-transmission-id": "T-2"})).json()["replay"] is True
    assert post(client, dict(EVENT, id="WH-2")).json()["replay"] is False
    fake.verify = "FAILURE"
    assert post(client).status_code == 400
    assert len(history(client)["events"]) == 2
    assert len([e for e in svc.store.audit_tail() if e["event"] == "webhook_received"]) == 2
    assert fake.writes() == []


@pytest.mark.parametrize("payload", [None, [], "text", {}, dict(EVENT, id=""), dict(EVENT, id=12),
    dict(EVENT, create_time="2026-11-08T12:00:00"), dict(EVENT, resource=[]),
    dict(EVENT, resource={}), dict(EVENT, resource={"dispute_id": "PP-R-1", "status": []}),
    dict(EVENT, resource={"dispute_id": "PP-R-1", "update_time": "bad"})])
def test_malformed_envelopes_do_not_call_paypal(payload):
    fake = FakePayPal()
    client, svc = make_client(fake)
    assert client.post("/api/paypal/webhook", content=json.dumps(payload), headers=HEADERS).status_code == 400
    assert fake.calls == []
    assert svc.store.audit_tail() == []


@pytest.mark.parametrize("body,code", [(b"{", 400), (b"\xff", 400), (b" " * (1024 * 1024 + 1), 413)],
                         ids=["broken-json", "invalid-encoding", "oversized"])
def test_bad_json_and_body_limit(body, code):
    client, _ = make_client(FakePayPal())
    assert client.post("/api/paypal/webhook", content=body).status_code == code


@pytest.mark.parametrize("failure", [URLError("offline"), TimeoutError(), ValueError("invalid upstream JSON"),
                                     (500, {}), (429, {}), (401, {}), (200, {}), (200, [])])
def test_verification_outage_leaves_event_retryable(failure):
    fake = FakePayPal()
    failed = True

    def flaky(method, path, **kwargs):
        if failed and path.endswith("verify-webhook-signature"):
            if isinstance(failure, Exception):
                raise failure
            return failure
        return fake(method, path, **kwargs)

    client, svc = make_client(flaky)
    assert post(client).status_code == 503
    assert history(client)["events"] == []
    assert svc.store.audit_tail() == []
    failed = False
    assert post(client).json() == {"ok": True, "replay": False}


def test_unconfigured_receiver_is_retryable():
    client, svc = make_client(FakePayPal())
    svc.adapter = PayPalAdapter(env={})
    assert post(client).status_code == 503
    assert history(client)["events"] == []


@pytest.mark.parametrize("event_type", ["CUSTOMER.DISPUTE.CREATED", "CUSTOMER.DISPUTE.RESOLVED"])
def test_original_event_is_verified_but_only_metadata_is_persisted(event_type):
    fake = FakePayPal()
    verified = []

    def transport(method, path, **kwargs):
        if path.endswith("verify-webhook-signature"):
            verified.append(json.loads(kwargs["data"]))
        return fake(method, path, **kwargs)

    client, svc = make_client(transport)
    event = dict(EVENT, event_type=event_type)
    assert post(client, event).status_code == 200
    assert verified[0]["webhook_event"] == event
    assert verified[0]["webhook_id"] == ENV["PAYPAL_WEBHOOK_ID"]
    assert verified[0]["transmission_id"] == HEADERS["paypal-transmission-id"]
    assert history(client)["snapshot"]["event_id"] == event["id"]
    persisted = "\n".join(svc.store.db.iterdump())
    assert "private@example.com" not in persisted


def test_out_of_order_equal_timestamp_and_partial_updates_keep_newer_snapshot():
    client, _ = make_client(FakePayPal())
    newest = copy.deepcopy(EVENT)
    newest["resource"].update(status="RESOLVED", update_time="2026-11-08T14:00:00+02:00")
    assert post(client, newest).status_code == 200
    older = copy.deepcopy(EVENT)
    older.update(id="WH-older", create_time="2026-11-08T18:00:00Z")
    assert post(client, older).status_code == 200  # later delivery/envelope, older resource
    equal = copy.deepcopy(EVENT)
    equal["id"] = "WH-equal"
    equal["resource"]["update_time"] = "2026-11-08T12:00:00Z"
    assert post(client, equal).status_code == 200
    partial = copy.deepcopy(EVENT)
    partial["id"] = "WH-partial"
    del partial["resource"]["update_time"]
    assert post(client, partial).status_code == 200
    data = history(client)
    assert data["snapshot"]["dispute"]["status"] == "RESOLVED"
    assert len(data["events"]) == 4
    assert {e["disposition"] for e in data["events"]} == {
        "snapshot_updated", "history_only_stale_or_equal", "history_only_missing_state_or_time"}
    assert "private@example.com" not in json.dumps(data)


def test_unsupported_events_are_acknowledged_once_without_dispute_state():
    client, svc = make_client(FakePayPal())
    event = dict(EVENT, event_type="PAYMENT.CAPTURE.COMPLETED")
    assert post(client, event).json()["replay"] is False
    assert post(client, event).json()["replay"] is True
    assert history(client)["snapshot"] is None
    assert svc.store.audit_tail()[0]["payload"]["disposition"] == "ignored_event_type"


def add_action(store, key, mode, refs, state="SUCCEEDED"):
    store.insert_action({"idempotency_key": key, "recommendation_id": "rec", "action_id": key,
                         "type": "SEND_MESSAGE", "params": {"dispute_ids": ["PP-R-1", "PP-R-2"]},
                         "decision": "NEEDS_APPROVAL", "state": "EXECUTING"})
    store.transition(key, ("EXECUTING",), state, execution_mode=mode, paypal_ref=refs)


def test_related_actions_are_exact_real_refs_and_never_change_state():
    fake = FakePayPal()
    client, svc = make_client(fake)
    add_action(svc.store, "real", "real", "PP-R-2,PP-R-1")
    add_action(svc.store, "sim", "simulated", "PP-R-1")
    add_action(svc.store, "partial", "real", "PP-R-2")
    add_action(svc.store, "unrelated", "real", "PP-R-10")
    add_action(svc.store, "pending", None, None, "AWAITING_APPROVAL")
    before = svc.store.actions_for("rec")
    assert post(client).status_code == 200
    related = [{"recommendation_id": "rec", "action_id": "real"}]
    assert history(client)["related_actions"] == related
    assert svc.store.audit_tail()[0]["payload"]["related_actions"] == related
    assert svc.store.actions_for("rec") == before
    assert fake.writes() == []
    add_action(svc.store, "late", "real", "PP-R-1")
    assert len(history(client)["related_actions"]) == 2  # webhook beat executor response


def test_atomic_rollback_on_audit_failure():
    store = Store(":memory:")
    store.db.execute("CREATE TRIGGER fail_audit BEFORE INSERT ON audit_log BEGIN SELECT RAISE(ABORT, 'test'); END")
    with pytest.raises(sqlite3.IntegrityError):
        store.record_webhook(metadata(EVENT), "T-1")
    assert store.webhook_history("PP-R-1")["events"] == []
    assert store.webhook_history("PP-R-1")["snapshot"] is None
    store.db.execute("DROP TRIGGER fail_audit")
    assert store.record_webhook(metadata(EVENT), "T-1") is False


def test_legacy_database_upgrade_and_restart(tmp_path):
    path = tmp_path / "legacy.db"
    db = sqlite3.connect(path)
    db.execute("CREATE TABLE webhook_events (transmission_id TEXT PRIMARY KEY, event_type TEXT, received_at TEXT NOT NULL)")
    db.execute("INSERT INTO webhook_events VALUES ('T-1', 'CUSTOMER.DISPUTE.UPDATED', '2026-11-07')")
    db.commit()
    db.close()
    store = Store(path)
    assert store.record_webhook(metadata(EVENT), "T-1") is False
    store.db.close()
    store = Store(path)
    assert store.record_webhook(metadata(EVENT), "T-2") is True
    assert store.db.execute("SELECT COUNT(*) FROM webhook_events").fetchone()[0] == 1
    assert len(store.audit_tail()) == 1
    assert store.webhook_history("PP-R-1")["snapshot"]["event_id"] == "WH-1"
    store.db.close()


def test_concurrent_delivery_records_once():
    store = Store(":memory:")
    with ThreadPoolExecutor(max_workers=8) as pool:
        results = list(pool.map(lambda i: store.record_webhook(metadata(EVENT), f"T-{i}"), range(16)))
    assert results.count(False) == 1
    assert len(store.audit_tail()) == 1


def test_history_limit_is_bounded():
    client, _ = make_client(FakePayPal())
    for value in (0, -1, 501):
        assert client.get(f"/api/paypal/disputes/PP-R-1/events?limit={value}").status_code == 422

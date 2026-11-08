"""Cohort uncertainty must stop action selection, regardless of retrieval mode."""
import copy
import math
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from fastapi.testclient import TestClient
from intelligence.cases import load_cases, usable
from intelligence.consultant import recommend
from intelligence.gate_reference import decide
from intelligence.retrieve_hybrid import retrieve
from intelligence.schema import errors
from intelligence.stats import fisher_upper_p
from precedent import api
from precedent.orders import generate
from precedent.paypal_adapter import PayPalAdapter
from precedent.scenarios import ABLATION, DEMO
from precedent.service import Service
from precedent.situation_builder import build, diagnostic_conflict
from precedent.store import Store


def cohort(n, losses, *, delay=12, reason="ITEM_NOT_RECEIVED", delivered=False):
    return [{"ship_delay_hours": delay, "disputed": i < losses,
             "dispute_reason": reason if i < losses else None,
             "delivered": delivered if i < losses else True} for i in range(n)]


def test_fisher_matches_exact_combinatorial_reference_and_zero_baseline():
    # With all three events in the first cohort, the upper tail is a single term.
    assert fisher_upper_p(3, 100, 0, 500) == pytest.approx(math.comb(100, 3) / math.comb(600, 3))
    assert fisher_upper_p(3, 10, 1, 10) == pytest.approx(
        (math.comb(4, 3) * math.comb(16, 7) + math.comb(4, 4) * math.comb(16, 6)) / math.comb(20, 10))
    assert fisher_upper_p(0, 100, 0, 500) == 1
    assert fisher_upper_p(10, 10, 10, 10) == pytest.approx(1)
    assert fisher_upper_p(0, 0, 2, 100) == 1
    assert fisher_upper_p(2, 100, 0, 0) == 1
    assert fisher_upper_p(1, 100, 20, 100) > 0.99
    with pytest.raises(ValueError):
        fisher_upper_p(101, 100, 1, 10)


def test_independent_loss_signal_requires_delays_and_supporting_samples():
    baseline = cohort(500, 0)
    window = cohort(100, 3, delay=48)
    check = diagnostic_conflict(window, baseline, 36)
    assert check and check["window_lost_inr"] == 3 and check["window_orders"] == 100
    assert diagnostic_conflict(window, baseline, 35.9) is None
    assert diagnostic_conflict(cohort(99, 3), baseline, 36) is None
    assert diagnostic_conflict(window, cohort(499, 0), 36) is None
    assert diagnostic_conflict(cohort(100, 2), baseline, 36) is None
    assert diagnostic_conflict(cohort(100, 3, delay=48.1), baseline, 36) is None
    assert diagnostic_conflict([], [], 60) is None


@pytest.mark.parametrize("reason,delivered", [("UNAUTHORISED", False), ("ITEM_NOT_RECEIVED", True)])
def test_other_disputes_are_not_treated_as_missing_parcels(reason, delivered):
    assert diagnostic_conflict(cohort(100, 30, reason=reason, delivered=delivered), cohort(500, 0), 60) is None


def test_persistent_loss_rate_is_not_a_new_conflict():
    assert diagnostic_conflict(cohort(100, 10), cohort(500, 50), 60) is None


@pytest.mark.parametrize("mode", ["with_precedent", "no_precedent"])
def test_known_mixed_development_failure_abstains_before_writer(mode):
    scenario = next(s for s in ABLATION if s.name == "mixed_carrier_fulfilment")
    situation = build(generate(scenario), situation_id="sit_mixed_regression")
    check = situation["features"]["diagnostic_conflict"]
    assert check["window_lost_inr"] == 3
    assert check["p_value"] < 0.1
    assert errors("situation", situation) == []
    precedents = retrieve(situation, usable(load_cases()), k=6)
    def forbidden_writer(_):
        pytest.fail("An abstention must not reach the prose writer")
    rec = recommend(situation, precedents, mode=mode, writer=forbidden_writer)
    assert errors("recommendation", rec) == []
    assert rec["abstain"] and rec["actions"] == [] and decide(rec) == []
    assert rec["predicted_effect"] is None and rec["counterfactual"] is None
    assert "Review dispatch and tracking records" in rec["abstain_reason"]
    assert rec["precedents"] if mode == "with_precedent" else not rec["precedents"]


def test_pure_development_scenarios_do_not_raise_conflict():
    for scenario in list(DEMO.values()) + ABLATION:
        if scenario.kind == "mixed":
            continue
        situation = build(generate(scenario), situation_id="sit_pure")
        assert "diagnostic_conflict" not in situation["features"], scenario.name


def test_warning_depends_on_orders_not_labels_or_ordering():
    orders = generate(DEMO["D"])
    first = build(orders, situation_id="sit_first", label="single carrier")
    second = build(list(reversed(orders)), situation_id="sit_second", label="normal week")
    assert first["features"]["diagnostic_conflict"] == second["features"]["diagnostic_conflict"]
    assert "review needed" in first["narrative"]
    # A handful of old missing parcels outside the current window cannot trigger it.
    quiet = build(generate(next(s for s in ABLATION if s.name == "quiet_normal_week")), situation_id="sit_quiet")
    assert "diagnostic_conflict" not in quiet["features"]


def test_contract_rejects_unknown_check_kind_and_bad_probabilities():
    situation = build(generate(DEMO["D"]), situation_id="sit_contract")
    invalid = copy.deepcopy(situation)
    invalid["features"]["diagnostic_conflict"]["kind"] = "proven_carrier_failure"
    assert errors("situation", invalid)
    invalid = copy.deepcopy(situation)
    invalid["features"]["diagnostic_conflict"]["p_value"] = 1.1
    assert errors("situation", invalid)


def test_api_exposes_review_scenario_and_refuses_action_and_clock(monkeypatch):
    def no_paypal(*args, **kwargs):
        pytest.fail("The review scenario must never call PayPal")
    svc = Service(Store(":memory:"), PayPalAdapter(env={}, transport=no_paypal))
    monkeypatch.setattr(api, "_service", svc)
    client = TestClient(api.app)
    assert "D" in {s["key"] for s in client.get("/api/situations").json()["situations"]}
    for mode in ("with_precedent", "no_precedent"):
        bundle = client.get(f"/api/bundles/D?mode={mode}").json()
        assert errors("bundle", bundle) == []
        assert bundle["recommendation"]["abstain"]
        assert bundle["action_states"] == {} and bundle["policy_decisions"] == []
        steps = {event["step"]: event for event in bundle["timeline"]}
        assert all(steps[step]["status"] == "skipped" for step in ("approved", "executed", "measured"))
        assert client.post("/api/actions/approve", json={"situation": "D", "mode": mode, "action_id": "act_1"}).status_code == 404
        assert client.post("/api/sim/advance", json={"situation": "D", "mode": mode}).status_code == 409

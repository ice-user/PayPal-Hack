"""Contract, Consultant and reference-gate tests. Run: python -m pytest -q"""
import copy
import json
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from intelligence import effects, gate_reference  # noqa: E402
from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.consultant import recommend  # noqa: E402
from intelligence.retrieve_baseline import retrieve  # noqa: E402
from intelligence.schema import errors, thresholds  # noqa: E402
from intelligence.stats import binomial_upper_p, wilson_ci  # noqa: E402

FIX = ROOT / "contracts" / "fixtures"


def situation(key):
    return json.loads((FIX / "situations" / f"{key}.json").read_text(encoding="utf-8"))


@pytest.fixture(scope="module")
def cases():
    return usable(load_cases())


# ---------- case library ----------

def test_cases_valid_and_honestly_labelled(cases):
    assert len(cases) >= 20
    for c in cases:
        assert c["causal_claim"] is False
        if c["provenance"] == "authored":
            assert c["evidence_quality"] == "illustrative"
        if c["evidence_quality"] != "measured_observational":
            o = c["outcome"]
            assert o.get("before") is None and o.get("after") is None and o.get("observed_change") is None


def test_case_schema_rejects_authored_case_claiming_measured_numbers(cases):
    bad = copy.deepcopy(cases[0])
    bad["evidence_quality"] = "measured_observational"
    assert errors("case", bad), "authored case must not be labelled measured"
    bad2 = copy.deepcopy(cases[0])
    bad2["outcome"]["before"] = 0.03
    assert errors("case", bad2), "illustrative case must not carry before/after numbers"


# ---------- fixtures ----------

@pytest.mark.parametrize("name", sorted(p.name for p in (FIX / "bundles").glob("*.json")))
def test_bundle_fixtures_validate(name):
    bundle = json.loads((FIX / "bundles" / name).read_text(encoding="utf-8"))
    assert errors("bundle", bundle) == []


def test_situations_are_anomalous_with_sane_intervals():
    for k in "ABC":
        f = situation(k)["features"]
        lo, hi = f["dispute_rate_7d_ci95"]
        assert lo <= f["dispute_rate_7d"] <= hi
        assert f["anomaly"]["is_anomalous"] and f["anomaly"]["p_value"] < 0.01


# ---------- intervention intelligence ----------

def test_same_symptom_three_different_recommendations(cases):
    recs = {k: recommend(situation(k), retrieve(situation(k), cases, k=6)) for k in "ABC"}
    diagnoses = {r["diagnosis"] for r in recs.values()}
    assert len(diagnoses) == 3
    action_sets = {tuple(sorted((a["type"], a["title"]) for a in r["actions"])) for r in recs.values()}
    assert len(action_sets) == 3
    assert all(not r["abstain"] and r["grounding"] == "precedent" for r in recs.values())


def test_every_action_cites_supporting_cases(cases):
    for k in "ABC":
        r = recommend(situation(k), retrieve(situation(k), cases, k=6))
        shown = {p["case_id"] for p in r["precedents"]}
        for a in r["actions"]:
            assert a["supporting_cases"] and set(a["supporting_cases"]) <= shown


def test_baseline_ignores_signals_and_is_blocked(cases):
    recs = [recommend(situation(k), [], mode="no_precedent") for k in "ABC"]
    assert len({tuple(a["type"] for a in r["actions"]) for r in recs}) == 1
    for r in recs:
        assert r["grounding"] == "none" and r["precedents"] == []
        for d in gate_reference.decide(r):
            assert d["decision"] == "BLOCKED" and "insufficient_precedent" in d["rules_hit"]


def test_abstains_below_k_min(cases):
    sit = situation("A")
    weak = [dict(p, similarity=0.3) for p in retrieve(sit, cases, k=6)]
    r = recommend(sit, weak)
    assert r["abstain"] and r["actions"] == [] and r["abstain_reason"]
    assert gate_reference.decide(r) == []


def test_no_numeric_effect_without_measured_cases(cases):
    for k in "ABC":
        r = recommend(situation(k), retrieve(situation(k), cases, k=6))
        assert r["predicted_effect"] is None and r["counterfactual"] is None
        assert any("no numeric forecast" in n for n in r["playbook_notes"])


def test_effect_computed_only_from_measured_cases(cases):
    template = copy.deepcopy(cases[0])
    items = []
    for i, (before, after) in enumerate([(0.015, 0.006), (0.012, 0.005)]):
        c = copy.deepcopy(template)
        c.update(case_id=f"case_test_m{i}", provenance="public", evidence_quality="measured_observational")
        c["outcome"].update(before=before, after=after, observed_change=after - before, measurement_period_days=14)
        items.append({"case": c, "similarity": 0.9, "matched_on": [], "differs_on": []})
    effect, cf = effects.compute(items)
    assert effect["n_measured_cases"] == 2 and effect["source"] == "computed_from_measured_cases"
    assert effect["range"] == [0.005, 0.006] and cf["range"] == [0.012, 0.015]
    assert effect["causal_claim"] is False
    assert effects.compute(items[:1]) == (None, None)


def test_writer_can_only_change_prose(cases):
    sit = situation("A")
    prec = retrieve(sit, cases, k=6)
    plain = recommend(sit, prec)

    def evil_writer(rec):
        return {"diagnosis_detail": "Rewritten.", "rationales": {"act_1": "New words."},
                "actions": [{"type": "ACCEPT_CLAIM"}], "confidence": 0.99, "model": "test"}

    r = recommend(sit, prec, writer=evil_writer)
    assert r["diagnosis_detail"] == "Rewritten." and r["actions"][0]["rationale"] == "New words."
    assert [a["type"] for a in r["actions"]] == [a["type"] for a in plain["actions"]]
    assert r["confidence"] == plain["confidence"]
    assert r["generated_by"]["engine"] == "llm"


def test_deterministic(cases):
    sit = situation("B")
    assert recommend(sit, retrieve(sit, cases, k=6)) == recommend(sit, retrieve(sit, cases, k=6))


# ---------- reference gate ----------

def _money_rec(value):
    return {
        "actions": [{"action_id": "act_1", "type": "MAKE_OFFER", "params": {"amount": {"currency_code": "USD", "value": value}},
                     "rationale": "x", "supporting_cases": ["c1"]}],
        "precedents": [{"case_id": f"c{i}", "similarity": 0.9} for i in range(1, 4)],
        "abstain": False, "confidence": 0.8,
    }


def test_gate_money_tiers():
    cap = thresholds()["money"]["hard_cap"]
    under = gate_reference.decide(_money_rec(cap - 1))[0]
    over = gate_reference.decide(_money_rec(cap + 1))[0]
    assert under["decision"] == "NEEDS_APPROVAL" and "money_requires_approval" in under["rules_hit"]
    assert over["decision"] == "BLOCKED" and "amount_over_hard_cap" in over["rules_hit"]


def test_gate_disallowed_type_blocked():
    rec = _money_rec(10)
    d = gate_reference.decide(rec, allowlist=["FLAG_ONLY"])[0]
    assert d["decision"] == "BLOCKED" and d["rules_hit"] == ["type_not_allowed"]


# ---------- stats ----------

def test_wilson_and_binomial():
    lo, hi = wilson_ci(26, 1840)
    assert 0.0096 < lo < 0.0098 and 0.0205 < hi < 0.0208
    assert binomial_upper_p(0, 100, 0.01) == 1.0
    assert binomial_upper_p(26, 1840, 0.003) < 1e-6
    assert binomial_upper_p(6, 1840, 0.003) > 0.3

"""Retrieval regressions; no model download, network or financial execution."""
import copy
import json
import sys
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from intelligence.cases import load_cases, usable
from intelligence.consultant import recommend
from intelligence.narrative_similarity import lexical_scores
from intelligence.retrieve_baseline import retrieve as baseline
from intelligence.retrieve_hybrid import HybridRetriever, make_retriever, retrieve
from intelligence.schema import errors
from precedent.service import Service, plan
from precedent.paypal_adapter import PayPalAdapter
from precedent.store import Store


@pytest.fixture
def library():
    return usable(load_cases())


def situation(key="A"):
    return json.loads((ROOT / "contracts/fixtures/situations" / f"{key}.json").read_text())


def test_text_breaks_structured_ties_without_changing_similarity(library):
    a, b = copy.deepcopy(library[0]), copy.deepcopy(library[0])
    a.update(case_id="case_a", narrative="Warehouse backlog packing queue")
    b.update(case_id="case_b", narrative="Carrier parcel tracking missing")
    query = dict(situation(), narrative=b["narrative"])
    assert baseline(query, [a, b])[0]["case"]["case_id"] == "case_a"
    hybrid = retrieve(query, [a, b])
    assert hybrid[0]["case"]["case_id"] == "case_b"
    assert hybrid[0]["similarity"] == baseline(query, [b])[0]["similarity"]
    assert hybrid == retrieve(query, [b, a])
    assert set(hybrid[0]) == {"case", "similarity", "matched_on", "differs_on"}


def test_text_cannot_promote_sparse_case_or_displace_eligible_case(library):
    strong = baseline(situation(), library, k=1)[0]["case"]
    weak = copy.deepcopy(strong)
    weak.update(case_id="case_sparse", situation_features={}, narrative=situation()["narrative"])
    result = retrieve(situation(), [strong, weak], k=2)
    assert result[0]["case"]["case_id"] == strong["case_id"]
    assert result[1]["similarity"] == 0
    assert recommend(situation(), [result[1]])["abstain"]


def test_review_filter_empty_inputs_and_duplicate_ids(library):
    pending, rejected = copy.deepcopy(library[0]), copy.deepcopy(library[1])
    pending["review_status"], rejected["review_status"] = "pending", "rejected"
    assert retrieve(situation(), [pending, rejected]) == []
    assert retrieve(situation(), []) == []
    assert retrieve(situation(), library, k=0) == []
    assert retrieve(situation(), library, k=-1) == []
    with pytest.raises(ValueError, match="Duplicate"):
        retrieve(situation(), [library[0], library[0]])


def test_blank_narrative_retains_structured_order(library):
    query = dict(situation(), narrative="")
    assert retrieve(query, library) == baseline(query, library)


def test_measured_boost_does_not_apply_to_simulated_outcomes(library):
    a, b = copy.deepcopy(library[0]), copy.deepcopy(library[0])
    a["case_id"], b["case_id"] = "case_a", "case_b"
    b.update(provenance="public", evidence_quality="measured_observational")
    b["outcome"].update(before=0.03, after=0.01, measurement_period_days=14)
    assert retrieve(situation(), [a, b])[0]["case"]["case_id"] == "case_b"
    b.update(provenance="live_simulated", evidence_quality="simulated")
    b["outcome"].update(before=None, after=None)
    assert retrieve(situation(), [a, b])[0]["case"]["case_id"] == "case_a"


def test_lexical_scores_handle_empty_and_changed_corpus():
    assert lexical_scores("", ["parcel", ""]) == [0, 0]
    assert lexical_scores("the and", ["parcel"]) == [0]
    assert lexical_scores("parcel", []) == []
    first = lexical_scores("parcel", ["parcel", "backlog"])
    assert first[0] == pytest.approx(1) and first[1] == 0
    changed = lexical_scores("parcel", ["backlog", "parcel"])
    assert changed == first[::-1]


@pytest.mark.parametrize("scores", [[float("nan")], [1.1], [-0.1], []])
def test_invalid_embedding_scores_are_rejected(library, scores):
    with pytest.raises(ValueError, match="finite score"):
        HybridRetriever(lambda q, d: scores)(situation(), library[:1])


def test_semantic_model_is_local_cached_and_uses_narratives_only(monkeypatch, library):
    encoded = []
    class FakeModel:
        def __init__(self, path, **kwargs):
            assert path == "local-model"
            assert kwargs == {"local_files_only": True, "trust_remote_code": False}

        def encode(self, text, **kwargs):
            encoded.append(text)
            assert kwargs == {"normalize_embeddings": True}
            return [1.0, 0.0] if text == "missing parcel" else [0.0, 1.0]

    monkeypatch.setitem(sys.modules, "sentence_transformers", SimpleNamespace(SentenceTransformer=FakeModel))
    semantic = make_retriever({"PRECEDENT_RETRIEVER": "semantic", "PRECEDENT_EMBEDDING_MODEL": "local-model"})
    a, b = copy.deepcopy(library[0]), copy.deepcopy(library[0])
    a.update(case_id="case_a", narrative="backlog")
    b.update(case_id="case_b", narrative="missing parcel")
    query = dict(situation(), narrative="missing parcel")
    assert semantic(query, [a, b])[0]["case"]["case_id"] == "case_b"
    semantic(query, [a, b])
    assert encoded == ["missing parcel", "backlog"]


def test_configuration_is_explicit():
    assert make_retriever({}) is retrieve
    assert make_retriever({"PRECEDENT_RETRIEVER": "structured"}) is baseline
    with pytest.raises(ValueError, match="local model path"):
        make_retriever({"PRECEDENT_RETRIEVER": "semantic"})
    with pytest.raises(ValueError, match="Unknown"):
        make_retriever({"PRECEDENT_RETRIEVER": "typo"})


def test_full_hybrid_plan_keeps_three_demo_diagnoses_and_no_forecasts(library):
    diagnoses = set()
    for key in "ABC":
        rec, decisions = plan(situation(key), library, "with_precedent")
        assert not rec["abstain"]
        assert errors("recommendation", rec) == []
        assert rec["predicted_effect"] is None and rec["counterfactual"] is None
        assert any(d["decision"] == "NEEDS_APPROVAL" for d in decisions)
        diagnoses.add(rec["diagnosis"])
    assert len(diagnoses) == 3


def test_service_uses_selected_retriever_and_ablation_skips_it():
    calls = []
    def selected(query, cases, **kwargs):
        calls.append(query["situation_id"])
        return retrieve(query, cases, **kwargs)

    svc = Service(store=Store(":memory:"), adapter=PayPalAdapter(env={}), retriever=selected)
    assert errors("bundle", svc.bundle("A", "with_precedent")) == []
    svc.bundle("A", "with_precedent")
    svc.bundle("B", "no_precedent")
    assert calls == ["sit_demo_A"]

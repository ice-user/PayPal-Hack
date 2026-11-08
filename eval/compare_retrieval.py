"""Development-only retrieval comparison; prints JSON, never rewrites frozen results.

Run: python eval/compare_retrieval.py
Optional: --semantic-model PATH (requires requirements-embeddings.txt).
These known scenarios are regression checks, not a new held-out evaluation.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from intelligence.cases import load_cases, usable
from intelligence.consultant import DIAGNOSIS, FAMILY, recommend
from intelligence.gate_reference import decide
from intelligence.retrieve_baseline import retrieve as baseline
from intelligence.retrieve_hybrid import make_retriever, retrieve as hybrid
from precedent.orders import generate
from precedent.scenarios import ABLATION
from precedent.situation_builder import build


def compare(retrievers: dict) -> dict:
    cases = usable(load_cases())
    queries = [(s, build(generate(s), situation_id=f"sit_retrieval_{i}", label=s.name))
               for i, s in enumerate(ABLATION)]
    report = {"dataset": "development (previously used; not held out)", "modes": {}}
    for name, retriever in retrievers.items():
        hits = total = correct = acting_total = unsafe = abstentions = 0
        for scenario, situation in queries:
            expected = scenario.expected
            items = retriever(situation, cases, k=6)
            rec = recommend(situation, items)
            if expected["family"]:
                total += 1
                hits += any(FAMILY.get(p["case"]["intervention"]) == expected["family"] for p in items[:3])
            right_family = rec["diagnosis"] == DIAGNOSIS.get(expected["family"])
            if not expected["should_abstain"]:
                acting_total += 1
                correct += right_family and not rec["abstain"]
            would_act = any(d["tier"] != "PREPARE" and d["decision"] != "BLOCKED" for d in decide(rec))
            unsafe += would_act and (expected["should_abstain"] or not right_family)
            abstentions += rec["abstain"]
        report["modes"][name] = {
            "recall_at_3": {"hits": hits, "total": total},
            "correct_family_when_action_expected": {"hits": correct, "total": acting_total},
            "unsafe_actions": unsafe, "abstentions": abstentions, "scenarios": len(queries),
        }
    return report


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--semantic-model", help="Local SentenceTransformer model path")
    args = parser.parse_args()
    modes = {"structured": baseline, "hybrid_tfidf": hybrid}
    if args.semantic_model:
        modes["hybrid_semantic"] = make_retriever({
            "PRECEDENT_RETRIEVER": "semantic", "PRECEDENT_EMBEDDING_MODEL": args.semantic_model})
    print(json.dumps(compare(modes), indent=2))

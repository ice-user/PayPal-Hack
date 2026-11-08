"""Fuse structured and narrative ranks without changing policy similarity units."""
from __future__ import annotations

import math

from .cases import usable
from .narrative_similarity import SemanticScores, lexical_scores
from .retrieve_baseline import retrieve as structured_retrieve
from .schema import thresholds

RRF_OFFSET = 60
TEXT_WEIGHT = 0.1
MEASURED_BOOST = 1.02


def _ranks(values: list[float]) -> dict[float, int]:
    # Equal scores have equal ranks; case IDs only break the final fused tie.
    ranks = {}
    for rank, value in enumerate(sorted(values, reverse=True), 1):
        ranks.setdefault(value, rank)
    return ranks


class HybridRetriever:
    def __init__(self, narrative_scores=lexical_scores):
        self.narrative_scores = narrative_scores

    def __call__(self, situation: dict, cases: list[dict], *, k: int = 5,
                 merchant_size: str | None = "mid") -> list[dict]:
        if k <= 0:
            return []
        approved = usable(cases)
        if len({c["case_id"] for c in approved}) != len(approved):
            raise ValueError("Duplicate case IDs in retrieval library.")
        items = structured_retrieve(situation, approved, k=len(approved), merchant_size=merchant_size)
        if not items:
            return []
        text = self.narrative_scores(situation.get("narrative", ""),
                                     [p["case"].get("narrative", "") for p in items])
        if len(text) != len(items) or not all(math.isfinite(x) and 0 <= x <= 1 for x in text):
            raise ValueError("Narrative scorer must return one finite score in [0, 1] per case.")
        structured_ranks = _ranks([p["similarity"] for p in items])
        text_ranks = _ranks(text)
        has_text_signal = any(text)
        floor = thresholds()["similarity_min"]
        ranked = []
        for item, text_score in zip(items, text):
            fused = (1 - TEXT_WEIGHT) / (RRF_OFFSET + structured_ranks[item["similarity"]])
            if has_text_signal:
                fused += TEXT_WEIGHT / (RRF_OFFSET + text_ranks[text_score])
            case = item["case"]
            outcome = case.get("outcome", {})
            if (case.get("provenance") == "public"
                    and case.get("evidence_quality") == "measured_observational"
                    and outcome.get("before") is not None and outcome.get("after") is not None):
                fused *= MEASURED_BOOST
            # Text and outcome boosts cannot promote a weak case across the policy
            # floor, or crowd eligible cases out of the candidate set.
            ranked.append((item["similarity"] >= floor, fused, item))
        ranked.sort(key=lambda r: (-r[0], -r[1], -r[2]["similarity"], r[2]["case"]["case_id"]))
        return [item for _, _, item in ranked[:k]]


retrieve = HybridRetriever()


def make_retriever(env: dict):
    """Explicit modes keep the baseline reproducible and semantic setup visible."""
    mode = env.get("PRECEDENT_RETRIEVER", "hybrid")
    if mode == "structured":
        return structured_retrieve
    if mode == "hybrid":
        return retrieve
    if mode == "semantic":
        path = env.get("PRECEDENT_EMBEDDING_MODEL")
        if not path:
            raise ValueError("Semantic retrieval requires PRECEDENT_EMBEDDING_MODEL (a local model path).")
        return HybridRetriever(SemanticScores(path))
    raise ValueError(f"Unknown PRECEDENT_RETRIEVER mode: {mode!r}")

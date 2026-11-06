"""Baseline precedent retriever: weighted distance over normalised structured features.

This is a stand-in so the Consultant and the fixtures have real retrieval behind them.
Person B owns the production Retriever (hybrid: this structured score + narrative
embeddings, reciprocal-rank fusion, measured-outcome boost). Keep the output shape.
"""
from __future__ import annotations

# feature key -> (weight, human label)
FEATURES: dict[str, tuple[float, str]] = {
    "concentration_carrier": (2.0, "carrier concentration"),
    "disputed_orders_delivered_share": (2.0, "share of disputed orders delivered"),
    "ship_delay": (1.5, "fulfilment delay"),
    "carriers_elevated": (1.5, "number of carriers elevated"),
    "inr_share": (1.0, "item-not-received share"),
    "unauthorised_share": (1.0, "unauthorised share"),
    "snad_share": (1.0, "not-as-described share"),
    "concentration_sku": (1.0, "SKU concentration"),
    "trend_slope": (0.5, "trend"),
}
MATCH_TOL = 0.10
DIFFER_TOL = 0.25


def _clip(x: float) -> float:
    return max(0.0, min(1.0, x))


def situation_vector(situation: dict) -> dict[str, float]:
    f = situation["features"]
    mix = f.get("reason_mix", {})
    conc = f.get("concentration", {})
    v = {
        "concentration_carrier": conc.get("carrier"),
        "concentration_sku": conc.get("sku"),
        "disputed_orders_delivered_share": f.get("disputed_orders_delivered_share"),
        "ship_delay": None if f.get("ship_delay_hours_p50") is None else _clip(f["ship_delay_hours_p50"] / 72),
        "carriers_elevated": None if f.get("carriers_elevated") is None else _clip(f["carriers_elevated"] / 5),
        "inr_share": mix.get("ITEM_NOT_RECEIVED"),
        "unauthorised_share": mix.get("UNAUTHORISED"),
        "snad_share": mix.get("NOT_AS_DESCRIBED"),
        "trend_slope": f.get("trend_slope"),
    }
    return {k: float(x) for k, x in v.items() if x is not None}


def case_vector(case: dict) -> dict[str, float]:
    f = case["situation_features"]
    v = {
        "concentration_carrier": f.get("concentration_carrier"),
        "concentration_sku": f.get("concentration_sku"),
        "disputed_orders_delivered_share": f.get("disputed_orders_delivered_share"),
        "ship_delay": None if f.get("ship_delay_hours_p50") is None else _clip(f["ship_delay_hours_p50"] / 72),
        "carriers_elevated": None if f.get("carriers_elevated") is None else _clip(f["carriers_elevated"] / 5),
        "inr_share": f.get("inr_share"),
        "unauthorised_share": f.get("unauthorised_share"),
        "snad_share": f.get("snad_share"),
        "trend_slope": f.get("trend_slope"),
    }
    return {k: float(x) for k, x in v.items() if x is not None}


def score(sv: dict[str, float], cv: dict[str, float]) -> tuple[float, list[str], list[str]]:
    """Similarity in [0, 1] plus matched_on / differs_on feature labels."""
    total_w = sum(w for w, _ in FEATURES.values())
    shared = [k for k in FEATURES if k in sv and k in cv]
    if not shared:
        return 0.0, [], []
    w_shared = sum(FEATURES[k][0] for k in shared)
    wmean = sum(FEATURES[k][0] * abs(sv[k] - cv[k]) for k in shared) / w_shared
    coverage = w_shared / total_w
    sim = _clip(1 - 2 * wmean) * (0.5 + 0.5 * coverage)
    matched = [FEATURES[k][1] for k in shared if abs(sv[k] - cv[k]) <= MATCH_TOL]
    differs = [FEATURES[k][1] for k in shared if abs(sv[k] - cv[k]) >= DIFFER_TOL]
    return round(sim, 3), matched, differs


def retrieve(situation: dict, cases: list[dict], *, k: int = 5, merchant_size: str | None = "mid") -> list[dict]:
    """Top-k precedents, most similar first. Each item: case, similarity, matched_on, differs_on."""
    sv = situation_vector(situation)
    scored = []
    for case in cases:
        sim, matched, differs = score(sv, case_vector(case))
        size = case.get("context", {}).get("merchant_size")
        if merchant_size and size and size not in (merchant_size, "unknown"):
            differs = differs + [f"merchant size ({size} vs {merchant_size})"]
        scored.append({"case": case, "similarity": sim, "matched_on": matched, "differs_on": differs})
    scored.sort(key=lambda r: (-r["similarity"], r["case"]["case_id"]))
    return scored[:k]

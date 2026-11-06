"""Predicted effect and counterfactual, computed ONLY from measured cases.

Reference implementation of the rule in BRIEF.md decision 8 (Person B owns the
production version). The Consultant never writes these numbers.
"""
from __future__ import annotations

from .schema import thresholds


def compute(supporting: list[dict], *, horizon_days: int = 14) -> tuple[dict | None, dict | None]:
    """supporting: retrieval items (with 'case') for the chosen intervention.

    Returns (predicted_effect, counterfactual) or (None, None) when fewer than
    min_measured_cases_for_effect cases have measured before/after numbers.
    """
    need = thresholds()["min_measured_cases_for_effect"]
    measured = [
        r["case"] for r in supporting
        if r["case"]["evidence_quality"] == "measured_observational"
        and r["case"]["outcome"].get("before") is not None
        and r["case"]["outcome"].get("after") is not None
    ]
    if len(measured) < need:
        return None, None
    afters = sorted(c["outcome"]["after"] for c in measured)
    befores = sorted(c["outcome"]["before"] for c in measured)
    base = {"metric": "dispute_rate_7d", "horizon_days": horizon_days,
            "n_measured_cases": len(measured), "evidence_quality": "measured_observational",
            "causal_claim": False, "source": "computed_from_measured_cases"}
    effect = dict(base, range=[afters[0], afters[-1]])
    counterfactual = dict(base, range=[befores[0], befores[-1]])
    return effect, counterfactual

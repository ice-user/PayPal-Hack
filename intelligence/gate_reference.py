"""Reference Policy Gate used to build fixtures and to test the Consultant against.

Person B owns the production gate (with tenant allowlists, rate limits and the audit
log). This implements the same deterministic tier rules from docs/BRIEF.md decision 5
so both sides can check they agree.
"""
from __future__ import annotations

from .schema import thresholds, validate

TRIAGE_MIN_BACKERS = 2  # mirrors intelligence.triage.MIN_BACKERS


def _tier(action_type: str, th: dict) -> str:
    for tier, types in th["tiers"].items():
        if action_type in types:
            return tier
    return "UNKNOWN"


def decide(recommendation: dict, *, allowlist: list[str] | None = None) -> list[dict]:
    th = thresholds()
    money = th["money"]
    supported = [p for p in recommendation["precedents"] if p["similarity"] >= th["similarity_min"]]
    out = []
    for a in recommendation["actions"]:
        tier = _tier(a["type"], th)
        rules: list[str] = []
        decision = th["tier_default_decision"].get(tier, "BLOCKED")
        why: list[str] = []

        triage = bool(a.get("params", {}).get("triage_group"))
        if tier == "UNKNOWN" or (allowlist is not None and a["type"] not in allowlist):
            rules.append("type_not_allowed")
            decision, why = "BLOCKED", [f"{a['type']} is not an allowed action type."]
        elif recommendation["abstain"] and not triage:
            rules.append("consultant_abstained")
            decision, why = "BLOCKED", ["The Consultant abstained."]
        else:
            if tier != "PREPARE" and triage:
                # Dispute-level triage: backed by dispute-level cases, independent of the spike-level plan.
                backers = len(a.get("supporting_cases", []))
                if backers < TRIAGE_MIN_BACKERS:
                    rules.append("insufficient_precedent")
                    decision = "BLOCKED"
                    why.append(f"Needs at least {TRIAGE_MIN_BACKERS} agreeing dispute cases; has {backers}.")
            elif tier != "PREPARE":
                backing = [p for p in supported if p["case_id"] in a.get("supporting_cases", [])]
                if len(supported) < th["k_min"] or not backing:
                    rules.append("insufficient_precedent")
                    decision = "BLOCKED"
                    why.append(f"Needs at least {th['k_min']} similar precedents and at least one supporting this action.")
                if recommendation["confidence"] < th["confidence_min"]:
                    rules.append("confidence_below_floor")
                    decision = "BLOCKED"
                    why.append(f"Confidence {recommendation['confidence']} is below {th['confidence_min']}.")
            if tier == "MONEY":
                amount = float(a["params"].get("amount", {}).get("value", 0))
                if amount > money["hard_cap"]:
                    rules.append("amount_over_hard_cap")
                    decision = "BLOCKED"
                    why.append(f"{amount:.2f} {money['currency']} exceeds the hard cap of {money['hard_cap']}.")
                elif decision != "BLOCKED":
                    rules.append("money_requires_approval")
                    why.append(f"Moves {amount:.2f} {money['currency']}: explicit approval required.")
            if decision == "NEEDS_APPROVAL" and tier == "EXTERNAL":
                rules.append("external_action_requires_approval")
                why.append("Visible to buyers or PayPal: one-click approval required.")
            if decision == "AUTO":
                rules.append("prepare_only")
                why.append("Preparation only: nothing leaves the system.")

        d = {"action_id": a["action_id"], "decision": decision, "tier": tier if tier != "UNKNOWN" else "PREPARE",
             "rules_hit": rules, "explanation": " ".join(why)[:400]}
        validate("policy_decision", d)
        out.append(d)
    return out

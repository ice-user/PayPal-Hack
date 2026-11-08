"""The Consultant: turns a SituationRecord plus retrieved precedents into a Recommendation.

Design (see docs/BRIEF.md and docs/DESIGN.md):
- The decision is made by deterministic code: precedents vote for interventions,
  weighted by similarity and evidence quality. Actions come from a fixed enum and
  fixed templates; the Consultant never builds a PayPal call.
- An optional `writer` (an LLM) may only rewrite prose fields (diagnosis detail and
  action rationales). It cannot add actions, change amounts or write numbers that
  were not computed. Its output is validated like everything else.
- It abstains when fewer than k_min precedents clear the similarity threshold or
  when confidence is below the floor.
- It never writes predicted_effect or counterfactual: `effects.compute` does, from
  measured cases only.
- mode="no_precedent" is the ablation baseline: same situation, no retrieval.
"""
from __future__ import annotations

from collections import defaultdict
from typing import Callable

from . import effects
from .schema import thresholds, validate

QUALITY_WEIGHT = {
    "measured_observational": 1.0,
    "aggregate_disclosure": 0.8,
    "incomplete_report": 0.6,
    "illustrative": 0.5,
    "simulated": 0.4,
}
QUALITY_ORDER = list(QUALITY_WEIGHT)  # strongest first

FAMILY = {
    "delivery_confirmation_tracking": "carrier",
    "carrier_switch": "carrier",
    "fulfilment_workflow_fix": "fulfilment",
    "proactive_buyer_messaging": "fulfilment",
    "evidence_collection_response": "delivered",
    "partial_refund_offer": "delivered",
    "accept_and_refund": "delivered",
    "fraud_screening": "fraud",
    "listing_and_policy_clarity": "listing",
    "processor_compliance_controls": "compliance",
}

DIAGNOSIS = {
    "carrier": "Carrier-specific delivery or tracking failure",
    "fulfilment": "Fulfilment delay before hand-off to carriers",
    "delivered": "Disputes on orders with confirmed delivery",
    "fraud": "Unauthorised transactions (fraud pattern)",
    "listing": "Listing or descriptor mismatch",
    "compliance": "Processor or programme compliance issue",
}


# ---------- helpers ----------

def _pct(x: float | None) -> str:
    return "n/a" if x is None else f"{round(x * 100)}%"


def _facts(situation: dict) -> dict:
    f = situation["features"]
    conc = f.get("concentration", {})
    base = f.get("dispute_rate_30d_baseline") or 0
    ratio = (f["dispute_rate_7d"] / base) if base else None
    return {
        "carrier": conc.get("top_carrier", "the top carrier"),
        "sku": conc.get("top_sku", "the top SKU"),
        "carrier_share": conc.get("carrier"),
        "sku_share": conc.get("sku"),
        "carriers_elevated": f.get("carriers_elevated"),
        "delay_h": f.get("ship_delay_hours_p50"),
        "delivered_share": f.get("disputed_orders_delivered_share"),
        "open_disputes": f.get("open_disputes", 0),
        "avg_amount": f.get("avg_amount") or 0.0,
        "ratio": ratio,
        "inr_share": f.get("reason_mix", {}).get("ITEM_NOT_RECEIVED"),
        "dispute_ids": situation.get("paypal_dispute_ids", []),
    }


def _diagnosis_detail(family: str, x: dict) -> str:
    ratio = f"{x['ratio']:.1f}x" if x["ratio"] else "above"
    lead = (f"Disputes are {ratio} the 30-day baseline and {_pct(x['inr_share'])} are item-not-received. ")
    if family == "carrier":
        return lead + (f"{_pct(x['carrier_share'])} of disputes are on {x['carrier']}, only "
                       f"{x['carriers_elevated']} carrier is elevated, orders ship in about {x['delay_h']:.0f}h, "
                       f"and {_pct(x['delivered_share'])} of disputed orders show a delivery scan. "
                       "That points at the carrier, not the warehouse.")
    if family == "fulfilment":
        return lead + (f"Disputes are spread across {x['carriers_elevated']} carriers (top carrier "
                       f"{_pct(x['carrier_share'])}) and the median time to ship is {x['delay_h']:.0f}h. "
                       "Parcels are leaving late, so the problem is upstream of the carriers.")
    if family == "delivered":
        return lead + (f"{_pct(x['delivered_share'])} of disputed orders have a confirmed delivery scan and "
                       f"orders ship in about {x['delay_h']:.0f}h. The parcels arrived, so the useful response "
                       "is evidence, not a fulfilment fix.")
    return lead + "The pattern matches precedents outside the item-not-received playbook."


def _action_templates(intervention: str, x: dict, situation: dict) -> list[dict]:
    """Fixed templates per intervention. Types come from the enum only."""
    n_open = x["open_disputes"]
    ids = x["dispute_ids"]
    t = {
        "delivery_confirmation_tracking": [
            {"type": "PROVIDE_EVIDENCE",
             "title": f"File tracking evidence on open item-not-received disputes on {x['carrier']}",
             "params": {"evidence_type": "PROOF_OF_FULFILLMENT", "scope": "open_inr_disputes",
                        "filter": {"carrier": x["carrier"]}, "dispute_ids": ids,
                        "estimated_disputes": round(n_open * (x["carrier_share"] or 0))}},
            {"type": "FLAG_ONLY",
             "title": f"Require delivery confirmation on {x['carrier']} shipments",
             "params": {"note": f"Turn on signature or photo confirmation for {x['carrier']} until its scans recover."}},
        ],
        "carrier_switch": [
            {"type": "FLAG_ONLY",
             "title": f"Route new {x['sku']} orders away from {x['carrier']} for now",
             "params": {"note": f"Temporarily ship {x['sku']} with another carrier."}},
            {"type": "SEND_MESSAGE",
             "title": f"Tell buyers with parcels on {x['carrier']} what is happening",
             "params": {"audience": "buyers_with_open_orders_on_carrier", "filter": {"carrier": x["carrier"]},
                        "template_id": "carrier_delay_notice"}},
        ],
        "fulfilment_workflow_fix": [
            {"type": "FLAG_ONLY",
             "title": "Clear the unshipped backlog (orders waiting over 48h)",
             "params": {"note": "Prioritise the oldest unshipped orders and check pick-and-pack capacity."}},
            {"type": "SEND_MESSAGE",
             "title": "Send a ship-date update to buyers with late orders",
             "params": {"audience": "buyers_with_unshipped_orders_over_48h", "template_id": "ship_date_update"}},
        ],
        "proactive_buyer_messaging": [
            {"type": "SEND_MESSAGE",
             "title": "Send a ship-date update to buyers with late orders",
             "params": {"audience": "buyers_with_unshipped_orders_over_48h", "template_id": "ship_date_update"}},
        ],
        "evidence_collection_response": [
            {"type": "PROVIDE_EVIDENCE",
             "title": "File proof of delivery on disputes with a confirmed delivery scan",
             "params": {"evidence_type": "PROOF_OF_FULFILLMENT", "scope": "open_inr_disputes",
                        "filter": {"delivery_confirmed": True}, "dispute_ids": ids,
                        "estimated_disputes": round(n_open * (x["delivered_share"] or 0))}},
        ],
        "partial_refund_offer": [
            {"type": "MAKE_OFFER",
             "title": "Offer partial refunds on low-value disputes",
             "params": {"offer_type": "REFUND", "per_dispute_fraction": 0.3,
                        "dispute_count": min(n_open, 5),
                        "amount": {"currency_code": "USD",
                                   "value": round(min(n_open, 5) * x["avg_amount"] * 0.3, 2)}}},
        ],
        "accept_and_refund": [
            {"type": "ACCEPT_CLAIM",
             "title": "Accept low-value claims instead of contesting them",
             "params": {"dispute_count": min(n_open, 3),
                        "amount": {"currency_code": "USD", "value": round(min(n_open, 3) * x["avg_amount"], 2)}}},
        ],
        "fraud_screening": [
            {"type": "FLAG_ONLY", "title": "Tighten checkout fraud checks",
             "params": {"note": "Add velocity limits and review orders to forwarding addresses."}},
        ],
        "listing_and_policy_clarity": [
            {"type": "FLAG_ONLY", "title": "Correct the listing or billing descriptor",
             "params": {"note": "Fix the listing or statement name that buyers do not recognise."}},
        ],
        "processor_compliance_controls": [
            {"type": "FLAG_ONLY", "title": "Review processor compliance controls",
             "params": {"note": "Escalate to compliance review."}},
        ],
    }
    return [dict(a) for a in t.get(intervention, [])]


def _strongest(qualities: list[str]) -> str:
    for q in QUALITY_ORDER:
        if q in qualities:
            return q
    return "none"


def _precedent_view(item: dict) -> dict:
    c = item["case"]
    return {
        "case_id": c["case_id"],
        "title": c["title"],
        "similarity": item["similarity"],
        "matched_on": item["matched_on"],
        "differs_on": item["differs_on"],
        "intervention": c["intervention"],
        "outcome_summary": c["outcome"]["summary"],
        "measurement_period_days": c["outcome"].get("measurement_period_days"),
        "evidence_quality": c["evidence_quality"],
        "provenance": c["provenance"],
    }


# ---------- main entry ----------

def recommend(situation: dict, precedents: list[dict], *, mode: str = "with_precedent",
              writer: Callable[[dict], dict] | None = None, created_at: str | None = None) -> dict:
    """Return a schema-valid Recommendation.

    precedents: retrieval items, each {"case", "similarity", "matched_on", "differs_on"}.
    """
    th = thresholds()
    sid = situation["situation_id"]
    x = _facts(situation)
    rec_id = f"rec_{sid.removeprefix('sit_')}_{'wp' if mode == 'with_precedent' else 'np'}"

    anomaly = situation["features"]["anomaly"]
    if not anomaly["is_anomalous"]:
        # Applies in both modes: deciding whether there is anything to fix is not retrieval.
        why = ("the sample is too small to tell a real spike from noise"
               if anomaly.get("min_sample_met") is False else "the dispute rate is within normal variation")
        rec = {
            "recommendation_id": rec_id, "situation_id": sid, "mode": mode,
            "grounding": "precedent" if mode == "with_precedent" else "none",
            "diagnosis": "No actionable anomaly",
            "precedents": [_precedent_view(p) for p in precedents[:5]] if mode == "with_precedent" else [],
            "actions": [], "predicted_effect": None, "counterfactual": None, "playbook_notes": [],
            "confidence": 0.0, "evidence_quality": "none", "abstain": True,
            "abstain_reason": f"No action: {why} (binomial p = {anomaly['p_value']}).",
            "generated_by": {"engine": "rules", "version": "0.1.0"},
        }
    elif mode == "no_precedent":
        rec = _baseline(situation, x, rec_id)
    else:
        rec = _with_precedent(situation, precedents, x, rec_id, th)

    if created_at:
        rec["created_at"] = created_at
    if writer and not rec["abstain"]:
        rec = _apply_writer(rec, writer)
    validate("recommendation", rec)
    return rec


def _with_precedent(situation: dict, precedents: list[dict], x: dict, rec_id: str, th: dict) -> dict:
    eligible = [p for p in precedents if p["similarity"] >= th["similarity_min"]]
    shown = [_precedent_view(p) for p in precedents[:5]]
    base = {
        "recommendation_id": rec_id, "situation_id": situation["situation_id"],
        "mode": "with_precedent", "grounding": "precedent", "precedents": shown,
        "predicted_effect": None, "counterfactual": None,
        "generated_by": {"engine": "rules", "version": "0.1.0"},
    }

    if len(eligible) < th["k_min"]:
        return dict(base, diagnosis="Not enough similar precedents", actions=[], playbook_notes=[],
                    confidence=0.0, evidence_quality="none", abstain=True,
                    abstain_reason=(f"Only {len(eligible)} case(s) cleared the similarity threshold "
                                    f"{th['similarity_min']}; at least {th['k_min']} are required. "
                                    "No action is recommended."))

    votes: dict[str, float] = defaultdict(float)
    for p in eligible:
        votes[p["case"]["intervention"]] += p["similarity"] * QUALITY_WEIGHT[p["case"]["evidence_quality"]]
    ranked = sorted(votes.items(), key=lambda kv: (-kv[1], kv[0]))
    total = sum(votes.values())
    chosen = [ranked[0][0]]
    if len(ranked) > 1 and ranked[1][1] >= 0.5 * ranked[0][1]:
        chosen.append(ranked[1][0])

    supporting = [p for p in eligible if p["case"]["intervention"] in chosen]
    family = FAMILY[chosen[0]]

    actions, seen = [], set()
    for interv in chosen:
        backers = [p for p in supporting if p["case"]["intervention"] == interv]
        for tmpl in _action_templates(interv, x, situation):
            key = (tmpl["type"], tmpl["title"])
            if key in seen:
                continue
            seen.add(key)
            actions.append({
                "action_id": f"act_{len(actions) + 1}",
                "type": tmpl["type"],
                "title": tmpl["title"],
                "params": tmpl["params"],
                "rationale": (f"Followed in {len(backers)} similar case(s). "
                              f"Shared signals: {', '.join(backers[0]['matched_on'][:3]) or 'overall profile'}."),
                "supporting_cases": [p["case"]["case_id"] for p in backers],
            })
    actions = actions[:3]

    quality = _strongest([p["case"]["evidence_quality"] for p in supporting])
    avg_sim = sum(p["similarity"] for p in supporting) / len(supporting)
    # Agreement is measured at the diagnosis-family level: two carrier fixes agree with each other.
    share = sum(v for i, v in votes.items() if FAMILY[i] == family) / total
    confidence = round(min(0.95, avg_sim * share * (0.7 + 0.3 * QUALITY_WEIGHT.get(quality, 0.4))), 2)

    effect, counterfactual = effects.compute(supporting)
    notes = []
    for p in supporting[:3]:
        c = p["case"]
        if c["evidence_quality"] != "measured_observational":
            notes.append(f"{c['title']} ({c['provenance']}, {c['evidence_quality']}): {c['outcome']['summary']}")
    if effect is None:
        notes.append("No measured precedents match this pattern, so no numeric forecast is shown.")

    if confidence < th["confidence_min"]:
        return dict(base, diagnosis=DIAGNOSIS[family], actions=[], playbook_notes=notes,
                    confidence=confidence, evidence_quality=quality, abstain=True,
                    abstain_reason=(f"Confidence {confidence} is below the floor {th['confidence_min']}. "
                                    "Precedents disagree or match weakly."))

    return dict(base, diagnosis=DIAGNOSIS[family], diagnosis_detail=_diagnosis_detail(family, x),
                actions=actions, predicted_effect=effect, counterfactual=counterfactual,
                playbook_notes=notes, confidence=confidence, evidence_quality=quality,
                abstain=False, abstain_reason=None)


def _baseline(situation: dict, x: dict, rec_id: str) -> dict:
    """Ablation baseline: a generic answer to 'dispute spike' with no precedent lookup.
    Deliberately identical across situations: that is what the toggle demonstrates."""
    n_open = x["open_disputes"]
    actions = [
        {"action_id": "act_1", "type": "PROVIDE_EVIDENCE",
         "title": "File tracking evidence on all open item-not-received disputes",
         "params": {"evidence_type": "PROOF_OF_FULFILLMENT", "scope": "open_inr_disputes",
                    "dispute_ids": x["dispute_ids"], "estimated_disputes": n_open},
         "rationale": "Generic dispute playbook. No precedent consulted.", "supporting_cases": []},
        {"action_id": "act_2", "type": "SEND_MESSAGE",
         "title": "Send an apology message to every buyer with an open dispute",
         "params": {"audience": "buyers_with_open_disputes", "template_id": "generic_apology"},
         "rationale": "Generic dispute playbook. No precedent consulted.", "supporting_cases": []},
        {"action_id": "act_3", "type": "MAKE_OFFER",
         "title": "Offer a 20% partial refund on every open dispute",
         "params": {"offer_type": "REFUND", "per_dispute_fraction": 0.2, "dispute_count": n_open,
                    "amount": {"currency_code": "USD", "value": round(n_open * x["avg_amount"] * 0.2, 2)}},
         "rationale": "Generic dispute playbook. No precedent consulted.", "supporting_cases": []},
    ]
    return {
        "recommendation_id": rec_id, "situation_id": situation["situation_id"],
        "mode": "no_precedent", "grounding": "none",
        "diagnosis": "Spike in item-not-received disputes",
        "diagnosis_detail": "Generic reading of the symptom only. Concentration, fulfilment delay and delivery signals were not compared with any precedent.",
        "precedents": [], "actions": actions, "predicted_effect": None, "counterfactual": None,
        "playbook_notes": ["Ablation baseline: no precedents were retrieved, so nothing here is cited."],
        "confidence": 0.3, "evidence_quality": "none", "abstain": False, "abstain_reason": None,
        "generated_by": {"engine": "rules", "version": "0.1.0"},
    }


def _apply_writer(rec: dict, writer: Callable[[dict], dict]) -> dict:
    """Let an LLM rewrite prose only. Anything else it returns is ignored."""
    out = writer(rec) or {}
    if not out:
        return rec  # writer declined or was rejected: keep the rules prose and engine label
    new = dict(rec)
    if isinstance(out.get("diagnosis_detail"), str):
        new["diagnosis_detail"] = out["diagnosis_detail"][:1200]
    rationales = out.get("rationales") or {}
    new["actions"] = [
        dict(a, rationale=rationales[a["action_id"]][:600]) if isinstance(rationales.get(a["action_id"]), str) else a
        for a in rec["actions"]
    ]
    new["generated_by"] = {"engine": "llm", "model": str(out.get("model", "unknown")), "version": "0.1.0"}
    return new

"""Dispute-level triage: case-based reasoning on each open item-not-received dispute.

For every open dispute this builds a fingerprint from the parcel's real shipment state,
retrieves the closest dispute-level cases (dispute_cases/), and lets the cases whose
response was appropriate vote. Cases whose response backfired are returned as warnings.
Disputes that end up with the same response become one action, which the policy gate
then treats like any other action.

Also here: the spec's System A ("generic consultant"), which applies one generic remedy
to every dispute without looking at shipment state or deadlines.

See docs/TECHKART_TEST_ENV.md.
"""
from __future__ import annotations

import json
from collections import defaultdict
from datetime import date
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
CASES_PATH = ROOT / "dispute_cases" / "dispute_cases_v0.json"

SIM_MIN = 0.6          # a case must be at least this close to vote
K = 5                  # cases retrieved per dispute
MIN_BACKERS = 2        # distinct agreeing cases needed before a response may act externally
QUALITY_WEIGHT = 0.5   # every dispute case is authored and illustrative
MONEY_BATCH_CAP = 500.0  # matches the policy gate's hard cap; refunds are batched under it

PROOF_LEVEL = {"none": 0.0, "tracking": 0.34, "confirmation": 0.67, "gps": 1.0, "signature": 1.0}
WEIGHTS = {"status": 3.0, "proof": 2.0, "deadline_first": 2.0, "days_to_due": 0.5, "amount": 0.5}

RESPONSES = {
    # response: (action type, label, asserts delivery?)
    "evidence_delivery": ("PROVIDE_EVIDENCE", "File proof of delivery", True),
    "evidence_delivery_documented": ("PROVIDE_EVIDENCE", "File proof of delivery with GPS or signature records", True),
    "message_eta": ("SEND_MESSAGE", "Message buyers with the real delivery window", False),
    "evidence_in_transit": ("PROVIDE_EVIDENCE", "Respond before the deadline: shipped, still in transit", False),
    "refund_lost": ("ACCEPT_CLAIM", "Refund buyers whose parcels were lost", False),
    "gather_info": ("FLAG_ONLY", "Pull dispatch records and request carrier traces", False),
    "manual_review": ("FLAG_ONLY", "Review by hand: no close precedent", False),
}
STATE_LABEL = {"delivered": "Delivered", "in_transit": "In transit", "lost": "Lost (carrier confirmed)",
               "unknown": "No tracking"}


def load_dispute_cases(path: Path = CASES_PATH) -> list[dict]:
    return json.loads(path.read_text(encoding="utf-8"))["cases"]


def _days(a: str, b: date) -> int:
    return (date.fromisoformat(a) - b).days


def fingerprint(d: dict, today: date) -> dict:
    """Shipment facts for one dispute, in the same fields the dispute cases use."""
    deadline_first = 0
    if d["shipment_status"] == "in_transit" and d.get("expected_delivery"):
        # Waiting is only safe if the parcel is due at least a day before the deadline.
        deadline_first = int(_days(d["expected_delivery"], today) > _days(d["response_due"], today) - 1)
    return {"status": d["shipment_status"], "proof": d["proof"], "deadline_first": deadline_first,
            "days_to_due": max(0, _days(d["response_due"], today)), "amount": d["amount"]}


def similarity(a: dict, b: dict) -> float:
    gaps = {
        "status": 0.0 if a["status"] == b["status"] else 1.0,
        "proof": abs(PROOF_LEVEL[a["proof"]] - PROOF_LEVEL[b["proof"]]),
        "deadline_first": abs(a["deadline_first"] - b["deadline_first"]),
        "days_to_due": min(1.0, abs(a["days_to_due"] - b["days_to_due"]) / 14),
        "amount": min(1.0, abs(a["amount"] - b["amount"]) / 200),
    }
    wmean = sum(WEIGHTS[k] * g for k, g in gaps.items()) / sum(WEIGHTS.values())
    return round(max(0.0, min(1.0, 1 - 2 * wmean)), 3)


def decide(d: dict, cases: list[dict], today: date) -> dict:
    """Retrieve, vote and return the chosen response for one dispute."""
    fp = fingerprint(d, today)
    ranked = sorted(((similarity(fp, c["fingerprint"]), c) for c in cases), key=lambda t: (-t[0], t[1]["case_id"]))[:K]
    close = [(s, c) for s, c in ranked if s >= SIM_MIN]
    votes: dict[str, float] = defaultdict(float)
    backers: dict[str, list[str]] = defaultdict(list)
    for s, c in close:
        if c["appropriate"]:
            votes[c["response"]] += s * QUALITY_WEIGHT
            backers[c["response"]].append(c["case_id"])
    warnings = [c["case_id"] for s, c in close if not c["appropriate"]]
    if not votes:
        return {"fingerprint": fp, "response": "manual_review", "confidence": 0.0, "backers": [], "warnings": warnings,
                "top": [(s, c["case_id"]) for s, c in ranked]}
    response = max(votes, key=lambda r: (votes[r], r))
    total = sum(votes.values())
    return {"fingerprint": fp, "response": response, "confidence": round(votes[response] / total, 2),
            "backers": backers[response], "warnings": warnings, "top": [(s, c["case_id"]) for s, c in ranked]}


def _batches(disputes: list[dict], cap: float) -> list[list[dict]]:
    out, cur, tot = [], [], 0.0
    for d in sorted(disputes, key=lambda x: (x["response_due"], x["dispute_id"])):
        if cur and tot + d["amount"] > cap:
            out.append(cur)
            cur, tot = [], 0.0
        cur.append(d)
        tot += d["amount"]
    if cur:
        out.append(cur)
    return out


def _real_ids(group: list[dict], sandbox: dict[str, str]) -> list[str]:
    """Real PayPal sandbox dispute IDs mapped to this group's shipment state, if configured."""
    states = {d["shipment_status"] for d in group}
    return [sandbox[s] for s in sorted(states) if s in sandbox]


def triage(disputes: list[dict], today: date, *, cases: list[dict] | None = None, carrier: str = "the carrier",
           sandbox: dict[str, str] | None = None, start_index: int = 1) -> dict:
    """Decide every open item-not-received dispute and build grouped actions.

    Returns {"actions": [...], "groups": [...], "rows": [...], "precedents": [...]}.
    `sandbox` maps a shipment state to one real PayPal sandbox dispute ID to execute on.
    """
    cases = cases if cases is not None else load_dispute_cases()
    by_id = {c["case_id"]: c for c in cases}
    sandbox = sandbox or {}
    inr = [d for d in disputes if d["reason"] == "ITEM_NOT_RECEIVED"]
    decided = [(d, decide(d, cases, today)) for d in inr]

    grouped: dict[str, list[tuple[dict, dict]]] = defaultdict(list)
    for d, dec in decided:
        grouped[dec["response"]].append((d, dec))

    order = list(RESPONSES)
    actions, groups = [], []
    idx = start_index
    for response in sorted(grouped, key=order.index):
        members = grouped[response]
        group_disputes = [d for d, _ in members]
        backers = sorted({b for _, dec in members for b in dec["backers"]})
        warnings = sorted({w for _, dec in members for w in dec["warnings"]})
        atype, label, asserts = RESPONSES[response]
        external = atype != "FLAG_ONLY"
        chunks = _batches(group_disputes, MONEY_BATCH_CAP) if atype == "ACCEPT_CLAIM" else [group_disputes]
        group_action_ids = []
        for n, chunk in enumerate(chunks, 1):
            total = round(sum(d["amount"] for d in chunk), 2)
            due = min(d["response_due"] for d in chunk)
            batch = f" (batch {n} of {len(chunks)})" if len(chunks) > 1 else ""
            title = f"{label}: {len(chunk)} dispute{'s' if len(chunk) != 1 else ''}{batch}"
            params = {
                "triage_group": response, "response": response, "dispute_count": len(chunk),
                "synthetic_dispute_ids": [d["dispute_id"] for d in chunk],
                "dispute_ids": _real_ids(chunk, sandbox) if external else [],
                "earliest_due": due, "asserts_delivery": asserts, "total_value": total,
            }
            if response.startswith("evidence_"):
                params["evidence_type"] = "PROOF_OF_FULFILLMENT"
                params["include"] = (["carrier", "tracking_number", "delivery_confirmation"] +
                                     (["gps_or_signature_record"] if response == "evidence_delivery_documented" else [])
                                     if response != "evidence_in_transit" else
                                     ["carrier", "tracking_number", "ship_date", "agreed_delivery_window"])
            if response == "message_eta":
                params["template_id"] = "delivery_window_update"
            if atype == "ACCEPT_CLAIM":
                params["amount"] = {"currency_code": "USD", "value": total}
                params["note"] = f"Also file carrier claims with {carrier} for these parcels."
            why = {
                "evidence_delivery": "Delivery is confirmed, so file the confirmation itself, not just a tracking number.",
                "evidence_delivery_documented": "Delivery is confirmed and documented; include the GPS or signature record.",
                "message_eta": "Parcels are moving and due before the response deadline: tell buyers the real window, re-check before the deadline.",
                "evidence_in_transit": "The deadline comes before delivery: respond now with shipment proof and the agreed window, without claiming delivery.",
                "refund_lost": "The carrier confirmed these parcels lost: resolve with the buyer instead of contesting.",
                "gather_info": "No tracking on file: check dispatch records and ask the carrier for a trace before acting.",
                "manual_review": "No dispute case is close enough to follow.",
            }[response]
            rationale = f"{why} Followed in {len(backers)} similar dispute case(s)."
            if warnings:
                rationale += f" Avoid what backfired in {len(warnings)} case(s), e.g. \"{by_id[warnings[0]]['title']}\"."
            actions.append({"action_id": f"act_{idx}", "type": atype, "title": title[:120], "params": params,
                            "rationale": rationale[:600], "supporting_cases": backers})
            group_action_ids.append(f"act_{idx}")
            idx += 1
        groups.append({
            "response": response, "label": label,
            "states": sorted({STATE_LABEL[d["shipment_status"]] for d in group_disputes}),
            "count": len(group_disputes), "total_value": round(sum(d["amount"] for d in group_disputes), 2),
            "earliest_due": min(d["response_due"] for d in group_disputes),
            "action_ids": group_action_ids, "cites": backers, "warnings": warnings,
            "confidence": round(sum(dec["confidence"] for _, dec in members) / len(members), 2),
        })

    rows = [{"dispute_id": d["dispute_id"], "order_id": d["order_id"], "carrier": d["carrier"], "sku": d["sku"],
             "amount": d["amount"], "status": d["shipment_status"], "proof": d["proof"],
             "expected_delivery": d.get("expected_delivery"), "response_due": d["response_due"],
             "response": dec["response"]} for d, dec in sorted(decided, key=lambda t: t[0]["response_due"])]
    used = sorted({c for g in groups for c in g["cites"] + g["warnings"]})
    precedents = [{"case_id": c, "title": by_id[c]["title"], "response": by_id[c]["response"],
                   "appropriate": by_id[c]["appropriate"], "outcome": by_id[c]["outcome"]} for c in used]
    return {"actions": actions, "groups": groups, "rows": rows, "precedents": precedents,
            "untriaged": len(disputes) - len(inr)}


# ---------- System A: the spec's generic consultant ----------

def generic_plan(disputes: list[dict]) -> dict[str, str]:
    """One generic remedy per dispute: submit tracking where there is any, offer a refund
    where there is none. Ignores shipment state, proof level and deadlines (spec section 4)."""
    return {d["dispute_id"]: ("generic_tracking" if d["proof"] != "none" else "generic_refund")
            for d in disputes if d["reason"] == "ITEM_NOT_RECEIVED"}


def generic_triage(disputes: list[dict], *, start_index: int = 1) -> dict:
    """System A as actions, for the dashboard's 'Without precedent' view. It cites no cases,
    so the policy gate blocks its external actions, exactly as for the situation level."""
    plan = generic_plan(disputes)
    inr = [d for d in disputes if d["reason"] == "ITEM_NOT_RECEIVED"]
    tracked = [d for d in inr if plan[d["dispute_id"]] == "generic_tracking"]
    untracked = [d for d in inr if plan[d["dispute_id"]] == "generic_refund"]
    actions, groups, idx = [], [], start_index
    for response, members, atype, label in (
            ("generic_tracking", tracked, "PROVIDE_EVIDENCE", "Submit tracking numbers as proof of fulfilment"),
            ("generic_refund", untracked, "MAKE_OFFER", "Offer refunds where there is no tracking")):
        if not members:
            continue
        total = round(sum(d["amount"] for d in members), 2)
        params = {"triage_group": response, "response": response, "dispute_count": len(members),
                  "synthetic_dispute_ids": [d["dispute_id"] for d in members], "dispute_ids": [],
                  "earliest_due": min(d["response_due"] for d in members), "asserts_delivery": response == "generic_tracking",
                  "total_value": total}
        if atype == "MAKE_OFFER":
            params.update(amount={"currency_code": "USD", "value": total}, offer_type="REFUND")
        else:
            params["evidence_type"] = "PROOF_OF_FULFILLMENT"
        actions.append({"action_id": f"act_{idx}", "type": atype, "title": f"{label}: {len(members)} disputes",
                        "params": params, "supporting_cases": [],
                        "rationale": "Generic advice applied to every dispute alike. Shipment state and deadlines are not checked."})
        groups.append({"response": response, "label": label, "states": sorted({STATE_LABEL[d["shipment_status"]] for d in members}),
                       "count": len(members), "total_value": total, "earliest_due": params["earliest_due"],
                       "action_ids": [f"act_{idx}"], "cites": [], "warnings": [], "confidence": 0.0})
        idx += 1
    rows = [{"dispute_id": d["dispute_id"], "order_id": d["order_id"], "carrier": d["carrier"], "sku": d["sku"],
             "amount": d["amount"], "status": d["shipment_status"], "proof": d["proof"],
             "expected_delivery": d.get("expected_delivery"), "response_due": d["response_due"],
             "response": plan[d["dispute_id"]]} for d in sorted(inr, key=lambda x: x["response_due"])]
    return {"actions": actions, "groups": groups, "rows": rows, "precedents": [], "untriaged": len(disputes) - len(inr)}

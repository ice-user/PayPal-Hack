"""Score System A (generic consultant) and System B (Precedent) on the TechKart test set.

Run:  python eval/run_techkart.py            # pre-registered TK_TEST
      python eval/run_techkart.py demo       # the demo merchant only (not a result)

Metrics follow the spec (docs/TECHKART_TEST_ENV.md). Every dispute's correct path comes
from the generator's ground truth: its true shipment state, and whether the response
deadline falls before expected delivery. Results: eval/results/techkart/.
"""
from __future__ import annotations

import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "backend")]

from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.gate_reference import decide as gate  # noqa: E402
from intelligence.retrieve_hybrid import retrieve  # noqa: E402
from intelligence.consultant import recommend, DIAGNOSIS  # noqa: E402
from intelligence.triage import RESPONSES, fingerprint, generic_plan, load_dispute_cases, triage  # noqa: E402
from precedent.situation_builder import build  # noqa: E402
from precedent.techkart import TECHKART, TK_TEST, generate  # noqa: E402

OUT = ROOT / "eval" / "results" / "techkart"
FAMILY_OF = {v: k for k, v in DIAGNOSIS.items()}

# What each response does, for scoring. asserts: claims the parcel was delivered.
# contests: files evidence against the buyer. external: visible to the buyer or PayPal.
EFFECT = {
    "evidence_delivery": {"asserts": True, "contests": True, "external": True, "now": True},
    "evidence_delivery_documented": {"asserts": True, "contests": True, "external": True, "now": True, "documented": True},
    "message_eta": {"asserts": False, "contests": False, "external": True, "now": False},
    "evidence_in_transit": {"asserts": False, "contests": True, "external": True, "now": True},
    "refund_lost": {"asserts": False, "contests": False, "external": True, "now": True, "refund": True},
    "gather_info": {"asserts": False, "contests": False, "external": False, "now": False},
    "manual_review": {"asserts": False, "contests": False, "external": False, "now": False},
    # System A
    "generic_tracking": {"asserts": True, "contests": True, "external": True, "now": True},
    "generic_refund": {"asserts": False, "contests": False, "external": True, "now": True, "refund": True},
}


def expected_path(d: dict, today) -> str:
    st = d["true_state"]
    if st == "delivered_confirmation":
        return "evidence_delivery"
    if st == "delivered_documented":
        return "evidence_delivery_documented"
    if st == "lost":
        return "refund_lost"
    if st == "unknown":
        return "gather_info"
    return "evidence_in_transit" if fingerprint(d, today)["deadline_first"] else "message_eta"


def state_appropriate(d: dict, response: str) -> bool:
    """Does the response fit the parcel's true state, even if it is not the exact best path?"""
    e = EFFECT[response]
    st = d["true_state"]
    if st.startswith("delivered"):
        return e["contests"]                       # contesting a delivered parcel is legitimate
    if st == "in_transit":
        return not e["asserts"] and not e.get("refund")
    if st == "lost":
        return bool(e.get("refund"))
    return not e["external"]                       # unknown: no external action before checking


def score(disputes: list[dict], responses: dict[str, str], today) -> dict:
    c = Counter()
    for d in disputes:
        r = responses[d["dispute_id"]]
        e = EFFECT[r]
        exp = expected_path(d, today)
        st = d["true_state"]
        c["n"] += 1
        c["valid"] += r == exp
        c["state_ok"] += state_appropriate(d, r)
        delivered = st.startswith("delivered")
        if (e["asserts"] and not delivered) or (st == "lost" and e["contests"]):
            c["unsupported"] += 1
        if st == "delivered_documented":
            c["doc_n"] += 1
            c["doc_ok"] += bool(e.get("documented"))
        if exp == "evidence_in_transit":
            c["deadline_n"] += 1
            c["deadline_ok"] += e["now"] and not e["asserts"]
            c["deadline_missed"] += not e["now"]
        if st == "unknown":
            c["unknown_n"] += 1
            c["abstain_ok"] += not e["external"]
    return dict(c)


def run(scenarios) -> dict:
    cases = usable(load_cases())
    dcases = load_dispute_cases()
    runs = []
    for s in scenarios:
        orders, disputes = generate(s)
        situation = build(orders, situation_id=f"sit_tk_{s.name.split(':')[0].replace(' ', '_')}", label=s.name)
        inr = [d for d in disputes if d["reason"] == "ITEM_NOT_RECEIVED"]
        out = {"scenario": s.name, "disputes": len(inr), "truth": s.expected}
        for system in ("A", "B"):
            mode = "with_precedent" if system == "B" else "no_precedent"
            precedents = retrieve(situation, cases, k=6) if system == "B" else []
            rec = recommend(situation, precedents, mode=mode, created_at=s.end.isoformat() + "T09:00:00Z")
            family = None if rec["abstain"] else FAMILY_OF.get(rec["diagnosis"])
            if system == "B":
                t = triage(disputes, s.end, cases=dcases, carrier=s.target_carrier, start_index=len(rec["actions"]) + 1)
                responses = {r["dispute_id"]: r["response"] for r in t["rows"]}
                rec = dict(rec, actions=rec["actions"] + t["actions"])
                decisions = gate(rec)
                tri = [x for x in decisions if any(a["action_id"] == x["action_id"] and a["params"].get("triage_group")
                                                   for a in rec["actions"])]
                gate_counts = dict(Counter(x["decision"] for x in tri))
                over_cap = sum(1 for a in rec["actions"] if a["type"] == "ACCEPT_CLAIM"
                               and a["params"]["amount"]["value"] > 500)
            else:
                responses = generic_plan(disputes)
                gate_counts, over_cap = {}, 0
            out[system] = {"abstain": rec["abstain"], "family": family, "confidence": rec["confidence"],
                           "scores": score(inr, responses, s.end), "gate": gate_counts, "over_cap": over_cap,
                           "responses": dict(Counter(responses.values()))}
        runs.append(out)
    return {"runs": runs}


def summarise(result: dict) -> str:
    tot = {"A": Counter(), "B": Counter()}
    sit = defaultdict(Counter)
    for r in result["runs"]:
        for sysname in ("A", "B"):
            tot[sysname].update(r[sysname]["scores"])
            t = r["truth"]
            x = r[sysname]
            if t["should_abstain"]:
                sit[sysname]["quiet_n"] += 1
                sit[sysname]["quiet_ok"] += x["abstain"]
            else:
                sit[sysname]["spike_n"] += 1
                sit[sysname]["spike_ok"] += (not x["abstain"]) and x["family"] == t["family"]

    def pct(a, b):
        return f"{a}/{b} ({100 * a / b:.0f}%)" if b else "n/a"

    rows = [
        ("Recommendation validity (exact spec path)", "valid", "n"),
        ("Fits the parcel's true state", "state_ok", "n"),
        ("Evidence completeness (GPS or signature included)", "doc_ok", "doc_n"),
        ("Deadline compliance (responds before the deadline without claiming delivery)", "deadline_ok", "deadline_n"),
        ("Appropriate abstention (no tracking: no external action)", "abstain_ok", "unknown_n"),
    ]
    lines = ["# TechKart evaluation: System A (generic) vs System B (Precedent)", "",
             f"Scenarios: {len(result['runs'])}. Open item-not-received disputes scored: {tot['B']['n']}.", "",
             "| Metric | System A, generic | System B, Precedent |", "|---|---|---|"]
    for label, num, den in rows:
        lines.append(f"| {label} | {pct(tot['A'][num], tot['A'][den])} | {pct(tot['B'][num], tot['B'][den])} |")
    lines.append(f"| Unsupported claims (lower is better) | {pct(tot['A']['unsupported'], tot['A']['n'])} | "
                 f"{pct(tot['B']['unsupported'], tot['B']['n'])} |")
    lines.append(f"| Missed a deadline by waiting (lower is better) | {pct(tot['A']['deadline_missed'], tot['A']['deadline_n'])} | "
                 f"{pct(tot['B']['deadline_missed'], tot['B']['deadline_n'])} |")
    lines.append(f"| Spike scenarios: right cause | {pct(sit['A']['spike_ok'], sit['A']['spike_n'])} | "
                 f"{pct(sit['B']['spike_ok'], sit['B']['spike_n'])} |")
    lines.append(f"| Quiet scenarios: plan abstains | {pct(sit['A']['quiet_ok'], sit['A']['quiet_n'])} | "
                 f"{pct(sit['B']['quiet_ok'], sit['B']['quiet_n'])} |")
    gate_tot = Counter()
    for r in result["runs"]:
        gate_tot.update(r["B"]["gate"])
    over = sum(r["B"]["over_cap"] for r in result["runs"])
    lines += ["", f"System B triage actions through the policy gate: {dict(gate_tot)}. Refund actions over the $500 cap: {over}.",
              "", "## Per scenario", "",
              "| Scenario | Disputes | A valid | B valid | A unsupported | B unsupported | B plan |", "|---|---|---|---|---|---|---|"]
    for r in result["runs"]:
        a, b = r["A"]["scores"], r["B"]["scores"]
        plan = "abstains" if r["B"]["abstain"] else (r["B"]["family"] or "?")
        lines.append(f"| {r['scenario']} | {r['disputes']} | {a.get('valid', 0)} | {b.get('valid', 0)} | "
                     f"{a.get('unsupported', 0)} | {b.get('unsupported', 0)} | {plan} |")
    lines += ["", "## Reading this", "",
              "- System A is the spec's generic consultant, scripted: it submits tracking on every dispute that has it "
              "and offers refunds where there is none. It is not an LLM; a Claude baseline would be a stronger test.",
              "- The same team wrote the dispute cases, the decision paths and this test set, so agreement partly "
              "reflects internal consistency. This shows the mechanism works as designed, not real-world win rates.",
              "- Situation-level rows use the existing Consultant; quiet scenarios have no spike, but their open "
              "disputes are still triaged.",
              "- API execution success is measured separately on the PayPal sandbox."]
    return "\n".join(lines) + "\n"


def main() -> None:
    which = sys.argv[1] if len(sys.argv) > 1 else "test"
    scenarios = [TECHKART] if which == "demo" else TK_TEST
    result = run(scenarios)
    text = summarise(result)
    print(text)
    if which == "test":
        OUT.mkdir(parents=True, exist_ok=True)
        (OUT / "runs.json").write_text(json.dumps(result, indent=2), encoding="utf-8", newline="\n")
        (OUT / "summary.md").write_text(text, encoding="utf-8", newline="\n")
        print(f"wrote {OUT}")


if __name__ == "__main__":
    main()

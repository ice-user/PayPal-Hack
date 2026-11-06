"""Precedent ablation: the same Consultant with and without case retrieval.

For each ablation scenario (backend/precedent/scenarios.py, planted ground truth):
  1. generate the synthetic order feed and build the SituationRecord
  2. run System A (no_precedent) and System B (with_precedent), then the reference gate
  3. score automatic sanity checks against ground truth
  4. run a held-out-family check: remove every case of the true family and see whether
     System B abstains (safe) or confidently picks the wrong fix (unsafe)
  5. write a blind score sheet for two human raters

The automatic checks are a sanity layer, not the human rubric (eval/RUBRIC.md).
Caveat: the authored cases were written by the same team that planted the scenarios,
so agreement here partly measures internal consistency, not real-world efficacy.

Run:  python eval/run_ablation.py
"""
from __future__ import annotations

import csv
import json
import random
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from intelligence import gate_reference  # noqa: E402
from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.consultant import DIAGNOSIS, FAMILY, recommend  # noqa: E402
from intelligence.retrieve_baseline import retrieve  # noqa: E402
from precedent.orders import generate  # noqa: E402
from precedent.scenarios import ABLATION  # noqa: E402
from precedent.situation_builder import build  # noqa: E402

OUT = ROOT / "eval" / "results"
DIAG_TO_FAMILY = {v: k for k, v in DIAGNOSIS.items()}


def family_of(rec: dict) -> str | None:
    if rec["abstain"]:
        return None
    return DIAG_TO_FAMILY.get(rec["diagnosis"], "generic")


def can_act(decisions: list[dict]) -> bool:
    """True if at least one external or money action would get past the gate."""
    return any(d["decision"] != "BLOCKED" and d["tier"] != "PREPARE" for d in decisions)


def plan_text(rec: dict, *, with_citations: bool) -> str:
    if rec["abstain"]:
        return f"ABSTAIN: {rec['abstain_reason']}"
    lines = [f"Diagnosis: {rec['diagnosis']}"]
    for a in rec["actions"]:
        line = f"- [{a['type']}] {a.get('title', '')}"
        if with_citations and a["supporting_cases"]:
            line += f" (cites {', '.join(a['supporting_cases'])})"
        lines.append(line)
    return "\n".join(lines)


def run() -> dict:
    cases = usable(load_cases())
    rows = []
    for i, s in enumerate(ABLATION, start=1):
        situation = build(generate(s), situation_id=f"sit_abl_{i:02d}", label=s.name)
        prec = retrieve(situation, cases, k=6)
        exp = s.expected
        row = {"id": f"S{i:02d}", "scenario": s.name, "kind": s.kind, "expected": exp,
               "narrative": situation["narrative"], "features": situation["features"], "systems": {},
               "top3": [(p["case"]["case_id"], p["similarity"]) for p in prec[:3]]}
        if exp["family"]:
            row["recall_at_3"] = any(FAMILY.get(p["case"]["intervention"]) == exp["family"] for p in prec[:3])
        for mode, key in (("no_precedent", "A"), ("with_precedent", "B")):
            rec = recommend(situation, prec, mode=mode)
            dec = gate_reference.decide(rec)
            fam = family_of(rec)
            row["systems"][key] = {
                "mode": mode, "recommendation": rec, "decisions": [d["decision"] for d in dec],
                "family": fam,
                "family_correct": (fam == exp["family"]) if not exp["should_abstain"] else None,
                "abstained": rec["abstain"],
                "abstain_correct": rec["abstain"] == exp["should_abstain"],
                "would_act": can_act(dec),
                "unsafe_act": can_act(dec) and (exp["should_abstain"] or fam != exp["family"]),
                "all_actions_cited": all(a["supporting_cases"] for a in rec["actions"]),
                "numeric_effect_shown": rec["predicted_effect"] is not None,
            }
        # held-out family: does System B fail safe when its playbook for this cause is missing?
        if exp["family"] and not exp["should_abstain"]:
            held = [c for c in cases if FAMILY.get(c["intervention"]) != exp["family"]]
            rec_h = recommend(situation, retrieve(situation, held, k=6), mode="with_precedent")
            fam_h = family_of(rec_h)
            row["held_out_family"] = {"abstained": rec_h["abstain"], "family": fam_h,
                                      "unsafe_act": can_act(gate_reference.decide(rec_h)) and fam_h != exp["family"],
                                      "confidence": rec_h["confidence"]}
        rows.append(row)
    return {"cases_in_library": len(cases), "rows": rows}


def summarise(result: dict) -> str:
    rows = result["rows"]
    act_rows = [r for r in rows if not r["expected"]["should_abstain"]]
    abst_rows = [r for r in rows if r["expected"]["should_abstain"]]
    held = [r["held_out_family"] for r in rows if "held_out_family" in r]

    def pct(n, d):
        return f"{n}/{d} ({(100 * n / d):.0f}%)" if d else "n/a"

    lines = ["# Ablation results (automatic sanity checks)", "",
             f"Scenarios: {len(rows)} ({len(act_rows)} where acting is right, {len(abst_rows)} where abstaining is right). "
             f"Case library: {result['cases_in_library']} approved cases (authored and public; none measured).", "",
             "| Check | System A: no precedent | System B: with precedent |", "|---|---|---|"]
    for label, fn, base in [
        ("Right diagnosis family (when acting is right)", lambda s: s["family_correct"], act_rows),
        ("Abstained correctly (all scenarios)", lambda s: s["abstain_correct"], rows),
        ("Unsafe: an action would pass the gate when it should not", lambda s: s["unsafe_act"], rows),
        ("Would act at all (an action passes the gate)", lambda s: s["would_act"], rows),
        ("Every action cites a case (an abstention counts as yes)", lambda s: s["all_actions_cited"], rows),
        ("Numeric effect shown (should be 0: no measured cases)", lambda s: s["numeric_effect_shown"], rows),
    ]:
        a = sum(bool(fn(r["systems"]["A"])) for r in base)
        b = sum(bool(fn(r["systems"]["B"])) for r in base)
        lines.append(f"| {label} | {pct(a, len(base))} | {pct(b, len(base))} |")
    r3 = [r["recall_at_3"] for r in rows if "recall_at_3" in r]
    lines += ["", f"Retriever Recall@3 (a case of the true cause in the top 3): {pct(sum(r3), len(r3))}"]
    lines += ["", "## Held-out family (System B with the true cause's cases removed)", "",
              f"- Abstained: {pct(sum(h['abstained'] for h in held), len(held))}",
              f"- Unsafe (a wrong-cause action would pass the gate): {pct(sum(h['unsafe_act'] for h in held), len(held))}",
              "- A wrong family whose actions are all prepare-only (for example a fraud flag) is not counted as unsafe: "
              "nothing leaves the system without a human.",
              "", "## Per scenario", "",
              "| ID | Scenario | Expected | A: family / abstain | B: family / abstain / conf | Held-out B |", "|---|---|---|---|---|---|"]
    for r in rows:
        e = r["expected"]
        exp = "abstain" if e["should_abstain"] else e["family"]
        A, B = r["systems"]["A"], r["systems"]["B"]
        ho = r.get("held_out_family")
        ho_txt = "n/a" if not ho else ("abstain" if ho["abstained"] else f"{ho['family']} ({ho['confidence']})")
        lines.append(f"| {r['id']} | {r['scenario']} | {exp} | {A['family'] or 'abstain'} | "
                     f"{B['family'] or 'abstain'} / {B['recommendation']['confidence']} | {ho_txt} |")
    lines += ["", "## Caveats", "",
              "- Scenarios and authored cases come from the same team, so System B's accuracy partly reflects "
              "internal consistency. The held-out-family check is the more honest signal: it shows what happens "
              "when the library does not contain the answer.",
              "- System A is a rules baseline standing in for 'the same Consultant without retrieval'. "
              "An LLM baseline is a planned follow-up.",
              "- Human scores on the rubric (eval/RUBRIC.md) are the primary result; this table is a sanity layer."]
    return "\n".join(lines) + "\n"


def score_sheet(result: dict) -> None:
    """Blind sheet: plans shown as Plan 1 / Plan 2 in random order; key kept separately."""
    rng = random.Random(2026)
    sheet, key = [], []
    for r in result["rows"]:
        order = ["A", "B"]
        rng.shuffle(order)
        for slot, system in enumerate(order, start=1):
            rec = r["systems"][system]["recommendation"]
            item = f"{r['id']}-P{slot}"
            sheet.append({
                "item": item, "situation": r["narrative"],
                "plan_pass1_no_citations": plan_text(rec, with_citations=False),
                "plan_pass2_with_citations": plan_text(rec, with_citations=True),
                "appropriate_intervention_0to2": "", "grounded_in_cited_evidence_0to2": "",
                "unsupported_claims_count": "", "abstained_when_it_should_YN_NA": "",
                "rater": "", "notes": "",
            })
            key.append({"item": item, "system": system, "mode": r["systems"][system]["mode"]})
    with open(OUT / "score_sheet.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=list(sheet[0]))
        w.writeheader()
        w.writerows(sheet)
    (OUT / "score_sheet_KEY_do_not_open_before_rating.json").write_text(json.dumps(key, indent=2), encoding="utf-8")


def main() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    result = run()
    (OUT / "ablation_runs.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    summary = summarise(result)
    (OUT / "summary.md").write_text(summary, encoding="utf-8")
    score_sheet(result)
    print(summary)


if __name__ == "__main__":
    main()

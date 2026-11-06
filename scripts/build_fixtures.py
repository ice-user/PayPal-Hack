"""Build /contracts/fixtures for the three demo situations.

Pipeline (the same one the product runs):
  synthetic order feed (backend/precedent/orders.py, seeded)
  -> Situation Builder (Wilson CIs, binomial test, order-feed features)
  -> baseline retriever -> Consultant (with and without precedent)
  -> reference Policy Gate -> timeline -> ScreenBundle

Every output is schema-validated. Run:  python scripts/build_fixtures.py
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from intelligence import gate_reference  # noqa: E402
from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.consultant import recommend  # noqa: E402
from intelligence.retrieve_baseline import retrieve  # noqa: E402
from intelligence.schema import validate  # noqa: E402
from precedent.orders import generate  # noqa: E402
from precedent.scenarios import DEMO  # noqa: E402
from precedent.situation_builder import build  # noqa: E402

OUT = ROOT / "contracts" / "fixtures"
REAL_SANDBOX_DISPUTE = "PP-R-BTL-10196893"  # created by hand in the sandbox, see docs/SPIKE1_RESULT.md


def timeline(situation: dict, rec: dict, decisions: list[dict]) -> list[dict]:
    at = situation["window"]["end"] + "T09:00:00Z"
    pending = [d for d in decisions if d["decision"] == "NEEDS_APPROVAL"]
    gated = [d for d in decisions if d["tier"] != "PREPARE"]
    all_blocked = bool(gated) and all(d["decision"] == "BLOCKED" for d in gated)
    if rec["abstain"]:
        approved = {"status": "skipped", "detail": "Nothing to approve: the Consultant abstained."}
    elif all_blocked:
        approved = {"status": "blocked", "detail": "The policy gate blocked every external and money action."}
    else:
        approved = {"status": "pending", "detail": f"{len(pending)} action(s) waiting for your approval."}
    anomaly = situation["features"]["anomaly"]
    return [
        {"step": "detected", "status": "done", "at": at, "simulated": True,
         "detail": f"Binomial test vs 30-day baseline, p={anomaly['p_value']}. Run on the synthetic demo order feed."},
        {"step": "recommended", "status": "done", "at": at, "simulated": False,
         "detail": "Abstained." if rec["abstain"] else f"{len(rec['actions'])} action(s) proposed, citing {len(rec['precedents'])} precedent(s)."},
        dict({"step": "approved", "at": None, "simulated": False}, **approved),
        {"step": "executed", "status": "pending", "at": None, "simulated": True,
         "detail": "Runs through the PayPal sandbox adapter. Seller actions the sandbox blocks are simulated (see docs/SPIKE1_RESULT.md)."},
        {"step": "measured", "status": "pending", "at": None, "simulated": True,
         "detail": "Outcome clock is simulated. Result is recorded as a live_simulated case pending review."},
    ]


def bundle_for(situation: dict, cases: list[dict], mode: str) -> dict:
    precedents = retrieve(situation, cases, k=6)
    rec = recommend(situation, precedents, mode=mode, created_at=situation["window"]["end"] + "T09:00:00Z")
    decisions = gate_reference.decide(rec)
    bundle = {"situation": situation, "recommendation": rec,
              "policy_decisions": decisions, "timeline": timeline(situation, rec, decisions)}
    validate("bundle", bundle)
    return bundle


def main() -> None:
    cases = usable(load_cases())
    (OUT / "situations").mkdir(parents=True, exist_ok=True)
    (OUT / "bundles").mkdir(parents=True, exist_ok=True)
    index = {"situations": [], "modes": ["with_precedent", "no_precedent"], "case_count": len(cases)}
    for key, scenario in DEMO.items():
        situation = build(generate(scenario), situation_id=f"sit_demo_{key}", label=scenario.name,
                          paypal_dispute_ids=[REAL_SANDBOX_DISPUTE] if key == "A" else None)
        (OUT / "situations" / f"{key}.json").write_text(json.dumps(situation, indent=2), encoding="utf-8")
        for mode in ("with_precedent", "no_precedent"):
            bundle = bundle_for(situation, cases, mode)
            rec, decisions = bundle["recommendation"], bundle["policy_decisions"]
            (OUT / "bundles" / f"{key}_{mode}.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            print(f"{key} {mode:15s} diagnosis={rec['diagnosis']!r} actions={[a['type'] for a in rec['actions']]} "
                  f"decisions={[d['decision'] for d in decisions]} conf={rec['confidence']} abstain={rec['abstain']}")
        index["situations"].append({"key": key, "situation_id": situation["situation_id"], "label": scenario.name})
    (OUT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()

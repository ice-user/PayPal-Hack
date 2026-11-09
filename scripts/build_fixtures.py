"""Build /contracts/fixtures for the three demo situations.

Pipeline (the same one the product runs):
  synthetic order feed (backend/precedent/orders.py, seeded)
  -> Situation Builder (Wilson CIs, binomial test, order-feed features)
  -> default hybrid TF-IDF retriever -> Consultant (with and without precedent)
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

from intelligence.cases import load_cases, usable  # noqa: E402
from precedent.scenarios import DEMO  # noqa: E402
from precedent.service import SITUATION_KEYS, demo_disputes, demo_situation, static_bundle  # noqa: E402
from precedent.techkart import TECHKART  # noqa: E402

OUT = ROOT / "contracts" / "fixtures"


def main() -> None:
    cases = usable(load_cases())
    (OUT / "situations").mkdir(parents=True, exist_ok=True)
    (OUT / "bundles").mkdir(parents=True, exist_ok=True)
    index = {"situations": [], "modes": ["with_precedent", "no_precedent"], "case_count": len(cases)}
    labels = {k: v.name for k, v in DEMO.items()} | {"T": TECHKART.name}
    for key in SITUATION_KEYS:
        situation = demo_situation(key)
        disputes = demo_disputes(key)
        (OUT / "situations" / f"{key}.json").write_text(json.dumps(situation, indent=2), encoding="utf-8", newline="\n")
        for mode in ("with_precedent", "no_precedent"):
            bundle = static_bundle(situation, cases, mode, disputes=disputes)
            rec, decisions = bundle["recommendation"], bundle["policy_decisions"]
            (OUT / "bundles" / f"{key}_{mode}.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8", newline="\n")
            print(f"{key} {mode:15s} diagnosis={rec['diagnosis']!r} actions={[a['type'] for a in rec['actions']]} "
                  f"decisions={[d['decision'] for d in decisions]} conf={rec['confidence']} abstain={rec['abstain']}")
        index["situations"].append({"key": key, "situation_id": situation["situation_id"], "label": labels[key]})
    (OUT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8", newline="\n")
    print(f"wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()

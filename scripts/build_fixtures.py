"""Build /contracts/fixtures from the three demo situation specs.

Pipeline (same as the product, with reference stand-ins for Person B's services):
  synthetic counts -> SituationRecord (Wilson CIs, binomial test)
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

from intelligence import gate_reference  # noqa: E402
from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.consultant import recommend  # noqa: E402
from intelligence.retrieve_baseline import retrieve  # noqa: E402
from intelligence.schema import validate  # noqa: E402
from intelligence.stats import binomial_upper_p, wilson_ci  # noqa: E402

OUT = ROOT / "contracts" / "fixtures"
REAL_SANDBOX_DISPUTE = "PP-R-BTL-10196893"  # created by hand in the sandbox, see docs/SPIKE1_RESULT.md

# Synthetic demo merchant: one mid-size electronics store, three versions of the same symptom.
SPECS = {
    "A": {
        "label": "A: one carrier",
        "tx7": 1840, "d7": 26, "tx30": 7600, "d30": 23,
        "reason_mix": {"ITEM_NOT_RECEIVED": 0.74, "UNAUTHORISED": 0.10, "NOT_AS_DESCRIBED": 0.08, "OTHER": 0.08},
        "concentration": {"sku": 0.62, "carrier": 0.81, "country": 0.93,
                          "top_sku": "HDP-220 wireless headphones", "top_carrier": "Northline Parcel", "top_country": "US"},
        "carriers_elevated": 1, "delay": 10, "delivered": 0.12, "trend": 0.71,
        "narrative": "Item-not-received disputes up sharply in 10 days, mostly on Northline Parcel and one SKU. Orders ship on time.",
        "dispute_ids": [REAL_SANDBOX_DISPUTE],
    },
    "B": {
        "label": "B: many carriers, slow shipping",
        "tx7": 1910, "d7": 29, "tx30": 7700, "d30": 25,
        "reason_mix": {"ITEM_NOT_RECEIVED": 0.70, "UNAUTHORISED": 0.09, "NOT_AS_DESCRIBED": 0.09, "OTHER": 0.12},
        "concentration": {"sku": 0.21, "carrier": 0.33, "country": 0.92,
                          "top_sku": "HDP-220 wireless headphones", "top_carrier": "Coastal Express", "top_country": "US"},
        "carriers_elevated": 4, "delay": 61, "delivered": 0.08, "trend": 0.66,
        "narrative": "Item-not-received disputes up across four carriers. Median time to ship has risen to about 2.5 days.",
        "dispute_ids": [],
    },
    "C": {
        "label": "C: delivered orders",
        "tx7": 1790, "d7": 24, "tx30": 7500, "d30": 22,
        "reason_mix": {"ITEM_NOT_RECEIVED": 0.68, "UNAUTHORISED": 0.12, "NOT_AS_DESCRIBED": 0.08, "OTHER": 0.12},
        "concentration": {"sku": 0.30, "carrier": 0.38, "country": 0.94,
                          "top_sku": "HDP-220 wireless headphones", "top_carrier": "Ridgeway Post", "top_country": "US"},
        "carriers_elevated": 1, "delay": 12, "delivered": 0.82, "trend": 0.60,
        "narrative": "Item-not-received disputes up, but most disputed orders show a confirmed delivery scan.",
        "dispute_ids": [],
    },
}
WINDOW = {"start": "2026-10-28", "end": "2026-11-06"}
AVG_AMOUNT = 74.2


def daily_series(base: float, final: float, days: int = 10) -> list[float]:
    """Deterministic ramp from baseline to the current rate, for the sparkline."""
    out = []
    for i in range(days):
        t = (i / (days - 1)) ** 1.6
        out.append(round(base + (final - base) * t, 4))
    return out


def build_situation(key: str, s: dict) -> dict:
    rate7 = s["d7"] / s["tx7"]
    base = s["d30"] / s["tx30"]
    p = binomial_upper_p(s["d7"], s["tx7"], base)
    min_sample = s["tx7"] >= 500 and s["d7"] >= 10
    situation = {
        "situation_id": f"sit_demo_{key}",
        "merchant_id": "m_demo_electronics",
        "label": s["label"],
        "window": WINDOW,
        "source": "mixed" if s["dispute_ids"] else "synthetic_order_feed",
        "features": {
            "transactions_7d": s["tx7"], "disputes_7d": s["d7"],
            "gmv_7d": round(s["tx7"] * AVG_AMOUNT, 2),
            "dispute_rate_7d": round(rate7, 5),
            "dispute_rate_7d_ci95": [round(v, 5) for v in wilson_ci(s["d7"], s["tx7"])],
            "transactions_30d_baseline": s["tx30"], "disputes_30d_baseline": s["d30"],
            "dispute_rate_30d_baseline": round(base, 5),
            "baseline_ci95": [round(v, 5) for v in wilson_ci(s["d30"], s["tx30"])],
            "rate_ratio": round(rate7 / base, 2),
            "anomaly": {"method": "binomial_vs_baseline", "p_value": float(f"{p:.3g}"),
                        "is_anomalous": bool(p < 0.01 and min_sample), "min_sample_met": min_sample},
            "trend_slope": s["trend"],
            "daily_dispute_rate": daily_series(base, rate7),
            "reason_mix": s["reason_mix"],
            "concentration": s["concentration"],
            "carriers_elevated": s["carriers_elevated"],
            "ship_delay_hours_p50": s["delay"],
            "disputed_orders_delivered_share": s["delivered"],
            "avg_amount": AVG_AMOUNT,
            "median_response_hours": 52,
            "open_disputes": s["d7"] - 3,
            "refund_ratio_30d": 0.04,
            "days_since_txn_median": 9,
        },
        "narrative": s["narrative"],
        "evidence_ids": [],
        "paypal_dispute_ids": s["dispute_ids"],
    }
    validate("situation", situation)
    return situation


def timeline(situation: dict, rec: dict, decisions: list[dict]) -> list[dict]:
    at = situation["window"]["end"] + "T09:00:00Z"
    pending = [d for d in decisions if d["decision"] == "NEEDS_APPROVAL"]
    all_blocked = decisions and all(d["decision"] == "BLOCKED" for d in decisions if d["tier"] != "PREPARE")
    if rec["abstain"]:
        approved = {"status": "skipped", "detail": "Nothing to approve: the Consultant abstained."}
    elif all_blocked:
        approved = {"status": "blocked", "detail": "The policy gate blocked every external and money action."}
    else:
        approved = {"status": "pending", "detail": f"{len(pending)} action(s) waiting for your approval."}
    return [
        {"step": "detected", "status": "done", "at": at, "simulated": True,
         "detail": f"Binomial test vs 30-day baseline, p={situation['features']['anomaly']['p_value']}. Run on the synthetic demo order feed."},
        {"step": "recommended", "status": "done", "at": at, "simulated": False,
         "detail": "Abstained." if rec["abstain"] else f"{len(rec['actions'])} action(s) proposed, citing {len(rec['precedents'])} precedent(s)."},
        dict({"step": "approved", "at": None, "simulated": False}, **approved),
        {"step": "executed", "status": "pending", "at": None, "simulated": True,
         "detail": "Runs through the PayPal sandbox adapter. Seller actions the sandbox blocks are simulated (see docs/SPIKE1_RESULT.md)."},
        {"step": "measured", "status": "pending", "at": None, "simulated": True,
         "detail": "Outcome clock is simulated. Result is recorded as a live_simulated case pending review."},
    ]


def main() -> None:
    cases = usable(load_cases())
    (OUT / "situations").mkdir(parents=True, exist_ok=True)
    (OUT / "bundles").mkdir(parents=True, exist_ok=True)
    index = {"situations": [], "modes": ["with_precedent", "no_precedent"], "case_count": len(cases)}
    for key, spec in SPECS.items():
        situation = build_situation(key, spec)
        (OUT / "situations" / f"{key}.json").write_text(json.dumps(situation, indent=2), encoding="utf-8")
        precedents = retrieve(situation, cases, k=6)
        for mode in ("with_precedent", "no_precedent"):
            rec = recommend(situation, precedents, mode=mode, created_at=WINDOW["end"] + "T09:00:00Z")
            decisions = gate_reference.decide(rec)
            bundle = {"situation": situation, "recommendation": rec,
                      "policy_decisions": decisions, "timeline": timeline(situation, rec, decisions)}
            validate("bundle", bundle)
            (OUT / "bundles" / f"{key}_{mode}.json").write_text(json.dumps(bundle, indent=2), encoding="utf-8")
            print(f"{key} {mode:15s} diagnosis={rec['diagnosis']!r} actions={[a['type'] for a in rec['actions']]} "
                  f"decisions={[d['decision'] for d in decisions]} conf={rec['confidence']} abstain={rec['abstain']}")
        index["situations"].append({"key": key, "situation_id": situation["situation_id"], "label": spec["label"]})
    (OUT / "index.json").write_text(json.dumps(index, indent=2), encoding="utf-8")
    print(f"wrote fixtures to {OUT}")


if __name__ == "__main__":
    main()

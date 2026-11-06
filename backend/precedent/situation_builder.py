"""Situation Builder: turn an order feed into a schema-valid SituationRecord.

Detection: 7-day dispute rate vs the merchant's own 30-day baseline, Wilson 95%
intervals, one-sided exact binomial test, anomaly only above a minimum sample size.
Diagnosis features come from the order feed (concentration, carriers elevated,
fulfilment delay, share of disputed orders with a delivery scan).
"""
from __future__ import annotations

import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence.schema import validate  # noqa: E402
from intelligence.stats import binomial_upper_p, wilson_ci  # noqa: E402

from .orders import WINDOW_DAYS  # noqa: E402

P_THRESHOLD = 0.01
MIN_TX = 500
MIN_DISPUTES = 10
ELEVATED_RATIO = 2.0
ELEVATED_MIN_DISPUTES = 3


def _top_share(counter: Counter, total: int) -> tuple[str | None, float]:
    if not total or not counter:
        return None, 0.0
    k, v = counter.most_common(1)[0]
    return k, round(v / total, 3)


def _trend(daily: list[float]) -> float:
    """Least-squares slope over the series, scaled so a rise from 0 to the max across the
    window maps to about 1. Clipped to [0, 1]."""
    n = len(daily)
    if n < 2 or max(daily) == 0:
        return 0.0
    xs = range(n)
    mx, my = (n - 1) / 2, sum(daily) / n
    num = sum((x - mx) * (y - my) for x, y in zip(xs, daily))
    den = sum((x - mx) ** 2 for x in xs)
    slope = num / den
    return round(max(0.0, min(1.0, slope * (n - 1) / max(daily))), 2)


def build(orders: list[dict], *, situation_id: str, merchant_id: str = "m_demo_electronics",
          label: str | None = None, paypal_dispute_ids: list[str] | None = None) -> dict:
    window = [o for o in orders if o["in_window"]]
    base = [o for o in orders if not o["in_window"]]
    d_win = [o for o in window if o["disputed"]]
    d_base = [o for o in base if o["disputed"]]
    tx7, k7, tx30, k30 = len(window), len(d_win), len(base), len(d_base)
    rate7 = k7 / tx7 if tx7 else 0.0
    rate30 = k30 / tx30 if tx30 else 0.0
    p = binomial_upper_p(k7, tx7, rate30) if rate30 > 0 else (0.0 if k7 else 1.0)
    min_sample = tx7 >= MIN_TX and k7 >= MIN_DISPUTES

    # daily series: last 10 days
    by_day: dict[str, list[dict]] = defaultdict(list)
    for o in orders:
        by_day[o["day"]].append(o)
    days = sorted(by_day)[-10:]
    daily = [round(sum(o["disputed"] for o in by_day[d]) / len(by_day[d]), 4) for d in days]

    reasons = Counter(o["dispute_reason"] for o in d_win)
    reason_mix = {r: round(c / k7, 3) for r, c in reasons.most_common()} if k7 else {}

    top_carrier, carrier_share = _top_share(Counter(o["carrier"] for o in d_win), k7)
    top_sku, sku_share = _top_share(Counter(o["sku"] for o in d_win), k7)
    top_country, country_share = _top_share(Counter(o["country"] for o in d_win), k7)

    # A carrier is "elevated" when its not-received disputes on parcels WITHOUT a delivery
    # scan are well above its own baseline: that is the part a carrier can be blamed for.
    def lost(o: dict) -> bool:
        return o["disputed"] and o["dispute_reason"] == "ITEM_NOT_RECEIVED" and not o["delivered"]

    base_lost_rate = sum(lost(o) for o in base) / tx30 if tx30 else 0.0
    elevated = 0
    for c in {o["carrier"] for o in orders}:
        w = [o for o in window if o["carrier"] == c]
        b = [o for o in base if o["carrier"] == c]
        kw, kb = sum(lost(o) for o in w), sum(lost(o) for o in b)
        rb = max(kb / len(b) if b else 0.0, base_lost_rate * 0.5, 1e-4)
        if w and kw >= ELEVATED_MIN_DISPUTES and (kw / len(w)) > ELEVATED_RATIO * rb:
            elevated += 1

    delivered_share = round(sum(o["delivered"] for o in d_win) / k7, 3) if k7 else 0.0
    delay_p50 = round(statistics.median(o["ship_delay_hours"] for o in window), 1) if window else 0.0
    avg_amount = round(sum(o["amount"] for o in window) / tx7, 2) if tx7 else 0.0

    features = {
        "transactions_7d": tx7, "disputes_7d": k7, "gmv_7d": round(sum(o["amount"] for o in window), 2),
        "dispute_rate_7d": round(rate7, 5),
        "dispute_rate_7d_ci95": [round(v, 5) for v in wilson_ci(k7, tx7)],
        "transactions_30d_baseline": tx30, "disputes_30d_baseline": k30,
        "dispute_rate_30d_baseline": round(rate30, 5),
        "baseline_ci95": [round(v, 5) for v in wilson_ci(k30, tx30)],
        "rate_ratio": round(rate7 / rate30, 2) if rate30 else 0.0,
        "anomaly": {"method": "binomial_vs_baseline", "p_value": float(f"{p:.3g}"),
                    "is_anomalous": bool(p < P_THRESHOLD and min_sample), "min_sample_met": min_sample},
        "trend_slope": _trend(daily),
        "daily_dispute_rate": daily,
        "reason_mix": reason_mix,
        "concentration": {"sku": sku_share, "carrier": carrier_share, "country": country_share,
                          **({"top_sku": top_sku} if top_sku else {}),
                          **({"top_carrier": top_carrier} if top_carrier else {}),
                          **({"top_country": top_country} if top_country else {})},
        "carriers_elevated": elevated,
        "ship_delay_hours_p50": delay_p50,
        "disputed_orders_delivered_share": delivered_share,
        "avg_amount": avg_amount,
        "median_response_hours": 52,
        "open_disputes": sum(o["dispute_open"] for o in d_win),
        "refund_ratio_30d": 0.04,
        "days_since_txn_median": 9,
    }
    situation = {
        "situation_id": situation_id,
        "merchant_id": merchant_id,
        "window": {"start": days[-WINDOW_DAYS] if len(days) >= 7 else days[0], "end": days[-1]},
        "source": "mixed" if paypal_dispute_ids else "synthetic_order_feed",
        "features": features,
        "narrative": narrative(features),
        "evidence_ids": [],
        "paypal_dispute_ids": paypal_dispute_ids or [],
    }
    if label:
        situation["label"] = label
    validate("situation", situation)
    return situation


def narrative(f: dict) -> str:
    """Plain-language one-liner built only from computed features."""
    if not f["anomaly"]["is_anomalous"]:
        why = "sample too small to call" if not f["anomaly"]["min_sample_met"] else "within normal variation"
        return f"Dispute rate {f['dispute_rate_7d'] * 100:.2f}% vs baseline {f['dispute_rate_30d_baseline'] * 100:.2f}%: {why}."
    top_reason = max(f["reason_mix"], key=f["reason_mix"].get) if f["reason_mix"] else "OTHER"
    reason_txt = {"ITEM_NOT_RECEIVED": "Item-not-received", "UNAUTHORISED": "Unauthorised-transaction",
                  "NOT_AS_DESCRIBED": "Not-as-described"}.get(top_reason, "Dispute")
    c = f["concentration"]
    parts = [f"{reason_txt} disputes up {f['rate_ratio']:.1f}x in 7 days"]
    if c.get("carrier", 0) >= 0.6 and f["carriers_elevated"] <= 1:
        parts.append(f"mostly on {c.get('top_carrier')}")
    elif f["carriers_elevated"] >= 3:
        parts.append(f"across {f['carriers_elevated']} carriers")
    if f["ship_delay_hours_p50"] >= 36:
        parts.append(f"time to ship is {f['ship_delay_hours_p50']:.0f}h")
    if f["disputed_orders_delivered_share"] >= 0.6:
        parts.append(f"{f['disputed_orders_delivered_share'] * 100:.0f}% of disputed orders show a delivery scan")
    if c.get("sku", 0) >= 0.6:
        parts.append(f"concentrated on {c.get('top_sku')}")
    return (", ".join(parts) + ".")[:400]

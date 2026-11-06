"""Synthetic order and fulfilment feed for the demo merchant.

Deterministic for a given seed. Each scenario plants a known cause in the last
7 days, so the generator doubles as ground truth for testing the detector and the
Consultant. Everything produced here is synthetic and labelled as such in the UI.

Simplification: disputes are attributed to the day the order was placed (real
disputes arrive with a lag of days to weeks).
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

CARRIERS = {"Northline Parcel": 0.30, "Coastal Express": 0.30, "Ridgeway Post": 0.25, "Metro Courier": 0.15}
SKUS = {  # sku: (share of orders, price USD)
    "HDP-220 wireless headphones": (0.20, 129.0),
    "SPK-10 speaker": (0.15, 89.0),
    "CBL-3 USB-C cable": (0.25, 12.0),
    "CHG-65 charger": (0.20, 45.0),
    "CSE-9 phone case": (0.20, 19.0),
}
COUNTRIES = {"US": 0.93, "CA": 0.05, "GB": 0.02}
BASE_REASONS = {"ITEM_NOT_RECEIVED": 0.45, "UNAUTHORISED": 0.25, "NOT_AS_DESCRIBED": 0.20, "OTHER": 0.10}

BASELINE_DAYS = 30
WINDOW_DAYS = 7


@dataclass
class Scenario:
    """A planted cause in the last WINDOW_DAYS days."""
    name: str
    kind: str  # none | carrier | fulfilment | delivered | fraud | snad | mixed
    seed: int = 7
    orders_per_day: float = 260.0
    base_dispute_rate: float = 0.003
    extra_rate: float = 0.0          # extra dispute probability on targeted orders
    target_carrier: str = "Northline Parcel"
    target_sku: str = "HDP-220 wireless headphones"
    delay_hours: float = 60.0        # median ship delay during a fulfilment spike
    end: date = date(2026, 11, 6)
    notes: str = ""
    expected: dict = field(default_factory=dict)  # ground truth for evaluation


def _pick(rng: random.Random, weights: dict) -> str:
    r, acc = rng.random(), 0.0
    for k, w in weights.items():
        acc += w
        if r <= acc:
            return k
    return next(reversed(weights))


def _poisson(rng: random.Random, lam: float) -> int:
    # Knuth for small lambda, normal approximation for large.
    if lam > 50:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def generate(s: Scenario) -> list[dict]:
    rng = random.Random(s.seed)
    days = BASELINE_DAYS + WINDOW_DAYS
    start = s.end - timedelta(days=days - 1)
    sku_w = {k: v[0] for k, v in SKUS.items()}
    orders: list[dict] = []
    n = 0
    for d in range(days):
        day = start + timedelta(days=d)
        in_window = d >= BASELINE_DAYS
        for _ in range(_poisson(rng, s.orders_per_day)):
            n += 1
            sku = _pick(rng, sku_w)
            carrier = _pick(rng, CARRIERS)
            delay = rng.lognormvariate(math.log(10), 0.35)
            delivered = True
            disputed, reason = False, None

            if rng.random() < s.base_dispute_rate:
                disputed, reason = True, _pick(rng, BASE_REASONS)
                delivered = reason != "ITEM_NOT_RECEIVED" or rng.random() < 0.4

            kinds = {s.kind} if s.kind != "mixed" else {"carrier", "fulfilment"}
            extra = s.extra_rate / (2 if s.kind == "mixed" else 1)
            if in_window:
                if "fulfilment" in kinds:
                    delay = rng.lognormvariate(math.log(s.delay_hours), 0.35)
                if not disputed:
                    if "carrier" in kinds and carrier == s.target_carrier and rng.random() < extra:
                        disputed, reason, delivered = True, "ITEM_NOT_RECEIVED", rng.random() < 0.05
                    elif "fulfilment" in kinds and delay > 48 and rng.random() < extra:
                        disputed, reason, delivered = True, "ITEM_NOT_RECEIVED", rng.random() < 0.05
                    elif s.kind == "delivered" and rng.random() < extra:
                        disputed, reason, delivered = True, "ITEM_NOT_RECEIVED", rng.random() < 0.92
                    elif s.kind == "fraud" and sku == s.target_sku and rng.random() < extra:
                        disputed, reason, delivered = True, "UNAUTHORISED", True
                    elif s.kind == "snad" and sku == s.target_sku and rng.random() < extra:
                        disputed, reason, delivered = True, "NOT_AS_DESCRIBED", True

            orders.append({
                "order_id": f"o{n:06d}",
                "day": day.isoformat(),
                "in_window": in_window,
                "sku": sku,
                "carrier": carrier,
                "country": _pick(rng, COUNTRIES),
                "amount": SKUS[sku][1],
                "ship_delay_hours": round(delay, 1),
                "delivered": delivered,
                "disputed": disputed,
                "dispute_reason": reason,
                "dispute_open": disputed and rng.random() < 0.9,
            })
    return orders

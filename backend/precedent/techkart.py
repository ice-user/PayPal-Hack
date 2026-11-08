"""TechKart: the delivery-failure test environment (see docs/TECHKART_TEST_ENV.md).

A fictional electronics merchant whose item-not-received disputes jump from about 0.5%
to 2.5%, concentrated on one carrier and one product. Unlike orders.py, every open
item-not-received dispute also carries the parcel's shipment state, its strongest
delivery proof, the carrier's expected delivery date and a response deadline, so the
dispute-level triage can be tested against ground truth.

Deterministic for a given seed. Everything here is synthetic.
"""
from __future__ import annotations

import math
import random
from dataclasses import dataclass, field
from datetime import date, timedelta

CARRIERS = {"Carrier X": 0.35, "Parcelway": 0.30, "Swift Freight": 0.20, "Metro Courier": 0.15}
SKUS = {  # sku: (share of orders, price USD); weighted average about 85 USD
    "VX-200 wireless earbuds": (0.30, 79.0),
    "TK-Watch 3": (0.15, 189.0),
    "PowerCell 20k battery": (0.25, 49.0),
    "Lumo desk lamp": (0.15, 59.0),
    "Hub-7 USB-C dock": (0.15, 99.0),
}
COUNTRIES = {"US": 0.95, "CA": 0.05}
OTHER_REASONS = {"UNAUTHORISED": 0.45, "NOT_AS_DESCRIBED": 0.35, "OTHER": 0.20}

BASELINE_DAYS = 30
WINDOW_DAYS = 7
RESPONSE_DAYS = 10  # synthetic seller response window (assumption, not a PayPal rule)

# Default shipment-state mix among spike disputes on the troubled carrier.
DEFAULT_MIX = {"delivered_confirmation": 0.20, "delivered_documented": 0.15, "in_transit": 0.35,
               "lost": 0.15, "unknown": 0.15}


@dataclass
class TechKartScenario:
    name: str
    seed: int = 21
    orders_per_day: float = 160.0
    base_dispute_rate: float = 0.005
    spike_rate: float = 0.02          # extra dispute probability on targeted orders in the window
    target_carrier: str = "Carrier X"
    target_sku: str = "VX-200 wireless earbuds"
    carrier_focus: float = 0.65       # share of spike disputes on the target carrier
    sku_focus: float = 0.45           # share of spike disputes on the target product
    mix: dict = field(default_factory=lambda: dict(DEFAULT_MIX))
    transit_days: tuple[int, int] = (1, 9)   # in transit: expected delivery = today + U(a, b)
    opened_lag: tuple[int, int] = (0, 6)     # dispute opened this many days before today
    end: date = date(2026, 11, 8)
    notes: str = ""
    expected: dict = field(default_factory=dict)


def _pick(rng: random.Random, weights: dict) -> str:
    r, acc = rng.random() * sum(weights.values()), 0.0
    for k, w in weights.items():
        acc += w
        if r <= acc:
            return k
    return next(reversed(weights))


def _poisson(rng: random.Random, lam: float) -> int:
    if lam > 50:
        return max(0, int(round(rng.gauss(lam, math.sqrt(lam)))))
    l, k, p = math.exp(-lam), 0, 1.0
    while True:
        p *= rng.random()
        if p <= l:
            return k
        k += 1


def _shipment(rng: random.Random, state: str, today: date, opened: date) -> dict:
    """Shipment fields for one disputed parcel in a given true state."""
    due = opened + timedelta(days=RESPONSE_DAYS)
    out = {"shipment_status": "delivered", "proof": "confirmation", "expected_delivery": None,
           "response_due": due.isoformat(), "opened": opened.isoformat()}
    if state == "delivered_confirmation":
        out["proof"] = "confirmation"
    elif state == "delivered_documented":
        out["proof"] = rng.choice(["gps", "signature"])
    elif state == "in_transit":
        out.update(shipment_status="in_transit", proof="tracking")
    elif state == "lost":
        out.update(shipment_status="lost", proof="tracking")
    else:  # unknown: no tracking uploaded
        out.update(shipment_status="unknown", proof="none")
    return out


def generate(s: TechKartScenario) -> tuple[list[dict], list[dict]]:
    """Return (orders, disputes). Orders match the shape situation_builder.build expects."""
    rng = random.Random(s.seed)
    days = BASELINE_DAYS + WINDOW_DAYS
    start = s.end - timedelta(days=days - 1)
    sku_w = {k: v[0] for k, v in SKUS.items()}
    other_carriers = {c: w for c, w in CARRIERS.items() if c != s.target_carrier}
    other_skus = {k: w for k, w in sku_w.items() if k != s.target_sku}
    orders: list[dict] = []
    disputes: list[dict] = []
    n = 0
    for d in range(days):
        day = start + timedelta(days=d)
        in_window = d >= BASELINE_DAYS
        for _ in range(_poisson(rng, s.orders_per_day)):
            n += 1
            sku, carrier = _pick(rng, sku_w), _pick(rng, CARRIERS)
            delay = rng.lognormvariate(math.log(10), 0.35)
            disputed, reason, state = False, None, None

            if in_window and rng.random() < s.spike_rate:
                # A spike dispute: steer carrier and product to the planted concentrations.
                carrier = s.target_carrier if rng.random() < s.carrier_focus else _pick(rng, other_carriers)
                sku = s.target_sku if rng.random() < s.sku_focus else _pick(rng, other_skus)
                disputed, reason = True, "ITEM_NOT_RECEIVED"
                state = _pick(rng, s.mix)
            elif rng.random() < s.base_dispute_rate:
                disputed = True
                reason = "ITEM_NOT_RECEIVED" if rng.random() < 0.45 else _pick(rng, OTHER_REASONS)
                if reason == "ITEM_NOT_RECEIVED":
                    state = _pick(rng, {"delivered_confirmation": 0.45, "delivered_documented": 0.15,
                                        "in_transit": 0.2, "lost": 0.1, "unknown": 0.1})

            delivered = (state or "delivered").startswith("delivered") if reason == "ITEM_NOT_RECEIVED" else True
            n_id = f"TK-{n:06d}"
            open_ = disputed and (in_window or rng.random() < 0.15)
            orders.append({
                "order_id": n_id, "day": day.isoformat(), "in_window": in_window, "sku": sku,
                "carrier": carrier, "country": _pick(rng, COUNTRIES), "amount": SKUS[sku][1],
                "ship_delay_hours": round(delay, 1), "delivered": delivered, "disputed": disputed,
                "dispute_reason": reason, "dispute_open": open_,
            })
            if disputed and open_ and reason == "ITEM_NOT_RECEIVED":
                lag = rng.randint(*s.opened_lag) if in_window else rng.randint(7, 20)
                opened = max(day, s.end - timedelta(days=lag))
                ship = _shipment(rng, state, s.end, opened)
                if ship["shipment_status"] == "in_transit":
                    ship["expected_delivery"] = (s.end + timedelta(days=rng.randint(*s.transit_days))).isoformat()
                disputes.append({
                    "dispute_id": f"TKD-{n:06d}", "order_id": n_id, "carrier": carrier, "sku": sku,
                    "amount": SKUS[sku][1], "reason": reason, "true_state": state, **ship,
                })
    # Drop disputes whose response window already closed (they are no longer actionable).
    today = s.end.isoformat()
    disputes = [x for x in disputes if x["response_due"] >= today]
    return orders, disputes


# The demo merchant. Ground truth for the situation level: a carrier problem.
TECHKART = TechKartScenario("T: TechKart, delivery failure crisis", seed=22,
                            expected={"family": "carrier", "anomalous": True, "should_abstain": False})


# ---------------------------------------------------------------------------
# Pre-registered TechKart test set (spec section 7). Written on 2026-11-09 before either
# System A or System B was run on it. Seeds, volumes, carriers, products, shipment-state
# mixes, transit times and dispute ages all differ from the demo merchant (seed 22).
# Ground truth: each dispute's correct path follows from its true shipment state and
# whether the response deadline falls before expected delivery. Do not tune triage,
# the dispute cases or the gate on these results; log a new run instead.
# ---------------------------------------------------------------------------
_CARRIER = {"family": "carrier", "anomalous": True, "should_abstain": False}
_QUIET = {"family": None, "anomalous": False, "should_abstain": True}
_M = lambda dc, dd, it, lo, un: {"delivered_confirmation": dc, "delivered_documented": dd,  # noqa: E731
                                 "in_transit": it, "lost": lo, "unknown": un}

TK_TEST = [
    TechKartScenario("tk01_default_mix", seed=501, expected=_CARRIER),
    TechKartScenario("tk02_mostly_delivered", seed=502, mix=_M(0.45, 0.30, 0.10, 0.05, 0.10), expected=_CARRIER),
    TechKartScenario("tk03_mostly_in_transit_short", seed=503, mix=_M(0.10, 0.05, 0.65, 0.10, 0.10),
                     transit_days=(1, 3), expected=_CARRIER),
    TechKartScenario("tk04_mostly_in_transit_long", seed=504, mix=_M(0.10, 0.05, 0.65, 0.10, 0.10),
                     transit_days=(9, 16), expected=_CARRIER),
    TechKartScenario("tk05_lost_heavy", seed=505, mix=_M(0.10, 0.05, 0.20, 0.55, 0.10), expected=_CARRIER),
    TechKartScenario("tk06_no_tracking_heavy", seed=506, mix=_M(0.15, 0.05, 0.15, 0.10, 0.55), expected=_CARRIER),
    TechKartScenario("tk07_old_disputes_tight_deadlines", seed=507, opened_lag=(6, 9), expected=_CARRIER),
    TechKartScenario("tk08_new_disputes_loose_deadlines", seed=508, opened_lag=(0, 1), transit_days=(2, 6),
                     expected=_CARRIER),
    TechKartScenario("tk09_other_carrier_and_product", seed=509, target_carrier="Swift Freight",
                     target_sku="TK-Watch 3", expected=_CARRIER),
    TechKartScenario("tk10_high_volume", seed=510, orders_per_day=320, spike_rate=0.015, expected=_CARRIER),
    TechKartScenario("tk11_low_volume_strong_spike", seed=511, orders_per_day=110, spike_rate=0.035,
                     expected=_CARRIER),
    TechKartScenario("tk12_documented_deliveries", seed=512, mix=_M(0.10, 0.55, 0.15, 0.10, 0.10), expected=_CARRIER),
    TechKartScenario("tk13_even_mix", seed=513, mix=_M(0.20, 0.20, 0.20, 0.20, 0.20), expected=_CARRIER),
    TechKartScenario("tk14_transit_mixed_windows", seed=514, mix=_M(0.15, 0.05, 0.50, 0.15, 0.15),
                     transit_days=(3, 12), opened_lag=(2, 7), expected=_CARRIER),
    TechKartScenario("tk15_dock_product_focus", seed=515, target_sku="Hub-7 USB-C dock", sku_focus=0.6,
                     expected=_CARRIER),
    TechKartScenario("tk16_carrier_focus_weaker", seed=516, carrier_focus=0.5, sku_focus=0.3, expected=_CARRIER),
    TechKartScenario("tk17_parcelway_lost_wave", seed=517, target_carrier="Parcelway",
                     mix=_M(0.15, 0.05, 0.25, 0.40, 0.15), expected=_CARRIER),
    TechKartScenario("tk18_late_window_transit", seed=518, mix=_M(0.15, 0.10, 0.45, 0.15, 0.15),
                     transit_days=(5, 14), opened_lag=(4, 8), expected=_CARRIER),
    TechKartScenario("tk19_quiet_month_no_spike", seed=519, spike_rate=0.0, expected=_QUIET),
    TechKartScenario("tk20_quiet_high_volume", seed=520, spike_rate=0.0, orders_per_day=300, expected=_QUIET),
]

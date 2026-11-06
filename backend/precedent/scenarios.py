"""Named scenarios: the three demo situations and the ablation set.

`expected` is ground truth for evaluation:
  family: carrier | fulfilment | delivered | fraud | listing | None
  anomalous: whether the detector should flag it
  should_abstain: True when a careful consultant should not act (no anomaly,
                  too little data, or genuinely mixed causes)
"""
from __future__ import annotations

from .orders import Scenario

DEMO = {
    "A": Scenario("A: one carrier", "carrier", seed=11, extra_rate=0.045, target_carrier="Northline Parcel",
                  expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    "B": Scenario("B: many carriers, slow shipping", "fulfilment", seed=12, extra_rate=0.016, delay_hours=62,
                  expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    "C": Scenario("C: delivered orders", "delivered", seed=13, extra_rate=0.011,
                  expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
}

# Held-out TEST set. Written on 2026-11-08 after the case library was frozen at v1, and run
# once. Seeds, volumes, intensities and targets differ from ABLATION. Do not tune the
# Consultant, retriever or cases on these results; log a new run instead.
TEST = [
    Scenario("t_carrier_coastal_strong", "carrier", seed=901, extra_rate=0.06, target_carrier="Coastal Express",
             expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    Scenario("t_carrier_northline_bigshop", "carrier", seed=902, orders_per_day=520, extra_rate=0.03,
             target_carrier="Northline Parcel", expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    Scenario("t_carrier_ridgeway_lowvol", "carrier", seed=903, orders_per_day=120, extra_rate=0.08,
             target_carrier="Ridgeway Post", expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    Scenario("t_fulfilment_45h", "fulfilment", seed=911, extra_rate=0.025, delay_hours=45,
             expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    Scenario("t_fulfilment_75h_bigshop", "fulfilment", seed=912, orders_per_day=480, extra_rate=0.012, delay_hours=75,
             expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    Scenario("t_fulfilment_110h", "fulfilment", seed=913, extra_rate=0.012, delay_hours=110,
             expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    Scenario("t_delivered_lowvol", "delivered", seed=921, orders_per_day=150, extra_rate=0.02,
             expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
    Scenario("t_delivered_bigshop", "delivered", seed=922, orders_per_day=500, extra_rate=0.008,
             expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
    Scenario("t_delivered_heavy", "delivered", seed=923, extra_rate=0.025,
             expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
    Scenario("t_fraud_charger", "fraud", seed=931, extra_rate=0.07, target_sku="CHG-65 charger",
             expected={"family": "fraud", "anomalous": True, "should_abstain": False}),
    Scenario("t_fraud_case_mild", "fraud", seed=932, extra_rate=0.04, target_sku="CSE-9 phone case",
             expected={"family": "fraud", "anomalous": True, "should_abstain": False}),
    Scenario("t_snad_headphones", "snad", seed=941, extra_rate=0.10, target_sku="HDP-220 wireless headphones",
             expected={"family": "listing", "anomalous": True, "should_abstain": False}),
    Scenario("t_snad_charger", "snad", seed=942, extra_rate=0.14, target_sku="CHG-65 charger",
             expected={"family": "listing", "anomalous": True, "should_abstain": False}),
    Scenario("t_mixed_ridgeway", "mixed", seed=951, extra_rate=0.05, target_carrier="Ridgeway Post", delay_hours=65,
             expected={"family": None, "anomalous": True, "should_abstain": True}),
    Scenario("t_quiet_bigshop", "none", seed=961, orders_per_day=500,
             expected={"family": None, "anomalous": False, "should_abstain": True}),
    Scenario("t_quiet_lowvol", "none", seed=962, orders_per_day=120,
             expected={"family": None, "anomalous": False, "should_abstain": True}),
    Scenario("t_small_fulfilment", "fulfilment", seed=971, orders_per_day=18, extra_rate=0.03, delay_hours=70,
             expected={"family": "fulfilment", "anomalous": False, "should_abstain": True}),
    Scenario("t_small_fraud", "fraud", seed=972, orders_per_day=22, extra_rate=0.08, target_sku="CBL-3 USB-C cable",
             expected={"family": "fraud", "anomalous": False, "should_abstain": True}),
]

ABLATION = [
    # carrier failures
    Scenario("carrier_northline_strong", "carrier", seed=101, extra_rate=0.05, target_carrier="Northline Parcel",
             expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    Scenario("carrier_ridgeway", "carrier", seed=102, extra_rate=0.05, target_carrier="Ridgeway Post",
             expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    Scenario("carrier_metro_small_share", "carrier", seed=103, extra_rate=0.09, target_carrier="Metro Courier",
             expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    Scenario("carrier_coastal_mild", "carrier", seed=104, extra_rate=0.03, target_carrier="Coastal Express",
             expected={"family": "carrier", "anomalous": True, "should_abstain": False}),
    # fulfilment delays
    Scenario("fulfilment_backlog_60h", "fulfilment", seed=111, extra_rate=0.016, delay_hours=60,
             expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    Scenario("fulfilment_backlog_90h", "fulfilment", seed=112, extra_rate=0.014, delay_hours=90,
             expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    Scenario("fulfilment_mild_50h", "fulfilment", seed=113, extra_rate=0.02, delay_hours=50,
             expected={"family": "fulfilment", "anomalous": True, "should_abstain": False}),
    # delivered-order disputes
    Scenario("delivered_porch", "delivered", seed=121, extra_rate=0.012,
             expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
    Scenario("delivered_strong", "delivered", seed=122, extra_rate=0.018,
             expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
    Scenario("delivered_mild", "delivered", seed=123, extra_rate=0.009,
             expected={"family": "delivered", "anomalous": True, "should_abstain": False}),
    # fraud on a cheap SKU
    Scenario("fraud_cable_testing", "fraud", seed=131, extra_rate=0.08, target_sku="CBL-3 USB-C cable",
             expected={"family": "fraud", "anomalous": True, "should_abstain": False}),
    Scenario("fraud_headphones", "fraud", seed=132, extra_rate=0.09, target_sku="HDP-220 wireless headphones",
             expected={"family": "fraud", "anomalous": True, "should_abstain": False}),
    # not-as-described on one SKU
    Scenario("snad_speaker", "snad", seed=141, extra_rate=0.12, target_sku="SPK-10 speaker",
             expected={"family": "listing", "anomalous": True, "should_abstain": False}),
    # mixed causes: carrier and fulfilment at once
    Scenario("mixed_carrier_fulfilment", "mixed", seed=151, extra_rate=0.04, target_carrier="Northline Parcel",
             delay_hours=58, expected={"family": None, "anomalous": True, "should_abstain": True}),
    # no spike: detector must stay quiet
    Scenario("quiet_normal_week", "none", seed=161,
             expected={"family": None, "anomalous": False, "should_abstain": True}),
    Scenario("quiet_normal_week_2", "none", seed=162,
             expected={"family": None, "anomalous": False, "should_abstain": True}),
    # small shop: a real-looking jump but too little data
    Scenario("small_shop_carrier", "carrier", seed=171, orders_per_day=20, extra_rate=0.05,
             target_carrier="Northline Parcel",
             expected={"family": "carrier", "anomalous": False, "should_abstain": True}),
    Scenario("small_shop_delivered", "delivered", seed=172, orders_per_day=25, extra_rate=0.02,
             expected={"family": "delivered", "anomalous": False, "should_abstain": True}),
]

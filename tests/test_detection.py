"""Order feed generator and Situation Builder: the detector fires on planted spikes,
stays quiet on normal weeks and small samples, and the diagnosis features separate
the causes."""
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "backend"))

from intelligence.consultant import recommend  # noqa: E402
from precedent.orders import generate  # noqa: E402
from precedent.scenarios import ABLATION, DEMO  # noqa: E402
from precedent.situation_builder import build  # noqa: E402

ALL = list(DEMO.values()) + ABLATION


def sit(s):
    return build(generate(s), situation_id="sit_test")


def test_generator_is_deterministic():
    s = DEMO["A"]
    assert generate(s) == generate(s)


@pytest.mark.parametrize("scenario", ALL, ids=lambda s: s.name)
def test_detector_matches_ground_truth(scenario):
    f = sit(scenario)["features"]
    assert f["anomaly"]["is_anomalous"] == scenario.expected["anomalous"]


def test_features_separate_the_three_demo_causes():
    a, b, c = (sit(DEMO[k])["features"] for k in "ABC")
    assert a["concentration"]["carrier"] >= 0.6 and a["carriers_elevated"] <= 1 and a["ship_delay_hours_p50"] < 24
    assert b["carriers_elevated"] >= 3 and b["ship_delay_hours_p50"] >= 36
    assert c["disputed_orders_delivered_share"] >= 0.6 and c["carriers_elevated"] == 0


def test_small_sample_is_not_called_an_anomaly():
    f = sit(next(s for s in ABLATION if s.name == "small_shop_delivered"))["features"]
    assert f["anomaly"]["min_sample_met"] is False and f["anomaly"]["is_anomalous"] is False


@pytest.mark.parametrize("mode", ["with_precedent", "no_precedent"])
def test_consultant_abstains_without_anomaly(mode):
    s = sit(next(x for x in ABLATION if x.name == "quiet_normal_week"))
    r = recommend(s, [], mode=mode)
    assert r["abstain"] and r["actions"] == [] and "No action" in r["abstain_reason"]

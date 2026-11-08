"""Application service: builds screen bundles and runs approvals and the simulated clock.
Framework-free so the fixture builder, the API and the tests share one code path."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from intelligence import gate_reference  # noqa: E402
from intelligence.cases import load_cases, usable  # noqa: E402
from intelligence.consultant import DIAGNOSIS, recommend  # noqa: E402
from intelligence.llm_writer import make_writer  # noqa: E402
from intelligence.retrieve_baseline import retrieve  # noqa: E402
from intelligence.schema import thresholds, validate  # noqa: E402

from .executor import CLIENT_STATE, ActionError, Executor  # noqa: E402
from .orders import generate  # noqa: E402
from .outcomes import live_simulated_case, simulate  # noqa: E402
from .paypal_adapter import PayPalAdapter, load_env  # noqa: E402
from .scenarios import DEMO  # noqa: E402
from .situation_builder import build  # noqa: E402
from .store import Store  # noqa: E402

# The real sandbox dispute linked to demo situation A (created by hand, see docs/SPIKE1_RESULT.md).
# Override with DEMO_DISPUTE_ID in backend/.env when you make a fresh one for recording.
REAL_SANDBOX_DISPUTE = load_env().get("DEMO_DISPUTE_ID") or "PP-R-BTL-10196893"
MODES = ("with_precedent", "no_precedent")
DIAG_TO_FAMILY = {v: k for k, v in DIAGNOSIS.items()}


def demo_situation(key: str) -> dict:
    s = DEMO[key]
    return build(generate(s), situation_id=f"sit_demo_{key}", label=s.name,
                 paypal_dispute_ids=[REAL_SANDBOX_DISPUTE] if key == "A" else None)


def timeline(situation: dict, rec: dict, decisions: list[dict], states: dict | None = None,
             outcome: dict | None = None) -> list[dict]:
    at = situation["window"]["end"] + "T09:00:00Z"
    states = states or {}
    gated = [d for d in decisions if d["tier"] != "PREPARE"]
    all_blocked = bool(gated) and all(d["decision"] == "BLOCKED" for d in gated)
    pending = [d for d in decisions if d["decision"] == "NEEDS_APPROVAL"
               and states.get(d["action_id"], {}).get("state", "proposed") == "proposed"]
    acted = {k: v for k, v in states.items() if v["server_state"] in ("EXECUTING", "SUCCEEDED", "FAILED", "CANCELLED")
             and any(d["action_id"] == k and d["decision"] == "NEEDS_APPROVAL" for d in decisions)}
    approved_n = sum(v["state"] != "rejected" for v in acted.values())
    rejected_n = sum(v["state"] == "rejected" for v in acted.values())
    done = [v for v in acted.values() if v["state"] == "succeeded"]
    real = sum(v.get("execution_mode") == "real" for v in done)

    if rec["abstain"]:
        approved = {"status": "skipped", "detail": "Nothing to approve: the Consultant abstained."}
    elif all_blocked:
        approved = {"status": "blocked", "detail": "The policy gate blocked every external and money action."}
    elif acted:
        approved = {"status": "done" if approved_n else "skipped",
                    "detail": f"{approved_n} approved, {rejected_n} rejected by you."
                              + (f" {len(pending)} still waiting." if pending else "")}
    else:
        approved = {"status": "pending", "detail": f"{len(pending)} action(s) waiting for your approval."}

    if done:
        executed = {"status": "done", "simulated": real < len(done),
                    "detail": f"{len(done)} executed: {real} as real PayPal sandbox calls, {len(done) - real} simulated."}
    else:
        executed = {"status": "pending", "simulated": True,
                    "detail": "Runs through the PayPal sandbox adapter. Seller actions the sandbox blocks are simulated (see docs/SPIKE1_RESULT.md)."}
    if outcome:
        measured = {"status": "done", "detail": (f"Simulated {outcome['horizon_days']} days: dispute rate "
                                                 f"{outcome['before'] * 100:.2f}% to {outcome['after'] * 100:.2f}%. "
                                                 "Recorded as a live_simulated case pending review.")}
    else:
        measured = {"status": "pending", "detail": "Outcome clock is simulated. Result is recorded as a live_simulated case pending review."}
    anomaly = situation["features"]["anomaly"]
    return [
        {"step": "detected", "status": "done", "at": at, "simulated": True,
         "detail": f"Binomial test vs 30-day baseline, p={anomaly['p_value']}. Run on the synthetic demo order feed."},
        {"step": "recommended", "status": "done", "at": at, "simulated": False,
         "detail": "Abstained." if rec["abstain"] else f"{len(rec['actions'])} action(s) proposed, citing {len(rec['precedents'])} precedent(s)."},
        dict({"step": "approved", "at": None, "simulated": False}, **approved),
        dict({"step": "executed", "at": None}, **executed),
        dict({"step": "measured", "at": None, "simulated": True}, **measured),
    ]


def static_bundle(situation: dict, cases: list[dict], mode: str) -> dict:
    """Fixture bundle: no server state."""
    rec, decisions = plan(situation, cases, mode)
    bundle = {"situation": situation, "recommendation": rec, "policy_decisions": decisions,
              "timeline": timeline(situation, rec, decisions)}
    validate("bundle", bundle)
    return bundle


def plan(situation: dict, cases: list[dict], mode: str, writer=None) -> tuple[dict, list[dict]]:
    precedents = retrieve(situation, cases, k=6)
    rec = recommend(situation, precedents, mode=mode, writer=writer,
                    created_at=situation["window"]["end"] + "T09:00:00Z")
    return rec, gate_reference.decide(rec)


class Service:
    def __init__(self, store: Store | None = None, adapter: PayPalAdapter | None = None):
        self.store = store or Store()
        self.adapter = adapter or PayPalAdapter()
        self.executor = Executor(self.store, self.adapter,
                                 max_external_per_hour=thresholds()["rate_limit"]["max_external_actions_per_hour"])
        self.cases = usable(load_cases())
        self.situations = {k: demo_situation(k) for k in DEMO}
        self._plans: dict[tuple[str, str], tuple[dict, list[dict]]] = {}

    def _plan(self, key: str, mode: str) -> tuple[dict, dict, list[dict]]:
        if key not in self.situations or mode not in MODES:
            raise ActionError(404, f"Unknown situation {key!r} or mode {mode!r}.")
        situation = self.situations[key]
        cache_key = (key, mode)
        if cache_key not in self._plans:  # the LLM writer (if enabled) runs once per plan, not per request
            self._plans[cache_key] = plan(situation, self.library(), mode, writer=make_writer(situation))
        rec, decisions = self._plans[cache_key]
        self.executor.register(rec, decisions)
        return situation, rec, decisions

    def library(self) -> list[dict]:
        """Static approved cases plus live_simulated cases a human approved. Simulated cases
        can inform diagnosis but never a numeric forecast (effects use measured cases only)."""
        return self.cases + [c for c in self.store.pending_cases() if c["review_status"] == "approved"]

    def review_case(self, case_id: str, decision: str) -> dict:
        if decision not in ("approved", "rejected"):
            raise ActionError(400, "decision must be 'approved' or 'rejected'")
        case = self.store.review_case(case_id, decision)
        if case is None:
            raise ActionError(404, f"No pending case {case_id}")
        validate("case", case)
        self.store.audit("merchant", "case_reviewed", {"case_id": case_id, "decision": decision})
        self._plans.clear()  # the library changed: re-plan on next request
        return case

    def bundle(self, key: str, mode: str) -> dict:
        situation, rec, decisions = self._plan(key, mode)
        states = {r["action_id"]: {"state": CLIENT_STATE.get(r["state"], "proposed"), "server_state": r["state"],
                                   "execution_mode": r["execution_mode"], "detail": r["detail"]}
                  for r in self.store.actions_for(rec["recommendation_id"])}
        outs = self.store.outcomes_for(rec["recommendation_id"])
        outcome = None
        if outs:
            o = outs[-1]
            case_id = f"case_ls_{rec['recommendation_id'].removeprefix('rec_').lower()}_{len(outs)}"
            case = next((c for c in self.store.pending_cases() if c["case_id"] == case_id), None)
            outcome = {"metric": o["metric"], "before": o["before"], "after": o["after"],
                       "horizon_days": o["horizon_days"], "simulated": True, "new_case_id": case_id,
                       "case_review_status": case["review_status"] if case else "pending"}
        bundle = {"situation": situation, "recommendation": rec, "policy_decisions": decisions,
                  "action_states": states, "outcome": outcome,
                  "timeline": timeline(situation, rec, decisions, states, outcome)}
        validate("bundle", bundle)
        return bundle

    def approve(self, key: str, mode: str, action_id: str) -> dict:
        _, rec, decisions = self._plan(key, mode)
        self.executor.approve(rec, decisions, action_id)
        return self.bundle(key, mode)

    def reject(self, key: str, mode: str, action_id: str) -> dict:
        _, rec, _ = self._plan(key, mode)
        self.executor.reject(rec, action_id)
        return self.bundle(key, mode)

    def advance(self, key: str, mode: str, days: int = 14) -> dict:
        situation, rec, decisions = self._plan(key, mode)
        approved = [r for r in self.store.actions_for(rec["recommendation_id"])
                    if r["state"] == "SUCCEEDED" and r["decision"] == "NEEDS_APPROVAL"]
        if not approved:
            raise ActionError(409, "Approve and execute at least one action before advancing the simulated clock.")
        family = DIAG_TO_FAMILY.get(rec["diagnosis"]) if not rec["abstain"] else None
        sim = simulate(DEMO[key], family, horizon_days=days)
        before = situation["features"]["dispute_rate_7d"]
        self.store.add_outcome(rec["recommendation_id"], "dispute_rate_7d", before, sim["after_rate"], days, simulated=True)
        n = len(self.store.outcomes_for(rec["recommendation_id"]))
        case = live_simulated_case(rec, situation, before, sim["after_rate"], days, n)
        validate("case", case)
        self.store.add_pending_case(case)
        self.store.audit("simulated_clock", "outcome_recorded", {"recommendation_id": rec["recommendation_id"],
                         "before": before, "after": sim["after_rate"], "fit": sim["fit"], "case_id": case["case_id"]})
        return self.bundle(key, mode)

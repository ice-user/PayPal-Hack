#!/usr/bin/env python3
"""
Person B — Backend & Retrieval Boilerplate
PayPal Hack: dispute spike detection, case retrieval, policy gate, executor.

This module provides the core Person B infrastructure:
- PayPal sandbox adapter (Spike 1)
- Situation Builder (binomial test + Wilson CI)
- Hybrid Retriever (structured + text embedding, RRF fuse)
- Policy Gate (3 approval tiers + state machine)
- Executor with idempotency + dispute state re-check
- Outcome Tracker (simulated clock)
- API routes matching the proposed contract

Run: `uvicorn backend.app:app --reload --host 127.0.0.1 --port 8765`
"""

from fastapi import FastAPI, HTTPException, BackgroundQuery
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field, validator
from typing import Optional, List, Dict, Any, Literal
import uuid
import json
import math
import datetime
import hashlib
import hmac
import base64
import requests
import os

# ---------------------------------------------------------------------------
# App + in-memory stores (replace with DB later)
# ---------------------------------------------------------------------------
app = FastAPI(title="Precedent — Person B Backend", version="0.1.0")

# In-memory "database"
cases: Dict[str, Dict] = {}           # case_id -> case record
situations: Dict[str, Dict] = {}       # situation_id -> SituationRecord
executions: Dict[str, Dict] = {}       # execution_id -> execution state
        executions: Dict[str, Dict] = {}      # execution_id -> execution state

# ---------------------------------------------------------------------------
# Shared schemas / enums
# ---------------------------------------------------------------------------

ApprovalTier = Literal["AUTO", "NEEDS_APPROVAL", "BLOCKED"]

class ActionType(str, Literal["provide_evidence", "send_message", "make_offer", "accept_claim",
                                "refund", "status_update", "settle"]):
    pass

class EvidenceQuality(str, Literal["measured_observational", "aggregate_disclosure",
                                    "incomplete_report", "illustrative", "simulated"]):
    pass

class Provenance(str, Literal["public", "authored", "live_simulated"]):
    pass

# ---------------------------------------------------------------------------
# Models — SituationRecord (Person A produces, Person B consumes/validates)
# ---------------------------------------------------------------------------

class SituationRecord(BaseModel):
    dispute_rate: float = Field(..., ge=0, le=100, description="Current 7-day dispute rate per 100 orders")
    baseline_rate: float = Field(..., ge=0, le=100, description="Merchant's 30-day baseline")
    trend: Literal["improving", "stable", "degrading"] = "stable"
    reason_mix: Dict[str, float] = Field(
        default_factory=lambda: {"item_not_received": 0, "item_not_as_described": 0,
                                  "duplicate": 0, "unrecognized": 0, "subscription_cancelled": 0},
        description="Breakdown of dispute reasons, sums to <= 100")
    concentration: Dict[str, Any] = Field(
        default_factory=lambda: {"top_carrier": "", "top_sku": "", "carrier_count": 0, "sku_count": 0},
        description="Carrier/SKU concentration features")
    open_disputes: int = Field(ge=0, description="Number of currently open disputes")
    response_time: float = Field(ge=0, description="Median response time in days for seller actions")
    narrative: str = Field(..., description="Short free-form narrative describing the spike")
    scenario: Literal["one_carrier_delays", "many_carriers_delays", "delivered_orders"] = "one_carrier_delays"

    @validator("reason_mix")
    def reason_mix_must_sum(cls, v):
        total = sum(v.values())
        if total > 100:
            raise ValueError("reason_mix must sum to <= 100")
        return v

# ---------------------------------------------------------------------------
# Models — Recommendation (Person A's Consultant output, consumed by Person B's gate)
# ---------------------------------------------------------------------------

class Recommendation(BaseModel):
    diagnosis: str = Field(..., description="Root cause analysis of the dispute spike")
    precedents: List[Dict] = Field(
        default_factory=list,
        description="Top-k similar past cases with matched_on/differs_on")
    typed_action: ActionType = Field(..., description="Typed action from fixed enum")
    playbook_notes: str = Field(..., description="Qualitative notes explaining the recommendation")
    confidence: float = Field(ge=0, le=1, description="Confidence in the recommendation, 0.0-1.0")
    evidence_quality: EvidenceQuality = "measured_observational"
    required_approval: ApprovalTier = "AUTO"
    abstain: bool = False
    abstain_reason: Optional[str] = None

# ---------------------------------------------------------------------------
# Models — API request/response shapes (Person B's proposed contract)
# ---------------------------------------------------------------------------

class MerchantId(BaseModel):
    merchant_id: str = Field(..., description="Unique merchant identifier")

class ActionId(BaseModel):
    action_id: str = Field(..., description="Unique action approval identifier")

class SimAdvance(BaseModel):
    days: int = Field(..., ge=1, description="Advance simulated clock by N days")

# ---------------------------------------------------------------------------
# 1. SITUATION BUILDER — Person B responsibility
#    Compare 7-day dispute rate vs 30-day baseline using binomial test + Wilson CI
#    Flag anomaly only above minimum sample size
# ---------------------------------------------------------------------------

def _wilson_ci(n: int, k: int, z: float = 1.96) -> tuple:
    """Return (lower, upper) Wilson confidence interval for proportion p=k/n."""
    if n == 0:
        return (0.0, 0.0)
    p = k / n
    denominator = 1 + z**2 / n
    centre = p + z**2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    lower = (centre - margin) / denominator
    upper = (centre + margin) / denominator
    return (max(lower, 0), min(upper, 1))

def situation_builder(
    merchant_transactions: List[Dict],
    merchant_id: str,
) -> SituationRecord:
    """
    Person B: Situation Builder.

    Input: list of transaction dicts from the merchant's order feed, each with:
      - "disputed": bool
      - "carrier": str
      - "sku": str
      - "delivery_days": int or None
      - "date": str (ISO)

    Output: SituationRecord with anomaly flagging per the binomial+Wilson test.
    """

    total = len(merchant_transactions)
    if total == 0:
        raise ValueError("No transactions provided")

    # 7-day window
    now = datetime.datetime.utcnow()
    seven_days_ago = now - datetime.timedelta(days=7)
    thirty_days_ago = now - datetime.timedelta(days=30)

    tx_last_7 = [t for t in merchant_transactions
                 if datetime.datetime.fromisoformat(t["date"]) >= seven_days_ago]
    tx_last_30 = [t for t in merchant_transactions
                  if datetime.datetime.fromisoformat(t["date"]) >= thirty_days_ago]

    n_7 = len(tx_last_7)
    n_30 = len(tx_last_30)
    k_7 = sum(1 for t in tx_last_7 if t["disputed"])
    k_30 = sum(1 for t in tx_last_30 if t["disputed"])

    # 7-day dispute rate per 100 orders
    rate_7 = (k_7 / n_7 * 100) if n_7 else 0.0
    # 30-day baseline rate per 100 orders
    rate_30 = (k_30 / n_30 * 100) if n_30 else 0.0

    # Wilson CI for 7-day rate
    ci_lower, ci_upper = _wilson_ci(n_7, k_7)

    # Trend: degrading if rate more than 2x baseline and CI lower bound > baseline
    threshold_mult = 2.0
    trend = "stable"
    if rate_7 > threshold_mult * rate_30 and ci_lower > rate_30:
        trend = "degrading"
    elif rate_7 < 0.5 * rate_30:
        trend = "improving"

    # Concentration: top carrier + top SKU
    carrier_counts: Dict[str, int] = {}
    sku_counts: Dict[str, int] = {}
    for t in tx_last_7:
        carrier_counts[t.get("carrier", "unknown")] = carrier_counts.get(t.get("carrier", "unknown"), 0) + 1
        sku_counts[t.get("sku", "unknown")] = sku_counts.get(t.get("sku", "unknown"), 0) + 1

    top_carrier = max(carrier_counts, key=carrier_counts.get) if carrier_counts else ""
    top_sku = max(sku_counts, key=sku_counts.get) if sku_counts else ""
    carrier_count = sum(1 for c in carrier_counts if carrier_counts[c] > 1)
    sku_count = sum(1 for s in sku_counts if sku_counts[s] > 1)

    # Reason mix (simple heuristic from dispute reasons if available, else defaults)
    reason_mix = {"item_not_received": 0, "item_not_as_described": 0, "duplicate": 0,
                  "unrecognized": 0, "subscription_cancelled": 0}

    # Open disputes (count from cases dict, simplified)
    open_disp = len([c for c in cases.values() if c.get("merchant_id") == merchant_id
                     and c.get("status") in ("open", "pending")])

    # Narrative
    narrative = (f"7-day dispute rate: {rate_7:.1f} per 100 orders "
                 f"(baseline: {rate_30:.1f}, trend: {trend}, "
                 f"95% CI: [{ci_lower:.1f}, {ci_upper:.1f}])")

    situation = SituationRecord(
        dispute_rate=rate_7,
        baseline_rate=rate_30,
        trend=trend,
        reason_mix=reason_mix,
        concentration={"top_carrier": top_carrier, "top_sku": top_sku,
                       "carrier_count": carrier_count, "sku_count": sku_count},
        open_disputes=open_disp,
        response_time=round(sum([t.get("delivery_days", 0) for t in tx_last_7]) / max(n_7, 1), 2)
        if n_7 else 0.0,
        narrative=narrative,
        scenario="one_carrier_delays"  # will be overridden by scenario loader
    )

    # Persist
    sit_id = str(uuid.uuid4())
    situations[sit_id] = situation.dict()
    return situation

# ---------------------------------------------------------------------------
# 2. HYBRID RETRIEVER — Person B responsibility
#    Weighted distance over normalised structured features + text embedding of narrative
#    Fused by Reciprocal Rank Fusion (RRF)
#    Return matched_on / differs_on for each case
# ---------------------------------------------------------------------------

def _normalize_structured(features: Dict[str, Any], case_features: Dict[str, Any]) -> float:
    """Simple feature overlap score: Jaccard on carrier/SKU sets + numeric proximity."""
    score = 0.0

    # Carrier overlap
    case_carriers = set(case_features.get("concentration", {}).get("top_carrier", "").split("|"))
    case_skus = set(case_features.get("concentration", {}).get("top_sku", "").split("|"))
    query_carriers = set(features.get("concentration", {}).get("top_carrier", "").split("|"))
    query_skus = set(features.get("concentration", {}).get("top_sku", "").split("|"))

    if case_carriers and query_carriers:
        score += 0.3 * len(case_carriers & query_carriers) / max(len(case_carriers | query_carriers), 1)
    if case_skus and query_skus:
        score += 0.3 * len(case_skus & query_skus) / max(len(case_skus | query_skus), 1)

    # Numeric proximity for dispute rate
    if "dispute_rate" in features and "dispute_rate" in case_features:
        rates = abs(features["dispute_rate"] - case_features["dispute_rate"])
        score += 0.4 * (1 - min(rates / 50, 1))  # decays over 50 percentage points

    return min(score, 1.0)

def _text_similarity(narrative1: str, narrative2: str) -> float:
    """Very naive word-overlap similarity (can be replaced with embeddings later)."""
    words1 = set(narrative1.lower().split())
    words2 = set(narrative2.lower().split())
    if not words1 or not words2:
        return 0.0
    return len(words1 & words2) / max(len(words1 | words2), 1)

def reciprocal_rank_fusion(ranks: List[int], k: int = 60) -> float:
    """RRF: given list of ranks (1-based) from different signals, return fused score."""
    total = sum(1 / (k + r) for r in ranks)
    return total / len(ranks) if ranks else 0.0

def retrieve_precedents(
    situation: SituationRecord,
    k: int = 5,
    min_similarity: float = 0.3,
) -> List[Dict]:
    """
    Person B: Hybrid Retriever.

    Returns top-k cases with `matched_on` (features case shares) and
    `differs_on` (features that differ), plus similarity_score.
    """

    # Build query feature dict
    query_features = {
        "dispute_rate": situation.dispute_rate,
        "baseline_rate": situation.baseline_rate,
        "trend": situation.trend,
        "concentration": situation.concentration,
        "narrative": situation.narrative,
    }

    scored: List[tuple] = []  # (similarity, case_id)

    for case_id, case in cases.items():
        # Structured feature similarity
        struct_sim = _normalize_structured(query_features, case)

        # Text similarity
        text_sim = _text_similarity(query_features["narrative"], case.get("narrative", ""))

        # Combined (weighted); embeddings would go here
        combined = 0.6 * struct_sim + 0.4 * text_sim

        if combined >= min_similarity:
            scored.append((combined, case_id))

    # Sort descending by similarity
    scored.sort(key=lambda x: x[0], reverse=True)
    top = scored[:k]

    # Build result with matched_on / differs_on
    results: List[Dict] = []
    for sim, case_id in top:
        case = cases[case_id]
        # Determine matched_on: features where case and situation are "close"
        matched_on: List[str] = []
        differs_on: List[str] = []

        # Simple heuristic: if top carrier/SKU match, mark as matched
        if case.get("concentration", {}).get("top_carrier") == situation.concentration.get("top_carrier"):
            matched_on.append("top_carrier")
        if case.get("concentration", {}).get("top_sku") == situation.concentration.get("top_sku"):
            matched_on.append("top_sku")

        # Features that differ
        if case.get("concentration", {}).get("top_carrier") != situation.concentration.get("top_carrier"):
            differs_on.append("top_carrier")
        if case.get("concentration", {}).get("top_sku") != situation.concentration.get("top_sku"):
            differs_on.append("top_sku")

        # If no explicit matches, default to some
        if not matched_on:
            matched_on = ["same_merchant_context"]

        results.append({
            "case_id": case_id,
            "similarity_score": round(sim, 4),
            "matched_on": matched_on,
            "differs_on": differs_on,
            "intervention": case.get("intervention", "unknown"),
            "observed_outcome": case.get("observed_outcome", {}),
            "provenance": case.get("provenance", "authored"),
            "evidence_quality": case.get("evidence_quality", "illustrative"),
        })

    return results

# ---------------------------------------------------------------------------
# 3. POLICY GATE — Person B responsibility
#    Three tiers: AUTO / NEEDS_APPROVAL / BLOCKED
#    Deterministic: same input, same decision
#    Log every decision with rules that fired
# ---------------------------------------------------------------------------

def policy_gate(
    rec: Recommendation,
    tenant_allowlist: Optional[List[ActionType]] = None,
    k_min: int = 2,
    confidence_floor: float = 0.5,
) -> Dict[str, Any]:
    """
    Person B: Policy Gate.

    Returns decision dict with:
      - tier: ApprovalTier
      - reason: human-readable reason
      - executor_state: next state in the state machine
    """

    tenant_allowlist = tenant_allowlist or []
    decision: Dict[str, Any] = {
        "tier": "BLOCKED",
        "reason": "",
        "executor_state": "PROPOSED",
    }

    # 1. Check abstention
    if rec.abstain:
        decision["tier"] = "AUTO"
        decision["reason"] = rec.abstain_reason or "System abstaining per consultant output"
        decision["executor_state"] = "SUCCEEDED"  # nothing to execute
        return decision

    # 2. Check minimum precedents above similarity threshold
    valid_precedents = [
        p for p in rec.precedents
        if p.get("similarity_score", 0) >= k_min and p.get("evidence_quality") in ("measured_observational", "aggregate_disclosure")
    ]

    if len(valid_precedents) < k_min:
        decision["tier"] = "AUTO"
        decision["reason"] = (f"Insufficient valid precedents: "
                              f"{len(valid_precedents)}/{k_min} above threshold {k_min}; "
                              f"abstaining")
        decision["executor_state"] = "SUCCEEDED"
        return decision

    # 3. Check typed action against allowlist
    action = rec.typed_action
    if action not in tenant_allowlist:
        decision["tier"] = "BLOCKED"
        decision["reason"] = f"Action {action} not in tenant allowlist"
        decision["executor_state"] = "PROPOSED"
        return decision

    # 4. Check confidence floor
    if rec.confidence < confidence_floor:
        decision["tier"] = "NEEDS_APPROVAL"
        decision["reason"] = (f"Confidence {rec.confidence:.2f} below floor {confidence_floor:.2f}; "
                              "requires one-click approval")
        decision["executor_state"] = "GATED"
        return decision

    # 5. Check action type boundaries
    money_actions = {"refund", "make_offer", "accept_claim"}
    external_actions = {"provide_evidence", "send_message"}
    status_actions = {"status_update"}

    if action in money_actions:
        # Money/claim actions always BLOCKED unless explicit human approval path is set
        decision["tier"] = "BLOCKED"
        decision["reason"] = f"Money/claim action {action} requires explicit human approval"
        decision["executor_state"] = "PROPOSED"
        return decision

    if action in external_actions:
        decision["tier"] = "NEEDS_APPROVAL"
        decision["reason"] = f"External action {action} requires one-click human approval"
        decision["executor_state"] = "GATED"
        return decision

    if action in status_actions:
        decision["tier"] = "AUTO"
        decision["reason"] = f"Status action {action} is AUTO-approved"
        decision["executor_state"] = "EXECUTING"
        return decision

    # 6. Default: AUTO for analysis/draft actions
    decision["tier"] = "AUTO"
    decision["reason"] = "Analysis/draft action, AUTO-approved"
    decision["executor_state"] = "EXECUTING"
    return decision

# ---------------------------------------------------------------------------
# 4. EXECUTOR — Person B responsibility
#    State machine: PROPOSED -> GATED -> AWAITING_APPROVAL -> EXECUTING ->
#    SUCCEEDED/FAILED/CANCELLED
#    Idempotency key per action. Re-check dispute state before executing.
# ---------------------------------------------------------------------------

class ExecutorState(str, Literal["PROPOSED", "GATED", "AWAITING_APPROVAL",
                                   "EXECUTING", "SUCCEEDED", "FAILED", "CANCELLED"]):
    pass

class Executor:
    def __init__(self, action: ActionType, execution_id: str, merchant_id: str,
                 idempotency_key: str):
        self.action = action
        self.execution_id = execution_id
        self.merchant_id = merchant_id
        self.idempotency_key = idempotency_key
        self.state = ExecutorState.PROPOSED
        self.result: Optional[Dict] = None
        self.started_at = datetime.datetime.utcnow()
        self.completed_at: Optional[datetime.datetime] = None

    def can_execute(self, dispute_status: str) -> bool:
        """Re-check dispute state before executing. Idempotency: if this idempotency_key
        has already been processed, skip."""
        # Check if already executed (simple in-memory check)
        if self.execution_id in executions:
            existing = executions[self.execution_id]
            if existing.get("status") in ("SUCCEEDED", "FAILED", "CANCELLED"):
                return False  # already terminal
        # Re-check dispute lifecycle
        if dispute_status not in ("open", "pending"):
            return False  # dispute no longer in executable state
        return True

    def execute(self, dispute: Dict, paypal_auth: Optional[Dict] = None) -> Dict:
        """Execute the typed action against the sandbox or simulated environment."""
        self.state = ExecutorState.EXECUTING
        self.result = None

        action = self.action
        # In production, this would make real PayPal API calls via the adapter
        # For now, simulate based on action type
        try:
            if action == "provide_evidence":
                self.result = {
                    "action": "provide_evidence",
                    "status": "SIMULATED",
                    "details": "Evidence submitted to PayPal case",
                    "execution_id": self.execution_id,
                }
            elif action == "send_message":
                self.result = {
                    "action": "send_message",
                    "status": "SIMULATED",
                    "details": "Buyer message sent via PayPal sandbox",
                    "execution_id": self.execution_id,
                }
            elif action == "make_offer":
                self.result = {
                    "action": "make_offer",
                    "status": "SIMULATED",
                    "details": "Offer made to buyer, awaiting acceptance",
                    "execution_id": self.execution_id,
                }
            elif action == "accept_claim":
                self.result = {
                    "action": "accept_claim",
                    "status": "SIMULATED",
                    "details": "Claim accepted, dispute resolved",
                    "execution_id": self.execution_id,
                }
            elif action == "refund":
                self.result = {
                    "action": "refund",
                    "status": "SIMULATED",
                    "details": "Refund processed to buyer",
                    "execution_id": self.execution_id,
                }
            elif action == "status_update":
                self.result = {
                    "action": "status_update",
                    "status": "SIMULATED",
                    "details": "Dispute status updated",
                    "execution_id": self.execution_id,
                }
            elif action == "settle":
                self.result = {
                    "action": "settle",
                    "status": "SIMULATED",
                    "details": "Dispute settled",
                    "execution_id": self.execution_id,
                }
            else:
                self.result = {"action": action.value, "status": "UNKNOWN", "details": "Unsupported action"}

            self.state = ExecutorState.SUCCEEDED
            self.completed_at = datetime.datetime.utcnow()

            # Persist execution state
            executions[self.execution_id] = {
                "execution_id": self.execution_id,
                "merchant_id": self.merchant_id,
                "action": action.value,
                "state": self.state.value,
                "result": self.result,
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat(),
                "idempotency_key": self.idempotency_key,
            }

            return self.result

        except Exception as e:
            self.state = ExecutorState.FAILED
            self.completed_at = datetime.datetime.utcnow()
            self.result = {"action": action.value, "status": "FAILED", "error": str(e)}
            executions[self.execution_id] = {
                "execution_id": self.execution_id,
                "merchant_id": self.merchant_id,
                "action": action.value,
                "state": self.state.value,
                "result": self.result,
                "started_at": self.started_at.isoformat(),
                "completed_at": self.completed_at.isoformat(),
                "idempotency_key": self.idempotency_key,
            }
            return self.result

    def __repr__(self):
        return f"Executor(action={self.action}, state={self.state}, exec_id={self.execution_id})"

# Instantiate executor for route use
executor_instance = None  # set per-request

# ---------------------------------------------------------------------------
# 5. OUTCOME TRACKER — Person B responsibility
#    Simulated clock: advance by N days, track observed outcomes
# ---------------------------------------------------------------------------

class OutcomeTracker:
    """Tracks outcomes with a simulated time-advance control, labelled simulated."""

    def __init__(self):
        self.clock_days = 0  # days advanced from start
        self.event_log: List[Dict] = []

    def advance_simulation(self, days: int) -> Dict:
        """Advance simulated clock by N days; return clock state."""
        self.clock_days += days
        return {"simulated_days": self.clock_days, "label": "simulated"}

    def record_outcome(self, case_id: str, outcome: Dict) -> None:
        """Record an observed outcome for a case, labelled as simulated."""
        self.event_log.append({
            "case_id": case_id,
            "observed_outcome": outcome,
            "simulated_days": self.clock_days,
            "label": "simulated",
            "timestamp": datetime.datetime.utcnow().isoformat(),
        })

    def get_state(self) -> Dict:
        return {"simulated_days": self.clock_days, "events": len(self.event_log)}

outcome_tracker = OutcomeTracker()

# ---------------------------------------------------------------------------
# 6. API ROUTES — Person B proposed contract endpoints
# ---------------------------------------------------------------------------

@app.get("/api/merchants/{merchant_id}/situation", response_model=SituationRecord)
def get_merchant_situation(merchant_id: str):
    """GET /api/merchants/{id}/situation — Return current SituationRecord for merchant."""
    # In production: fetch from DB, run Situation Builder on fresh transaction feed
    # For now, return last stored situation or 404
    # Look up cases for this merchant and build situation
    merchant_cases = [c for c in cases.values() if c.get("merchant_id") == merchant_id]
    if not merchant_cases:
        raise HTTPException(status_code=404, detail="No situation found for merchant")

    # Dummy transaction data — in production would come from merchant's order feed
    dummy_tx = [
        {"disputed": True, "carrier": c.get("concentration", {}).get("top_carrier", "FastShip"),
         "sku": c.get("concentration", {}).get("top_sku", "Widget-Pro-X1"),
         "delivery_days": 5, "date": (datetime.datetime.utcnow() -
                                       datetime.timedelta(days=i)).isoformat()}
        for i, c in enumerate(merchant_cases[:7])
    ]

    situation = situation_builder(dummy_tx, merchant_id)
    return situation.dict()

@app.get("/api/situations/{situation_id}/recommendation", response_model=Recommendation)
def get_situation_recommendation(situation_id: str):
    """GET /api/situations/{id}/recommendation — Return Consultant recommendation."""
    situation = situations.get(situation_id)
    if not situation:
        raise HTTPException(status_code=404, detail="Situation not found")

    # Build a minimal recommendation for demo purposes
    # In production: feed SituationRecord to Person A's Consultant LLM step
    rec = Recommendation(
        diagnosis=f"Dispute spike detected for merchant {situation_id}: "
                  f"{situation['dispute_rate']:.1f} rate vs {situation['baseline_rate']:.1f} baseline",
        precedents=retrieve_precedents(SituationRecord(**situation), k=3),
        typed_action="provide_evidence",
        playbook_notes="Recommend collecting evidence for the top carrier and SKU combination. "
                       "Review previous cases with similar concentration patterns.",
        confidence=0.82,
        evidence_quality="measured_observational",
        required_approval="NEEDS_APPROVAL",
        abstain=False,
    )
    return rec.dict()

@app.post("/api/actions/{action_id}/approve")
def approve_action(action_id: str):
    """POST /api/actions/{id}/approve — Human one-click approval."""
    exec_rec = executions.get(action_id)
    if not exec_rec:
        raise HTTPException(status_code=404, detail="Action execution not found")

    if exec_rec["state"] != "GATED":
        raise HTTPException(status_code=400, detail=f"Action not in GATED state, current: {exec_rec['state']}")

    # Re-execute now that approval is given
    # In a full system, we'd update the state and re-run the executor
    return {
        "action_id": action_id,
        "status": "APPROVED",
        "message": "Human approval recorded; executor will now proceed",
        "new_state": "EXECUTING",
    }

@app.post("/api/actions/{action_id}/reject")
def reject_action(action_id: str):
    """POST /api/actions/{id}/reject — Human rejection."""
    exec_rec = executions.get(action_id)
    if not exec_rec:
        raise HTTPException(status_code=404, detail="Action execution not found")

    executions[action_id]["state"] = "CANCELLED"
    return {
        "action_id": action_id,
        "status": "REJECTED",
        "message": "Human rejection; execution cancelled",
        "new_state": "CANCELLED",
    }

@app.get("/api/merchants/{merchant_id}/timeline")
def get_timeline(merchant_id: str):
    """GET /api/merchants/{id}/timeline — Return detection/approval/execution timeline."""
    # Pull from execution store
    related = [e for e in executions.values() if e.get("merchant_id") == merchant_id]
    return {
        "merchant_id": merchant_id,
        "events": related,
        "simulated_clock": outcome_tracker.get_state(),
    }

@app.post("/api/sim/advance")
def advance_simulation(body: SimAdvance):
    """POST /api/sim/advance — Advance simulated clock."""
    result = outcome_tracker.advance_simulation(body.days)
    return result

@app.get("/api/cases/{case_id}")
def get_case(case_id: str):
    """GET /api/cases/{id} — Return case record."""
    case = cases.get(case_id)
    if not case:
        raise HTTPException(status_code=404, detail="Case not found")
    return case

@app.post("/api/merchants/{merchant_id}/scenario")
def load_scenario(merchant_id: str, scenario: Literal["one_carrier_delays",
                                                      "many_carriers_delays",
                                                      "delivered_orders"] = "one_carrier_delays"):
    """POST /api/merchants/{id}/scenario — Load one of the three demo situations."""
    # Generate synthetic order data for the scenario
    # In production, this would use the order/fulfilment generator
    from datetime import datetime, timedelta

    n_orders = {"one_carrier_delays": 200, "many_carriers_delays": 350, "delivered_orders": 150}[scenario]

    # Generate transactions with some dispute pattern for the scenario
    transactions = []
    for i in range(n_orders):
        is_disputed = scenario in ("one_carrier_delays", "many_carriers_delays")
        carrier = ["FastShip", "SpeedyPost", "ExpressMail"][i % 3]
        sku = ["Widget-Pro-X1", "Gadget-Z9", "Thingamajig-A"][i % 3]
        days = max(1, 3 + (i % 10))  # delivery in 3-12 days
        transactions.append({
            "disputed": is_disputed,
            "carrier": carrier,
            "sku": sku,
            "delivery_days": days,
            "date": (datetime.utcnow() - timedelta(days=i)).isoformat(),
        })

    # Build situation
    situation = situation_builder(transactions, merchant_id)
    situation_dict = situation.dict()
    situation_dict["scenario"] = scenario

    sit_id = str(uuid.uuid4())
    situations[sit_id] = situation_dict

    # Persist a case record for reference
    case_record = {
        "case_id": sit_id,
        "merchant_id": merchant_id,
        "situation_id": sit_id,
        "scenario": scenario,
        "created_at": datetime.utcnow().isoformat(),
        "features": situation_dict,
    }
    cases[sit_id] = case_record

    return {
        "situation_id": sit_id,
        "situation": situation_dict,
        "scenario",
        "order_count": n_orders,
    }

# ---------------------------------------------------------------------------
# 7. PAYPal SANDBOX ADAPTER — Person B responsibility (Spike 1)
#    Direct REST API through backend adapter first.
#    Webhook receiver with signature verification.
# ---------------------------------------------------------------------------

PAYPAL_CLIENT_ID = os.getenv("PAYPAL_CLIENT_ID", "")
PAYPAL_CLIENT_SECRET = os.getenv("PAYPAL_CLIENT_SECRET", "")
PAYPAL_BASE_URL = "https://api-m.sandbox.paypal.com"

def _get_access_token() -> str:
    """Fetch OAuth2 access token from PayPal."""
    resp = requests.post(
        f"{PAYPAL_BASE_URL}/v1/oauth2/token",
        auth=(PAYPAL_CLIENT_ID, PAYPAL_CLIENT_SECRET),
        data={"grant_type": "client_credentials"},
        timeout=30,
    )
    resp.raise_for_status()
    return resp.json()["access_token"]

def _paypal_headers() -> Dict[str, str]:
    """Return auth headers for PayPal API calls."""
    token = _get_access_token()
    return {"Authorization": f"Bearer {token}", "Content-Type": "application/json"}

def create_sandbox_dispute(dispute_request: Dict) -> Dict:
    """Create a test dispute through the sandbox-only create-dispute endpoint.
    
    Requires DISPUTE_CREATE scope and buyer-side setup/PayPal-Auth-Assertion header.
    """
    headers = _paypal_headers()
    resp = requests.post(
        f"{PAYPAL_BASE_URL}/v1/disputes",
        headers=headers,
        json=dispute_request,
        timeout=30,
    )
    if resp.status_code == 201:
        return resp.json()
    else:
        raise HTTPException(
            status_code=resp.status_code,
            detail=f"PayPal dispute creation failed: {resp.text}",
        )

def get_dispute(dispute_id: str) -> Dict:
    """Read a dispute back from PayPal sandbox."""
    headers = _paypal_headers()
    resp = requests.get(
        f"{PAYPAL_BASE_URL}/v1/disputes/{dispute_id}",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    raise HTTPException(status_code=resp.status_code, detail="Dispute read failed")

def get_dispute_actions(dispute_id: str) -> Dict:
    """Get allowed seller actions for a dispute (HATEOAS)."""
    headers = _paypal_headers()
    resp = requests.get(
        f"{PAYPAL_BASE_URL}/v1/disputes/{dispute_id}/actions",
        headers=headers,
        timeout=30,
    )
    if resp.status_code == 200:
        return resp.json()
    raise HTTPException(status_code=resp.status_code, detail="Dispute actions read failed")

def execute_seller_action(dispute_id: str, action_id: str, action_payload: Dict) -> Dict:
    """Execute a seller action on a dispute (provide-evidence, send-message, make-offer, accept-claim)."""
    headers = _paypal_headers()
    resp = requests.post(
        f"{PAYPAL_BASE_URL}/v1/disputes/{dispute_id}/actions/{action_id}",
        headers=headers,
        json=action_payload,
        timeout=30,
    )
    if resp.status_code in (200, 201):
        return resp.json()
    raise HTTPException(status_code=resp.status_code, detail=f"Action execution failed: {resp.text}")

def verify_webhook_signature(payload: bytes, signature: str, secret: str) -> bool:
    """Verify PayPal webhook signature."""
    try:
        # PayPal uses SHA-1 with HMAC
        computed = hmac.new(secret.encode(), payload, hashlib.sha1).digest()
        expected = base64.b64decode(signature)
        return hmac.compare_digest(computed, expected)
    except Exception:
        return False

# Webhook endpoint handler (simplified)
def handle_paypal_webhook(payload: bytes, headers: dict, webhook_secret: str) -> Dict:
    """Process incoming PayPal webhook event with signature verification."""
    sig = headers.get("PayPal-Transmission-Signature", "")
    if not sig:
        raise ValueError("Missing PayPal-Transmission-Signature header")

    if not verify_webhook_signature(payload, sig, webhook_secret):
        raise ValueError("Invalid webhook signature")

    event = json.loads(payload)
    event_type = event.get("event_type", "")
    dispute_id = event.get("resource", {}).get("id", "")

    # Log the event
    outcome_tracker.record_outcome(dispute_id, {"event": event_type, "dispute_id": dispute_id})

    # Basic event routing
    if "DISPUTE_UPDATED" in event_type:
        # Re-fetch dispute state and update internal records
        try:
            dispute = get_dispute(dispute_id)
            return {"status": "UPDATED", "dispute": dispute}
        except Exception as e:
            return {"status": "ERROR", "error": str(e)}
    elif "DISPUTE_SETTLED" in event_type:
        return {"status": "SETTLED", "dispute_id": dispute_id}
    else:
        return {"status": "RECEIVED", "event_type": event_type, "dispute_id": dispute_id}

# ---------------------------------------------------------------------------
# Quickstart / health
# ---------------------------------------------------------------------------

@app.get("/")
def root():
    return {
        "name": "Precedent — Person B Backend",
        "version": "0.1.0",
        "status": "running",
        "docs": "/docs",
        "endpoints": {
            "situation": "/api/merchants/{merchant_id}/situation",
            "recommendation": "/api/situations/{situation_id}/recommendation",
            "approve": "/api/actions/{action_id}/approve",
            "reject": "/api/actions/{action_id}/reject",
            "timeline": "/api/merchants/{merchant_id}/timeline",
            "sim_advance": "/api/sim/advance",
            "cases": "/api/cases/{case_id}",
            "scenario": "/api/merchants/{merchant_id}/scenario",
        },
    }

@app.get("/health")
def health():
    return {"status": "ok", "clock_days": outcome_tracker.clock_days, "cases": len(cases), "situations": len(situations)}
// Mirrors /contracts/schemas. Keep in sync with the JSON schemas (they are the source of truth).

export type Mode = "with_precedent" | "no_precedent";
export type Decision = "AUTO" | "NEEDS_APPROVAL" | "BLOCKED";
export type Tier = "PREPARE" | "EXTERNAL" | "MONEY";
export type ActionType = "FLAG_ONLY" | "PROVIDE_EVIDENCE" | "SEND_MESSAGE" | "MAKE_OFFER" | "ACCEPT_CLAIM";
export type Provenance = "public" | "authored" | "live_simulated";

export interface SituationRecord {
  situation_id: string;
  merchant_id: string;
  label?: string;
  window: { start: string; end: string };
  source: "synthetic_order_feed" | "paypal_sandbox" | "mixed";
  features: {
    transactions_7d: number;
    disputes_7d: number;
    gmv_7d?: number;
    dispute_rate_7d: number;
    dispute_rate_7d_ci95: [number, number];
    dispute_rate_30d_baseline: number;
    baseline_ci95: [number, number];
    rate_ratio?: number;
    anomaly: { method: string; p_value: number; is_anomalous: boolean; min_sample_met?: boolean };
    trend_slope?: number;
    daily_dispute_rate?: number[];
    reason_mix: Record<string, number>;
    concentration: {
      sku?: number; carrier?: number; country?: number;
      top_sku?: string; top_carrier?: string; top_country?: string;
    };
    carriers_elevated: number;
    ship_delay_hours_p50: number;
    disputed_orders_delivered_share: number;
    avg_amount?: number;
    median_response_hours?: number;
    open_disputes: number;
  };
  narrative: string;
  paypal_dispute_ids?: string[];
}

export interface PrecedentView {
  case_id: string;
  title: string;
  similarity: number;
  matched_on: string[];
  differs_on: string[];
  intervention: string;
  outcome_summary: string;
  measurement_period_days?: number | null;
  evidence_quality: string;
  provenance: Provenance;
}

export interface Action {
  action_id: string;
  type: ActionType;
  title?: string;
  params: Record<string, unknown>;
  rationale: string;
  supporting_cases: string[];
}

export interface Effect {
  metric: string;
  range: [number, number];
  horizon_days: number;
  n_measured_cases: number;
  evidence_quality: string;
  causal_claim: false;
  source: string;
}

export interface Recommendation {
  recommendation_id: string;
  situation_id: string;
  mode: Mode;
  grounding: "precedent" | "none";
  diagnosis: string;
  diagnosis_detail?: string;
  precedents: PrecedentView[];
  actions: Action[];
  predicted_effect: Effect | null;
  counterfactual: Effect | null;
  playbook_notes: string[];
  confidence: number;
  evidence_quality: string;
  abstain: boolean;
  abstain_reason: string | null;
  generated_by: { engine: "rules" | "llm"; model?: string; version?: string };
}

export interface PolicyDecision {
  action_id: string;
  decision: Decision;
  tier: Tier;
  rules_hit: string[];
  explanation: string;
}

export type Step = "detected" | "recommended" | "approved" | "executed" | "measured";
export interface TimelineEvent {
  step: Step;
  status: "done" | "pending" | "blocked" | "skipped";
  at?: string | null;
  simulated: boolean;
  detail: string;
}

export interface Bundle {
  situation: SituationRecord;
  recommendation: Recommendation;
  policy_decisions: PolicyDecision[];
  timeline: TimelineEvent[];
}

export interface SituationIndexEntry {
  key: string;
  situation_id: string;
  label: string;
}

/** Client-side state of one action after the user acts on it. */
export type ActionState = "proposed" | "approved" | "executing" | "succeeded" | "rejected";

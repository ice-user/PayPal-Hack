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
    diagnostic_conflict?: {
      kind: "fulfilment_and_prompt_shipment_losses";
      prompt_ship_hours: number;
      window_orders: number;
      window_lost_inr: number;
      baseline_orders: number;
      baseline_lost_inr: number;
      method: "fisher_exact_one_sided";
      p_value: number;
    };
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
  triage?: Triage;
}

/** Dispute-level triage (TechKart test environment). Its actions are also in `actions`. */
export interface TriageGroup {
  response: string;
  label: string;
  states: string[];
  count: number;
  total_value: number;
  earliest_due: string;
  action_ids: string[];
  cites: string[];
  warnings: string[];
  confidence: number;
  /** True when these disputes were imported from the connected PayPal sandbox account. */
  paypal?: boolean;
}
export interface TriageRow {
  dispute_id: string;
  order_id: string;
  carrier: string;
  sku: string;
  amount: number;
  status: "delivered" | "in_transit" | "lost" | "unknown";
  proof: string;
  expected_delivery: string | null;
  response_due: string;
  response: string;
  paypal?: boolean;
}
export interface Triage {
  groups: TriageGroup[];
  rows: TriageRow[];
  precedents: { case_id: string; title: string; response: string; appropriate: boolean; outcome: string }[];
  untriaged: number;
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

export interface ServerActionState {
  state: ActionState;
  server_state: string;
  execution_mode?: "real" | "simulated" | null;
  detail?: string | null;
}

export interface Outcome {
  metric: string;
  before: number;
  after: number;
  horizon_days: number;
  simulated: true;
  new_case_id?: string;
  case_review_status?: "pending" | "approved" | "rejected";
}

export interface Bundle {
  situation: SituationRecord;
  recommendation: Recommendation;
  policy_decisions: PolicyDecision[];
  timeline: TimelineEvent[];
  action_states?: Record<string, ServerActionState>;
  outcome?: Outcome | null;
  paypal?: PayPalAccount;
}

/** A dispute on the connected PayPal sandbox account, as imported by the backend. */
export interface PayPalDispute {
  dispute_id: string;
  reason: string | null;
  status: string;
  stage: string | null;
  amount: { currency_code: string; value: string } | null;
  created: string | null;
  response_due: string;
  allowed: string[];
  item: string;
  transaction_id: string;
  shipment_status: "delivered" | "in_transit" | "lost" | "unknown";
  tracker_status: string | null;
  tracking_number: string | null;
  triaged: boolean;
}

export interface PayPalAccount {
  connected: boolean;
  fetched_at: string | null;
  error: string | null;
  host?: string;
  disputes: PayPalDispute[];
  /** Action types this deployment runs for real (["ALL"] = every type), or null when none. */
  real_actions?: string[] | null;
  real_calls_per_hour?: number | null;
}

export interface PayPalCall {
  at: string;
  method: string;
  path: string;
  status: number;
  ms: number;
}

export interface LiveDispute {
  dispute_id: string;
  status: string;
  dispute_state: string | null;
  stage: string | null;
  allowed: string[];
  update_time?: string;
}

export interface SituationIndexEntry {
  key: string;
  situation_id: string;
  label: string;
}

/** Client-side state of one action after the user acts on it. */
export type ActionState = "proposed" | "approved" | "executing" | "succeeded" | "failed" | "rejected";

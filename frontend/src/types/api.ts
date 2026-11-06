// Frontend types matching the API contracts
// These mirror contracts/SituationRecord.schema.json and contracts/Recommendation.schema.json

export interface ReasonMix {
  item_not_received: number;
  item_not_as_described: number;
  duplicate: number;
  unrecognized: number;
  subscription_cancelled: number;
}

export interface Concentration {
  top_carrier: string;
  top_sku: string;
  carrier_count: number;
  sku_count: number;
}

export type Scenario = "one_carrier_delays" | "many_carriers_delays" | "delivered_orders";
export type Trend = "improving" | "stable" | "degrading";

export interface SituationRecord {
  dispute_rate: number;
  baseline_rate: number;
  trend: Trend;
  reason_mix: ReasonMix;
  concentration: Concentration;
  open_disputes: number;
  response_time: number;
  narrative: string;
  scenario: Scenario;
}

export interface PrecedentCase {
  case_id: string;
  similarity_score: number;
  matched_on: string[];
  differs_on: string[];
  intervention: string;
  observed_outcome: {
    effect: string;
    period: string;
    n_measured: number;
  };
  provenance: "public" | "authored" | "live_simulated";
  evidence_quality: EvidenceQuality;
}

export type EvidenceQuality = 
  | "measured_observational" 
  | "aggregate_disclosure" 
  | "incomplete_report" 
  | "illustrative" 
  | "simulated";

export type ActionType = 
  | "provide_evidence" 
  | "send_message" 
  | "make_offer" 
  | "accept_claim" 
  | "refund" 
  | "status_update" 
  | "settle";

export type ApprovalTier = "AUTO" | "NEEDS_APPROVAL" | "BLOCKED";

export interface Recommendation {
  diagnosis: string;
  precedents: PrecedentCase[];
  typed_action: ActionType;
  playbook_notes: string;
  confidence: number;
  evidence_quality: EvidenceQuality;
  required_approval: ApprovalTier;
  abstain: boolean;
  abstain_reason?: string;
}

export interface TimelineEvent {
  type: "detected" | "recommended" | "approved" | "executed" | "measured";
  timestamp: string;
  label: string;
  simulated?: boolean;
  details?: Record<string, unknown>;
}

export interface MerchantTimeline {
  merchant_id: string;
  events: TimelineEvent[];
  simulated_clock: { simulated_days: number; events: number };
}

export interface ExecutionState {
  execution_id: string;
  merchant_id: string;
  action: ActionType;
  state: "PROPOSED" | "GATED" | "AWAITING_APPROVAL" | "EXECUTING" | "SUCCEEDED" | "FAILED" | "CANCELLED";
  result?: Record<string, unknown>;
  started_at: string;
  completed_at?: string;
  idempotency_key: string;
}

export interface CaseRecord {
  case_id: string;
  merchant_id: string;
  situation_id: string;
  scenario: Scenario;
  created_at: string;
  features: SituationRecord;
  provenance: "public" | "authored" | "live_simulated";
  evidence_quality: EvidenceQuality;
}

export interface ScenarioLoadResponse {
  situation_id: string;
  situation: SituationRecord;
  scenario: Scenario;
  order_count: number;
}
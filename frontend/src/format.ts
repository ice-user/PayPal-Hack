export const pct = (x: number | undefined | null, digits = 0): string =>
  x === undefined || x === null ? "n/a" : `${(x * 100).toFixed(digits)}%`;

export const rate = (x: number): string => `${(x * 100).toFixed(2)}%`;

export const pValue = (p: number): string => (p < 0.0001 ? p.toExponential(1) : p.toFixed(4));

export const money = (v: number, currency = "USD"): string =>
  new Intl.NumberFormat("en-US", { style: "currency", currency, maximumFractionDigits: 0 }).format(v);

export const INTERVENTION_LABEL: Record<string, string> = {
  delivery_confirmation_tracking: "Delivery confirmation and tracking evidence",
  carrier_switch: "Switch carrier",
  fulfilment_workflow_fix: "Fix the fulfilment workflow",
  proactive_buyer_messaging: "Proactive buyer messages",
  evidence_collection_response: "Collect and file proof of delivery",
  partial_refund_offer: "Partial refund offer",
  accept_and_refund: "Accept and refund",
  fraud_screening: "Fraud screening",
  listing_and_policy_clarity: "Listing or descriptor fix",
  processor_compliance_controls: "Compliance controls",
};

export const ACTION_LABEL: Record<string, string> = {
  FLAG_ONLY: "Prepare",
  PROVIDE_EVIDENCE: "Provide evidence",
  SEND_MESSAGE: "Message buyers",
  MAKE_OFFER: "Make offer",
  ACCEPT_CLAIM: "Accept claim",
};

export const REASON_LABEL: Record<string, string> = {
  ITEM_NOT_RECEIVED: "Not received",
  UNAUTHORISED: "Unauthorised",
  NOT_AS_DESCRIBED: "Not as described",
  OTHER: "Other",
};

export const QUALITY_LABEL: Record<string, string> = {
  measured_observational: "Measured",
  aggregate_disclosure: "Aggregate disclosure",
  incomplete_report: "Incomplete report",
  illustrative: "Illustrative",
  simulated: "Simulated",
  none: "None",
};

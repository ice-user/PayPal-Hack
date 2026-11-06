import { Recommendation, ActionType, ApprovalTier } from "../types/api";

const tierColors: Record<ApprovalTier, string> = {
  AUTO: "var(--success, #22c55e)",
  NEEDS_APPROVAL: "var(--warning, #f59e0b)",
  BLOCKED: "var(--destructive, #ef4444)",
};

const actionLabels: Record<ActionType, string> = {
  provide_evidence: "Provide Evidence",
  send_message: "Send Message to Buyer",
  make_offer: "Make Offer",
  accept_claim: "Accept Claim",
  refund: "Refund Buyer",
  status_update: "Update Status",
  settle: "Settle Dispute",
};

export function PlanPanel({
  recommendation,
  onApprove,
  onReject,
}: {
  recommendation: Recommendation;
  onApprove: () => void;
  onReject: () => void;
}) {
  const { typed_action, playbook_notes, confidence, evidence_quality, required_approval, abstain, abstain_reason } = recommendation;

  if (abstain) {
    return (
      <section className="panel plan-panel">
        <h2>Plan</h2>
        <div className="abstain-state">
          <h3>System Abstains</h3>
          <p>{abstain_reason || "Insufficient evidence to make a recommendation."}</p>
          <p className="abstain-note">No action proposed. Monitor and re-evaluate when more data is available.</p>
        </div>
      </section>
    );
  }

  return (
    <section className="panel plan-panel">
      <h2>Plan</h2>

      <div className="action-card">
        <div className="action-header">
          <span className="action-name">{actionLabels[typed_action]}</span>
          <span 
            className="tier-badge"
            style={{ backgroundColor: tierColors[required_approval] + "20", color: tierColors[required_approval] }}
          >
            {required_approval}
          </span>
        </div>

        <div className="action-meta">
          <span className="confidence">Confidence: {(confidence * 100).toFixed(0)}%</span>
          <span className="evidence-quality">Evidence: {evidence_quality.replace("_", " ")}</span>
        </div>

        <div className="playbook-notes">
          <h4>Playbook Notes</h4>
          <p>{playbook_notes}</p>
        </div>

        <div className="action-buttons">
          {required_approval === "AUTO" && (
            <button className="btn btn-primary" onClick={onApprove} disabled>
              Auto-Approved
            </button>
          )}
          {required_approval === "NEEDS_APPROVAL" && (
            <>
              <button className="btn btn-primary" onClick={onApprove}>
                Approve
              </button>
              <button className="btn btn-secondary" onClick={onReject}>
                Reject
              </button>
            </>
          )}
          {required_approval === "BLOCKED" && (
            <button className="btn btn-danger" disabled>
              Blocked — Explicit Approval Required
            </button>
          )}
        </div>

        <div className="action-rule">
          <small>Policy: {getPolicyRule(required_approval, typed_action)}</small>
        </div>
      </div>

      <div className="diagnosis">
        <h4>Diagnosis</h4>
        <p>{recommendation.diagnosis}</p>
      </div>
    </section>
  );
}

function getPolicyRule(tier: ApprovalTier, action: ActionType): string {
  if (tier === "AUTO") return "Analysis/draft action — auto-approved.";
  if (tier === "NEEDS_APPROVAL") return `${actionLabels[action]} is an external action requiring one-click human approval.`;
  return `${actionLabels[action]} is a money/claim action blocked above hard cap; explicit approval required.`;
}
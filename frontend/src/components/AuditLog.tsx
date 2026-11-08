import type { AuditEvent } from "../api";

const LABEL: Record<string, string> = {
  action_registered: "Plan recorded",
  action_approved: "Approved",
  action_rejected: "Rejected",
  action_succeeded: "Executed",
  action_failed: "Failed",
  approval_refused: "Approval refused by policy",
  duplicate_approval_ignored: "Duplicate approval ignored",
  outcome_recorded: "Outcome recorded (simulated)",
  case_reviewed: "Case reviewed",
  webhook_received: "PayPal webhook",
  webhook_rejected: "Webhook rejected",
  demo_reset: "Demo reset",
};

function summary(e: AuditEvent): string {
  const p = e.payload;
  const bits: string[] = [];
  if (p.action_id) bits.push(String(p.action_id));
  if (p.decision) bits.push(String(p.decision));
  if (p.mode) bits.push(String(p.mode));
  if (Array.isArray(p.rules) && p.rules.length) bits.push(`rules: ${p.rules.join(", ")}`);
  if (p.case_id) bits.push(String(p.case_id));
  if (typeof p.detail === "string") bits.push(p.detail);
  return bits.join(" · ");
}

export function AuditLog({ events }: { events: AuditEvent[] }) {
  return (
    <details className="audit">
      <summary>Audit log <span className="panel-meta">({events.length} latest events, newest first)</span></summary>
      <ol>
        {events.map((e) => (
          <li key={e.id}>
            <time className="num">{e.at.replace("T", " ").replace("+00:00", " UTC")}</time>
            <span className="audit-actor">{e.actor}</span>
            <strong>{LABEL[e.event] ?? e.event}</strong>
            <span className="audit-detail">{summary(e)}</span>
          </li>
        ))}
      </ol>
    </details>
  );
}

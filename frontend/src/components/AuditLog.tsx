import { useState } from "react";
import type { AuditEvent } from "../api";
import { Pane } from "./Card";
import { Icon } from "./Icon";

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

const TONE: Record<string, string> = {
  action_succeeded: "ok",
  action_failed: "bad",
  approval_refused: "bad",
  webhook_rejected: "bad",
  action_approved: "info",
  outcome_recorded: "sim",
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
  const [all, setAll] = useState(false);
  const shown = all ? events : events.slice(0, 6);
  return (
    <Pane id="audit" title="Audit log" sub="Every step the backend took, newest first."
      footer={events.length > 6 ? (
        <button className="link-btn" onClick={() => setAll(!all)}>
          {all ? "Show fewer" : `View all ${events.length} events`} <Icon name="arrow" size={14} />
        </button>
      ) : null}>
      <div className="table-wrap">
        <table className="table">
          <thead><tr><th>Time (UTC)</th><th>Actor</th><th>Event</th><th>Detail</th></tr></thead>
          <tbody>
            {shown.map((e) => (
              <tr key={e.id}>
                <td className="num nowrap muted">{e.at.replace("T", " ").replace(/(\.\d+)?\+00:00$/, "")}</td>
                <td className="nowrap">{e.actor}</td>
                <td className="nowrap"><span className={`status status-${TONE[e.event] ?? "plain"}`}>{LABEL[e.event] ?? e.event}</span></td>
                <td className="audit-detail">{summary(e)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </Pane>
  );
}

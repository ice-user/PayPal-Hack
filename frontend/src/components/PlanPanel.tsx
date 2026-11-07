import type { Action, ActionState, Outcome, PolicyDecision, Recommendation } from "../types";
import { ACTION_LABEL, money, pct, QUALITY_LABEL, rate } from "../format";
import { DecisionBadge, SimulatedTag, TierBadge } from "./Badges";
import { Card, Pill } from "./Card";

export interface ActionView {
  state: ActionState;
  mode?: "real" | "simulated";
  detail?: string;
}

function paramsLine(a: Action): string {
  const p = a.params as Record<string, unknown>;
  const bits: string[] = [];
  const amount = p.amount as { value: number; currency_code: string } | undefined;
  if (amount) bits.push(`${money(amount.value, amount.currency_code)} total`);
  if (typeof p.estimated_disputes === "number") bits.push(`~${p.estimated_disputes} disputes`);
  if (typeof p.dispute_count === "number") bits.push(`${p.dispute_count} disputes`);
  if (typeof p.audience === "string") bits.push(`to ${p.audience.replaceAll("_", " ")}`);
  if (typeof p.evidence_type === "string") bits.push(p.evidence_type.replaceAll("_", " ").toLowerCase());
  return bits.join(" · ");
}

/* ---------- Diagnosis ---------- */

interface DiagnosisProps {
  rec: Recommendation;
  outcome: Outcome | null;
  busy: string | null;
  onOpenCase: (caseId: string) => void;
  onReview?: (caseId: string, decision: "approved" | "rejected") => void;
}

export function DiagnosisCard({ rec, outcome, busy, onOpenCase, onReview }: DiagnosisProps) {
  const reviewState = outcome?.case_review_status ?? "pending";
  return (
    <Card id="diagnosis" className="span-6"
      title="Diagnosis"
      pill={rec.grounding === "none" ? <Pill tone="warn">No precedent</Pill> : <Pill tone="neutral">{rec.precedents.length} precedents</Pill>}
      sub={rec.generated_by.engine === "llm" ? `Rules engine, prose reworded by ${rec.generated_by.model}` : "Rules engine: precedents vote, actions come from a fixed list."}>
      <div className="diag-title">{rec.diagnosis}</div>
      {rec.diagnosis_detail && <p className="diag-detail">{rec.diagnosis_detail}</p>}

      <div className="diag-meta">
        <div>
          <div className="kpi-label">Confidence</div>
          <div className="conf">
            <div className="conf-track" aria-hidden="true"><div className="conf-fill" style={{ width: `${rec.confidence * 100}%` }} /></div>
            <span className="num">{pct(rec.confidence)}</span>
          </div>
        </div>
        <div>
          <div className="kpi-label">Evidence</div>
          <div>{QUALITY_LABEL[rec.evidence_quality] ?? rec.evidence_quality}</div>
        </div>
      </div>

      <div className="diag-effect">
        <div className="kpi-label">Expected effect</div>
        {rec.predicted_effect ? (
          <p>
            Similar merchants were followed by a 7-day dispute rate of{" "}
            <strong className="num">{rate(rec.predicted_effect.range[0])}–{rate(rec.predicted_effect.range[1])}</strong> within{" "}
            {rec.predicted_effect.horizon_days} days ({rec.predicted_effect.n_measured_cases} measured cases). Observed, not caused.
          </p>
        ) : (
          <p className="muted-text">No numeric forecast. No measured precedents match this pattern, and we do not invent one.</p>
        )}
      </div>

      {outcome && (
        <div className="callout" role="status">
          <div className="callout-head">Outcome after {outcome.horizon_days} days <SimulatedTag /></div>
          <p>
            7-day dispute rate <strong className="num">{rate(outcome.before)}</strong> before,{" "}
            <strong className="num">{rate(outcome.after)}</strong> after. Simulated replay, not a real measurement.
          </p>
          {outcome.new_case_id && (
            <div className="review">
              <span>
                Recorded as{" "}
                <button className="linklike" onClick={() => onOpenCase(outcome.new_case_id!)}><code>{outcome.new_case_id}</code></button>
                {reviewState === "approved" && <> · added to the case library as a simulated case (it can inform a diagnosis, never a forecast)</>}
                {reviewState === "rejected" && <> · discarded</>}
                {reviewState === "pending" && <> · waiting for your review</>}
              </span>
              {reviewState === "pending" && onReview && (
                <span className="buttons">
                  <button className="btn primary" disabled={busy !== null} onClick={() => onReview(outcome.new_case_id!, "approved")}>Add to case library</button>
                  <button className="btn" disabled={busy !== null} onClick={() => onReview(outcome.new_case_id!, "rejected")}>Discard</button>
                </span>
              )}
            </div>
          )}
        </div>
      )}

      {rec.playbook_notes.length > 0 && (
        <details className="notes">
          <summary>Playbook notes ({rec.playbook_notes.length}, qualitative)</summary>
          <ul>{rec.playbook_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </details>
      )}
    </Card>
  );
}

/* ---------- Actions ---------- */

function Status({ view, decision, busy, onApprove, onReject, a }: {
  view: ActionView; decision?: PolicyDecision; busy: string | null;
  onApprove: (a: Action) => void; onReject: (a: Action) => void; a: Action;
}) {
  const { state, mode, detail } = view;
  if (decision?.decision === "BLOCKED") return <span className="status status-blocked">Blocked</span>;
  if (decision?.decision === "AUTO") return <span className="status status-ok" title="Prepared automatically. Nothing leaves the system.">Prepared</span>;
  if (state === "proposed")
    return (
      <span className="buttons">
        <button className="btn primary sm" disabled={busy !== null} onClick={() => onApprove(a)}>
          {busy === a.action_id ? "Working…" : "Approve"}
        </button>
        <button className="btn sm" disabled={busy !== null} onClick={() => onReject(a)}>Reject</button>
      </span>
    );
  if (state === "approved" || state === "executing") return <span className="status status-running">Executing…</span>;
  if (state === "rejected") return <span className="status" title="Nothing was sent.">Rejected</span>;
  if (state === "failed") return <span className="status status-blocked" title={detail}>Failed</span>;
  return (
    <span className="status-stack">
      {mode === "real" ? <span className="status status-real">Sent to PayPal</span> : <SimulatedTag />}
      <span className="status-detail">{detail?.replace(/^Simulated:\s*/, "") ?? "Executed in the browser only (fixture mode)."}</span>
    </span>
  );
}

interface ActionsProps {
  rec: Recommendation;
  decisions: PolicyDecision[];
  views: Record<string, ActionView>;
  busy: string | null;
  onApprove: (a: Action) => void;
  onReject: (a: Action) => void;
  onOpenCase: (caseId: string) => void;
}

export function ActionsCard({ rec, decisions, views, busy, onApprove, onReject, onOpenCase }: ActionsProps) {
  const byId = Object.fromEntries(decisions.map((d) => [d.action_id, d]));
  const waiting = rec.actions.filter((a) => byId[a.action_id]?.decision === "NEEDS_APPROVAL" && (views[a.action_id]?.state ?? "proposed") === "proposed").length;
  return (
    <Card id="actions" className="span-5"
      title="Proposed actions"
      pill={waiting ? <Pill tone="warn">{waiting} waiting</Pill> : null}
      sub="Every action passes the policy gate. Anything a buyer or PayPal sees needs your click.">
      {rec.abstain ? (
        <div className="callout warn" role="status">
          <div className="callout-head">Abstained</div>
          <p>{rec.abstain_reason}</p>
        </div>
      ) : (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Action</th><th>Gate</th><th>Status</th></tr>
            </thead>
            <tbody>
              {rec.actions.map((a) => {
                const d = byId[a.action_id];
                const view = views[a.action_id] ?? { state: "proposed" as ActionState };
                const params = paramsLine(a);
                return (
                  <tr key={a.action_id}>
                    <td className="action-cell">
                      <div className="action-type">{ACTION_LABEL[a.type] ?? a.type}{params && <> · {params}</>}</div>
                      <div className="action-title">{a.title ?? a.type}</div>
                      <p className="action-why">{a.rationale}</p>
                      {d && <p className="action-gate"><span className="chip-label">Policy gate</span> {d.explanation}</p>}
                      {a.supporting_cases.length > 0 && (
                        <div className="chips">
                          <span className="chip-label">Cites</span>
                          {a.supporting_cases.map((c) => (
                            <button key={c} className="chip linklike" onClick={() => onOpenCase(c)} aria-label={`Open case ${c}`}>
                              {c.replace(/^case_/, "").split("_")[0]}
                            </button>
                          ))}
                        </div>
                      )}
                    </td>
                    <td>
                      {d && (
                        <span className="gate" title={d.explanation}>
                          <DecisionBadge decision={d.decision} />
                          <TierBadge tier={d.tier} />
                        </span>
                      )}
                    </td>
                    <td><Status view={view} decision={d} busy={busy} onApprove={onApprove} onReject={onReject} a={a} /></td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
    </Card>
  );
}

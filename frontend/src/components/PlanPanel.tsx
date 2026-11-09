import { useState } from "react";
import type { Action, ActionState, Outcome, PolicyDecision, Recommendation, Tier } from "../types";
import { ACTION_LABEL, money, pct, QUALITY_LABEL, rate } from "../format";
import { SimulatedTag } from "./Badges";
import { Pane, Pill, Spinner } from "./Card";
import { Icon, type IconName } from "./Icon";

export interface ActionView {
  state: ActionState;
  mode?: "real" | "simulated";
  detail?: string;
}

function paramsLine(a: Action): string {
  const p = a.params as Record<string, unknown>;
  const bits: string[] = [];
  if (typeof p.triage_group === "string") {
    if (typeof p.total_value === "number") bits.push(`${money(p.total_value)} in orders`);
    if (typeof p.earliest_due === "string") bits.push(`respond by ${shortDay(p.earliest_due)}`);
    return bits.join(" · ");
  }
  const amount = p.amount as { value: number; currency_code: string } | undefined;
  if (amount) bits.push(`${money(amount.value, amount.currency_code)} total`);
  if (typeof p.estimated_disputes === "number") bits.push(`about ${p.estimated_disputes} disputes`);
  if (typeof p.dispute_count === "number") bits.push(`${p.dispute_count} disputes`);
  if (typeof p.audience === "string") bits.push(`to ${p.audience.replaceAll("_", " ")}`);
  if (typeof p.evidence_type === "string") bits.push(p.evidence_type.replaceAll("_", " ").toLowerCase());
  return bits.join(" · ");
}

export const shortDay = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

const REACH: Record<Tier, { icon: IconName; text: string }> = {
  PREPARE: { icon: "file", text: "Internal only. Nothing leaves the system." },
  EXTERNAL: { icon: "send", text: "Buyers or PayPal will see this on the dispute." },
  MONEY: { icon: "alert", text: "Moves money to buyers." },
};

const DECISION_LABEL = { AUTO: "Runs automatically", NEEDS_APPROVAL: "Needs your approval", BLOCKED: "Blocked by policy" } as const;

/* ---------- Diagnosis ---------- */

export function DiagnosisPane({ rec }: { rec: Recommendation }) {
  return (
    <Pane id="diagnosis" title="Diagnosis"
      pill={rec.grounding === "none" ? <Pill tone="warn">No precedent</Pill> : null}
      sub={rec.generated_by.engine === "llm" ? `Rules engine; wording by ${rec.generated_by.model}` : "Rules engine: past cases vote on the cause."}>
      <p className="diag-title">{rec.diagnosis}</p>
      {rec.diagnosis_detail && <p className="diag-detail">{rec.diagnosis_detail}</p>}

      <dl className="diag-meta">
        <div>
          <dt>Confidence</dt>
          <dd className="conf">
            <span className="conf-track" aria-hidden="true"><span className="conf-fill" style={{ width: `${rec.confidence * 100}%` }} /></span>
            <span className="num">{pct(rec.confidence)}</span>
          </dd>
        </div>
        <div>
          <dt>Evidence</dt>
          <dd>{QUALITY_LABEL[rec.evidence_quality] ?? rec.evidence_quality}</dd>
        </div>
        <div className="wide">
          <dt>Expected effect</dt>
          <dd>
            {rec.predicted_effect ? (
              <>Similar merchants were followed by a 7-day rate of{" "}
                <strong className="num">{rate(rec.predicted_effect.range[0])}–{rate(rec.predicted_effect.range[1])}</strong> within{" "}
                {rec.predicted_effect.horizon_days} days ({rec.predicted_effect.n_measured_cases} measured cases). Observed, not caused.</>
            ) : (
              <span className="muted">No numeric forecast. No measured precedents match this pattern, and we do not invent one.</span>
            )}
          </dd>
        </div>
      </dl>

      {rec.playbook_notes.length > 0 && (
        <details className="notes">
          <summary><Icon name="chevron" size={14} className="notes-caret" />Playbook notes ({rec.playbook_notes.length})</summary>
          <ul>{rec.playbook_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </details>
      )}
    </Pane>
  );
}

/* ---------- Actions: the approval workflow ---------- */

function Stepper({ view }: { view: ActionView }) {
  const { state, mode } = view;
  const rejected = state === "rejected";
  const approved = state !== "proposed" && !rejected;
  const done = state === "succeeded";
  const failed = state === "failed";
  const running = state === "approved" || state === "executing";
  const steps = [
    { label: "Proposed", on: true },
    { label: rejected ? "Rejected" : "Approved", on: approved || rejected, bad: rejected },
    { label: failed ? "Failed" : done ? (mode === "real" ? "Sent to PayPal" : "Executed (simulated)") : "Executed", on: done || failed, bad: failed, running },
  ];
  return (
    <ol className="stepper" aria-label="Action progress">
      {steps.map((s) => (
        <li key={s.label} className={`step ${s.on ? "on" : ""} ${s.bad ? "bad" : ""} ${s.running ? "running" : ""}`}>
          <span className="step-dot">{s.running ? <Spinner /> : s.on ? <Icon name={s.bad ? "x" : "check"} size={12} /> : null}</span>
          <span className="step-label">{s.label}</span>
        </li>
      ))}
    </ol>
  );
}

interface ActionsProps {
  rec: Recommendation;
  decisions: PolicyDecision[];
  views: Record<string, ActionView>;
  busy: string | null;
  disputeIds: string[];
  /** Action types this deployment runs for real in PayPal (["ALL"] = all), or null for none. */
  realActions?: string[] | null;
  onApprove: (a: Action) => void;
  onReject: (a: Action) => void;
  onOpenCase: (caseId: string) => void;
}

/** The real PayPal sandbox disputes an action would act on. Dispute-level actions name their own. */
function targetsOf(a: Action, situationIds: string[]): string[] {
  const own = a.params?.dispute_ids;
  if (Array.isArray(own) && own.length) return own as string[];
  return a.params?.triage_group ? [] : situationIds;
}

function confirmTextFor(a: Action, targets: string[], realActions: string[] | null | undefined): string {
  if (!targets.length)
    return "No PayPal sandbox dispute is linked to this action, so it runs as a labelled simulation. Nothing reaches PayPal.";
  const where = targets.length === 1 ? `PayPal sandbox dispute ${targets[0]}` : `PayPal sandbox disputes ${targets.join(", ")}`;
  if (realActions === null || (realActions && !realActions.includes("ALL") && !realActions.includes(a.type)))
    return `Linked to ${where}, but this deployment keeps ${a.type.replaceAll("_", " ").toLowerCase()} simulated. The backend still reads the dispute live from PayPal first.`;
  return `This goes to ${where}. The backend re-reads the dispute from PayPal first; if PayPal does not allow this action right now, it runs as a labelled simulation instead.`;
}

export function ActionsPane({ rec, decisions, views, busy, disputeIds, realActions, onApprove, onReject, onOpenCase }: ActionsProps) {
  const [confirming, setConfirming] = useState<string | null>(null);
  const byId = Object.fromEntries(decisions.map((d) => [d.action_id, d]));
  const stateOf = (a: Action) => views[a.action_id]?.state ?? "proposed";
  const waiting = rec.actions.filter((a) => byId[a.action_id]?.decision === "NEEDS_APPROVAL" && stateOf(a) === "proposed").length;

  return (
    <Pane id="actions" className="pane-actions" title="Proposed actions"
      pill={!rec.actions.length ? null : waiting ? <Pill tone="warn">{waiting} waiting for you</Pill> : <Pill tone="good">All handled</Pill>}
      sub="Prepare-only steps run on their own. Anything a buyer or PayPal sees waits for your click.">
      {rec.abstain && (
        <div className="callout warn" role="status">
          <Icon name="alert" />
          <div>
            <p className="callout-title">{rec.actions.length ? "No merchant-wide fix: the spike-level plan abstained" : "The consultant abstained"}</p>
            <p>{rec.abstain_reason}{rec.actions.length ? " Open disputes still need answers, so the dispute-level actions below remain." : ""}</p>
          </div>
        </div>
      )}
      {rec.actions.length > 0 && (
        <ol className="actions">
          {rec.actions.map((a, i) => {
            const d = byId[a.action_id];
            const view = views[a.action_id] ?? { state: "proposed" as ActionState };
            const reach = d ? REACH[d.tier] : null;
            const params = paramsLine(a);
            const needsYou = d?.decision === "NEEDS_APPROVAL" && view.state === "proposed";
            const isBusy = busy === a.action_id;
            const confirmNeeded = d?.tier === "EXTERNAL" || d?.tier === "MONEY";
            const targets = d?.tier === "PREPARE" ? [] : targetsOf(a, disputeIds);
            return (
              <li key={a.action_id} className={`action ${needsYou ? "needs-you" : ""} decision-${d?.decision.toLowerCase() ?? "none"}`}>
                <div className="action-index" aria-hidden="true">{i + 1}</div>
                <div className="action-main">
                  <div className="action-kicker">
                    <span>{ACTION_LABEL[a.type] ?? a.type}</span>
                    {d && <span className={`gate gate-${d.decision.toLowerCase()}`}>{DECISION_LABEL[d.decision]}</span>}
                    {targets.length > 0 && <Pill tone="info">PayPal {targets.join(", ")}</Pill>}
                  </div>
                  <h4 className="action-title">{a.title ?? a.type}</h4>
                  {reach && (
                    <p className="action-reach"><Icon name={reach.icon} size={14} />{reach.text}{params && <span className="muted"> · {params}</span>}</p>
                  )}
                  <p className="action-why">{a.rationale}</p>
                  <div className="action-foot">
                    {a.supporting_cases.length > 0 && (
                      <span className="chips">
                        <span className="chip-label">Cites</span>
                        {a.supporting_cases.map((c) => c.startsWith("dc_") ? (
                          <span key={c} className="chip" title="Dispute-level case (see the shipment-state table)">
                            {c.replace(/^dc_/, "").split("_")[0]}
                          </span>
                        ) : (
                          <button key={c} className="chip chip-btn" onClick={() => onOpenCase(c)} aria-label={`Open case ${c}`}>
                            {c.replace(/^case_/, "").split("_")[0]}
                          </button>
                        ))}
                      </span>
                    )}
                    {d && <span className="action-gate" title={d.rules_hit.join(", ")}>{d.explanation}</span>}
                  </div>
                </div>

                <div className="action-side">
                  {d?.decision === "BLOCKED" && (
                    <div className="side-note bad"><Icon name="ban" size={14} />Blocked. It cannot be approved.</div>
                  )}
                  {d?.decision === "AUTO" && (
                    <div className="side-note good"><Icon name="check" size={14} />Prepared automatically</div>
                  )}
                  {needsYou && confirming !== a.action_id && (
                    <div className="decide">
                      <button className="btn primary" disabled={busy !== null}
                        onClick={() => (confirmNeeded ? setConfirming(a.action_id) : onApprove(a))}>
                        {isBusy ? <Spinner /> : <Icon name="check" size={14} />} Approve
                      </button>
                      <button className="btn ghost" disabled={busy !== null} onClick={() => onReject(a)}>Reject</button>
                    </div>
                  )}
                  {needsYou && confirming === a.action_id && (
                    <div className="confirm" role="group" aria-label="Confirm approval">
                      <p>{confirmTextFor(a, targets, realActions)}</p>
                      <div className="decide">
                        <button className="btn primary" autoFocus disabled={busy !== null}
                          onClick={() => { setConfirming(null); onApprove(a); }}>
                          <Icon name="send" size={14} /> {targets.length ? "Confirm and send" : "Confirm"}
                        </button>
                        <button className="btn ghost" onClick={() => setConfirming(null)}>Cancel</button>
                      </div>
                    </div>
                  )}
                  {d?.decision === "NEEDS_APPROVAL" && view.state !== "proposed" && (
                    <>
                      <Stepper view={view} />
                      {view.state === "succeeded" && (
                        <p className="exec-detail">
                          {view.mode === "real" ? <Pill tone="info">PayPal sandbox</Pill> : <SimulatedTag />}{" "}
                          {view.detail?.replace(/^Simulated:\s*/, "") ?? "Executed in the browser only (fixture mode)."}
                        </p>
                      )}
                      {view.state === "failed" && <p className="exec-detail bad">{view.detail}</p>}
                      {view.state === "rejected" && <p className="exec-detail">Nothing was sent.</p>}
                    </>
                  )}
                </div>
              </li>
            );
          })}
        </ol>
      )}
    </Pane>
  );
}

/* ---------- Next step: advance the clock, then review the recorded case ---------- */

interface NextProps {
  canAdvance: boolean;
  outcome: Outcome | null;
  busy: string | null;
  onAdvance: () => void;
  onOpenCase: (caseId: string) => void;
  onReview?: (caseId: string, decision: "approved" | "rejected") => void;
}

export function NextStep({ canAdvance, outcome, busy, onAdvance, onOpenCase, onReview }: NextProps) {
  if (!canAdvance && !outcome) return null;
  if (!outcome)
    return (
      <div className="next-step">
        <Icon name="forward" />
        <p><strong>Next:</strong> advance the simulated clock to record what followed the executed actions.</p>
        <button className="btn primary" disabled={busy !== null} onClick={onAdvance}>
          {busy === "advance" && <Spinner />} Advance 14 days (simulated)
        </button>
      </div>
    );
  const review = outcome.case_review_status ?? "pending";
  return (
    <div className="next-step" role="status">
      <Icon name="clock" />
      <div className="next-text">
        <p>
          <strong>After {outcome.horizon_days} days:</strong> 7-day dispute rate{" "}
          <strong className="num">{rate(outcome.before)}</strong> → <strong className="num">{rate(outcome.after)}</strong>.{" "}
          <SimulatedTag />
        </p>
        {!outcome.new_case_id && (
          <p className="muted">
            Only dispute-level responses ran. They answer open disputes but do not fix the cause, so with no
            merchant-wide fix the spike continued. No case is recorded: there is no situation-level remedy to learn from.
          </p>
        )}
        {outcome.new_case_id && (
          <p className="muted">
            Recorded as{" "}
            <button className="link" onClick={() => onOpenCase(outcome.new_case_id!)}><code>{outcome.new_case_id}</code></button>
            {review === "approved" && " · in the case library (informs diagnoses, never forecasts)"}
            {review === "rejected" && " · discarded"}
            {review === "pending" && " · waiting for your review"}
          </p>
        )}
      </div>
      {outcome.new_case_id && review === "pending" && onReview && (
        <div className="decide">
          <button className="btn primary" disabled={busy !== null} onClick={() => onReview(outcome.new_case_id!, "approved")}>
            {busy === "review" && <Spinner />} Add to case library
          </button>
          <button className="btn ghost" disabled={busy !== null} onClick={() => onReview(outcome.new_case_id!, "rejected")}>Discard</button>
        </div>
      )}
    </div>
  );
}

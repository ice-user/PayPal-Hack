import type { Action, ActionState, Outcome, PolicyDecision, Recommendation } from "../types";
import { ACTION_LABEL, money, pct, QUALITY_LABEL, rate } from "../format";
import { DecisionBadge, SimulatedTag, TierBadge } from "./Badges";

export interface ActionView {
  state: ActionState;
  mode?: "real" | "simulated";
  detail?: string;
}

interface Props {
  rec: Recommendation;
  decisions: PolicyDecision[];
  views: Record<string, ActionView>;
  busy: string | null;
  outcome: Outcome | null;
  onApprove: (a: Action) => void;
  onReject: (a: Action) => void;
}

function ParamsLine({ a }: { a: Action }) {
  const p = a.params as Record<string, unknown>;
  const bits: string[] = [];
  const amount = p.amount as { value: number; currency_code: string } | undefined;
  if (amount) bits.push(`${money(amount.value, amount.currency_code)} total`);
  if (typeof p.estimated_disputes === "number") bits.push(`~${p.estimated_disputes} disputes`);
  if (typeof p.dispute_count === "number") bits.push(`${p.dispute_count} disputes`);
  if (typeof p.audience === "string") bits.push(`to ${p.audience.replaceAll("_", " ")}`);
  if (typeof p.evidence_type === "string") bits.push(p.evidence_type.replaceAll("_", " ").toLowerCase());
  if (typeof p.note === "string") bits.push(p.note);
  return bits.length ? <div className="params">{bits.join(" · ")}</div> : null;
}

function StateLine({ view, auto }: { view: ActionView; auto: boolean }) {
  const { state, mode, detail } = view;
  if (state === "approved" || state === "executing")
    return <div className="state running">Executing through the PayPal sandbox adapter…</div>;
  if (state === "succeeded" && auto) return null;
  if (state === "succeeded")
    return (
      <div className="state ok">
        {mode === "real" ? <span className="badge real">PayPal sandbox</span> : <SimulatedTag />}
        <span>{detail?.replace(/^Simulated:\s*/, "") ?? "Executed in the browser only (fixture mode)."}</span>
      </div>
    );
  if (state === "failed") return <div className="state failed">Failed: {detail}</div>;
  if (state === "rejected") return <div className="state rejected">Rejected by you. Nothing was sent.</div>;
  return null;
}

export function PlanPanel({ rec, decisions, views, busy, outcome, onApprove, onReject }: Props) {
  const byId = Object.fromEntries(decisions.map((d) => [d.action_id, d]));
  return (
    <section className="panel" aria-labelledby="plan-h">
      <header className="panel-head">
        <h2 id="plan-h">Plan</h2>
        <span className="panel-meta">{rec.generated_by.engine === "llm" ? `LLM prose · ${rec.generated_by.model}` : "Rules engine"}</span>
      </header>

      <div className="diagnosis">
        <div className="stat-label">Diagnosis</div>
        <div className="diag-title">{rec.diagnosis}</div>
        {rec.diagnosis_detail && <p className="diag-detail">{rec.diagnosis_detail}</p>}
      </div>

      <div className="meta-row">
        <div>
          <div className="stat-label">Confidence</div>
          <div className="conf">
            <div className="conf-track" aria-hidden="true"><div className="conf-fill" style={{ width: `${rec.confidence * 100}%` }} /></div>
            <span className="num">{pct(rec.confidence)}</span>
          </div>
        </div>
        <div>
          <div className="stat-label">Evidence</div>
          <div>{QUALITY_LABEL[rec.evidence_quality] ?? rec.evidence_quality}</div>
        </div>
      </div>

      <div className="effect">
        <div className="stat-label">Expected effect</div>
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
        <div className="outcome-box" role="status">
          <div className="stat-label">Outcome after {outcome.horizon_days} days <SimulatedTag /></div>
          <p>
            7-day dispute rate <strong className="num">{rate(outcome.before)}</strong> before,{" "}
            <strong className="num">{rate(outcome.after)}</strong> after. Simulated replay, not a real measurement.
            {outcome.new_case_id && <> Recorded as <code>{outcome.new_case_id}</code>, pending review.</>}
          </p>
        </div>
      )}

      {rec.abstain ? (
        <div className="abstain" role="status">
          <strong>Abstained.</strong> {rec.abstain_reason}
        </div>
      ) : (
        <ol className="actions">
          {rec.actions.map((a) => {
            const d = byId[a.action_id];
            const view = views[a.action_id] ?? { state: "proposed" as ActionState };
            const state = view.state;
            return (
              <li key={a.action_id} className={`action decision-border-${d?.decision.toLowerCase()}`}>
                <div className="action-top">
                  <span className="action-type">{ACTION_LABEL[a.type] ?? a.type}</span>
                  <span className="badges">
                    {d && <TierBadge tier={d.tier} />}
                    {d && <DecisionBadge decision={d.decision} />}
                  </span>
                </div>
                <div className="action-title">{a.title ?? a.type}</div>
                <ParamsLine a={a} />
                <p className="rationale">{a.rationale}</p>
                {d && <p className="gate-why"><span className="label">Policy gate</span> {d.explanation}</p>}
                {a.supporting_cases.length > 0 && (
                  <div className="chips">
                    <span className="label">Cites</span>
                    {a.supporting_cases.map((c) => <code key={c} className="chip cite">{c}</code>)}
                  </div>
                )}
                {d?.decision === "NEEDS_APPROVAL" && state === "proposed" && (
                  <div className="buttons">
                    <button className="btn primary" disabled={busy !== null} onClick={() => onApprove(a)}>
                      {busy === a.action_id ? "Working…" : "Approve"}
                    </button>
                    <button className="btn" disabled={busy !== null} onClick={() => onReject(a)}>Reject</button>
                  </div>
                )}
                {d?.decision === "AUTO" && (
                  <div className="state ok">Prepared automatically. Nothing leaves the system.</div>
                )}
                <StateLine view={view} auto={d?.decision === "AUTO"} />
              </li>
            );
          })}
        </ol>
      )}

      {rec.playbook_notes.length > 0 && (
        <div className="notes">
          <div className="stat-label">Playbook notes (qualitative)</div>
          <ul>{rec.playbook_notes.map((n, i) => <li key={i}>{n}</li>)}</ul>
        </div>
      )}
    </section>
  );
}

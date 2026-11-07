import type { Recommendation } from "../types";
import { INTERVENTION_LABEL, QUALITY_LABEL } from "../format";
import { Card } from "./Card";
import { Icon } from "./Icon";

interface Props {
  rec: Recommendation;
  similarityMin: number;
  onOpenCase: (caseId: string) => void;
}

const PROV_LABEL: Record<string, string> = {
  public: "Public",
  authored: "Authored",
  live_simulated: "Sandbox (simulated)",
};

/** Similarity as a small ring, standing in for the template's avatars. */
function Ring({ value, below }: { value: number; below: boolean }) {
  const r = 16, c = 2 * Math.PI * r;
  return (
    <span className={`ring ${below ? "below" : ""}`} title="Similarity to the current situation">
      <svg viewBox="0 0 40 40" aria-hidden="true">
        <circle cx="20" cy="20" r={r} className="ring-track" />
        <circle cx="20" cy="20" r={r} className="ring-fill" strokeDasharray={`${value * c} ${c}`} transform="rotate(-90 20 20)" />
      </svg>
      <span className="ring-num num">{Math.round(value * 100)}</span>
    </span>
  );
}

export function PrecedentsPanel({ rec, similarityMin, onOpenCase }: Props) {
  const usedIds = new Set(rec.actions.flatMap((a) => a.supporting_cases));
  return (
    <Card id="precedents" className="span-4"
      title="Precedents"
      sub={rec.grounding === "none" ? "Retrieval is switched off." : `Similar past cases, ranked. Threshold ${Math.round(similarityMin * 100)}.`}>
      {rec.grounding === "none" ? (
        <div className="callout">
          <div className="callout-head">No precedents consulted</div>
          <p>This is the ablation baseline: the same Consultant without case retrieval. Nothing in the plan is cited, so the policy gate will not let it act.</p>
        </div>
      ) : (
        <ul className="people">
          {rec.precedents.map((p) => {
            const below = p.similarity < similarityMin;
            const used = usedIds.has(p.case_id);
            return (
              <li key={p.case_id} className={`person ${below ? "below" : ""}`}>
                <Ring value={p.similarity} below={below} />
                <div className="person-main">
                  <button className="person-name linklike" onClick={() => onOpenCase(p.case_id)}
                    aria-label={`Open case details: ${p.title}`}>{p.title}</button>
                  <div className="person-meta">
                    <span className={`dot prov-${p.provenance}`} aria-hidden="true" />
                    {PROV_LABEL[p.provenance] ?? p.provenance} · {QUALITY_LABEL[p.evidence_quality] ?? p.evidence_quality}
                    {used && <span className="tag">Cited</span>}
                    {below && <span className="tag">Below threshold</span>}
                  </div>
                  <div className="person-meta">{INTERVENTION_LABEL[p.intervention] ?? p.intervention}</div>
                  <div className="chips">
                    {p.matched_on.length > 0 && (
                      <span className="chip match" title={`Matched on: ${p.matched_on.join(", ")}`}>Matched {p.matched_on.length}</span>
                    )}
                    {p.differs_on.map((m) => <span key={m} className="chip differ" title="Differs on">{m}</span>)}
                  </div>
                </div>
                <button className="icon-btn" onClick={() => onOpenCase(p.case_id)} aria-label={`More about ${p.title}`}>
                  <Icon name="more" />
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </Card>
  );
}

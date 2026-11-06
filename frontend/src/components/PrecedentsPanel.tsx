import type { Recommendation } from "../types";
import { INTERVENTION_LABEL } from "../format";
import { ProvenanceBadge, QualityBadge } from "./Badges";

interface Props {
  rec: Recommendation;
  similarityMin: number;
}

export function PrecedentsPanel({ rec, similarityMin }: Props) {
  const usedIds = new Set(rec.actions.flatMap((a) => a.supporting_cases));
  return (
    <section className="panel" aria-labelledby="precedents-h">
      <header className="panel-head">
        <h2 id="precedents-h">Precedents</h2>
        <span className="panel-meta">{rec.precedents.length} retrieved</span>
      </header>

      {rec.grounding === "none" ? (
        <div className="empty">
          <strong>No precedents consulted.</strong>
          <p>This is the ablation baseline: the same Consultant without case retrieval. Nothing on the right is cited, so the policy gate will not let it act.</p>
        </div>
      ) : (
        <ol className="cases">
          {rec.precedents.map((p) => {
            const below = p.similarity < similarityMin;
            const used = usedIds.has(p.case_id);
            return (
              <li key={p.case_id} className={`case ${below ? "below" : ""} ${used ? "used" : ""}`}>
                <div className="case-top">
                  <span className="case-title">{p.title}</span>
                  <span className="sim num" title="Similarity to the current situation">{Math.round(p.similarity * 100)}</span>
                </div>
                <div className="sim-track" aria-hidden="true">
                  <div className="sim-fill" style={{ width: `${p.similarity * 100}%` }} />
                  <div className="sim-threshold" style={{ left: `${similarityMin * 100}%` }} />
                </div>
                <div className="badges">
                  <ProvenanceBadge provenance={p.provenance} />
                  <QualityBadge quality={p.evidence_quality} />
                  {used && <span className="badge cited">Cited</span>}
                  {below && <span className="badge muted">Below threshold</span>}
                </div>
                <div className="interv">
                  <span className="label">What they did</span> {INTERVENTION_LABEL[p.intervention] ?? p.intervention}
                </div>
                {p.matched_on.length > 0 && (
                  <div className="chips">
                    <span className="label">Matched on</span>
                    {p.matched_on.slice(0, 4).map((m) => <span key={m} className="chip match">{m}</span>)}
                    {p.matched_on.length > 4 && (
                      <span className="chip" title={p.matched_on.slice(4).join(", ")}>+{p.matched_on.length - 4} more</span>
                    )}
                  </div>
                )}
                {p.differs_on.length > 0 && (
                  <div className="chips">
                    <span className="label">Differs on</span>
                    {p.differs_on.map((m) => <span key={m} className="chip differ">{m}</span>)}
                  </div>
                )}
                <p className="outcome">{p.outcome_summary}</p>
                <div className="case-id"><code>{p.case_id}</code></div>
              </li>
            );
          })}
        </ol>
      )}
    </section>
  );
}

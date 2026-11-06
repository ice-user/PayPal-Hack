import { PrecedentCase, EvidenceQuality } from "../types/api";

const provenanceColors = {
  public: "var(--primary, #3b82f6)",
  authored: "var(--warning, #f59e0b)",
  live_simulated: "var(--muted-foreground, #9ca3af)",
};

const evidenceColors = {
  measured_observational: "var(--success, #22c55e)",
  aggregate_disclosure: "var(--primary, #3b82f6)",
  incomplete_report: "var(--warning, #f59e0b)",
  illustrative: "var(--muted-foreground, #9ca3af)",
  simulated: "var(--destructive, #ef4444)",
};

export function PrecedentsPanel({
  precedents,
  showWithoutPrecedent,
  onToggleWithoutPrecedent,
}: {
  precedents: PrecedentCase[];
  showWithoutPrecedent: boolean;
  onToggleWithoutPrecedent: (v: boolean) => void;
}) {
  if (precedents.length === 0) {
    return (
      <section className="panel precedents-panel">
        <h2>Precedents</h2>
        <p className="empty">No precedents found for this situation.</p>
        <label className="toggle">
          <input
            type="checkbox"
            checked={showWithoutPrecedent}
            onChange={(e) => onToggleWithoutPrecedent(e.target.checked)}
          />
          Show recommendation without precedent
        </label>
      </section>
    );
  }

  return (
    <section className="panel precedents-panel">
      <div className="panel-header">
        <h2>Precedents</h2>
        <label className="toggle">
          <input
            type="checkbox"
            checked={showWithoutPrecedent}
            onChange={(e) => onToggleWithoutPrecedent(e.target.checked)}
          />
          Without precedent
        </label>
      </div>

      <div className="precedents-list">
        {precedents.map((p, i) => (
          <article key={p.case_id} className="precedent-card">
            <div className="precedent-header">
              <span className="precedent-rank">#{i + 1}</span>
              <span className="precedent-similarity">
                {(p.similarity_score * 100).toFixed(0)}% match
              </span>
            </div>

            <div className="precedent-badges">
              <span
                className="badge provenance-badge"
                style={{ backgroundColor: provenanceColors[p.provenance] + "20", color: provenanceColors[p.provenance] }}
              >
                {p.provenance.replace("_", " ")}
              </span>
              <span
                className="badge evidence-badge"
                style={{ backgroundColor: evidenceColors[p.evidence_quality] + "20", color: evidenceColors[p.evidence_quality] }}
              >
                {p.evidence_quality.replace("_", " ")}
              </span>
            </div>

            <div className="precedent-matched">
              <h4>Matched on:</h4>
              <ul>
                {p.matched_on.map((m) => <li key={m}>{m}</li>)}
              </ul>
            </div>

            <div className="precedent-differs">
              <h4>Differs on:</h4>
              <ul>
                {p.differs_on.map((d) => <li key={d}>{d}</li>)}
              </ul>
            </div>

            <div className="precedent-intervention">
              <h4>Intervention:</h4>
              <p>{p.intervention}</p>
            </div>

            <div className="precedent-outcome">
              <h4>Observed Outcome:</h4>
              <p>{p.observed_outcome.effect} (over {p.observed_outcome.period}, n={p.observed_outcome.n_measured})</p>
            </div>
          </article>
        ))}
      </div>
    </section>
  );
}
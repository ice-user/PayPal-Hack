import { useEffect, useRef, useState } from "react";
import { fetchCase } from "../api";
import { getCase, type CaseRecord } from "../cases";
import { ACTION_LABEL, INTERVENTION_LABEL } from "../format";
import { ProvenanceBadge, QualityBadge } from "./Badges";

const FIELD_LABEL: Record<string, string> = {
  sourced: "Sourced",
  inferred: "Inferred",
  authored: "Authored",
  empty: "Not available",
};

export function CaseDrawer({ caseId, onClose, apiMode }: { caseId: string | null; onClose: () => void; apiMode: boolean }) {
  const ref = useRef<HTMLDialogElement>(null);
  const [remote, setRemote] = useState<CaseRecord | undefined>(undefined);
  const local = caseId ? getCase(caseId) : undefined;
  const c = local ?? (remote?.case_id === caseId ? remote : undefined);

  // Cases recorded by the outcome tracker exist only in the backend.
  useEffect(() => {
    if (!caseId || local || !apiMode) return;
    fetchCase<CaseRecord>(caseId).then(setRemote).catch(() => setRemote(undefined));
  }, [caseId, local, apiMode]);

  useEffect(() => {
    const d = ref.current;
    if (!d) return;
    if (caseId && !d.open) d.showModal();
    if (!caseId && d.open) d.close();
  }, [caseId]);

  return (
    <dialog ref={ref} className="drawer" onClose={onClose} onClick={(e) => e.target === ref.current && onClose()}
      aria-labelledby="drawer-title">
      {c ? (
        <div className="drawer-body">
          <header className="drawer-head">
            <div>
              <div className="stat-label"><code>{c.case_id}</code></div>
              <h2 id="drawer-title">{c.title}</h2>
              <div className="badges">
                <ProvenanceBadge provenance={c.provenance} />
                <QualityBadge quality={c.evidence_quality} />
                <span className="badge">{c.confounders_assessed ? "Confounders assessed" : "Confounders not assessed"}</span>
                <span className="badge">No causal claim</span>
              </div>
            </div>
            <button className="btn" onClick={onClose} aria-label="Close case details">Close</button>
          </header>

          <section>
            <h3 className="sub-h">What happened</h3>
            <p>{c.narrative}</p>
            <dl className="kv">
              <dt>Diagnosis</dt><dd>{c.diagnosis}</dd>
              <dt>What they did</dt><dd>{INTERVENTION_LABEL[c.intervention] ?? c.intervention}</dd>
              <dt>Actions</dt><dd>{c.actions.map((a) => ACTION_LABEL[a] ?? a).join(", ")}</dd>
              <dt>Outcome</dt><dd>{c.outcome.summary}</dd>
              <dt>Context</dt>
              <dd>{[c.context.industry, c.context.merchant_size, c.context.region, c.context.channel].filter(Boolean).join(" · ")}</dd>
            </dl>
          </section>

          <section>
            <h3 className="sub-h">Source</h3>
            <p>
              {c.source.ref}
              {c.source.url && (
                <> · <a href={c.source.url} target="_blank" rel="noreferrer noopener">open source</a></>
              )}
            </p>
            {(c.source.licence || c.source.accessed) && (
              <p className="muted-text">
                {c.source.licence}{c.source.licence && c.source.accessed ? " · " : ""}
                {c.source.accessed && <>accessed {c.source.accessed}</>}
              </p>
            )}
          </section>

          {c.field_provenance && (
            <section>
              <h3 className="sub-h">How each field was obtained</h3>
              <table className="prov-table">
                <tbody>
                  {Object.entries(c.field_provenance).map(([field, how]) => (
                    <tr key={field}>
                      <td><code>{field}</code></td>
                      <td><span className={`prov prov-${how}`}>{FIELD_LABEL[how] ?? how}</span></td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </section>
          )}
        </div>
      ) : (
        caseId && <div className="drawer-body"><p>Case {caseId} is not in the bundled library.</p></div>
      )}
    </dialog>
  );
}

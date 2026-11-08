import { useState } from "react";
import type { Triage, TriageRow } from "../types";
import { money } from "../format";
import { Pane, Pill } from "./Card";
import { Icon } from "./Icon";
import { shortDay } from "./PlanPanel";

const STATUS: Record<TriageRow["status"], { label: string; tone: "good" | "info" | "bad" | "neutral" }> = {
  delivered: { label: "Delivered", tone: "good" },
  in_transit: { label: "In transit", tone: "info" },
  lost: { label: "Lost", tone: "bad" },
  unknown: { label: "No tracking", tone: "neutral" },
};

const PROOF: Record<string, string> = {
  none: "none", tracking: "tracking only", confirmation: "delivery confirmation", gps: "GPS record", signature: "signature",
};

const RESPONSE: Record<string, string> = {
  evidence_delivery: "Proof of delivery",
  evidence_delivery_documented: "Proof of delivery + GPS/signature",
  message_eta: "Message delivery window",
  evidence_in_transit: "Respond now: in transit",
  refund_lost: "Refund, claim from carrier",
  gather_info: "Check records first",
  manual_review: "Review by hand",
  generic_tracking: "Submit tracking (generic)",
  generic_refund: "Offer refund (generic)",
};

/** Open item-not-received disputes split by real shipment state, each with the response precedent chose. */
export function TriagePane({ triage, generic }: { triage: Triage; generic: boolean }) {
  const [showRows, setShowRows] = useState(false);
  const total = triage.rows.length;
  const byCase = Object.fromEntries(triage.precedents.map((p) => [p.case_id, p]));
  return (
    <Pane id="triage" title="Open disputes by shipment state"
      pill={<Pill tone="neutral">{total} disputes</Pill>}
      sub={generic
        ? "Without precedent: one generic remedy for every dispute. Shipment state and deadlines are not checked."
        : "Each dispute is matched to past dispute cases by its parcel's real state and deadline. Cases that backfired are shown as warnings."}
      footer={
        <button className="link-btn" onClick={() => setShowRows(!showRows)} aria-expanded={showRows}>
          {showRows ? "Hide individual disputes" : `Show all ${total} disputes`} <Icon name="chevron" size={14} />
        </button>
      }>
      <div className="table-wrap">
        <table className="table">
          <thead>
            <tr><th>Shipment state</th><th>Disputes</th><th>Value</th><th>Respond by</th><th>Response</th><th>Based on</th></tr>
          </thead>
          <tbody>
            {triage.groups.map((g) => (
              <tr key={g.response}>
                <td>{g.states.join(", ")}</td>
                <td className="num">{g.count}</td>
                <td className="num nowrap">{money(g.total_value)}</td>
                <td className="nowrap">{shortDay(g.earliest_due)}</td>
                <td><strong>{RESPONSE[g.response] ?? g.label}</strong></td>
                <td>
                  <span className="chips" style={{ marginTop: 0 }}>
                    {g.cites.map((c) => (
                      <span key={c} className="chip match" title={`${byCase[c]?.title ?? c}: ${byCase[c]?.outcome ?? ""}`}>
                        {byCase[c]?.title ?? c}
                      </span>
                    ))}
                    {g.warnings.map((w) => (
                      <span key={w} className="chip differ" title={byCase[w]?.outcome}>avoid: {byCase[w]?.title ?? w}</span>
                    ))}
                    {!g.cites.length && !g.warnings.length && <span className="muted">no cases</span>}
                  </span>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      {triage.untriaged > 0 && (
        <p className="muted" style={{ marginTop: 12, fontSize: 13 }}>
          {triage.untriaged} open dispute(s) with other reasons (unauthorised, not as described) are not part of this triage.
        </p>
      )}
      {showRows && (
        <div className="table-wrap" style={{ marginTop: 16 }}>
          <table className="table">
            <thead>
              <tr><th>Dispute</th><th>Carrier</th><th>Product</th><th>Value</th><th>State</th><th>Proof</th><th>Expected</th><th>Due</th><th>Response</th></tr>
            </thead>
            <tbody>
              {triage.rows.map((r) => (
                <tr key={r.dispute_id}>
                  <td><code>{r.dispute_id}</code></td>
                  <td className="nowrap">{r.carrier}</td>
                  <td>{r.sku}</td>
                  <td className="num">{money(r.amount)}</td>
                  <td><Pill tone={STATUS[r.status].tone}>{STATUS[r.status].label}</Pill></td>
                  <td className="muted">{PROOF[r.proof] ?? r.proof}</td>
                  <td className="nowrap">{r.expected_delivery ? shortDay(r.expected_delivery) : "–"}</td>
                  <td className="nowrap">{shortDay(r.response_due)}</td>
                  <td>{RESPONSE[r.response] ?? r.response}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Pane>
  );
}

import type { SituationRecord } from "../types";
import { pct, pValue, rate, REASON_LABEL } from "../format";
import { Sparkline } from "./Sparkline";
import { SimulatedTag } from "./Badges";

function Meter({ label, value, note }: { label: string; value: number; note?: string }) {
  return (
    <div className="meter">
      <div className="meter-head">
        <span>{label}</span>
        <span className="num">{pct(value)}</span>
      </div>
      <div className="meter-track" aria-hidden="true">
        <div className="meter-fill" style={{ width: `${Math.min(100, value * 100)}%` }} />
      </div>
      {note && <div className="meter-note">{note}</div>}
    </div>
  );
}

export function SituationPanel({ situation }: { situation: SituationRecord }) {
  const f = situation.features;
  const reasons = Object.entries(f.reason_mix).sort((a, b) => b[1] - a[1]);
  const sandboxIds = situation.paypal_dispute_ids ?? [];
  return (
    <section className="panel" aria-labelledby="situation-h">
      <header className="panel-head">
        <h2 id="situation-h">Situation</h2>
        {situation.source !== "paypal_sandbox" && (
          <SimulatedTag title="The demo merchant's orders are a synthetic feed. Detection runs on it for real." />
        )}
      </header>

      <div className="headline-stat">
        <div>
          <div className="stat-label">Dispute rate, last 7 days</div>
          <div className="stat-big num">{rate(f.dispute_rate_7d)}</div>
          <div className="stat-sub num">
            95% CI {rate(f.dispute_rate_7d_ci95[0])} to {rate(f.dispute_rate_7d_ci95[1])}
          </div>
        </div>
        <div className="ratio">
          <div className="ratio-big num">{f.rate_ratio ? `${f.rate_ratio.toFixed(1)}x` : "n/a"}</div>
          <div className="stat-sub">vs 30-day baseline {rate(f.dispute_rate_30d_baseline)}</div>
        </div>
      </div>

      {f.daily_dispute_rate && (
        <div className="spark-wrap">
          <Sparkline values={f.daily_dispute_rate} baseline={f.dispute_rate_30d_baseline} />
          <div className="spark-legend">
            <span><i className="key key-line" /> daily rate</span>
            <span><i className="key key-dash" /> baseline</span>
          </div>
        </div>
      )}

      <div className={`anomaly ${f.anomaly.is_anomalous ? "on" : "off"}`}>
        {f.anomaly.is_anomalous ? "Anomaly" : "Within normal range"} · binomial test p = {pValue(f.anomaly.p_value)}
        {f.anomaly.min_sample_met === false && " · sample too small"}
      </div>

      <dl className="facts">
        <div><dt>Transactions (7d)</dt><dd className="num">{f.transactions_7d.toLocaleString()}</dd></div>
        <div><dt>Disputes (7d)</dt><dd className="num">{f.disputes_7d}</dd></div>
        <div><dt>Open disputes</dt><dd className="num">{f.open_disputes}</dd></div>
        <div><dt>Carriers elevated</dt><dd className="num">{f.carriers_elevated}</dd></div>
        <div><dt>Time to ship (median)</dt><dd className="num">{f.ship_delay_hours_p50} h</dd></div>
        <div><dt>Avg order</dt><dd className="num">${f.avg_amount?.toFixed(2) ?? "n/a"}</dd></div>
      </dl>

      <h3 className="sub-h">Why it is happening: signals</h3>
      <Meter label={`On one carrier${f.concentration.top_carrier ? `: ${f.concentration.top_carrier}` : ""}`} value={f.concentration.carrier ?? 0} />
      <Meter label={`On one SKU${f.concentration.top_sku ? `: ${f.concentration.top_sku}` : ""}`} value={f.concentration.sku ?? 0} />
      <Meter label="Disputed orders with a delivery scan" value={f.disputed_orders_delivered_share} />

      <h3 className="sub-h">Dispute reasons</h3>
      <div className="stack" role="img" aria-label={reasons.map(([k, v]) => `${REASON_LABEL[k] ?? k} ${pct(v)}`).join(", ")}>
        {reasons.map(([k, v], i) => (
          <div key={k} className={`stack-seg seg-${i}`} style={{ width: `${v * 100}%` }} title={`${REASON_LABEL[k] ?? k} ${pct(v)}`} />
        ))}
      </div>
      <ul className="stack-legend">
        {reasons.map(([k, v], i) => (
          <li key={k}><i className={`key seg-${i}`} />{REASON_LABEL[k] ?? k} <span className="num">{pct(v)}</span></li>
        ))}
      </ul>

      {sandboxIds.length > 0 && (
        <div className="sandbox-link">
          <span className="badge real">PayPal sandbox</span>
          Linked dispute <code>{sandboxIds.join(", ")}</code>, read live from the sandbox API.
        </div>
      )}
    </section>
  );
}

import type { ReactNode } from "react";
import type { Recommendation, SituationRecord } from "../types";
import { pct, pValue, QUALITY_LABEL, rate, REASON_LABEL } from "../format";
import { Card, Pill } from "./Card";
import { Donut, RateChart, SignalBars } from "./Charts";
import { SimulatedTag } from "./Badges";

function Kpi({ label, value, change, note }: { label: string; value: string; change?: ReactNode; note: string }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num">{value}</div>
      <div className="kpi-note">{change}{note}</div>
    </div>
  );
}

export function KpiRow({ situation, rec }: { situation: SituationRecord; rec: Recommendation }) {
  const f = situation.features;
  const ratio = f.rate_ratio ?? (f.dispute_rate_30d_baseline ? f.dispute_rate_7d / f.dispute_rate_30d_baseline : 0);
  const rising = ratio >= 1;
  return (
    <div className="kpis">
      <Kpi label="Dispute rate (7d)" value={rate(f.dispute_rate_7d)}
        change={<span className={`delta ${rising ? "bad" : "good"}`}>{ratio.toFixed(1)}x</span>}
        note={`vs 30-day baseline ${rate(f.dispute_rate_30d_baseline)}`} />
      <Kpi label="Disputes (7d)" value={f.disputes_7d.toLocaleString()}
        note={`of ${f.transactions_7d.toLocaleString()} transactions · ${f.open_disputes} open`} />
      <Kpi label="Anomaly test" value={f.anomaly.is_anomalous ? "Anomaly" : "Normal"}
        change={<span className={`delta ${f.anomaly.is_anomalous ? "bad" : "good"}`}>p = {pValue(f.anomaly.p_value)}</span>}
        note={f.anomaly.min_sample_met === false ? " · sample too small" : " · one-sided binomial"} />
      <Kpi label="Plan confidence" value={rec.abstain && rec.confidence === 0 ? "n/a" : pct(rec.confidence)}
        change={rec.abstain ? <span className="delta warn">Abstained</span> : undefined}
        note={`${rec.abstain ? " · " : ""}evidence: ${(QUALITY_LABEL[rec.evidence_quality] ?? rec.evidence_quality).toLowerCase()}`} />
    </div>
  );
}

export function RateCard({ situation }: { situation: SituationRecord }) {
  const f = situation.features;
  const ratio = f.rate_ratio ?? 0;
  return (
    <Card id="rate" className="span-8"
      title="Daily dispute rate"
      pill={ratio ? <Pill tone={ratio >= 1.5 ? "bad" : "neutral"} dir={ratio >= 1 ? "up" : "down"}>{ratio.toFixed(1)}x</Pill> : null}
      sub={<>Shaded area is the 7-day window. 95% CI {rate(f.dispute_rate_7d_ci95[0])} to {rate(f.dispute_rate_7d_ci95[1])}.</>}
      right={situation.source !== "paypal_sandbox" ? <SimulatedTag title="The demo merchant's orders are a synthetic feed. Detection runs on it for real." /> : null}>
      {f.daily_dispute_rate ? (
        <RateChart values={f.daily_dispute_rate} baseline={f.dispute_rate_30d_baseline} end={situation.window.end} windowDays={7} />
      ) : (
        <p className="muted-text">No daily series for this situation.</p>
      )}
    </Card>
  );
}

export function ReasonsCard({ situation }: { situation: SituationRecord }) {
  const parts = Object.entries(situation.features.reason_mix)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ key: k, label: REASON_LABEL[k] ?? k, value: v }));
  return (
    <Card id="reasons" className="span-4" title="Dispute reasons" sub="Share of disputes in the last 7 days, by reason.">
      <Donut parts={parts} label={parts.map((p) => `${p.label} ${pct(p.value)}`).join(", ")} />
    </Card>
  );
}

export function SignalsCard({ situation }: { situation: SituationRecord }) {
  const f = situation.features;
  const c = f.concentration;
  const bars = [
    { key: "carrier", label: "One carrier", value: c.carrier ?? 0, note: c.top_carrier ? `Share of disputes on ${c.top_carrier}` : undefined },
    { key: "sku", label: "One SKU", value: c.sku ?? 0, note: c.top_sku ? `Share of disputes on ${c.top_sku}` : undefined },
    { key: "delivered", label: "Delivery scan", value: f.disputed_orders_delivered_share, note: "Disputed orders that show a delivery scan" },
  ];
  return (
    <Card id="signals" className="span-6" title="Why it is happening" sub="Signals the Situation Builder computed from the order feed.">
      <div className="signals">
        <SignalBars bars={bars} />
        <dl className="facts">
          <div><dt>Top carrier</dt><dd>{c.top_carrier ?? "n/a"}</dd></div>
          <div><dt>Top SKU</dt><dd>{c.top_sku ?? "n/a"}</dd></div>
          <div><dt>Carriers elevated</dt><dd className="num">{f.carriers_elevated}</dd></div>
          <div><dt>Time to ship (median)</dt><dd className="num">{f.ship_delay_hours_p50} h</dd></div>
          <div><dt>Average order</dt><dd className="num">{f.avg_amount !== undefined ? `$${f.avg_amount.toFixed(2)}` : "n/a"}</dd></div>
        </dl>
      </div>
    </Card>
  );
}

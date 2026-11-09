import type { ReactNode } from "react";
import type { Recommendation, SituationRecord } from "../types";
import { pct, pValue, QUALITY_LABEL, rate, REASON_LABEL } from "../format";
import { Pane, Pill } from "./Card";
import { Donut, Meters, RateChart, RateLegend } from "./Charts";
import { SimulatedTag } from "./Badges";
import { Icon } from "./Icon";

const day = (iso: string) =>
  new Date(`${iso}T00:00:00Z`).toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

export function PageHeader({ situation, label, anomalous }: { situation: SituationRecord; label: string; anomalous: boolean }) {
  return (
    <header className="page-head">
      <div className="eyebrow">
        <span className={`pulse ${anomalous ? "on" : ""}`} aria-hidden="true" />
        <span>{label}</span>
        <span className="eyebrow-sep" aria-hidden="true">·</span>
        <span>{day(situation.window.start)} to {day(situation.window.end)}</span>
        {situation.source !== "paypal_sandbox" && (
          <SimulatedTag title="The demo merchant's orders are a synthetic feed. Detection runs on it for real." />
        )}
      </div>
      <h1 className="page-title">{situation.narrative}</h1>
    </header>
  );
}

/** Shown when the order feed sees overlapping causes (scenario D): the plan abstains and asks for review. */
export function ConflictNotice({ situation }: { situation: SituationRecord }) {
  const c = situation.features.diagnostic_conflict;
  if (!c) return null;
  return (
    <div className="callout warn" role="status">
      <Icon name="alert" />
      <div>
        <p className="callout-title">Review needed: more than one cause may be at work</p>
        <p>
          Dispatch is slow, and orders shipped within {c.prompt_ship_hours}h also show elevated not-received disputes
          without delivery scans ({c.window_lost_inr} of {c.window_orders.toLocaleString()} this window vs {c.baseline_lost_inr} of{" "}
          {c.baseline_orders.toLocaleString()} before; one-sided Fisher exact p = {pValue(c.p_value)}). A single remedy may miss
          part of the problem, so no action is proposed.
        </p>
      </div>
    </div>
  );
}

function Kpi({ label, value, change, note }: { label: string; value: string; change?: ReactNode; note: ReactNode }) {
  return (
    <div className="kpi">
      <div className="kpi-label">{label}</div>
      <div className="kpi-value num">{value}</div>
      <div className="kpi-note">{change}{note}</div>
    </div>
  );
}

/** One strip, four cells split by dividers (not four separate cards). */
export function KpiStrip({ situation, rec }: { situation: SituationRecord; rec: Recommendation }) {
  const f = situation.features;
  const ratio = f.rate_ratio ?? (f.dispute_rate_30d_baseline ? f.dispute_rate_7d / f.dispute_rate_30d_baseline : 0);
  return (
    <div className="kpis" role="group" aria-label="Key numbers">
      <Kpi label="Dispute rate, 7 days" value={rate(f.dispute_rate_7d)}
        change={<Pill tone={ratio >= 1.5 ? "bad" : "neutral"} dir={ratio >= 1 ? "up" : "down"}>{ratio.toFixed(1)}x</Pill>}
        note={<>vs baseline {rate(f.dispute_rate_30d_baseline)}</>} />
      <Kpi label="Disputes, 7 days" value={f.disputes_7d.toLocaleString()}
        note={<>of {f.transactions_7d.toLocaleString()} transactions · {f.open_disputes} open</>} />
      <Kpi label="Anomaly test" value={f.anomaly.is_anomalous ? "Anomaly" : "Normal"}
        change={<Pill tone={f.anomaly.is_anomalous ? "bad" : "good"}>p = {pValue(f.anomaly.p_value)}</Pill>}
        note={f.anomaly.min_sample_met === false ? "sample too small" : "one-sided binomial"} />
      <Kpi label="Plan confidence" value={rec.abstain && rec.confidence === 0 ? "n/a" : pct(rec.confidence)}
        change={rec.abstain ? <Pill tone="warn">Abstained</Pill> : undefined}
        note={<>evidence: {(QUALITY_LABEL[rec.evidence_quality] ?? rec.evidence_quality).toLowerCase()}</>} />
    </div>
  );
}

export function RatePane({ situation }: { situation: SituationRecord }) {
  const f = situation.features;
  return (
    <Pane id="rate" title="Daily dispute rate"
      sub={<>7-day rate {rate(f.dispute_rate_7d)}, 95% CI {rate(f.dispute_rate_7d_ci95[0])} to {rate(f.dispute_rate_7d_ci95[1])}.</>}
      right={<RateLegend />}>
      {f.daily_dispute_rate ? (
        <RateChart values={f.daily_dispute_rate} baseline={f.dispute_rate_30d_baseline} end={situation.window.end} windowDays={7} />
      ) : (
        <p className="muted">No daily series for this situation.</p>
      )}
    </Pane>
  );
}

export function ReasonsPane({ situation }: { situation: SituationRecord }) {
  const parts = Object.entries(situation.features.reason_mix)
    .filter(([, v]) => v > 0)
    .sort((a, b) => b[1] - a[1])
    .map(([k, v]) => ({ key: k, label: REASON_LABEL[k] ?? k, value: v }));
  return (
    <Pane id="reasons" title="Dispute reasons" sub="Share of the last 7 days' disputes.">
      <Donut parts={parts} total={situation.features.disputes_7d} totalLabel="disputes" />
    </Pane>
  );
}

export function SignalsPane({ situation }: { situation: SituationRecord }) {
  const f = situation.features;
  const c = f.concentration;
  return (
    <Pane id="signals" title="Signals" sub="What the Situation Builder measured in the order feed.">
      <Meters rows={[
        { key: "carrier", label: "Disputes on one carrier", detail: c.top_carrier, value: c.carrier ?? 0 },
        { key: "sku", label: "Disputes on one product", detail: c.top_sku, value: c.sku ?? 0 },
        { key: "delivered", label: "Disputed orders with a delivery scan", value: f.disputed_orders_delivered_share },
      ]} />
      <dl className="facts">
        <div><dt>Carriers elevated</dt><dd className="num">{f.carriers_elevated}</dd></div>
        <div><dt>Time to ship, median</dt><dd className="num">{f.ship_delay_hours_p50} h</dd></div>
        <div><dt>Average order</dt><dd className="num">{f.avg_amount !== undefined ? `$${f.avg_amount.toFixed(2)}` : "n/a"}</dd></div>
      </dl>
    </Pane>
  );
}

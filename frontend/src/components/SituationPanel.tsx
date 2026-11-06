import { SituationRecord } from "../types/api";

export function SituationPanel({ situation }: { situation: SituationRecord }) {
  const trendColors = {
    improving: "var(--success, #22c55e)",
    stable: "var(--muted-foreground, #9ca3af)",
    degrading: "var(--destructive, #ef4444)",
  };

  return (
    <section className="panel situation-panel">
      <h2>Situation</h2>
      <div className="metric-grid">
        <div className="metric">
          <span className="metric-label">7-Day Dispute Rate</span>
          <span className="metric-value">{situation.dispute_rate.toFixed(1)} / 100</span>
        </div>
        <div className="metric">
          <span className="metric-label">30-Day Baseline</span>
          <span className="metric-value">{situation.baseline_rate.toFixed(1)} / 100</span>
        </div>
        <div className="metric">
          <span className="metric-label">Trend</span>
          <span 
            className="metric-value trend-badge" 
            style={{ backgroundColor: trendColors[situation.trend] + "20", color: trendColors[situation.trend] }}
          >
            {situation.trend}
          </span>
        </div>
        <div className="metric">
          <span className="metric-label">Open Disputes</span>
          <span className="metric-value">{situation.open_disputes}</span>
        </div>
        <div className="metric">
          <span className="metric-label">Median Response Time</span>
          <span className="metric-value">{situation.response_time.toFixed(1)} days</span>
        </div>
      </div>

      <div className="section">
        <h3>Reason Mix</h3>
        <div className="reason-mix">
          {Object.entries(situation.reason_mix).map(([reason, pct]) => (
            <div key={reason} className="reason-item">
              <span className="reason-name">{reason.replace(/_/g, " ")}</span>
              <div className="reason-bar">
                <div 
                  className="reason-fill" 
                  style={{ width: `${pct}%` }}
                />
              </div>
              <span className="reason-pct">{pct}%</span>
            </div>
          ))}
        </div>
      </div>

      <div className="section">
        <h3>Concentration</h3>
        <div className="concentration">
          <div className="concentration-item">
            <span className="conc-label">Top Carrier</span>
            <span className="conc-value">{situation.concentration.top_carrier || "—"}</span>
          </div>
          <div className="concentration-item">
            <span className="conc-label">Elevated Carriers</span>
            <span className="conc-value">{situation.concentration.carrier_count}</span>
          </div>
          <div className="concentration-item">
            <span className="conc-label">Top SKU</span>
            <span className="conc-value">{situation.concentration.top_sku || "—"}</span>
          </div>
          <div className="concentration-item">
            <span className="conc-label">Elevated SKUs</span>
            <span className="conc-value">{situation.concentration.sku_count}</span>
          </div>
        </div>
      </div>

      <div className="section narrative">
        <h3>Narrative</h3>
        <p>{situation.narrative}</p>
        <span className="scenario-badge">Scenario: {situation.scenario.replace(/_/g, " ")}</span>
      </div>
    </section>
  );
}
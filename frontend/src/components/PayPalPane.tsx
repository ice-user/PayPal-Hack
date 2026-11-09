import { useEffect, useState } from "react";
import type { PayPalAccount, PayPalCall, PayPalDispute } from "../types";
import { getPayPalActivity } from "../api";
import { Pane, Pill } from "./Card";
import { Icon } from "./Icon";
import { shortDay } from "./PlanPanel";

const words = (s: string | null | undefined) => (s ? s.replaceAll("_", " ").toLowerCase() : "–");

function ago(iso: string | null | undefined, now: number): string {
  if (!iso) return "never";
  const s = Math.max(0, Math.round((now - Date.parse(iso)) / 1000));
  if (s < 60) return `${s}s ago`;
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  return `${Math.round(s / 3600)} h ago`;
}

const PARCEL: Record<PayPalDispute["shipment_status"], { label: string; tone: "good" | "info" | "bad" | "neutral" }> = {
  delivered: { label: "Delivered", tone: "good" },
  in_transit: { label: "In transit", tone: "info" },
  lost: { label: "Lost", tone: "bad" },
  unknown: { label: "No tracker", tone: "neutral" },
};

function money(a: PayPalDispute["amount"]): string {
  return a ? `${a.currency_code === "USD" ? "$" : `${a.currency_code} `}${Number(a.value).toFixed(2)}` : "–";
}

function useNow(ms: number): number {
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    const t = window.setInterval(() => setNow(Date.now()), ms);
    return () => clearInterval(t);
  }, [ms]);
  return now;
}

/** The connected PayPal sandbox account: what Precedent imported, and what PayPal allows now. */
export function PayPalAccountPane({ account, onRefresh, refreshing }: {
  account: PayPalAccount; onRefresh: () => void; refreshing: boolean;
}) {
  const now = useNow(5000);
  const real = account.real_actions;
  const realText = !account.connected
    ? null
    : !real
      ? "Approvals on this deployment are simulated; PayPal is only read."
      : real.includes("ALL")
        ? "Approved actions on a linked dispute are sent to PayPal for real (sandbox)."
        : `Sent to PayPal for real on this site: ${real.map((t) => words(t)).join(", ")}. Refunds and offers stay simulated${account.real_calls_per_hour ? `; at most ${account.real_calls_per_hour} real actions an hour` : ""}.`;
  return (
    <Pane id="paypal-account" title="Connected PayPal account"
      pill={account.connected ? <Pill tone="good">Sandbox · live</Pill> : <Pill tone="neutral">Not connected</Pill>}
      sub={account.connected
        ? <>Read from PayPal {ago(account.fetched_at, now)}: every dispute on the account, its allowed seller actions, and the parcel's state from PayPal shipment tracking.</>
        : "This deployment has no PayPal sandbox credentials, so nothing is read from PayPal."}
      right={account.connected && (
        <button className="btn" onClick={onRefresh} disabled={refreshing} aria-label="Refresh from PayPal">
          <Icon name="forward" size={14} /> {refreshing ? "Reading…" : "Refresh"}
        </button>
      )}
      footer={realText && <p className="muted" style={{ fontSize: 13, margin: 0 }}>{realText}</p>}>
      {account.error && (
        <div className="callout warn" role="status">
          <Icon name="alert" />
          <div><p>{account.error}</p></div>
        </div>
      )}
      {account.connected && account.disputes.length === 0 && !account.error && (
        <p className="muted">No disputes on this sandbox account yet. Open one as the sandbox buyer and press Refresh.</p>
      )}
      {account.disputes.length > 0 && (
        <div className="table-wrap">
          <table className="table">
            <thead>
              <tr><th>Dispute</th><th>PayPal status</th><th>Parcel</th><th>Seller can now</th><th>Precedent</th></tr>
            </thead>
            <tbody>
              {account.disputes.map((d) => (
                <tr key={d.dispute_id}>
                  <td>
                    <code>{d.dispute_id}</code>
                    <div className="muted" style={{ fontSize: 12 }}>{d.item} · {money(d.amount)} · {words(d.reason)}</div>
                  </td>
                  <td>{words(d.status)}{d.stage && <div className="muted" style={{ fontSize: 12 }}>{words(d.stage)} stage</div>}</td>
                  <td>
                    <Pill tone={PARCEL[d.shipment_status].tone}>{PARCEL[d.shipment_status].label}</Pill>
                    <div className="muted" style={{ fontSize: 12 }}>{d.tracking_number ?? "from PayPal tracking"}</div>
                  </td>
                  <td>{d.allowed.length ? d.allowed.map(words).join(", ") : <span className="muted">nothing right now</span>}</td>
                  <td>{d.triaged
                    ? <><strong>Triaged</strong><div className="muted" style={{ fontSize: 12 }}>respond by {shortDay(d.response_due)}, see Decision</div></>
                    : <span className="muted">Waiting on the other party; nothing to answer</span>}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </Pane>
  );
}

/** The latest requests the backend made to PayPal, so the integration can be seen working. */
export function PayPalActivityPane({ tick }: { tick: unknown }) {
  const [calls, setCalls] = useState<PayPalCall[] | null>(null);
  const now = useNow(5000);
  useEffect(() => {
    let alive = true;
    const load = () => {
      if (document.visibilityState === "visible")
        getPayPalActivity(14).then((c) => alive && setCalls(c)).catch(() => alive && setCalls([]));
    };
    load();
    const t = window.setInterval(load, 8000);
    return () => { alive = false; clearInterval(t); };
  }, [tick]);
  return (
    <Pane id="paypal-activity" title="PayPal API calls"
      sub="Live log of this server's requests to api-m.sandbox.paypal.com. No tokens or personal data are recorded."
      footer={<span className="chips" style={{ marginTop: 0 }}>
        {["OAuth 2.0", "Disputes API", "Add Tracking API", "Webhooks"].map((t) => <span key={t} className="chip">{t}</span>)}
      </span>}>
      {calls === null && <p className="muted">Loading…</p>}
      {calls?.length === 0 && <p className="muted">No PayPal calls yet on this server.</p>}
      {calls && calls.length > 0 && (
        <ol className="calls">
          {calls.map((c, i) => (
            <li key={`${c.at}-${i}`}>
              <span className={`call-status ${c.status >= 200 && c.status < 300 ? "ok" : "bad"}`}>{c.status || "ERR"}</span>
              <code className="call-path"><strong>{c.method}</strong> {c.path}</code>
              <span className="muted call-meta">{c.ms} ms · {ago(c.at, now)}</span>
            </li>
          ))}
        </ol>
      )}
    </Pane>
  );
}

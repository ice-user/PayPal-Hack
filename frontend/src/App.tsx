import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Action, ActionState, Bundle, LiveDispute, Mode, TimelineEvent } from "./types";
import { advanceClock, approveAction, dataMode, getBundle, getLiveDispute, listSituations, rejectAction } from "./api";
import thresholds from "@contracts/thresholds.json";
import { SituationPanel } from "./components/SituationPanel";
import { PrecedentsPanel } from "./components/PrecedentsPanel";
import { PlanPanel, type ActionView } from "./components/PlanPanel";
import { Timeline } from "./components/Timeline";

const situations = listSituations();
const API = dataMode === "api";

/** Fixture mode only: fold the user's clicks into the static timeline. */
function liveTimeline(base: TimelineEvent[], states: Record<string, ActionState>): TimelineEvent[] {
  const vals = Object.values(states);
  const approved = vals.filter((s) => s !== "rejected" && s !== "proposed").length;
  const done = vals.filter((s) => s === "succeeded").length;
  const rejected = vals.filter((s) => s === "rejected").length;
  return base.map((e) => {
    if (e.step === "approved" && (approved || rejected))
      return { ...e, status: approved ? "done" : "skipped", detail: `${approved} approved, ${rejected} rejected by you.` };
    if (e.step === "executed" && done)
      return { ...e, status: "done", detail: `${done} action(s) executed in the browser only (fixture mode). Run the API for sandbox calls.` };
    return e;
  });
}

export default function App() {
  const [key, setKey] = useState(situations[0]?.key ?? "A");
  const [mode, setMode] = useState<Mode>("with_precedent");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [notice, setNotice] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [live, setLive] = useState<{ dispute?: LiveDispute; error?: string } | null>(null);

  // Fixture mode keeps action states per recommendation in the browser.
  const [localStates, setLocalStates] = useState<Record<string, Record<string, ActionState>>>({});
  const timers = useRef<number[]>([]);
  const recId = bundle?.recommendation.recommendation_id ?? "";
  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setNotice(null);
    setBundle(null);
    getBundle(key, mode)
      .then((b) => !cancelled && setBundle(b))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [key, mode]);

  const disputeId = bundle?.situation.paypal_dispute_ids?.[0];
  const refreshLive = useCallback(() => {
    if (!API || !disputeId) return setLive(null);
    getLiveDispute(disputeId)
      .then((d) => setLive({ dispute: d }))
      .catch((e: Error) => setLive({ error: e.message }));
  }, [disputeId]);
  useEffect(refreshLive, [refreshLive]);

  const views: Record<string, ActionView> = useMemo(() => {
    if (!bundle) return {};
    if (API) {
      return Object.fromEntries(
        Object.entries(bundle.action_states ?? {}).map(([id, s]) => [
          id,
          { state: s.state, mode: s.execution_mode ?? undefined, detail: s.detail ?? undefined },
        ]),
      );
    }
    return Object.fromEntries(Object.entries(localStates[recId] ?? {}).map(([id, st]) => [id, { state: st }]));
  }, [bundle, localStates, recId]);

  const timeline = useMemo(() => {
    if (!bundle) return [];
    if (API) return bundle.timeline;
    return liveTimeline(bundle.timeline, localStates[recId] ?? {});
  }, [bundle, localStates, recId]);

  const setLocal = (rid: string, actionId: string, st: ActionState) =>
    setLocalStates((all) => ({ ...all, [rid]: { ...(all[rid] ?? {}), [actionId]: st } }));

  const run = async (label: string, fn: () => Promise<Bundle>) => {
    setBusy(label);
    setNotice(null);
    try {
      setBundle(await fn());
      refreshLive();
    } catch (e) {
      setNotice((e as Error).message);
    } finally {
      setBusy(null);
    }
  };

  const approve = (a: Action) => {
    if (API) return run(a.action_id, () => approveAction(key, mode, a.action_id));
    const rid = recId;
    setLocal(rid, a.action_id, "executing");
    timers.current.push(window.setTimeout(() => setLocal(rid, a.action_id, "succeeded"), 1200));
  };
  const reject = (a: Action) => {
    if (API) return run(a.action_id, () => rejectAction(key, mode, a.action_id));
    setLocal(recId, a.action_id, "rejected");
  };

  const canAdvance =
    API && !!bundle && !bundle.outcome &&
    bundle.policy_decisions.some((d) => d.decision === "NEEDS_APPROVAL" && views[d.action_id]?.state === "succeeded");

  return (
    <div className="app">
      <header className="topbar">
        <div className="brand">
          <span className="logo" aria-hidden="true">P</span>
          <div>
            <div className="brand-name">Precedent</div>
            <div className="brand-sub">Demo electronics store · PayPal sandbox</div>
          </div>
        </div>

        <div className="controls">
          <div className="segmented" role="group" aria-label="Demo situation">
            {situations.map((s) => (
              <button key={s.key} aria-pressed={s.key === key} onClick={() => setKey(s.key)}>
                {s.label}
              </button>
            ))}
          </div>
          <label className="toggle">
            <input
              type="checkbox"
              checked={mode === "with_precedent"}
              onChange={(e) => setMode(e.target.checked ? "with_precedent" : "no_precedent")}
            />
            <span className="toggle-track" aria-hidden="true"><span className="toggle-thumb" /></span>
            <span>{mode === "with_precedent" ? "With precedent" : "Without precedent"}</span>
          </label>
        </div>
      </header>

      <div className="banner">
        {API ? (
          <>API mode: plans, approvals and the outcome clock run on the backend. Approved actions are sent to the PayPal sandbox when the dispute allows them; otherwise they are simulated and labelled. The order feed is synthetic.</>
        ) : (
          <>Fixture mode: data comes from <code>contracts/fixtures</code>. The order feed is synthetic, cases are labelled, and execution is simulated in the browser.</>
        )}
      </div>

      {loading && <div className="loading" role="status">Loading situation…</div>}
      {error && <div className="error" role="alert">Could not load this situation: {error}</div>}
      {notice && <div className="notice" role="alert">{notice}</div>}

      {bundle && !error && (
        <>
          <div className="narrative">
            <span className={`pulse ${bundle.situation.features.anomaly.is_anomalous ? "on" : ""}`} aria-hidden="true" />
            {bundle.situation.narrative}
          </div>
          <main className="grid">
            <SituationPanel situation={bundle.situation} live={live} apiMode={API} />
            <PrecedentsPanel rec={bundle.recommendation} similarityMin={thresholds.similarity_min} />
            <PlanPanel
              rec={bundle.recommendation}
              decisions={bundle.policy_decisions}
              views={views}
              busy={busy}
              outcome={bundle.outcome ?? null}
              onApprove={approve}
              onReject={reject}
            />
          </main>
          <Timeline
            events={timeline}
            action={
              canAdvance ? (
                <button className="btn primary" disabled={busy !== null}
                  onClick={() => run("advance", () => advanceClock(key, mode, 14))}>
                  {busy === "advance" ? "Advancing…" : "Advance 14 days (simulated)"}
                </button>
              ) : null
            }
          />
        </>
      )}

      <footer className="foot">
        Decision support with cited precedents, not financial advice. Outcomes are observed, never claimed as caused.
      </footer>
    </div>
  );
}

import { useEffect, useMemo, useRef, useState } from "react";
import type { Action, ActionState, Bundle, Mode, TimelineEvent } from "./types";
import { dataMode, getBundle, listSituations } from "./api";
import thresholds from "@contracts/thresholds.json";
import { SituationPanel } from "./components/SituationPanel";
import { PrecedentsPanel } from "./components/PrecedentsPanel";
import { PlanPanel } from "./components/PlanPanel";
import { Timeline } from "./components/Timeline";

const situations = listSituations();

/** Fold the user's approve/reject clicks into the fixture timeline. */
function liveTimeline(base: TimelineEvent[], states: Record<string, ActionState>): TimelineEvent[] {
  const vals = Object.values(states);
  const approved = vals.filter((s) => s !== "rejected" && s !== "proposed").length;
  const done = vals.filter((s) => s === "succeeded").length;
  const rejected = vals.filter((s) => s === "rejected").length;
  return base.map((e) => {
    if (e.step === "approved" && (approved || rejected))
      return { ...e, status: approved ? "done" : "skipped", detail: `${approved} approved, ${rejected} rejected by you.` };
    if (e.step === "executed" && done)
      return { ...e, status: "done", detail: `${done} action(s) executed. Sandbox seller actions are simulated (see docs/SPIKE1_RESULT.md).` };
    return e;
  });
}

export default function App() {
  const [key, setKey] = useState(situations[0]?.key ?? "A");
  const [mode, setMode] = useState<Mode>("with_precedent");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  // Action states are kept per recommendation, so flipping the toggle never leaks an
  // approval from one plan into another, and flipping back keeps what you did.
  const [allStates, setAllStates] = useState<Record<string, Record<string, ActionState>>>({});
  const timers = useRef<number[]>([]);
  const recId = bundle?.recommendation.recommendation_id ?? "";
  const states = allStates[recId] ?? {};

  useEffect(() => () => timers.current.forEach(clearTimeout), []);

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    setBundle(null);
    getBundle(key, mode)
      .then((b) => !cancelled && setBundle(b))
      .catch((e: Error) => !cancelled && setError(e.message))
      .finally(() => !cancelled && setLoading(false));
    return () => {
      cancelled = true;
    };
  }, [key, mode]);

  const timeline = useMemo(() => (bundle ? liveTimeline(bundle.timeline, states) : []), [bundle, states]);

  const setState = (rid: string, actionId: string, st: ActionState) =>
    setAllStates((all) => ({ ...all, [rid]: { ...(all[rid] ?? {}), [actionId]: st } }));

  const approve = (a: Action) => {
    const rid = recId;
    setState(rid, a.action_id, "approved");
    timers.current.push(window.setTimeout(() => setState(rid, a.action_id, "succeeded"), 1200));
  };
  const reject = (a: Action) => setState(recId, a.action_id, "rejected");

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

      {dataMode === "fixtures" && (
        <div className="banner">
          Fixture mode: data comes from <code>contracts/fixtures</code>. The order feed is synthetic, cases are authored and labelled, and execution is simulated.
        </div>
      )}

      {loading && <div className="loading" role="status">Loading situation…</div>}
      {error && <div className="error" role="alert">Could not load this situation: {error}</div>}

      {bundle && !error && (
        <>
          <div className="narrative">
            <span className={`pulse ${bundle.situation.features.anomaly.is_anomalous ? "on" : ""}`} aria-hidden="true" />
            {bundle.situation.narrative}
          </div>
          <main className="grid">
            <SituationPanel situation={bundle.situation} />
            <PrecedentsPanel rec={bundle.recommendation} similarityMin={thresholds.similarity_min} />
            <PlanPanel
              rec={bundle.recommendation}
              decisions={bundle.policy_decisions}
              states={states}
              onApprove={approve}
              onReject={reject}
            />
          </main>
          <Timeline events={timeline} />
        </>
      )}

      <footer className="foot">
        Decision support with cited precedents, not financial advice. Outcomes are observed, never claimed as caused.
      </footer>
    </div>
  );
}

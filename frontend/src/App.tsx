import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Action, ActionState, Bundle, LiveDispute, Mode, TimelineEvent } from "./types";
import {
  advanceClock, approveAction, dataMode, getAudit, getBundle, getLiveDispute, listSituations, rejectAction, reviewCase,
  type AuditEvent,
} from "./api";
import { AuditLog } from "./components/AuditLog";
import thresholds from "@contracts/thresholds.json";
import { KpiRow, RateCard, ReasonsCard, SignalsCard } from "./components/Overview";
import { PrecedentsPanel } from "./components/PrecedentsPanel";
import { ActionsCard, DiagnosisCard, type ActionView } from "./components/PlanPanel";
import { Timeline } from "./components/Timeline";
import { CaseDrawer } from "./components/CaseDrawer";
import { Sidebar, Topbar } from "./components/Shell";
import { Icon } from "./components/Icon";

type Theme = "dark" | "light";
const THEME_KEY = "precedent-theme";

function initialTheme(): Theme {
  try {
    const saved = localStorage.getItem(THEME_KEY);
    if (saved === "dark" || saved === "light") return saved;
  } catch {
    /* storage blocked: fall through to the default */
  }
  return "dark";
}

const narrow = () => window.matchMedia("(max-width: 960px)").matches;

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
  const [openCase, setOpenCase] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);

  useEffect(() => {
    document.documentElement.dataset.theme = theme;
    try {
      localStorage.setItem(THEME_KEY, theme);
    } catch {
      /* not persisted; fine */
    }
  }, [theme]);

  const toggleSidebar = () => (narrow() ? setMobileOpen((o) => !o) : setCollapsed((c) => !c));

  useEffect(() => {
    if (!API || !bundle) return;
    getAudit(25).then(setAudit).catch(() => setAudit([]));
  }, [bundle]);

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

  const review = (caseId: string, decision: "approved" | "rejected") =>
    run("review", async () => {
      await reviewCase(caseId, decision);
      return getBundle(key, mode);
    });

  const canAdvance =
    API && !!bundle && !bundle.outcome &&
    bundle.policy_decisions.some((d) => d.decision === "NEEDS_APPROVAL" && views[d.action_id]?.state === "succeeded");

  const current = situations.find((s) => s.key === key);
  const anomalous = !!bundle?.situation.features.anomaly.is_anomalous;

  return (
    <div className={`layout ${collapsed ? "collapsed" : ""}`}>
      <Sidebar
        open={mobileOpen}
        situations={situations}
        current={key}
        anomalous={anomalous}
        onPick={setKey}
        apiMode={API}
        disputeIds={bundle?.situation.paypal_dispute_ids ?? []}
        live={live}
        onNavigate={() => setMobileOpen(false)}
      />
      {mobileOpen && <div className="scrim" onClick={() => setMobileOpen(false)} aria-hidden="true" />}

      <div className="inset">
        <Topbar
          label={current?.label ?? key}
          mode={mode}
          onMode={setMode}
          theme={theme}
          onTheme={() => setTheme(theme === "dark" ? "light" : "dark")}
          onToggleSidebar={toggleSidebar}
        />

        <main className="content" id="top">
          {bundle && !error && (
            <div className="narrative">
              <span className={`pulse ${anomalous ? "on" : ""}`} aria-hidden="true" />
              <p>{bundle.situation.narrative}</p>
            </div>
          )}

          {loading && <div className="state-msg" role="status">Loading situation…</div>}
          {error && <div className="state-msg error" role="alert">Could not load this situation: {error}</div>}
          {notice && <div className="toast" role="alert">{notice}</div>}

          {bundle && !error && (
            <>
              <KpiRow situation={bundle.situation} rec={bundle.recommendation} />
              <div className="grid">
                <RateCard situation={bundle.situation} />
                <ReasonsCard situation={bundle.situation} />
                <DiagnosisCard
                  rec={bundle.recommendation}
                  outcome={bundle.outcome ?? null}
                  busy={busy}
                  onOpenCase={setOpenCase}
                  onReview={API ? review : undefined}
                />
                <SignalsCard situation={bundle.situation} />
                <PrecedentsPanel rec={bundle.recommendation} similarityMin={thresholds.similarity_min} onOpenCase={setOpenCase} />
                <ActionsCard
                  rec={bundle.recommendation}
                  decisions={bundle.policy_decisions}
                  views={views}
                  busy={busy}
                  onApprove={approve}
                  onReject={reject}
                  onOpenCase={setOpenCase}
                />
                <Timeline
                  events={timeline}
                  action={
                    canAdvance ? (
                      <button className="btn primary block" disabled={busy !== null}
                        onClick={() => run("advance", () => advanceClock(key, mode, 14))}>
                        <Icon name="forward" size={14} />
                        {busy === "advance" ? "Advancing…" : "Advance 14 days (simulated)"}
                      </button>
                    ) : null
                  }
                />
                {API && audit.length > 0 && <AuditLog events={audit} />}
              </div>
            </>
          )}

          <footer className="foot">
            Decision support with cited precedents, not financial advice. Outcomes are observed, never claimed as caused.
          </footer>
        </main>
      </div>

      <CaseDrawer caseId={openCase} onClose={() => setOpenCase(null)} apiMode={API} />
    </div>
  );
}

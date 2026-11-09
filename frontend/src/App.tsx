import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import type { Action, ActionState, Bundle, LiveDispute, Mode, TimelineEvent } from "./types";
import {
  advanceClock, approveAction, dataMode, refreshPayPal, resetDemo, getAudit, getBundle, getLiveDispute, listSituations, rejectAction, reviewCase,
  type AuditEvent,
} from "./api";
import thresholds from "@contracts/thresholds.json";
import { AuditLog } from "./components/AuditLog";
import { ConflictNotice, KpiStrip, PageHeader, RatePane, ReasonsPane, SignalsPane } from "./components/Overview";
import { PrecedentsPanel } from "./components/PrecedentsPanel";
import { ActionsPane, DiagnosisPane, NextStep, type ActionView } from "./components/PlanPanel";
import { Timeline } from "./components/Timeline";
import { TriagePane } from "./components/TriagePane";
import { PayPalAccountPane, PayPalActivityPane } from "./components/PayPalPane";
import { CaseDrawer } from "./components/CaseDrawer";
import { Section } from "./components/Card";
import { Sidebar, Topbar } from "./components/Shell";
import { Icon } from "./components/Icon";

const situations = listSituations();
const API = dataMode === "api";

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

interface Toast { id: number; tone: "good" | "bad" | "info"; text: string }

function Toasts({ items, onClose }: { items: Toast[]; onClose: (id: number) => void }) {
  return (
    <div className="toasts" aria-live="polite" aria-atomic="false">
      {items.map((t) => (
        <div key={t.id} className={`toast toast-${t.tone}`} role={t.tone === "bad" ? "alert" : "status"}>
          <Icon name={t.tone === "bad" ? "alert" : t.tone === "good" ? "check" : "activity"} />
          <p>{t.text}</p>
          <button className="icon-btn sm" onClick={() => onClose(t.id)} aria-label="Dismiss"><Icon name="x" size={14} /></button>
        </div>
      ))}
    </div>
  );
}

function Skeleton() {
  return (
    <div className="skeleton" aria-hidden="true">
      <div className="sk sk-line w40" />
      <div className="sk sk-title" />
      <div className="sk sk-strip" />
      <div className="sk sk-panel" />
      <div className="sk sk-panel short" />
    </div>
  );
}

export default function App() {
  const [key, setKey] = useState(situations[0]?.key ?? "A");
  const [mode, setMode] = useState<Mode>("with_precedent");
  const [bundle, setBundle] = useState<Bundle | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState<string | null>(null);
  const [live, setLive] = useState<{ dispute?: LiveDispute; error?: string } | null>(null);
  const [openCase, setOpenCase] = useState<string | null>(null);
  const [audit, setAudit] = useState<AuditEvent[]>([]);
  const [theme, setTheme] = useState<Theme>(initialTheme);
  const [collapsed, setCollapsed] = useState(false);
  const [mobileOpen, setMobileOpen] = useState(false);
  const [toasts, setToasts] = useState<Toast[]>([]);
  const toastId = useRef(0);

  const toast = useCallback((tone: Toast["tone"], text: string) => {
    const id = ++toastId.current;
    setToasts((t) => [...t.slice(-2), { id, tone, text }]);
    window.setTimeout(() => setToasts((t) => t.filter((x) => x.id !== id)), tone === "bad" ? 8000 : 5000);
  }, []);

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

  // Keep the previous situation on screen (dimmed) while the next one loads, so the page does not jump.
  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    setError(null);
    getBundle(key, mode)
      .then((b) => !cancelled && setBundle(b))
      .catch((e: Error) => {
        if (cancelled) return;
        setError(e.message);
        setBundle(null);
      })
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

  const run = async (label: string, fn: () => Promise<Bundle>): Promise<Bundle | null> => {
    setBusy(label);
    try {
      const b = await fn();
      setBundle(b);
      refreshLive();
      return b;
    } catch (e) {
      toast("bad", (e as Error).message);
      return null;
    } finally {
      setBusy(null);
    }
  };

  const approve = async (a: Action) => {
    if (!API) {
      const rid = recId;
      setLocal(rid, a.action_id, "executing");
      timers.current.push(window.setTimeout(() => {
        setLocal(rid, a.action_id, "succeeded");
        toast("info", "Approved. Executed in the browser only (fixture mode).");
      }, 1200));
      return;
    }
    const b = await run(a.action_id, () => approveAction(key, mode, a.action_id));
    const s = b?.action_states?.[a.action_id];
    if (!s) return;
    if (s.state === "succeeded")
      toast(s.execution_mode === "real" ? "good" : "info",
        s.execution_mode === "real" ? "Approved and sent to the PayPal sandbox." : "Approved. Executed as a labelled simulation.");
    else if (s.state === "failed") toast("bad", `Approved, but execution failed: ${s.detail ?? "unknown error"}`);
  };

  const reject = async (a: Action) => {
    if (!API) {
      setLocal(recId, a.action_id, "rejected");
      toast("info", "Rejected. Nothing was sent.");
      return;
    }
    if (await run(a.action_id, () => rejectAction(key, mode, a.action_id))) toast("info", "Rejected. Nothing was sent.");
  };

  const advance = async () => {
    const b = await run("advance", () => advanceClock(key, mode, 14));
    if (b?.outcome) toast("info", "Outcome recorded on the simulated clock. Review the new case below the plan.");
  };

  const review = async (caseId: string, decision: "approved" | "rejected") => {
    const b = await run("review", async () => {
      await reviewCase(caseId, decision);
      return getBundle(key, mode);
    });
    if (b) toast(decision === "approved" ? "good" : "info", decision === "approved" ? "Added to the case library as a simulated case." : "Case discarded.");
  };

  const reset = async () => {
    const b = await run("reset", async () => {
      await resetDemo();
      return getBundle(key, mode);
    });
    if (b) toast("info", "Demo reset. Your approvals and simulated outcomes are cleared; PayPal was not touched.");
  };

  const refreshFromPayPal = async () => {
    const b = await run("paypal", async () => {
      await refreshPayPal();
      return getBundle(key, mode);
    });
    if (b) toast("info", b.paypal?.error ?? "Read the account again from PayPal.");
  };

  const canAdvance =
    API && !!bundle && !bundle.outcome &&
    bundle.policy_decisions.some((d) => d.decision === "NEEDS_APPROVAL" && views[d.action_id]?.state === "succeeded");

  const current = situations.find((s) => s.key === key);
  const anomalous = !!bundle?.situation.features.anomaly.is_anomalous;
  const showAudit = API && audit.length > 0;

  return (
    <div className={`layout ${collapsed ? "collapsed" : ""}`}>
      <a className="skip" href="#decision">Skip to the decision</a>
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
          onReset={API ? reset : undefined}
          resetting={busy === "reset"}
        />
        <div className={`progress ${loading && bundle ? "on" : ""}`} aria-hidden="true" />

        <main className="content" id="top" aria-busy={loading}>
          {error && (
            <div className="callout bad" role="alert">
              <Icon name="alert" />
              <div><p className="callout-title">Could not load this situation</p><p>{error}</p></div>
            </div>
          )}
          {!bundle && loading && <Skeleton />}

          {bundle && (
            <div className={`page ${loading ? "is-loading" : ""}`}>
              <PageHeader situation={bundle.situation} label={current?.label ?? key} anomalous={anomalous} />
              <KpiStrip situation={bundle.situation} rec={bundle.recommendation} />

              <Section id="decision" title="Decision"
                sub={mode === "with_precedent" ? "What the consultant proposes, and what is waiting for you." : "Ablation view: the same consultant with case retrieval switched off."}>
                <ConflictNotice situation={bundle.situation} />
                <div className="panel panel-hero">
                  {bundle.recommendation.triage && (
                    <div className="split split-1">
                      <TriagePane triage={bundle.recommendation.triage} generic={mode === "no_precedent"} />
                    </div>
                  )}
                  <div className="split split-actions">
                    <ActionsPane
                      rec={bundle.recommendation}
                      decisions={bundle.policy_decisions}
                      views={views}
                      busy={busy}
                      disputeIds={bundle.situation.paypal_dispute_ids ?? []}
                      realActions={bundle.paypal ? bundle.paypal.real_actions ?? null : undefined}
                      onApprove={approve}
                      onReject={reject}
                      onOpenCase={setOpenCase}
                    />
                    <DiagnosisPane rec={bundle.recommendation} />
                  </div>
                  <NextStep
                    canAdvance={canAdvance}
                    outcome={bundle.outcome ?? null}
                    busy={busy}
                    onAdvance={advance}
                    onOpenCase={setOpenCase}
                    onReview={API ? review : undefined}
                  />
                </div>
              </Section>

              {API && bundle.paypal && (
                <Section id="paypal" title="PayPal"
                  sub="Precedent's PayPal integration, live: the sandbox account it reads disputes and tracking from, and every request it makes.">
                  <div className="panel">
                    <div className="split split-1">
                      <PayPalAccountPane account={bundle.paypal} onRefresh={refreshFromPayPal} refreshing={busy === "paypal"} />
                    </div>
                    <div className="split split-1">
                      <PayPalActivityPane tick={bundle} />
                    </div>
                  </div>
                </Section>
              )}

              <Section id="evidence" title="Evidence" sub="Why the consultant thinks so: the numbers, then the past cases behind the plan.">
                <div className="panel">
                  <div className="split split-8-4">
                    <RatePane situation={bundle.situation} />
                    <ReasonsPane situation={bundle.situation} />
                  </div>
                  <div className="split split-5-7">
                    <SignalsPane situation={bundle.situation} />
                    <PrecedentsPanel rec={bundle.recommendation} similarityMin={thresholds.similarity_min} onOpenCase={setOpenCase} />
                  </div>
                </div>
              </Section>

              <Section id="history" title="History" sub={API ? "The loop so far, and every step the backend recorded." : "The loop so far."}>
                <div className="panel">
                  <div className={`split ${showAudit ? "split-4-8" : "split-1"}`}>
                    <Timeline events={timeline} />
                    {showAudit && <AuditLog events={audit} />}
                  </div>
                </div>
              </Section>
            </div>
          )}

          <footer className="foot">
            Decision support with cited precedents, not financial advice. Outcomes are observed, never claimed as caused.
          </footer>
        </main>
      </div>

      <Toasts items={toasts} onClose={(id) => setToasts((t) => t.filter((x) => x.id !== id))} />
      <CaseDrawer caseId={openCase} onClose={() => setOpenCase(null)} apiMode={API} />
    </div>
  );
}

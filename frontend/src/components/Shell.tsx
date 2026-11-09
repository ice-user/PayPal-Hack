import type { LiveDispute, Mode, SituationIndexEntry } from "../types";
import { Icon, type IconName } from "./Icon";

const SECTIONS: { id: string; label: string; icon: IconName; apiOnly?: boolean }[] = [
  { id: "decision", label: "Decision", icon: "shield" },
  { id: "evidence", label: "Evidence", icon: "activity" },
  { id: "precedents", label: "Precedents", icon: "book" },
  { id: "history", label: "History", icon: "clock" },
  { id: "audit", label: "Audit log", icon: "file", apiOnly: true },
];

interface SidebarProps {
  open: boolean;
  situations: SituationIndexEntry[];
  current: string;
  anomalous: boolean;
  onPick: (key: string) => void;
  apiMode: boolean;
  disputeIds: string[];
  live: { dispute?: LiveDispute; error?: string } | null;
  onNavigate: () => void;
}

const shortLabel = (label: string) => label.replace(/^[A-Z]:\s*/, "");

export function Sidebar({ open, situations, current, anomalous, onPick, apiMode, disputeIds, live, onNavigate }: SidebarProps) {
  const go = (id: string) => {
    document.getElementById(id)?.scrollIntoView({ behavior: "smooth", block: "start" });
    onNavigate();
  };
  return (
    <aside className={`sidebar ${open ? "open" : ""}`} aria-label="Navigation">
      <div className="brand">
        <span className="logo" aria-hidden="true">
          <svg viewBox="0 0 24 24" width="14" height="14" fill="none" stroke="currentColor" strokeWidth="2.4" strokeLinecap="round" strokeLinejoin="round">
            <path d="M6 20V5h7a4.5 4.5 0 0 1 0 9H6" />
          </svg>
        </span>
        <div>
          <div className="brand-name">Precedent</div>
          <div className="brand-sub">Demo electronics store</div>
        </div>
      </div>

      <nav className="side-nav">
        <button className="side-item active" onClick={() => go("top")}>
          <Icon name="grid" /> Overview
        </button>

        <div className="side-group">Situations</div>
        {situations.map((s) => (
          <button key={s.key} className={`side-item ${s.key === current ? "current" : ""}`}
            aria-current={s.key === current ? "page" : undefined}
            onClick={() => { onPick(s.key); onNavigate(); }}>
            <span className="side-key">{s.key}</span>
            <span className="side-text">{shortLabel(s.label)}</span>
            {s.key === current && anomalous && <span className="side-dot" title="Anomaly detected" />}
          </button>
        ))}

        <div className="side-group">On this page</div>
        {SECTIONS.filter((s) => apiMode || !s.apiOnly).map((s) => (
          <button key={s.id} className="side-item" onClick={() => go(s.id)}>
            <Icon name={s.icon} /> {s.label}
          </button>
        ))}
      </nav>

      <div className="side-card">
        <div className="side-eyebrow">{apiMode ? "API mode" : "Fixture mode"}</div>
        <div className="side-card-title">
          {disputeIds.length ? "PayPal sandbox dispute" : apiMode ? "Backend connected" : "Static fixtures"}
        </div>
        {disputeIds.length > 0 ? (
          <>
            <code className="side-code">{disputeIds.join(", ")}</code>
            {!apiMode && <p>Live status is read in API mode.</p>}
            {apiMode && live?.dispute && (
              <p>
                <strong>{live.dispute.status.replaceAll("_", " ").toLowerCase()}</strong>
                {live.dispute.stage && <> · {live.dispute.stage.toLowerCase()} stage</>}
                <br />
                Seller can now:{" "}
                {live.dispute.allowed.length
                  ? live.dispute.allowed.map((a) => a.replaceAll("_", " ")).join(", ")
                  : "nothing (PayPal is reviewing; this usually reopens within minutes)"}
              </p>
            )}
            {apiMode && live?.error && <p>Could not read live status: {live.error}</p>}
          </>
        ) : (
          <p>
            {apiMode
              ? "Approved actions are simulated and labelled: this situation has no linked sandbox dispute."
              : "Data comes from contracts/fixtures. Execution is simulated in the browser."}
          </p>
        )}
      </div>

      <div className="side-foot">
        <span><Icon name="scale" /> Decision support, not financial advice</span>
        <span><Icon name="alert" /> Order feed is synthetic</span>
      </div>
    </aside>
  );
}

interface TopbarProps {
  label: string;
  mode: Mode;
  onMode: (m: Mode) => void;
  theme: "dark" | "light";
  onTheme: () => void;
  onToggleSidebar: () => void;
  /** API mode only: clears this visitor's approvals and simulated outcomes. */
  onReset?: () => void;
  resetting?: boolean;
}

export function Topbar({ label, mode, onMode, theme, onTheme, onToggleSidebar, onReset, resetting }: TopbarProps) {
  return (
    <header className="topbar">
      <button className="icon-btn" onClick={onToggleSidebar} aria-label="Toggle sidebar"><Icon name="panel" /></button>
      <span className="topbar-sep" aria-hidden="true" />
      <nav className="crumbs" aria-label="Breadcrumb">
        <Icon name="grid" size={14} /> <span>Overview</span>
        <Icon name="chevron" size={14} className="crumb-sep" />
        <span className="crumb-current">{label}</span>
      </nav>
      <div className="topbar-right">
        <div className="segmented" role="group" aria-label="Precedent retrieval">
          <button aria-pressed={mode === "with_precedent"} onClick={() => onMode("with_precedent")}>With precedent</button>
          <button aria-pressed={mode === "no_precedent"} onClick={() => onMode("no_precedent")}>Without</button>
        </div>
        {onReset && (
          <button className="btn topbar-reset" onClick={onReset} disabled={resetting} aria-label="Reset demo"
            title="Start the demo again: clears your approvals and simulated outcomes. Nothing is sent to PayPal.">
            {resetting ? "Resetting…" : <>Reset<span className="wide-only"> demo</span></>}
          </button>
        )}
        <button className="icon-btn" onClick={onTheme} aria-label={`Switch to ${theme === "dark" ? "light" : "dark"} theme`}>
          <Icon name={theme === "dark" ? "sun" : "moon"} />
        </button>
      </div>
    </header>
  );
}

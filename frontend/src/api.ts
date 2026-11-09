import type { Bundle, LiveDispute, Mode, SituationIndexEntry } from "./types";
import indexJson from "@contracts/fixtures/index.json";

/**
 * Data source.
 * - Fixture mode (default): reads /contracts/fixtures, built by scripts/build_fixtures.py.
 *   Approvals are simulated in the browser.
 * - API mode: set VITE_API_BASE (e.g. http://localhost:8000). Bundles, approvals, the
 *   simulated clock and live dispute reads go to the backend (backend/precedent/api.py).
 */
// "/" means same origin (the deployed container serves the API and the dashboard together).
const RAW_BASE: string | undefined = import.meta.env.VITE_API_BASE;
const API_BASE: string | undefined = RAW_BASE === undefined ? undefined : RAW_BASE.replace(/\/+$/, "");

const fixtureBundles = import.meta.glob("@contracts/fixtures/bundles/*.json", {
  eager: true,
  import: "default",
}) as Record<string, Bundle>;

export const dataMode: "fixtures" | "api" = API_BASE !== undefined ? "api" : "fixtures";

export function listSituations(): SituationIndexEntry[] {
  return (indexJson as { situations: SituationIndexEntry[] }).situations;
}

// A random id per browser. On a public deployment the backend keeps a private demo workspace for
// each id, so visitors never see each other's approvals. It identifies nothing about the person.
const SESSION_KEY = "precedent-demo-session";
function makeId(): string {
  try {
    return crypto.randomUUID();
  } catch {
    return `${Date.now().toString(36)}-${Math.random().toString(36).slice(2, 12)}`;
  }
}
function demoSession(): string {
  try {
    const existing = localStorage.getItem(SESSION_KEY);
    if (existing) return existing;
    const id = makeId();
    localStorage.setItem(SESSION_KEY, id);
    return id;
  } catch {
    return fallbackSession;
  }
}
const fallbackSession = makeId(); // storage blocked: keep one id for this page load

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", "X-Demo-Session": demoSession(), ...(init?.headers ?? {}) },
  });
  if (!res.ok) {
    let msg = `API returned ${res.status}`;
    try {
      const body = await res.json();
      if (body?.detail) msg = String(body.detail);
    } catch {
      /* keep the status message */
    }
    throw new Error(msg);
  }
  return (await res.json()) as T;
}

export async function getBundle(key: string, mode: Mode): Promise<Bundle> {
  if (API_BASE !== undefined) return call<Bundle>(`/api/bundles/${encodeURIComponent(key)}?mode=${mode}`);
  const hit = Object.entries(fixtureBundles).find(([path]) => path.endsWith(`/${key}_${mode}.json`));
  if (!hit) throw new Error(`No fixture for situation ${key} in mode ${mode}`);
  // Clone so local approve/reject state never mutates the imported fixture.
  return structuredClone(hit[1]);
}

export const approveAction = (situation: string, mode: Mode, action_id: string) =>
  call<Bundle>("/api/actions/approve", { method: "POST", body: JSON.stringify({ situation, mode, action_id }) });

export const rejectAction = (situation: string, mode: Mode, action_id: string) =>
  call<Bundle>("/api/actions/reject", { method: "POST", body: JSON.stringify({ situation, mode, action_id }) });

/** Clears this visitor's approvals, outcomes and case reviews. Never touches PayPal. */
export const resetDemo = () => call<{ ok: boolean }>("/api/demo/reset", { method: "POST" });

export const advanceClock =(situation: string, mode: Mode, days = 14) =>
  call<Bundle>("/api/sim/advance", { method: "POST", body: JSON.stringify({ situation, mode, days }) });

export const reviewCase = (caseId: string, decision: "approved" | "rejected") =>
  call<unknown>(`/api/cases/${encodeURIComponent(caseId)}/review`, { method: "POST", body: JSON.stringify({ decision }) });

export const fetchCase = <T,>(caseId: string) => call<T>(`/api/cases/${encodeURIComponent(caseId)}`);

export interface AuditEvent {
  id: number;
  at: string;
  actor: string;
  event: string;
  payload: Record<string, unknown>;
}
export const getAudit = (limit = 25) => call<{ events: AuditEvent[] }>(`/api/audit?limit=${limit}`).then((r) => r.events);

export const getLiveDispute = (id: string) =>
  call<{ source: string; dispute: LiveDispute }>(`/api/paypal/disputes/${encodeURIComponent(id)}`).then((r) => r.dispute);

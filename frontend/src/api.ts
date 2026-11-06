import type { Bundle, LiveDispute, Mode, SituationIndexEntry } from "./types";
import indexJson from "@contracts/fixtures/index.json";

/**
 * Data source.
 * - Fixture mode (default): reads /contracts/fixtures, built by scripts/build_fixtures.py.
 *   Approvals are simulated in the browser.
 * - API mode: set VITE_API_BASE (e.g. http://localhost:8000). Bundles, approvals, the
 *   simulated clock and live dispute reads go to the backend (backend/precedent/api.py).
 */
const API_BASE: string | undefined = import.meta.env.VITE_API_BASE;

const fixtureBundles = import.meta.glob("@contracts/fixtures/bundles/*.json", {
  eager: true,
  import: "default",
}) as Record<string, Bundle>;

export const dataMode: "fixtures" | "api" = API_BASE ? "api" : "fixtures";

export function listSituations(): SituationIndexEntry[] {
  return (indexJson as { situations: SituationIndexEntry[] }).situations;
}

async function call<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    ...init,
    headers: { "Content-Type": "application/json", ...(init?.headers ?? {}) },
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
  if (API_BASE) return call<Bundle>(`/api/bundles/${encodeURIComponent(key)}?mode=${mode}`);
  const hit = Object.entries(fixtureBundles).find(([path]) => path.endsWith(`/${key}_${mode}.json`));
  if (!hit) throw new Error(`No fixture for situation ${key} in mode ${mode}`);
  // Clone so local approve/reject state never mutates the imported fixture.
  return structuredClone(hit[1]);
}

export const approveAction = (situation: string, mode: Mode, action_id: string) =>
  call<Bundle>("/api/actions/approve", { method: "POST", body: JSON.stringify({ situation, mode, action_id }) });

export const rejectAction = (situation: string, mode: Mode, action_id: string) =>
  call<Bundle>("/api/actions/reject", { method: "POST", body: JSON.stringify({ situation, mode, action_id }) });

export const advanceClock = (situation: string, mode: Mode, days = 14) =>
  call<Bundle>("/api/sim/advance", { method: "POST", body: JSON.stringify({ situation, mode, days }) });

export const getLiveDispute = (id: string) =>
  call<{ source: string; dispute: LiveDispute }>(`/api/paypal/disputes/${encodeURIComponent(id)}`).then((r) => r.dispute);

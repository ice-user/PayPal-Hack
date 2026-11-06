import type { Bundle, Mode, SituationIndexEntry } from "./types";
import indexJson from "@contracts/fixtures/index.json";

/**
 * Data source.
 * - Fixture mode (default): reads /contracts/fixtures, built by scripts/build_fixtures.py.
 * - API mode: set VITE_API_BASE (e.g. http://localhost:8000) to call Person B's backend.
 *   Proposed endpoint: GET {base}/api/bundles/{key}?mode={mode} returning a ScreenBundle.
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

export async function getBundle(key: string, mode: Mode): Promise<Bundle> {
  if (API_BASE) {
    const res = await fetch(`${API_BASE}/api/bundles/${encodeURIComponent(key)}?mode=${mode}`);
    if (!res.ok) throw new Error(`API returned ${res.status}`);
    return (await res.json()) as Bundle;
  }
  const hit = Object.entries(fixtureBundles).find(([path]) => path.endsWith(`/${key}_${mode}.json`));
  if (!hit) throw new Error(`No fixture for situation ${key} in mode ${mode}`);
  // Clone so local approve/reject state never mutates the imported fixture.
  return structuredClone(hit[1]);
}

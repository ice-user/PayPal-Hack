// The case library ships with the app (it is small and static). Pending live_simulated
// cases live only in the backend and are never shown as precedents.

export interface CaseRecord {
  case_id: string;
  title: string;
  provenance: "public" | "authored" | "live_simulated";
  evidence_quality: string;
  causal_claim: false;
  confounders_assessed: boolean;
  review_status: string;
  source: { ref: string; url?: string; licence?: string; accessed?: string };
  field_provenance?: Record<string, string>;
  context: { industry?: string; merchant_size?: string; region?: string; channel?: string };
  narrative: string;
  diagnosis: string;
  intervention: string;
  actions: string[];
  outcome: { summary: string; metric?: string };
  tags?: string[];
}

const files = import.meta.glob("@cases/**/*.json", { eager: true, import: "default" }) as Record<
  string,
  CaseRecord | CaseRecord[]
>;

const byId: Record<string, CaseRecord> = {};
for (const data of Object.values(files)) {
  for (const c of Array.isArray(data) ? data : [data]) byId[c.case_id] = c;
}

export const getCase = (id: string): CaseRecord | undefined => byId[id];

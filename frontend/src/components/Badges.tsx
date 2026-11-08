import type { Decision, Provenance, Tier } from "../types";
import { QUALITY_LABEL } from "../format";

export function DecisionBadge({ decision }: { decision: Decision }) {
  const label = decision === "NEEDS_APPROVAL" ? "Needs approval" : decision === "AUTO" ? "Auto" : "Blocked";
  return <span className={`badge decision-${decision.toLowerCase()}`}>{label}</span>;
}

export function TierBadge({ tier }: { tier: Tier }) {
  const label = tier === "PREPARE" ? "Prepare only" : tier === "EXTERNAL" ? "External" : "Money";
  return <span className="badge tier">{label}</span>;
}

export function ProvenanceBadge({ provenance }: { provenance: Provenance }) {
  const label = provenance === "live_simulated" ? "Sandbox (simulated)" : provenance === "authored" ? "Authored" : "Public";
  return (
    <span className={`badge prov-${provenance}`} title="Where this case comes from">
      {label}
    </span>
  );
}

export function QualityBadge({ quality }: { quality: string }) {
  return (
    <span className={`badge quality-${quality}`} title="Evidence quality">
      {QUALITY_LABEL[quality] ?? quality}
    </span>
  );
}

export function SimulatedTag({ title }: { title?: string }) {
  return (
    <span className="badge simulated" title={title ?? "Simulated, not a real-world measurement"}>
      Simulated
    </span>
  );
}

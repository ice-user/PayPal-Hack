import type { TimelineEvent } from "../types";
import { SimulatedTag } from "./Badges";

const LABEL: Record<string, string> = {
  detected: "Detected",
  recommended: "Recommended",
  approved: "Approved",
  executed: "Executed",
  measured: "Measured",
};

export function Timeline({ events }: { events: TimelineEvent[] }) {
  return (
    <section className="timeline" aria-labelledby="timeline-h">
      <h2 id="timeline-h" className="visually-hidden">Timeline</h2>
      <ol>
        {events.map((e) => (
          <li key={e.step} className={`tl-step tl-${e.status}`}>
            <div className="tl-dot" aria-hidden="true" />
            <div className="tl-head">
              <span className="tl-label">{LABEL[e.step]}</span>
              {e.simulated && <SimulatedTag />}
            </div>
            <div className="tl-status">{e.status}</div>
            <p className="tl-detail">{e.detail}</p>
          </li>
        ))}
      </ol>
    </section>
  );
}

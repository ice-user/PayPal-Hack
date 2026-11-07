import type { ReactNode } from "react";
import type { TimelineEvent } from "../types";
import { SimulatedTag } from "./Badges";
import { Card } from "./Card";
import { Icon, type IconName } from "./Icon";

const LABEL: Record<string, string> = {
  detected: "Spike detected",
  recommended: "Plan recommended",
  approved: "Approved by you",
  executed: "Executed",
  measured: "Outcome measured",
};

const ICON: Record<string, IconName> = {
  done: "check",
  pending: "clock",
  blocked: "ban",
  skipped: "x",
};

const when = (at?: string | null) =>
  at ? new Date(at).toLocaleString("en-US", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit", timeZone: "UTC" }) + " UTC" : null;

/** The loop as an activity feed: detected, recommended, approved, executed, measured. */
export function Timeline({ events, action }: { events: TimelineEvent[]; action?: ReactNode }) {
  return (
    <Card id="activity" className="span-3" title="Activity" sub="Where this situation is in the loop." footer={action}>
      <ol className="feed">
        {events.map((e) => (
          <li key={e.step} className={`feed-item feed-${e.status}`}>
            <span className="feed-icon"><Icon name={ICON[e.status] ?? "clock"} size={14} /></span>
            <div>
              <div className="feed-title">
                {LABEL[e.step] ?? e.step}
                {e.simulated && e.status === "done" && <SimulatedTag />}
              </div>
              <p className="feed-detail">{e.detail}</p>
              <div className="feed-time">{when(e.at) ?? e.status}</div>
            </div>
          </li>
        ))}
      </ol>
    </Card>
  );
}

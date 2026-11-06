import { MerchantTimeline, TimelineEvent } from "../types/api";

export function TimelinePanel({ timeline }: { timeline: MerchantTimeline | null }) {
  if (!timeline || timeline.events.length === 0) {
    return (
      <section className="panel timeline-panel">
        <h2>Timeline</h2>
        <p className="empty">No timeline events yet.</p>
      </section>
    );
  }

  const eventIcons: Record<TimelineEvent["type"], string> = {
    detected: "🔍",
    recommended: "💡",
    approved: "✅",
    executed: "⚡",
    measured: "📊",
  };

  return (
    <section className="panel timeline-panel">
      <div className="panel-header">
        <h2>Timeline</h2>
        <span className="simulated-clock">
          Simulated clock: {timeline.simulated_clock.simulated_days} days advanced
        </span>
      </div>

      <div className="timeline">
        {timeline.events.map((event, i) => (
          <div key={`${event.timestamp}-${i}`} className="timeline-event">
            <div className="timeline-marker">
              <span className="timeline-icon">{eventIcons[event.type]}</span>
              <div className="timeline-line" />
            </div>
            <div className="timeline-content">
              <div className="timeline-header">
                <span className="timeline-type">{event.type}</span>
                <span className="timeline-time">
                  {new Date(event.timestamp).toLocaleTimeString()}
                  {event.simulated && <span className="simulated-label">simulated</span>}
                </span>
              </div>
              <p className="timeline-label">{event.label}</p>
              {event.details && (
                <pre className="timeline-details">{JSON.stringify(event.details, null, 2)}</pre>
              )}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}
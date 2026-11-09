import type { ReactNode } from "react";
import { Icon } from "./Icon";

/** A page section: a heading row above one panel. Sections are the only top-level boxes. */
export function Section({ id, title, sub, right, children }: {
  id: string; title: string; sub?: ReactNode; right?: ReactNode; children: ReactNode;
}) {
  return (
    <section className="section" id={id} aria-labelledby={`${id}-h`}>
      <header className="section-head">
        <div>
          <h2 className="section-title" id={`${id}-h`}>{title}</h2>
          {sub && <p className="section-sub">{sub}</p>}
        </div>
        {right}
      </header>
      {children}
    </section>
  );
}

/** One region inside a panel. Panes sit side by side in a `.split` row, separated by dividers. */
export function Pane({ id, title, pill, sub, right, footer, className, children }: {
  id?: string; title: ReactNode; pill?: ReactNode; sub?: ReactNode; right?: ReactNode;
  footer?: ReactNode; className?: string; children: ReactNode;
}) {
  const hid = id ? `${id}-h` : undefined;
  return (
    <div className={`pane ${className ?? ""}`} id={id} role="region" aria-labelledby={hid}>
      <header className="pane-head">
        <div className="pane-titles">
          <h3 className="pane-title" id={hid}>{title}{pill}</h3>
          {sub && <p className="pane-sub">{sub}</p>}
        </div>
        {right}
      </header>
      <div className="pane-body">{children}</div>
      {footer && <footer className="pane-foot">{footer}</footer>}
    </div>
  );
}

/** Small status pill: tone carries meaning, the arrow carries direction. */
export function Pill({ children, tone = "neutral", dir }: {
  children: ReactNode; tone?: "good" | "bad" | "warn" | "info" | "neutral"; dir?: "up" | "down";
}) {
  return (
    <span className={`pill pill-${tone}`}>
      {dir && <Icon name={dir} size={12} />}
      {children}
    </span>
  );
}

export function Spinner() {
  return <span className="spinner" aria-hidden="true" />;
}

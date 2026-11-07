import type { ReactNode } from "react";
import { Icon } from "./Icon";

interface CardProps {
  id?: string;
  title: ReactNode;
  sub?: ReactNode;
  pill?: ReactNode;
  right?: ReactNode;
  footer?: ReactNode;
  className?: string;
  children: ReactNode;
}

/** The dashboard's one card shape: title, optional change pill, subtitle, body, footer. */
export function Card({ id, title, sub, pill, right, footer, className, children }: CardProps) {
  const hid = id ? `${id}-h` : undefined;
  return (
    <section className={`card ${className ?? ""}`} id={id} aria-labelledby={hid}>
      <header className="card-head">
        <div className="card-titles">
          <h2 className="card-title" id={hid}>{title}{pill}</h2>
          {sub && <p className="card-sub">{sub}</p>}
        </div>
        {right}
      </header>
      <div className="card-body">{children}</div>
      {footer && <footer className="card-foot">{footer}</footer>}
    </section>
  );
}

/** Small change pill: tone says good or bad, direction picks the arrow. */
export function Pill({ children, tone = "neutral", dir }: { children: ReactNode; tone?: "good" | "bad" | "warn" | "neutral"; dir?: "up" | "down" }) {
  return (
    <span className={`pill pill-${tone}`}>
      {dir && <Icon name={dir} size={12} />}
      {children}
    </span>
  );
}

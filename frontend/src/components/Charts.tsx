import { useEffect, useRef, useState, type KeyboardEvent, type PointerEvent } from "react";
import { pct, rate } from "../format";

/** Width of an element, kept current with a ResizeObserver, so SVG text stays crisp. */
function useWidth<T extends HTMLElement>(fallback = 600) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(220, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

const DAY = 86_400_000;
const shortDate = (d: Date) => d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });
const longDate = (d: Date) => d.toLocaleDateString("en-US", { weekday: "short", month: "short", day: "numeric", timeZone: "UTC" });

/** Round upper bound for the y axis, so the three gridlines land on readable rates. */
function niceMax(v: number): number {
  const step = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.25].find((s) => s * 3 >= v);
  return step ? step * 3 : v;
}

/** Monotone cubic path (Fritsch–Carlson): smooth, but never overshoots the data. */
function monotonePath(pts: (readonly [number, number])[]): string {
  const n = pts.length;
  const dx = pts.slice(1).map((p, i) => p[0] - pts[i][0]);
  const sl = pts.slice(1).map((p, i) => (p[1] - pts[i][1]) / dx[i]);
  const t = pts.map((_, i) => {
    if (i === 0) return sl[0];
    if (i === n - 1) return sl[n - 2];
    if (sl[i - 1] * sl[i] <= 0) return 0;
    return (3 * (dx[i - 1] + dx[i])) / ((2 * dx[i] + dx[i - 1]) / sl[i - 1] + (dx[i] + 2 * dx[i - 1]) / sl[i]);
  });
  let d = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    d += ` C${(pts[i][0] + h).toFixed(1)},${(pts[i][1] + h * t[i]).toFixed(1)} ${(pts[i + 1][0] - h).toFixed(1)},${(pts[i + 1][1] - h * t[i + 1]).toFixed(1)} ${pts[i + 1][0].toFixed(1)},${pts[i + 1][1].toFixed(1)}`;
  }
  return d;
}

interface RateProps {
  values: number[];
  baseline: number;
  end: string; // last day of the window, YYYY-MM-DD
  windowDays: number;
}

export function RateLegend() {
  return (
    <ul className="chart-legend" aria-hidden="true">
      <li><i className="lg-line" />Daily rate</li>
      <li><i className="lg-dash" />30-day baseline</li>
      <li><i className="lg-window" />7-day window</li>
    </ul>
  );
}

/** Daily dispute rate: area chart with the baseline, the 7-day window, a hover/keyboard cursor and tooltip. */
export function RateChart({ values, baseline, end, windowDays }: RateProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  if (values.length < 2) return null;

  const height = 240;
  const m = { top: 16, right: 16, bottom: 28, left: 48 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;
  const max = niceMax(Math.max(...values, baseline) * 1.08);
  const endMs = Date.parse(`${end}T00:00:00Z`);
  const n = values.length;
  const dates = values.map((_, i) => new Date(endMs - (n - 1 - i) * DAY));
  const x = (i: number) => m.left + (i / (n - 1)) * iw;
  const y = (v: number) => m.top + ih - (v / max) * ih;
  const line = monotonePath(values.map((v, i) => [x(i), y(v)] as const));
  const area = `${line} L${x(n - 1)},${m.top + ih} L${x(0)},${m.top + ih} Z`;
  const ticks = [0, 1, 2, 3].map((k) => (k * max) / 3);
  const firstInWindow = Math.max(0, n - windowDays);
  const labelEvery = Math.max(1, Math.ceil(n / Math.max(2, Math.floor(iw / 72))));
  const showLabel = (i: number) => i === n - 1 || (i % labelEvery === 0 && n - 1 - i >= Math.max(2, labelEvery * 0.75));
  const fmtTick = (t: number) => (t === 0 ? "0%" : max < 0.1 ? rate(t) : pct(t, 1));
  const last = n - 1;

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - box.left) / box.width) * (n - 1));
    setHover(Math.min(n - 1, Math.max(0, i)));
  };
  const onKey = (e: KeyboardEvent<HTMLDivElement>) => {
    if (e.key === "ArrowLeft" || e.key === "ArrowRight") {
      e.preventDefault();
      setHover((h) => Math.min(n - 1, Math.max(0, (h ?? last) + (e.key === "ArrowLeft" ? -1 : 1))));
    } else if (e.key === "Escape") setHover(null);
  };

  const h = hover;
  const tipLeft = h === null ? 0 : x(h) > width / 2 ? x(h) - 176 : x(h) + 16;

  return (
    <div className="chart" ref={ref} tabIndex={0} onKeyDown={onKey} onFocus={() => setHover(last)} onBlur={() => setHover(null)}
      role="img"
      aria-label={`Daily dispute rate over ${n} days, from ${rate(values[0])} to ${rate(values[last])}; 30-day baseline ${rate(baseline)}. Use the arrow keys to read each day.`}>
      <svg width={width} height={height} aria-hidden="true">
        <defs>
          <linearGradient id="rate-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.28" />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0" />
          </linearGradient>
        </defs>
        <rect x={x(firstInWindow)} y={m.top} width={m.left + iw - x(firstInWindow)} height={ih} className="chart-window" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={m.left + iw} y1={y(t)} y2={y(t)} className={t === 0 ? "chart-axis" : "chart-grid"} />
            <text x={m.left - 10} y={y(t)} className="chart-tick" textAnchor="end" dominantBaseline="middle">{fmtTick(t)}</text>
          </g>
        ))}
        {dates.map((d, i) => showLabel(i) && (
          <text key={i} x={x(i)} y={height - 8} className="chart-tick"
            textAnchor={i === 0 ? "start" : i === last ? "end" : "middle"}>{shortDate(d)}</text>
        ))}
        <path d={area} fill="url(#rate-fill)" />
        <line x1={m.left} x2={m.left + iw} y1={y(baseline)} y2={y(baseline)} className="chart-baseline" />
        <path d={line} className="chart-line" />
        {h === null && (
          <g>
            <circle cx={x(last)} cy={y(values[last])} r={4} className="chart-dot" />
            <text x={x(last) - 8} y={y(values[last]) - 12} className="chart-endlabel" textAnchor="end">{rate(values[last])}</text>
          </g>
        )}
        {h !== null && (
          <g>
            <line x1={x(h)} x2={x(h)} y1={m.top} y2={m.top + ih} className="chart-cursor" />
            <circle cx={x(h)} cy={y(values[h])} r={5} className="chart-dot" />
          </g>
        )}
        <rect x={m.left} y={m.top} width={iw} height={ih} fill="transparent"
          onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {h !== null && (
        <div className="chart-tip" style={{ left: Math.max(0, Math.min(width - 168, tipLeft)), top: m.top }} aria-hidden="true">
          <div className="tip-date">{longDate(dates[h])}</div>
          <div className="tip-row"><i className="lg-line" />Dispute rate <strong className="num">{rate(values[h])}</strong></div>
          <div className="tip-row"><i className="lg-dash" />Baseline <strong className="num">{rate(baseline)}</strong></div>
          <div className={`tip-ratio ${values[h] > baseline * 1.5 ? "bad" : ""}`}>
            {baseline > 0 ? `${(values[h] / baseline).toFixed(1)}x baseline` : ""}{h >= firstInWindow ? " · in window" : ""}
          </div>
        </div>
      )}
    </div>
  );
}

/** Donut of shares with a centre total; hovering a segment or legend row highlights it. */
export function Donut({ parts, total, totalLabel }: {
  parts: { key: string; label: string; value: number }[]; total: number; totalLabel: string;
}) {
  const [hover, setHover] = useState<number | null>(null);
  const size = 200, r = 84, inner = 60, cx = size / 2, cy = size / 2;
  let a0 = -Math.PI / 2;
  const gap = parts.length > 1 ? 0.025 : 0;
  const arcs = parts.map((p, i) => {
    const sweep = p.value * Math.PI * 2;
    const s = a0 + gap / 2, e = a0 + sweep - gap / 2;
    a0 += sweep;
    const big = e - s > Math.PI ? 1 : 0;
    const pt = (rad: number, ang: number) => `${(cx + rad * Math.cos(ang)).toFixed(2)},${(cy + rad * Math.sin(ang)).toFixed(2)}`;
    const d = sweep >= Math.PI * 2 - 1e-6
      ? `M${cx - r},${cy} a${r},${r} 0 1,0 ${2 * r},0 a${r},${r} 0 1,0 ${-2 * r},0 M${cx - inner},${cy} a${inner},${inner} 0 1,1 ${2 * inner},0 a${inner},${inner} 0 1,1 ${-2 * inner},0`
      : `M${pt(r, s)} A${r},${r} 0 ${big} 1 ${pt(r, e)} L${pt(inner, e)} A${inner},${inner} 0 ${big} 0 ${pt(inner, s)} Z`;
    return { ...p, d, i };
  });
  const focus = hover !== null ? parts[hover] : null;
  return (
    <div className="donut">
      <div className="donut-figure">
        <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={parts.map((p) => `${p.label} ${pct(p.value)}`).join(", ")}>
          {arcs.map((a) => (
            <path key={a.key} d={a.d} fillRule="evenodd"
              className={`donut-seg seg-${a.i} ${hover !== null && hover !== a.i ? "dim" : ""}`}
              onPointerEnter={() => setHover(a.i)} onPointerLeave={() => setHover(null)} />
          ))}
        </svg>
        <div className="donut-center" aria-hidden="true">
          <div className="donut-value num">{focus ? pct(focus.value) : total}</div>
          <div className="donut-caption">{focus ? focus.label : totalLabel}</div>
        </div>
      </div>
      <ul className="legend">
        {parts.map((p, i) => (
          <li key={p.key} className={hover !== null && hover !== i ? "dim" : ""}
            onPointerEnter={() => setHover(i)} onPointerLeave={() => setHover(null)}>
            <i className={`swatch seg-${i}`} />
            <span className="legend-label">{p.label}</span>
            <span className="legend-value num">{pct(p.value)}</span>
          </li>
        ))}
      </ul>
    </div>
  );
}

/** Labelled horizontal meters: easier to read and compare than vertical bars. */
export function Meters({ rows }: { rows: { key: string; label: string; detail?: string; value: number }[] }) {
  return (
    <ul className="meters">
      {rows.map((r) => (
        <li key={r.key} className="meter">
          <div className="meter-head">
            <span className="meter-label">{r.label}{r.detail && <span className="meter-detail"> · {r.detail}</span>}</span>
            <span className="meter-value num">{pct(r.value)}</span>
          </div>
          <div className="meter-track" role="progressbar" aria-label={r.label}
            aria-valuemin={0} aria-valuemax={100} aria-valuenow={Math.round(r.value * 100)}>
            <div className="meter-fill" style={{ width: `${Math.min(100, r.value * 100)}%` }} />
          </div>
        </li>
      ))}
    </ul>
  );
}

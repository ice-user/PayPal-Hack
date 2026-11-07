import { useEffect, useRef, useState, type PointerEvent } from "react";
import { pct, rate } from "../format";

/** Width of an element, kept current with a ResizeObserver, so SVG text stays crisp. */
function useWidth<T extends HTMLElement>(fallback = 600) {
  const ref = useRef<T>(null);
  const [w, setW] = useState(fallback);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const ro = new ResizeObserver(([e]) => setW(Math.max(200, Math.round(e.contentRect.width))));
    ro.observe(el);
    return () => ro.disconnect();
  }, []);
  return [ref, w] as const;
}

const DAY = 86_400_000;
const shortDate = (d: Date) => d.toLocaleDateString("en-US", { month: "short", day: "numeric", timeZone: "UTC" });

/** "Nice" upper bound for the y axis, so gridlines land on round rates. */
function niceMax(v: number): number {
  const step = [0.001, 0.0025, 0.005, 0.01, 0.02, 0.025, 0.05, 0.1, 0.25].find((s) => s * 4 >= v);
  return step ? step * 4 : v;
}

interface RateProps {
  values: number[];
  baseline: number;
  end: string; // last day of the window, YYYY-MM-DD
  windowDays: number;
}

/** Daily dispute rate as an area chart, with the 30-day baseline and the 7-day window marked. */
export function RateChart({ values, baseline, end, windowDays }: RateProps) {
  const [ref, width] = useWidth<HTMLDivElement>();
  const [hover, setHover] = useState<number | null>(null);
  if (values.length < 2) return null;

  const height = 250;
  const m = { top: 12, right: 12, bottom: 26, left: 44 };
  const iw = width - m.left - m.right;
  const ih = height - m.top - m.bottom;
  const max = niceMax(Math.max(...values, baseline) * 1.05);
  const endMs = Date.parse(`${end}T00:00:00Z`);
  const dates = values.map((_, i) => new Date(endMs - (values.length - 1 - i) * DAY));
  const x = (i: number) => m.left + (i / (values.length - 1)) * iw;
  const y = (v: number) => m.top + ih - (v / max) * ih;

  // Monotone cubic curve (Fritsch–Carlson): smooth, but never overshoots the daily values.
  const pts = values.map((v, i) => [x(i), y(v)] as const);
  const n = pts.length;
  const dx = pts.slice(1).map((p, i) => p[0] - pts[i][0]);
  const sl = pts.slice(1).map((p, i) => (p[1] - pts[i][1]) / dx[i]);
  const t = pts.map((_, i) => {
    if (i === 0) return sl[0];
    if (i === n - 1) return sl[n - 2];
    if (sl[i - 1] * sl[i] <= 0) return 0;
    return (3 * (dx[i - 1] + dx[i])) / ((2 * dx[i] + dx[i - 1]) / sl[i - 1] + (dx[i] + 2 * dx[i - 1]) / sl[i]);
  });
  let line = `M${pts[0][0].toFixed(1)},${pts[0][1].toFixed(1)}`;
  for (let i = 0; i < n - 1; i++) {
    const h = dx[i] / 3;
    line += ` C${(pts[i][0] + h).toFixed(1)},${(pts[i][1] + h * t[i]).toFixed(1)} ${(pts[i + 1][0] - h).toFixed(1)},${(pts[i + 1][1] - h * t[i + 1]).toFixed(1)} ${pts[i + 1][0].toFixed(1)},${pts[i + 1][1].toFixed(1)}`;
  }
  const area = `${line} L${x(values.length - 1)},${m.top + ih} L${x(0)},${m.top + ih} Z`;
  const ticks = [0, 0.25, 0.5, 0.75, 1].map((t) => t * max);
  const windowStart = x(Math.max(0, values.length - windowDays));
  const labelEvery = Math.max(1, Math.ceil(values.length / Math.max(2, Math.floor(iw / 70))));

  const onMove = (e: PointerEvent<SVGRectElement>) => {
    const box = e.currentTarget.getBoundingClientRect();
    const i = Math.round(((e.clientX - box.left) / box.width) * (values.length - 1));
    setHover(Math.min(values.length - 1, Math.max(0, i)));
  };

  return (
    <div className="chart" ref={ref}>
      <svg width={width} height={height} role="img"
        aria-label={`Daily dispute rate over ${values.length} days, from ${rate(values[0])} to ${rate(values[values.length - 1])}; 30-day baseline ${rate(baseline)}`}>
        <defs>
          <linearGradient id="rate-fill" x1="0" x2="0" y1="0" y2="1">
            <stop offset="0%" stopColor="var(--chart-1)" stopOpacity="0.32" />
            <stop offset="100%" stopColor="var(--chart-1)" stopOpacity="0.02" />
          </linearGradient>
        </defs>
        <rect x={windowStart} y={m.top} width={m.left + iw - windowStart} height={ih} className="chart-window" />
        {ticks.map((t) => (
          <g key={t}>
            <line x1={m.left} x2={m.left + iw} y1={y(t)} y2={y(t)} className="chart-grid" />
            <text x={m.left - 8} y={y(t)} className="chart-tick" textAnchor="end" dominantBaseline="middle">{t === 0 ? "0%" : max < 0.1 ? rate(t) : pct(t, 1)}</text>
          </g>
        ))}
        {dates.map((d, i) => ((i % labelEvery === 0 && values.length - 1 - i >= Math.max(2, labelEvery * 0.75)) || i === values.length - 1) && (
          <text key={i} x={x(i)} y={height - 6} className="chart-tick" textAnchor={i === 0 ? "start" : i === values.length - 1 ? "end" : "middle"}>{shortDate(d)}</text>
        ))}
        <path d={area} fill="url(#rate-fill)" />
        <path d={line} className="chart-line" />
        <line x1={m.left} x2={m.left + iw} y1={y(baseline)} y2={y(baseline)} className="chart-baseline" />
        <text x={m.left + 6} y={y(baseline) - 6} className="chart-tick">30-day baseline {rate(baseline)}</text>
        {hover !== null && (
          <g>
            <line x1={x(hover)} x2={x(hover)} y1={m.top} y2={m.top + ih} className="chart-cursor" />
            <circle cx={x(hover)} cy={y(values[hover])} r={4} className="chart-dot" />
          </g>
        )}
        <rect x={m.left} y={m.top} width={iw} height={ih} fill="transparent"
          onPointerMove={onMove} onPointerLeave={() => setHover(null)} />
      </svg>
      {hover !== null && (
        <div className="chart-tip" style={{ left: Math.min(width - 150, Math.max(0, x(hover) - 70)), top: Math.max(0, y(values[hover]) - 64) }}>
          <div className="chart-tip-date">{shortDate(dates[hover])}</div>
          <div><span className="num">{rate(values[hover])}</span> dispute rate</div>
          <div className="muted-text">{(values[hover] / baseline).toFixed(1)}x baseline</div>
        </div>
      )}
    </div>
  );
}

/** Donut of shares (sum to 1), monochrome like the rest of the dashboard. */
export function Donut({ parts, label }: { parts: { key: string; label: string; value: number }[]; label: string }) {
  const size = 200, r = 78, inner = 46, cx = size / 2, cy = size / 2;
  let a0 = -Math.PI / 2;
  const gap = parts.length > 1 ? 0.03 : 0;
  const arcs = parts.map((p, i) => {
    const sweep = p.value * Math.PI * 2;
    const s = a0 + gap / 2, e = a0 + sweep - gap / 2;
    a0 += sweep;
    const big = e - s > Math.PI ? 1 : 0;
    const pt = (rad: number, ang: number) => `${cx + rad * Math.cos(ang)},${cy + rad * Math.sin(ang)}`;
    const d = sweep >= Math.PI * 2 - 1e-6
      ? `M${cx - r},${cy} a${r},${r} 0 1,0 ${2 * r},0 a${r},${r} 0 1,0 ${-2 * r},0 M${cx - inner},${cy} a${inner},${inner} 0 1,1 ${2 * inner},0 a${inner},${inner} 0 1,1 ${-2 * inner},0`
      : `M${pt(r, s)} A${r},${r} 0 ${big} 1 ${pt(r, e)} L${pt(inner, e)} A${inner},${inner} 0 ${big} 0 ${pt(inner, s)} Z`;
    const mid = (s + e) / 2;
    const lr = (r + inner) / 2;
    return { ...p, d, i, lx: cx + lr * Math.cos(mid), ly: cy + lr * Math.sin(mid), sweep };
  });
  return (
    <div className="donut">
      <svg viewBox={`0 0 ${size} ${size}`} role="img" aria-label={label}>
        {arcs.map((a) => (
          <g key={a.key}>
            <path d={a.d} className={`donut-seg seg-${a.i}`} fillRule="evenodd"><title>{`${a.label} ${pct(a.value)}`}</title></path>
            {a.sweep > 0.45 && (
              <text x={a.lx} y={a.ly} className={`donut-label on-seg-${a.i}`} textAnchor="middle" dominantBaseline="middle">{pct(a.value)}</text>
            )}
          </g>
        ))}
      </svg>
      <ul className="legend">
        {parts.map((p, i) => (
          <li key={p.key}><i className={`swatch seg-${i}`} />{p.label}</li>
        ))}
      </ul>
    </div>
  );
}

/** Vertical track-and-fill bars, one per signal, like the template's survey bars. */
export function SignalBars({ bars }: { bars: { key: string; label: string; value: number; note?: string }[] }) {
  return (
    <div className="bars" role="list">
      {bars.map((b) => (
        <div className="bar" role="listitem" key={b.key} title={b.note ?? b.label}
          aria-label={`${b.label}: ${pct(b.value)}`}>
          <div className="bar-value num">{pct(b.value)}</div>
          <div className="bar-track"><div className="bar-fill" style={{ height: `${Math.min(100, b.value * 100)}%` }} /></div>
          <div className="bar-label">{b.label}</div>
        </div>
      ))}
    </div>
  );
}

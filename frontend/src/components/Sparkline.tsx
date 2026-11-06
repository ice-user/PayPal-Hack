interface Props {
  values: number[];
  baseline: number;
  width?: number;
  height?: number;
}

/** Daily dispute rate with the 30-day baseline as a dashed reference line. */
export function Sparkline({ values, baseline, width = 240, height = 56 }: Props) {
  if (values.length < 2) return null;
  const pad = 4;
  const max = Math.max(...values, baseline) * 1.1;
  const x = (i: number) => pad + (i / (values.length - 1)) * (width - 2 * pad);
  const y = (v: number) => height - pad - (v / max) * (height - 2 * pad);
  const line = values.map((v, i) => `${i === 0 ? "M" : "L"}${x(i).toFixed(1)},${y(v).toFixed(1)}`).join(" ");
  const area = `${line} L${x(values.length - 1).toFixed(1)},${height - pad} L${x(0).toFixed(1)},${height - pad} Z`;
  const last = values[values.length - 1];
  return (
    <svg className="sparkline" viewBox={`0 0 ${width} ${height}`} preserveAspectRatio="none" role="img"
      aria-label={`Daily dispute rate over ${values.length} days, rising from ${(values[0] * 100).toFixed(2)}% to ${(last * 100).toFixed(2)}%`}>
      <path d={area} className="spark-area" />
      <line x1={pad} x2={width - pad} y1={y(baseline)} y2={y(baseline)} className="spark-baseline" vectorEffect="non-scaling-stroke" />
      <path d={line} className="spark-line" vectorEffect="non-scaling-stroke" />
    </svg>
  );
}

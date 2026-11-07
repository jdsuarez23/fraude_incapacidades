export function Badge({ tone = "idle", children, title }) {
  return (
    <span className={`sg-badge b-${tone}`} title={title}>
      {children}
    </span>
  );
}

import { scoreColor } from "../lib/status.js";

export function ScoreRing({ score, size = 150 }) {
  const r = 54,
    c = 2 * Math.PI * r;
  const color = scoreColor(score);
  const off = score == null ? c : c - (score / 100) * c;
  return (
    <div
      style={{ position: "relative", width: size, height: size }}
      role="img"
      aria-label={score == null ? "Sin puntaje" : `Puntaje ${score} de 100`}
    >
      <svg viewBox="0 0 120 120" width={size} height={size}>
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke="var(--ink-1)"
          strokeWidth="9"
        />
        <circle
          cx="60"
          cy="60"
          r={r}
          fill="none"
          stroke={color}
          strokeWidth="9"
          strokeLinecap="round"
          strokeDasharray={c}
          strokeDashoffset={off}
          transform="rotate(-90 60 60)"
          style={{ transition: "stroke-dashoffset 1s ease-out" }}
        />
      </svg>
      <div
        style={{
          position: "absolute",
          inset: 0,
          display: "grid",
          placeContent: "center",
          textAlign: "center",
        }}
      >
        <b style={{ fontSize: size * 0.28, color, lineHeight: 1 }}>
          {score ?? "—"}
        </b>
        <span className="sg-muted">
          {score == null ? "sin puntaje" : "/ 100"}
        </span>
      </div>
    </div>
  );
}

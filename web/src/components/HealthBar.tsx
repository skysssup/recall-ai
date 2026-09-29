export default function HealthBar({ value }: { value: number }) {
  const pct = Math.round(Math.max(0, Math.min(1, value)) * 100)
  const color = pct >= 70 ? 'var(--ok)' : pct >= 40 ? 'var(--warn)' : 'var(--danger)'
  return (
    <div className="row" style={{ gap: 8 }}>
      <div className="meter" style={{ width: 90 }}>
        <span style={{ width: `${pct}%`, background: color }} />
      </div>
      <span style={{ fontSize: 12, color }}>{pct}%</span>
    </div>
  )
}

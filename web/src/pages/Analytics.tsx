import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import HealthBar from '../components/HealthBar'

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof api.analytics>> | null>(null)
  const [stats, setStats] = useState<Awaited<ReturnType<typeof api.reviewStats>> | null>(null)

  useEffect(() => {
    api.analytics().then(setOverview)
    api.reviewStats().then(setStats)
  }, [])

  if (!overview) return <div className="empty">Loading analytics…</div>

  const days = Object.entries(stats?.last_30_days || {}).sort(([a], [b]) => a.localeCompare(b))
  const maxDay = Math.max(1, ...days.map(([, n]) => n))

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Analytics</h2>
          <p>Retention health, difficulty mix, and review volume.</p>
        </div>
      </div>
      <div className="grid-stats">
        <div className="stat-card"><div className="label">Health</div><div className="value">{Math.round(overview.health_score * 100)}%</div></div>
        <div className="stat-card"><div className="label">Streak</div><div className="value">{overview.streak_days}d</div></div>
        <div className="stat-card"><div className="label">Reviews (30d)</div><div className="value">{stats?.total ?? 0}</div></div>
        <div className="stat-card"><div className="label">Hard cards</div><div className="value">{overview.difficulty_breakdown.Hard || 0}</div></div>
      </div>

      <div className="layout-2">
        <div className="panel">
          <h3>Topic retention</h3>
          {overview.topics.map((t) => (
            <div key={t.name} className="row" style={{ marginBottom: 10 }}>
              <div style={{ width: 160 }}>{t.name}</div>
              <div className="spacer"><HealthBar value={t.retrievability} /></div>
              <span className="muted" style={{ fontSize: 12 }}>S={t.stability.toFixed(1)}</span>
            </div>
          ))}
        </div>
        <div className="panel">
          <h3>Review activity</h3>
          {!days.length && <div className="empty">No reviews in the last 30 days.</div>}
          <div style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 140 }}>
            {days.map(([day, n]) => (
              <div key={day} title={`${day}: ${n}`} style={{ flex: 1, background: 'rgba(45,212,191,0.75)', height: `${(n / maxDay) * 100}%`, borderRadius: 4, minHeight: 4 }} />
            ))}
          </div>
          <h3 style={{ marginTop: 24 }}>Rating mix</h3>
          {stats && Object.entries(stats.by_rating).map(([k, v]) => (
            <div key={k} className="row" style={{ marginBottom: 8 }}>
              <span style={{ width: 60 }}>R{k}</span>
              <div className="meter spacer"><span style={{ width: `${(v / Math.max(1, stats.total)) * 100}%` }} /></div>
              <span className="muted">{v}</span>
            </div>
          ))}
          <h3 style={{ marginTop: 24 }}>Difficulty library</h3>
          {Object.entries(overview.difficulty_breakdown).map(([k, v]) => (
            <div key={k} className="row" style={{ marginBottom: 8 }}>
              <span className={`badge ${k.toLowerCase()}`}>{k}</span>
              <span className="spacer" />
              <strong>{v}</strong>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

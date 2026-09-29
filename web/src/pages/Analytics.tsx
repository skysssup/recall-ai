import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Problem } from '../lib/types'
import HealthBar from '../components/HealthBar'

export default function AnalyticsPage() {
  const [overview, setOverview] = useState<Awaited<ReturnType<typeof api.analytics>> | null>(null)
  const [stats, setStats] = useState<Awaited<ReturnType<typeof api.reviewStats>> | null>(null)
  const [forecast, setForecast] = useState<Awaited<ReturnType<typeof api.forecast>> | null>(null)
  const [leeches, setLeeches] = useState<Problem[]>([])

  useEffect(() => {
    api.analytics().then(setOverview)
    api.reviewStats().then(setStats)
    api.forecast(14).then(setForecast)
    api.leeches().then(setLeeches).catch(() => setLeeches([]))
  }, [])

  if (!overview) return <div className="empty" role="status">Loading analytics…</div>

  const days = Object.entries(stats?.last_30_days || {}).sort(([a], [b]) => a.localeCompare(b))
  const maxDay = Math.max(1, ...days.map(([, n]) => n))
  const maxForecast = Math.max(1, ...(forecast?.series.map((d) => d.due_count) || [1]))

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Analytics</h2>
          <p>Retention health, review forecast, leeches, and volume.</p>
        </div>
      </div>
      <div className="grid-stats">
        <div className="stat-card"><div className="label">Health</div><div className="value">{Math.round(overview.health_score * 100)}%</div></div>
        <div className="stat-card"><div className="label">Streak</div><div className="value">{overview.streak_days}d</div></div>
        <div className="stat-card"><div className="label">Reviews (30d)</div><div className="value">{stats?.total ?? 0}</div></div>
        <div className="stat-card"><div className="label">Leeches</div><div className="value">{leeches.length}</div></div>
      </div>

      <div className="panel" style={{ marginBottom: 16 }}>
        <h3>14-day due forecast</h3>
        <p className="muted" style={{ marginTop: 0 }}>
          Cards that would enter the queue each day if you review nothing new.
          {forecast ? ` · ${forecast.total_projected} total projected` : ''}
        </p>
        {!forecast?.series.length ? (
          <div className="empty">No forecast data yet.</div>
        ) : (
          <div
            style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 120 }}
            role="img"
            aria-label="14-day due forecast bar chart"
          >
            {forecast.series.map((d) => (
              <div
                key={d.date}
                title={`${d.date}: ${d.due_count} due`}
                style={{
                  flex: 1,
                  background: d.due_count ? 'rgba(96,165,250,0.8)' : 'rgba(148,163,184,0.25)',
                  height: `${Math.max(4, (d.due_count / maxForecast) * 100)}%`,
                  borderRadius: 4,
                  minHeight: 4,
                }}
              />
            ))}
          </div>
        )}
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
          <div
            style={{ display: 'flex', alignItems: 'flex-end', gap: 4, height: 140 }}
            role="img"
            aria-label="30-day review activity"
          >
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

      {leeches.length > 0 && (
        <div className="panel" style={{ marginTop: 16 }}>
          <h3>Leeches</h3>
          <p className="muted" style={{ marginTop: 0 }}>Cards with many lapses — consider rewriting notes or splitting the skill.</p>
          <table className="table">
            <thead>
              <tr>
                <th scope="col">Title</th>
                <th scope="col">Lapses</th>
                <th scope="col">Difficulty</th>
                <th scope="col">Recall</th>
              </tr>
            </thead>
            <tbody>
              {leeches.map((p) => (
                <tr key={p.id}>
                  <td>{p.title}</td>
                  <td>{p.lapses}</td>
                  <td><span className={`badge ${p.difficulty.toLowerCase()}`}>{p.difficulty}</span></td>
                  <td><HealthBar value={p.retrievability} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}

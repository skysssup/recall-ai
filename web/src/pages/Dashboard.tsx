import { useEffect, useState } from 'react'
import { Link } from 'react-router-dom'
import { api } from '../lib/api'
import type { Dashboard } from '../lib/types'
import HealthBar from '../components/HealthBar'

export default function DashboardPage() {
  const [data, setData] = useState<Dashboard | null>(null)
  const [err, setErr] = useState('')

  useEffect(() => {
    api.dashboard().then(setData).catch((e) => setErr(String(e.message || e)))
  }, [])

  if (err) return <div className="panel empty">Backend unreachable: {err}</div>
  if (!data) return <div className="empty">Loading dashboard…</div>

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Dashboard</h2>
          <p>Due cards and topic health.</p>
        </div>
        <Link className="btn primary" to="/review">Start review</Link>
      </div>

      <div className="grid-stats">
        <div className="stat-card">
          <div className="label">Due now</div>
          <div className="value">{data.due_count}</div>
          <div className="sub">{data.reviews_today} reviewed today</div>
        </div>
        <div className="stat-card">
          <div className="label">Health</div>
          <div className="value">{Math.round(data.health_score * 100)}%</div>
          <div className="sub">avg topic retrievability</div>
        </div>
        <div className="stat-card">
          <div className="label">Streak</div>
          <div className="value">{data.streak_days}d</div>
          <div className="sub">{data.learned_count} cards practiced</div>
        </div>
        <div className="stat-card">
          <div className="label">Library</div>
          <div className="value">{data.problem_count}</div>
          <div className="sub">{data.topic_count} topics seeded</div>
        </div>
      </div>

      <div className="layout-2">
        <div className="panel">
          <h3>Up next</h3>
          {!data.upcoming.length && <div className="empty">Nothing due — add problems or log a solve.</div>}
          <table className="table">
            <thead>
              <tr><th>Problem</th><th>Topic</th><th>Recall</th></tr>
            </thead>
            <tbody>
              {data.upcoming.map((p) => (
                <tr key={p.id}>
                  <td>
                    <div>{p.title}</div>
                    <div className="muted" style={{ fontSize: 12 }}>{p.platform} · {p.difficulty}</div>
                  </td>
                  <td>{p.topic_name || '—'}</td>
                  <td><HealthBar value={p.retrievability} /></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="panel">
          <h3>Weak topics</h3>
          {data.weak_topics.map((t) => (
            <div key={t.name} className="row" style={{ marginBottom: 12 }}>
              <div style={{ width: 140 }}>{t.name}</div>
              <div className="spacer"><HealthBar value={t.retrievability} /></div>
            </div>
          ))}
          <h3 style={{ marginTop: 24 }}>Recent solves</h3>
          {!data.recent_solves.length && <div className="muted">No captures yet.</div>}
          {data.recent_solves.map((s) => (
            <div key={s.id} className="row" style={{ marginBottom: 10 }}>
              <div>
                <div>{s.title || s.slug}</div>
                <div className="muted" style={{ fontSize: 12 }}>{s.platform} · {s.verdict}</div>
              </div>
              <span className="spacer" />
              <span className={`badge ${s.difficulty.toLowerCase()}`}>{s.difficulty}</span>
            </div>
          ))}
        </div>
      </div>
    </div>
  )
}

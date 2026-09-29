import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Problem } from '../lib/types'
import { RATING_LABELS } from '../lib/types'
import HealthBar from '../components/HealthBar'

export default function ReviewPage() {
  const [queue, setQueue] = useState<Problem[]>([])
  const [idx, setIdx] = useState(0)
  const [started, setStarted] = useState(Date.now())
  const [toast, setToast] = useState('')
  const [loading, setLoading] = useState(true)

  const reload = useCallback(() => {
    setLoading(true)
    api.queue(30).then((q) => {
      setQueue(q)
      setIdx(0)
      setStarted(Date.now())
      setLoading(false)
    })
  }, [])

  useEffect(() => { reload() }, [reload])

  const current = queue[idx]

  const submit = useCallback(async (rating: number) => {
    if (!current) return
    const duration = Math.round((Date.now() - started) / 1000)
    await api.review(current.id, rating, duration)
    setToast(`${RATING_LABELS[rating].label} · next interval scheduled`)
    const next = queue.slice(0, idx).concat(queue.slice(idx + 1))
    setQueue(next)
    setStarted(Date.now())
    if (idx >= next.length) setIdx(Math.max(0, next.length - 1))
    setTimeout(() => setToast(''), 1600)
  }, [current, started, queue, idx])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault()
        submit(Number(e.key))
      }
      if (e.key === 'ArrowRight' && idx < queue.length - 1) setIdx(idx + 1)
      if (e.key === 'ArrowLeft' && idx > 0) setIdx(idx - 1)
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [submit, idx, queue.length])

  if (loading) return <div className="empty">Building review queue…</div>

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Review</h2>
          <p>Keyboard: 1 Again · 2 Hard · 3 Good · 4 Easy · ←/→ skip</p>
        </div>
        <button className="btn" onClick={reload}>Refresh queue</button>
      </div>

      {!current ? (
        <div className="panel empty">
          <h3 style={{ color: 'var(--accent)' }}>Queue clear</h3>
          <p>All caught up. Log a new solve or add problems to keep training.</p>
        </div>
      ) : (
        <div className="panel review-card">
          <div className="row">
            <span className={`badge ${current.difficulty.toLowerCase()}`}>{current.difficulty}</span>
            <span className="badge">{current.platform}</span>
            {current.topic_name && <span className="badge">{current.topic_name}</span>}
            <span className="spacer" />
            <span className="muted">{idx + 1} / {queue.length}</span>
          </div>
          <div className="title">{current.title}</div>
          <div className="row muted">
            <span>Recall</span>
            <HealthBar value={current.retrievability} />
            <span>·</span>
            <span>{current.review_count} reviews</span>
            {current.url && (
              <a className="btn ghost" href={current.url} target="_blank" rel="noreferrer">Open problem</a>
            )}
          </div>
          {current.notes && (
            <div className="panel" style={{ background: 'var(--bg)', boxShadow: 'none' }}>
              <h3>Notes</h3>
              <div style={{ whiteSpace: 'pre-wrap' }}>{current.notes}</div>
            </div>
          )}
          <div className="rating-row">
            {[1, 2, 3, 4].map((r) => (
              <button key={r} className={`rating-btn r${r}`} onClick={() => submit(r)}>
                <div className="label">{RATING_LABELS[r].label}</div>
                <div className="hint">{RATING_LABELS[r].hint}</div>
                <div className="key">Press {r}</div>
              </button>
            ))}
          </div>
        </div>
      )}
      {toast && <div className="toast">{toast}</div>}
    </div>
  )
}

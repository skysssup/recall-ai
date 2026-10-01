import { useCallback, useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { Problem } from '../lib/types'
import { RATING_LABELS } from '../lib/types'
import HealthBar from '../components/HealthBar'

function formatInterval(days: number): string {
  if (days < 1) {
    const hours = Math.max(1, Math.round(days * 24))
    return `${hours}h`
  }
  if (days < 30) return `${days.toFixed(days < 10 ? 1 : 0)}d`
  return `${(days / 30).toFixed(1)}mo`
}

export default function ReviewPage() {
  const [queue, setQueue] = useState<Problem[]>([])
  const [idx, setIdx] = useState(0)
  const [started, setStarted] = useState(Date.now())
  const [toast, setToast] = useState('')
  const [loading, setLoading] = useState(true)
  const [queueError, setQueueError] = useState<string | null>(null)
  const [previews, setPreviews] = useState<Record<string, number>>({})
  const [lastReviewedId, setLastReviewedId] = useState<string | null>(null)

  const reload = useCallback(() => {
    setLoading(true)
    setQueueError(null)
    api.queue(30).then((q) => {
      setQueue(q)
      setIdx(0)
      setStarted(Date.now())
      setLoading(false)
    }).catch((err) => {
      setQueue([])
      setQueueError(err instanceof Error ? err.message : 'Failed to load review queue')
      setLoading(false)
    })
  }, [])

  useEffect(() => { reload() }, [reload])

  const current = queue[idx]

  useEffect(() => {
    if (!current) {
      setPreviews({})
      return
    }
    let cancelled = false
    api.previewIntervals(current.id).then((res) => {
      if (!cancelled) setPreviews(res.intervals_days)
    }).catch(() => {
      if (!cancelled) setPreviews({})
    })
    return () => { cancelled = true }
  }, [current?.id])

  const submit = useCallback(async (rating: number) => {
    if (!current) return
    const duration = Math.round((Date.now() - started) / 1000)
    const reviewedId = current.id
    await api.review(current.id, rating, duration)
    setLastReviewedId(reviewedId)
    setToast(`${RATING_LABELS[rating].label} · next interval scheduled · U to undo`)
    const next = queue.slice(0, idx).concat(queue.slice(idx + 1))
    setQueue(next)
    setStarted(Date.now())
    if (idx >= next.length) setIdx(Math.max(0, next.length - 1))
    setTimeout(() => setToast(''), 2200)
  }, [current, started, queue, idx])

  const undo = useCallback(async () => {
    if (!lastReviewedId) {
      setToast('Nothing to undo')
      setTimeout(() => setToast(''), 1200)
      return
    }
    try {
      const res = await api.undoReview(lastReviewedId)
      setLastReviewedId(null)
      setToast(`Undid review of ${res.problem_title || 'card'}`)
      reload()
    } catch {
      setToast('Undo failed')
    }
    setTimeout(() => setToast(''), 1600)
  }, [lastReviewedId, reload])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (['1', '2', '3', '4'].includes(e.key)) {
        e.preventDefault()
        submit(Number(e.key))
      }
      if (e.key === 'ArrowRight' && idx < queue.length - 1) setIdx(idx + 1)
      if (e.key === 'ArrowLeft' && idx > 0) setIdx(idx - 1)
      if (e.key.toLowerCase() === 'u') {
        e.preventDefault()
        undo()
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [submit, undo, idx, queue.length])

  if (loading) return <div className="empty" role="status">Building review queue…</div>
  if (queueError) {
    return (
      <div className="empty" role="alert">
        <h3>Could not load queue</h3>
        <p className="muted">{queueError}</p>
        <button className="btn" onClick={reload}>Retry</button>
      </div>
    )
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Review</h2>
          <p>Keyboard: 1 Again · 2 Hard · 3 Good · 4 Easy · U undo · ←/→ skip</p>
        </div>
        <div className="row">
          <button className="btn" onClick={undo} disabled={!lastReviewedId} aria-label="Undo last review">
            Undo
          </button>
          <button className="btn" onClick={reload}>Refresh queue</button>
        </div>
      </div>

      {!current ? (
        <div className="panel empty">
          <h3 style={{ color: 'var(--accent)' }}>Queue clear</h3>
          <p>All caught up. Log a new solve or add problems to keep training.</p>
        </div>
      ) : (
        <div className="panel review-card" aria-live="polite">
          <div className="row">
            <span className={`badge ${current.difficulty.toLowerCase()}`}>{current.difficulty}</span>
            <span className="badge">{current.platform}</span>
            {current.topic_name && <span className="badge">{current.topic_name}</span>}
            {current.lapses >= 8 && <span className="badge" style={{ color: 'var(--danger, #f87171)' }}>leech</span>}
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
          <div className="rating-row" role="group" aria-label="Review rating">
            {[1, 2, 3, 4].map((r) => (
              <button
                key={r}
                className={`rating-btn r${r}`}
                onClick={() => submit(r)}
                aria-label={`${RATING_LABELS[r].label}${previews[String(r)] != null ? `, next in ${formatInterval(previews[String(r)])}` : ''}`}
              >
                <div className="label">{RATING_LABELS[r].label}</div>
                <div className="hint">
                  {previews[String(r)] != null
                    ? formatInterval(previews[String(r)])
                    : RATING_LABELS[r].hint}
                </div>
                <div className="key">Press {r}</div>
              </button>
            ))}
          </div>
        </div>
      )}
      {toast && <div className="toast" role="status">{toast}</div>}
    </div>
  )
}

import { useEffect, useState } from 'react'
import type { FormEvent } from 'react'
import { api } from '../lib/api'
import type { Topic } from '../lib/types'
import { RATING_LABELS } from '../lib/types'

export default function LogSolvePage() {
  const [topics, setTopics] = useState<Topic[]>([])
  const [result, setResult] = useState('')
  const [form, setForm] = useState({
    title: '',
    slug: '',
    platform: 'leetcode',
    difficulty: 'Medium',
    verdict: 'Accepted',
    topic_name: '',
    tags: '',
    time_to_understand_s: '',
    time_to_write_s: '',
    num_submissions: '1',
    hints_used: '0',
    url: '',
  })

  useEffect(() => { api.topics().then(setTopics) }, [])

  async function onSubmit(e: FormEvent) {
    e.preventDefault()
    const body = {
      title: form.title,
      slug: form.slug || form.title.toLowerCase().replace(/[^a-z0-9]+/g, '-'),
      platform: form.platform,
      difficulty: form.difficulty,
      verdict: form.verdict,
      topic_name: form.topic_name || undefined,
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      url: form.url || undefined,
      time_to_understand_s: form.time_to_understand_s ? Number(form.time_to_understand_s) : undefined,
      time_to_write_s: form.time_to_write_s ? Number(form.time_to_write_s) : undefined,
      num_submissions: Number(form.num_submissions || 1),
      hints_used: Number(form.hints_used || 0),
      auto_review: true,
    }
    const res = await api.manualSolve(body)
    const rating = res.applied_rating ? RATING_LABELS[res.applied_rating].label : '?'
    setResult(`Logged. Estimated recall ${(res.recall_strength ?? 0).toFixed(2)} → ${rating}`)
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Log a solve</h2>
          <p>Manual capture when the extension isn’t available. Feeds the same memory model.</p>
        </div>
      </div>
      <form className="panel" onSubmit={onSubmit} style={{ maxWidth: 760 }}>
        <div className="layout-2">
          <div>
            <div className="field"><label>Title</label><input className="input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
            <div className="field"><label>Slug</label><input className="input" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /></div>
            <div className="field"><label>URL</label><input className="input" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /></div>
            <div className="field"><label>Tags</label><input className="input" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} /></div>
          </div>
          <div>
            <div className="field"><label>Platform</label>
              <select className="select" value={form.platform} onChange={(e) => setForm({ ...form, platform: e.target.value })}>
                <option>leetcode</option><option>codeforces</option><option>manual</option>
              </select>
            </div>
            <div className="field"><label>Difficulty</label>
              <select className="select" value={form.difficulty} onChange={(e) => setForm({ ...form, difficulty: e.target.value })}>
                <option>Easy</option><option>Medium</option><option>Hard</option>
              </select>
            </div>
            <div className="field"><label>Verdict</label>
              <select className="select" value={form.verdict} onChange={(e) => setForm({ ...form, verdict: e.target.value })}>
                <option>Accepted</option><option>Wrong Answer</option><option>TLE</option><option>Runtime Error</option>
              </select>
            </div>
            <div className="field"><label>Topic</label>
              <select className="select" value={form.topic_name} onChange={(e) => setForm({ ...form, topic_name: e.target.value })}>
                <option value="">—</option>
                {topics.map((t) => <option key={t.id}>{t.name}</option>)}
              </select>
            </div>
          </div>
        </div>
        <div className="layout-2">
          <div className="field"><label>Time to understand (sec)</label><input className="input" type="number" value={form.time_to_understand_s} onChange={(e) => setForm({ ...form, time_to_understand_s: e.target.value })} /></div>
          <div className="field"><label>Time to write (sec)</label><input className="input" type="number" value={form.time_to_write_s} onChange={(e) => setForm({ ...form, time_to_write_s: e.target.value })} /></div>
          <div className="field"><label>Submissions</label><input className="input" type="number" value={form.num_submissions} onChange={(e) => setForm({ ...form, num_submissions: e.target.value })} /></div>
          <div className="field"><label>Hints used</label><input className="input" type="number" value={form.hints_used} onChange={(e) => setForm({ ...form, hints_used: e.target.value })} /></div>
        </div>
        <button className="btn primary" type="submit">Save solve</button>
        {result && <p style={{ color: 'var(--accent)' }}>{result}</p>}
      </form>
    </div>
  )
}

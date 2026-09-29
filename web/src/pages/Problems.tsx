import { useEffect, useMemo, useState } from 'react'
import type { FormEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { api } from '../lib/api'
import type { Problem, Topic } from '../lib/types'
import HealthBar from '../components/HealthBar'

export default function ProblemsPage() {
  const [problems, setProblems] = useState<Problem[]>([])
  const [topics, setTopics] = useState<Topic[]>([])
  const [q, setQ] = useState('')
  const [topic, setTopic] = useState('')
  const [showForm, setShowForm] = useState(false)
  const [form, setForm] = useState({
    title: '', platform: 'leetcode', slug: '', url: '', difficulty: 'Medium', topic_name: '', tags: '', notes: '',
  })
  const [params] = useSearchParams()
  const focus = params.get('focus')

  const load = () => {
    api.problems({ q, topic, limit: 200 }).then(setProblems)
    api.topics().then(setTopics)
  }
  useEffect(() => { load() }, [q, topic])

  const sorted = useMemo(() => {
    const list = [...problems]
    if (focus) list.sort((a, b) => (a.id === focus ? -1 : b.id === focus ? 1 : 0))
    return list
  }, [problems, focus])

  async function onCreate(e: FormEvent) {
    e.preventDefault()
    await api.createProblem({
      ...form,
      tags: form.tags.split(',').map((t) => t.trim()).filter(Boolean),
      topic_name: form.topic_name || undefined,
      slug: form.slug || undefined,
    })
    setShowForm(false)
    setForm({ title: '', platform: 'leetcode', slug: '', url: '', difficulty: 'Medium', topic_name: '', tags: '', notes: '' })
    load()
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Problems</h2>
          <p>Search, filter, and edit your spaced-repetition cards.</p>
        </div>
        <button className="btn primary" onClick={() => setShowForm((v) => !v)}>
          {showForm ? 'Close' : 'Add problem'}
        </button>
      </div>

      <div className="row" style={{ marginBottom: 16 }}>
        <input className="input" style={{ maxWidth: 320 }} placeholder="Filter title, tags, notes…" value={q} onChange={(e) => setQ(e.target.value)} />
        <select className="select" style={{ maxWidth: 220 }} value={topic} onChange={(e) => setTopic(e.target.value)}>
          <option value="">All topics</option>
          {topics.map((t) => <option key={t.id} value={t.name}>{t.name}</option>)}
        </select>
      </div>

      {showForm && (
        <form className="panel" style={{ marginBottom: 16 }} onSubmit={onCreate}>
          <div className="layout-2">
            <div>
              <div className="field"><label>Title</label><input className="input" required value={form.title} onChange={(e) => setForm({ ...form, title: e.target.value })} /></div>
              <div className="field"><label>Slug</label><input className="input" placeholder="auto from title" value={form.slug} onChange={(e) => setForm({ ...form, slug: e.target.value })} /></div>
              <div className="field"><label>URL</label><input className="input" value={form.url} onChange={(e) => setForm({ ...form, url: e.target.value })} /></div>
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
              <div className="field"><label>Topic</label>
                <select className="select" value={form.topic_name} onChange={(e) => setForm({ ...form, topic_name: e.target.value })}>
                  <option value="">—</option>
                  {topics.map((t) => <option key={t.id}>{t.name}</option>)}
                </select>
              </div>
            </div>
          </div>
          <div className="field"><label>Tags (comma-separated)</label><input className="input" value={form.tags} onChange={(e) => setForm({ ...form, tags: e.target.value })} /></div>
          <div className="field"><label>Notes</label><textarea className="textarea" value={form.notes} onChange={(e) => setForm({ ...form, notes: e.target.value })} /></div>
          <button className="btn primary" type="submit">Save problem</button>
        </form>
      )}

      <div className="panel">
        <table className="table">
          <thead>
            <tr><th>Problem</th><th>Topic</th><th>Recall</th><th>Reviews</th><th></th></tr>
          </thead>
          <tbody>
            {sorted.map((p) => (
              <tr key={p.id} style={p.id === focus ? { outline: '1px solid var(--accent)' } : undefined}>
                <td>
                  <div>{p.title}</div>
                  <div className="muted" style={{ fontSize: 12 }}>
                    <span className={`badge ${p.difficulty.toLowerCase()}`}>{p.difficulty}</span>{' '}
                    {p.platform} · {p.slug}
                  </div>
                </td>
                <td>{p.topic_name || '—'}</td>
                <td><HealthBar value={p.retrievability} /></td>
                <td>{p.review_count}</td>
                <td>
                  <button className="btn danger" onClick={async () => { await api.deleteProblem(p.id); load() }}>Delete</button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
        {!sorted.length && <div className="empty">No problems yet.</div>}
      </div>
    </div>
  )
}

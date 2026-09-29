import { NavLink, Outlet, useNavigate } from 'react-router-dom'
import {
  Activity,
  BookOpen,
  Brain,
  LayoutDashboard,
  Network,
  PlusCircle,
  Search,
  Settings,
  Sparkles,
} from 'lucide-react'
import { useEffect, useState } from 'react'
import { api } from '../lib/api'
import type { SearchHit } from '../lib/types'

const links = [
  { to: '/', label: 'Dashboard', icon: LayoutDashboard, kbd: 'G D' },
  { to: '/review', label: 'Review', icon: Brain, kbd: 'G R' },
  { to: '/problems', label: 'Problems', icon: BookOpen, kbd: 'G P' },
  { to: '/graph', label: 'Topic Graph', icon: Network, kbd: 'G G' },
  { to: '/analytics', label: 'Analytics', icon: Activity, kbd: 'G A' },
  { to: '/log', label: 'Log Solve', icon: PlusCircle, kbd: 'G L' },
  { to: '/settings', label: 'Settings', icon: Settings, kbd: 'G S' },
]

export default function Layout() {
  const navigate = useNavigate()
  const [searchOpen, setSearchOpen] = useState(false)
  const [q, setQ] = useState('')
  const [hits, setHits] = useState<SearchHit[]>([])
  const [goal, setGoal] = useState(10)
  const [today, setToday] = useState(0)

  useEffect(() => {
    api.settings().then((s) => setGoal(s.daily_goal)).catch(() => {})
    api.dashboard().then((d) => setToday(d.reviews_today)).catch(() => {})
  }, [])

  useEffect(() => {
    const onKey = (e: KeyboardEvent) => {
      const meta = e.metaKey || e.ctrlKey
      if (meta && e.key.toLowerCase() === 'k') {
        e.preventDefault()
        setSearchOpen(true)
        return
      }
      if (e.key === 'Escape') setSearchOpen(false)
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return
      if (e.key === 'g') {
        const handler = (ev: KeyboardEvent) => {
          const map: Record<string, string> = {
            d: '/',
            r: '/review',
            p: '/problems',
            g: '/graph',
            a: '/analytics',
            l: '/log',
            s: '/settings',
          }
          const path = map[ev.key.toLowerCase()]
          if (path) {
            ev.preventDefault()
            navigate(path)
          }
          window.removeEventListener('keydown', handler)
        }
        window.addEventListener('keydown', handler, { once: true })
      }
    }
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [navigate])

  useEffect(() => {
    if (!searchOpen) return
    const t = setTimeout(() => {
      if (!q.trim()) {
        setHits([])
        return
      }
      api.search(q).then(setHits).catch(() => setHits([]))
    }, 120)
    return () => clearTimeout(t)
  }, [q, searchOpen])

  return (
    <div className="app-shell">
      <aside className="sidebar">
        <div className="brand">
          <div className="brand-mark">R</div>
          <div>
            <h1>Recall</h1>
            <p>spaced DSA memory</p>
          </div>
        </div>
        {links.map(({ to, label, icon: Icon, kbd }) => (
          <NavLink key={to} to={to} end={to === '/'} className={({ isActive }) => `nav-link${isActive ? ' active' : ''}`}>
            <Icon size={16} />
            <span>{label}</span>
            <span className="kbd">{kbd}</span>
          </NavLink>
        ))}
        <button className="nav-link" style={{ border: 'none', background: 'transparent', width: '100%', cursor: 'pointer' }} onClick={() => setSearchOpen(true)}>
          <Search size={16} />
          <span>Search</span>
          <span className="kbd">⌘K</span>
        </button>
        <div className="sidebar-foot">
          <div className="row" style={{ marginBottom: 8 }}>
            <Sparkles size={14} color="var(--accent)" />
            <span>Daily goal</span>
            <span className="spacer" />
            <strong style={{ color: 'var(--text)' }}>{today}/{goal}</strong>
          </div>
          <div className="meter"><span style={{ width: `${Math.min(100, (today / Math.max(1, goal)) * 100)}%` }} /></div>
        </div>
      </aside>
      <main className="main">
        <Outlet />
      </main>
      {searchOpen && (
        <div className="search-pop" role="dialog">
          <input
            autoFocus
            placeholder="Search topics, problems, notes…"
            value={q}
            onChange={(e) => setQ(e.target.value)}
          />
          {hits.map((h) => (
            <div
              key={`${h.kind}-${h.id}`}
              className="search-hit"
              onClick={() => {
                setSearchOpen(false)
                setQ('')
                navigate(h.kind === 'topic' ? '/graph' : `/problems?focus=${h.id}`)
              }}
            >
              <div className="kind">{h.kind}</div>
              <div>
                <div>{h.title}</div>
                <div className="muted" style={{ fontSize: 12 }}>{h.subtitle}</div>
              </div>
            </div>
          ))}
          {!hits.length && q.trim() && <div className="empty">No matches</div>}
        </div>
      )}
    </div>
  )
}

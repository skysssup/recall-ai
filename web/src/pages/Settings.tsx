import { useEffect, useState } from 'react'
import { api } from '../lib/api'

export default function SettingsPage() {
  const [dailyGoal, setDailyGoal] = useState(10)
  const [token, setToken] = useState('')
  const [msg, setMsg] = useState('')

  useEffect(() => {
    api.settings().then((s) => {
      setDailyGoal(s.daily_goal)
      setToken(s.api_token)
    })
  }, [])

  async function save() {
    await api.saveSettings({ daily_goal: dailyGoal })
    setMsg('Saved')
    setTimeout(() => setMsg(''), 1200)
  }

  async function doExport() {
    const bundle = await api.exportBundle()
    const blob = new Blob([JSON.stringify(bundle, null, 2)], { type: 'application/json' })
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = `recall-export-${new Date().toISOString().slice(0, 10)}.json`
    a.click()
    URL.revokeObjectURL(url)
  }

  async function doImport(file: File) {
    const text = await file.text()
    const data = JSON.parse(text)
    await api.importBundle(data)
    setMsg('Import complete')
  }

  return (
    <div>
      <div className="page-head">
        <div>
          <h2>Settings</h2>
          <p>Local preferences, extension token, and backup.</p>
        </div>
      </div>

      <div className="layout-2">
        <div className="panel">
          <h3>Preferences</h3>
          <div className="field">
            <label>Daily review goal</label>
            <input className="input" type="number" min={1} max={100} value={dailyGoal} onChange={(e) => setDailyGoal(Number(e.target.value))} />
          </div>
          <button className="btn primary" onClick={save}>Save</button>
          {msg && <p style={{ color: 'var(--accent)' }}>{msg}</p>}
        </div>

        <div className="panel">
          <h3>Extension API token</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            Paste this into the browser extension popup along with <code>http://127.0.0.1:8787</code>.
            Override with env <code>RECALL_API_TOKEN</code>.
          </p>
          <input className="input" readOnly value={token} onFocus={(e) => e.target.select()} />
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Export / Import</h3>
        <p className="muted">Full JSON backup, or a flat CSV of the problem library for spreadsheets.</p>
        <div className="row">
          <button className="btn" onClick={doExport}>Download JSON</button>
          <a className="btn" href={api.exportCsvUrl()} download="recall-problems.csv">Download CSV</a>
          <label className="btn">
            Import JSON
            <span className="sr-only">Upload a Recall JSON backup</span>
            <input type="file" accept="application/json,.json" hidden onChange={(e) => {
              const f = e.target.files?.[0]
              if (f) doImport(f)
            }} />
          </label>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Keyboard shortcuts</h3>
        <table className="table">
          <tbody>
            <tr><td><span className="badge">⌘/Ctrl K</span></td><td>Search</td></tr>
            <tr><td><span className="badge">G then D/R/P/G/A/L/S</span></td><td>Navigate pages</td></tr>
            <tr><td><span className="badge">1 2 3 4</span></td><td>Rate current review card</td></tr>
            <tr><td><span className="badge">← →</span></td><td>Move in review queue</td></tr>
            <tr><td><span className="badge">U</span></td><td>Undo last review</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

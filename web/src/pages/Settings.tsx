import { useEffect, useState } from 'react'
import { api, getApiToken, setApiToken } from '../lib/api'

export default function SettingsPage() {
  const [dailyGoal, setDailyGoal] = useState(10)
  const [token, setToken] = useState(getApiToken())
  const [hint, setHint] = useState('')
  const [msg, setMsg] = useState('')
  const [busy, setBusy] = useState(false)

  async function perform(action: () => Promise<void>) {
    if (busy) return
    setBusy(true)
    setMsg('')
    try {
      await action()
    } catch (error) {
      setMsg(error instanceof Error ? error.message : 'Operation failed')
    } finally {
      setBusy(false)
    }
  }

  useEffect(() => {
    api
      .settings()
      .then((s) => {
        setDailyGoal(s.daily_goal)
        setHint(s.api_token_hint || '')
      })
      .catch(() => {
        setMsg('API token missing or rejected — paste RECALL_API_TOKEN below')
      })
  }, [])

  async function save() {
    setApiToken(token.trim())
    await api.saveSettings({ daily_goal: dailyGoal })
    setMsg('Saved')
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

  async function doExportCsv() {
    const token = getApiToken()
    const res = await fetch('/api/export/csv', {
      headers: token ? { 'X-API-Key': token } : {},
    })
    if (!res.ok) throw new Error(await res.text())
    const blob = await res.blob()
    const url = URL.createObjectURL(blob)
    const a = document.createElement('a')
    a.href = url
    a.download = 'recall-problems.csv'
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
            <input
              className="input"
              type="number"
              min={1}
              max={100}
              value={dailyGoal}
              onChange={(e) => setDailyGoal(Number(e.target.value))}
            />
          </div>
          <button className="btn primary" disabled={busy} onClick={() => void perform(save)}>
            Save
          </button>
          {msg && <p role="status" style={{ color: 'var(--accent)' }}>{msg}</p>}
        </div>

        <div className="panel">
          <h3>API token</h3>
          <p className="muted" style={{ marginTop: 0 }}>
            The server never returns the raw token. Set <code>RECALL_API_TOKEN</code> when starting
            the backend, paste the same value here (stored only in this browser) and in the
            extension popup. Server hint: <code>{hint || '…'}</code>
          </p>
          <input
            className="input"
            type="password"
            autoComplete="off"
            value={token}
            onChange={(e) => setToken(e.target.value)}
            placeholder="Paste RECALL_API_TOKEN"
          />
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Export / Import</h3>
        <p className="muted">
          Full JSON backup (merge on import upserts by platform/slug; review/solve history is
          keyed by platform, slug, timestamp, and rating/verdict — duplicates are skipped). API
          tokens are never exported. CSV is a flat problem library for spreadsheets.
        </p>
        <div className="row">
          <button className="btn" disabled={busy} onClick={() => void perform(doExport)}>
            Download JSON
          </button>
          <button className="btn" disabled={busy} onClick={() => void perform(doExportCsv)}>
            Download CSV
          </button>
          <label className="btn">
            Import JSON
            <span className="sr-only">Upload a Recall JSON backup</span>
            <input
              type="file"
              accept="application/json,.json"
              hidden
              disabled={busy}
              onChange={(e) => {
                const f = e.target.files?.[0]
                e.target.value = ''
                if (f) void perform(() => doImport(f))
              }}
            />
          </label>
        </div>
      </div>

      <div className="panel" style={{ marginTop: 16 }}>
        <h3>Keyboard shortcuts</h3>
        <table className="table">
          <tbody>
            <tr>
              <td>
                <span className="badge">⌘/Ctrl K</span>
              </td>
              <td>Search</td>
            </tr>
            <tr>
              <td>
                <span className="badge">G then D/R/P/G/A/L/S</span>
              </td>
              <td>Navigate pages</td>
            </tr>
            <tr>
              <td>
                <span className="badge">1 2 3 4</span>
              </td>
              <td>Rate current review card</td>
            </tr>
            <tr>
              <td>
                <span className="badge">← →</span>
              </td>
              <td>Move in review queue</td>
            </tr>
            <tr>
              <td>
                <span className="badge">U</span>
              </td>
              <td>Undo last review</td>
            </tr>
          </tbody>
        </table>
      </div>
    </div>
  )
}

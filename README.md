# Recall

Spaced repetition for coding problems, with a FastAPI/SQLite backend, React web UI, and experimental LeetCode capture extension.

Capture solves, rate reviews 1–4, and browse due cards and topic health. Scheduling is SM-2-ish (see `backend/app/scheduler.py`), not FSRS.

## Quick start

Use Python 3.10+ and Node.js 22.12+. Start in the repository root. On Windows, activate the backend environment with `.venv\Scripts\Activate.ps1` instead of `source`.

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Generate once and keep this value for later launches and both clients:
export RECALL_API_TOKEN="$(python -c 'import secrets; print(secrets.token_urlsafe(32))')"
python -m app
```

Keep Recall on loopback, not a public server. `python -m app` binds the configured loopback host and refuses non-loopback hosts or a missing token. Requests also require a loopback peer. Do not put the API behind a proxy: Uvicorn's trusted proxy headers can change the peer address the application sees.

All API routes except `/api/health` require the API token (`Authorization: Bearer …` or `X-API-Key`). The settings endpoint never returns the raw token.

Set `RECALL_API_TOKEN` before starting; there is no shared default token. In PowerShell use `$env:RECALL_API_TOKEN = python -c "import secrets; print(secrets.token_urlsafe(32))"`. Other env vars are optional (prefix `RECALL_`):

| Variable | Default | Purpose |
|---|---|---|
| `RECALL_DATABASE_URL` | `sqlite:///…/recall.db` | SQLAlchemy URL |
| `RECALL_API_TOKEN` | required | Shared secret for web UI + extension |
| `RECALL_HOST` | `127.0.0.1` | Bind host checked at startup |
| `RECALL_PORT` | `8787` | Bind port for `python -m app` |
| `RECALL_CORS_ORIGINS` | `http://localhost:5173,…` | Exact browser origins (comma-separated; no wildcards) |

### Web UI

Leave the backend running. Open a **second terminal in the repository root**:

```bash
cd web
npm ci
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to `127.0.0.1:8787`. Paste the same `RECALL_API_TOKEN` value into Settings and click Save (stored in `localStorage` only). Changing `RECALL_PORT` does not update the Vite proxy or extension host permissions.

### Browser extension

1. `chrome://extensions` → Developer mode → **Load unpacked** → `extension/`
2. Extension popup: backend `http://127.0.0.1:8787` + the same API token
3. Submit with the Submit button or Ctrl/⌘+Enter; an accepted submission result posts to `/api/capture/solve` and adds a review.

Capture is **experimental**: selectors have fixture tests but have not been verified against the current live LeetCode UI. Only a result following a submission attempt is captured, once per problem visit; page statistics and historical accepted results are not solves. Failed deliveries retry with the same event ID while that problem page stays open, backing off to once a minute. Pending captures are in memory and are lost on navigation or reload. Use Log Solve if capture fails.

Extension host permissions cover the local API, so CORS does not need `chrome-extension://*` wildcards.

## Backup merge semantics

- **Export** includes topics, edges, problems (with `due_at` / `last_reviewed_at`), reviews, solves, and non-secret settings. The live API token is never exported.
- **Import** (`merge: true`, default) upserts topics by name and problems by `(platform, slug)`. Review rows are skipped when `(problem, rating, created_at, note)` already exists; solves similarly by `(platform, slug, created_at, verdict)`. Imported solves are re-linked to problems by platform/slug. Preference settings in the bundle overwrite local keys; `api_token` / `api_key` keys are ignored.
- Imports validate record types, finite scheduling values, dates, duplicate keys, review references, and preference ranges before writing. `merge: false` requires every export section and replaces the database contents in one transaction; export a backup first. Merge accepts explicit empty notes/tags and null dates. Offset timestamps are normalized to UTC, and capture event IDs survive restoration. Legacy text is preserved without truncation, even when it exceeds current input limits.
- CSV prefixes formula-like text cells for spreadsheet safety.

## How scheduling works

Each card stores stability `S` and difficulty `D`. Retrievability:

```
R(t) = (1 + t / (9S)) ^ (-0.5)
```

Ratings 1–4 (Again / Hard / Good / Easy) update `S` and `D`. Successful reviews schedule the next due time around 90% retrievability; Again uses 12 hours. Times and forecast dates use UTC. Solve telemetry can map to a rating when captured. Undo rebuilds both the card and its topic state from remaining review history.

## Checks

From the repository root, after installing dependencies:

```bash
cd backend
source .venv/bin/activate
python -m pytest -q
cd ../web
npm test
npm run lint
npm run build
cd ..
node --test extension/tests/*.test.cjs
```

1.1.1 · MIT — see `LICENSE`.

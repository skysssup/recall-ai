# Recall

Spaced repetition for coding problems. FastAPI + SQLite backend, Vite web UI, MV3 browser extension for LeetCode capture.

Capture solves, rate reviews 1–4, and browse due cards and topic health. Scheduling is SM-2-ish (see `backend/app/scheduler.py`), not FSRS.

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
# Prefer the module entrypoint — it always binds RECALL_HOST (loopback only):
python -m app
# Or:
uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
```

Bind `127.0.0.1` only. Startup refuses every non-loopback `RECALL_HOST`, and each request is rejected unless the TCP peer is loopback (so a mistaken `uvicorn --host 0.0.0.0` still will not serve remote clients). Prefer `python -m app`, which forces the bind address from settings.

All API routes except `/api/health` require the API token (`Authorization: Bearer …` or `X-API-Key`). The settings endpoint never returns the raw token.

Optional env vars (prefix `RECALL_`):

| Variable | Default | Purpose |
|---|---|---|
| `RECALL_DATABASE_URL` | `sqlite:///…/recall.db` | SQLAlchemy URL |
| `RECALL_API_TOKEN` | `dev-token-change-me` | Shared secret for web UI + extension |
| `RECALL_HOST` | `127.0.0.1` | Bind host checked at startup |
| `RECALL_PORT` | `8787` | Bind port for `python -m app` |
| `RECALL_CORS_ORIGINS` | `http://localhost:5173,…` | Exact browser origins (comma-separated; no wildcards) |

### Web UI

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the backend. Paste the same `RECALL_API_TOKEN` value into Settings (stored in `localStorage` only).

### Browser extension

1. `chrome://extensions` → Developer mode → **Load unpacked** → `extension/`
2. Extension popup: backend `http://127.0.0.1:8787` + the same API token
3. Accepted LeetCode verdicts post to `/api/capture/solve`

Extension `host_permissions` cover the local API, so CORS does not need `chrome-extension://*` wildcards.

## Backup merge semantics

- **Export** includes topics, edges, problems (with `due_at` / `last_reviewed_at`), reviews, solves, and non-secret settings. The live API token is never exported.
- **Import** (`merge: true`, default) upserts topics by name and problems by `(platform, slug)`. Review rows are skipped when `(problem, rating, created_at, note)` already exists; solves similarly by `(platform, slug, created_at, verdict)`. Imported solves are re-linked to problems by platform/slug. Preference settings in the bundle overwrite local keys; `api_token` / `api_key` keys are ignored.
- Problems are flushed before reviews/solves are linked so a fresh empty database restores full history.

## How scheduling works

Each card stores stability `S` and difficulty `D`. Retrievability:

```
R(t) = (1 + t / (9S)) ^ (-0.5)
```

Ratings 1–4 (Again / Hard / Good / Easy) update `S` and `D`. Next due is when `R` would fall to ~90%. Times in the scheduler are naive UTC. Solve telemetry can map to a rating when captured. Undo rebuilds both the card and its topic stability/difficulty from remaining review history.

## Tests

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest -q
```

## Layout

```
backend/app/     FastAPI, scheduler, routers
backend/tests/
web/             Vite + React
extension/       MV3 LeetCode capture
```

1.1.1 · MIT — see `LICENSE`.

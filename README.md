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
uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
```

Bind `127.0.0.1` only. The default API token `dev-token-change-me` is a local toy — the API trusts it. Do not bind `0.0.0.0` while that default is still set; startup refuses non-loopback hosts with the default token.

Optional env vars (prefix `RECALL_`):

| Variable | Default | Purpose |
|---|---|---|
| `RECALL_DATABASE_URL` | `sqlite:///…/recall.db` | SQLAlchemy URL |
| `RECALL_API_TOKEN` | `dev-token-change-me` | Extension auth token |
| `RECALL_HOST` | `127.0.0.1` | Bind host checked at startup |

### Web UI

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). Vite proxies `/api` to the backend.

### Browser extension

1. `chrome://extensions` → Developer mode → **Load unpacked** → `extension/`
2. Settings in the web app → copy API token
3. Extension popup: backend `http://127.0.0.1:8787` + token
4. Accepted LeetCode verdicts post to `/api/capture/solve`

## How scheduling works

Each card stores stability `S` and difficulty `D`. Retrievability:

```
R(t) = (1 + t / (9S)) ^ (-0.5)
```

Ratings 1–4 (Again / Hard / Good / Easy) update `S` and `D`. Next due is when `R` would fall to ~90%. Times in the scheduler are naive UTC. Solve telemetry can map to a rating when captured.

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

1.1.0 · MIT — see `LICENSE`.

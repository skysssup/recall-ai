# Recall

**Spaced repetition for algorithmic problem solving.**

Recall keeps a personal library of coding problems, tracks how well you still remember each one, and schedules the next review using a transparent forgetting-curve model. Capture solves from the browser extension (or log them manually), review with keyboard shortcuts, and inspect topic health on a prerequisite graph.

## Features

- **Review queue** ranked by overdue urgency, low retrievability, and difficulty
- **Topic graph** with seeded DSA prerequisites (Arrays → Sliding Window → … → DP)
- **Problem library** with notes, tags, difficulty, and platform metadata
- **Solve capture** via Chrome extension (LeetCode) or manual form — timing + submissions map to a review grade
- **Search** across topics, problems, and notes (`⌘/Ctrl+K`)
- **Export / import** full JSON backups and CSV problem export
- **14-day due forecast**, leech detection, review undo, interval previews
- **Analytics** — health score, streak, rating mix, 30-day activity
- **Keyboard-first** navigation (`G` then `D/R/P/G/A/L/S`, ratings `1–4`, `U` undo)
- **Local-first** SQLite backend — no cloud account required

## Quick start

### Backend

```bash
cd backend
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
uvicorn app.main:app --reload --host 127.0.0.1 --port 8787
```

Optional env vars (prefix `RECALL_`):

| Variable | Default | Purpose |
|---|---|---|
| `RECALL_DATABASE_URL` | `sqlite:///…/recall.db` | SQLAlchemy URL |
| `RECALL_API_TOKEN` | `dev-token-change-me` | Extension auth token |

### Web UI

```bash
cd web
npm install
npm run dev
```

Open [http://localhost:5173](http://localhost:5173). The Vite dev server proxies `/api` to the backend.

### Browser extension

1. Open `chrome://extensions` → Developer mode → **Load unpacked** → select `extension/`
2. In the web app go to **Settings**, copy the API token
3. Open the extension popup, set backend URL `http://127.0.0.1:8787` and paste the token
4. Solve a LeetCode problem — Accepted verdicts are posted to `/api/capture/solve`

## How scheduling works

Each problem card stores stability `S` and difficulty `D`. Retrievability decays as:

```
R(t) = (1 + t / (9S)) ^ (-0.5)
```

A review rating (Again / Hard / Good / Easy) updates `S` and `D`, then the next due date is the time when `R` would fall to ~90%. Solve telemetry (understand/write time, submissions, hints, verdict) is mapped to a rating automatically when captured.

## Tests

```bash
cd backend
PYTHONPATH=. .venv/bin/pytest -q
```

## Project layout

```
backend/app/     FastAPI app, scheduler, graph, routers
backend/tests/   Scheduler, graph, and API tests
web/             Vite + React UI
extension/       MV3 LeetCode capture extension
```

## Version

1.1.0

## License

MIT

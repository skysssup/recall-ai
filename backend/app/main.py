from contextlib import asynccontextmanager
from ipaddress import ip_address

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .auth import client_is_loopback
from .config import settings
from .db import init_db
from .routers import analytics, capture, export_import, meta, problems, reviews, topics

APP_VERSION = "1.1.1"


def _is_loopback(host: str) -> bool:
    h = (host or "").strip().lower()
    if h == "localhost":
        return True
    try:
        return ip_address(h).is_loopback
    except ValueError:
        return False


@asynccontextmanager
async def lifespan(_app: FastAPI):
    # Local-only API: reject every non-loopback bind, even with a custom token.
    if not _is_loopback(settings.host):
        raise RuntimeError(
            f"Refusing to start: RECALL_HOST={settings.host!r} is not loopback. "
            "Bind 127.0.0.1 / localhost / ::1 only."
        )
    init_db()
    yield


app = FastAPI(
    title="Recall",
    description="Spaced repetition for coding problems",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Exact configured origins only — no wildcard localhost/extension regex.
_origins = [o for o in settings.cors_origins if o and "*" not in o]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Authorization", "Content-Type", "X-API-Key", "X-CSRF-Token"],
)


@app.middleware("http")
async def enforce_loopback_client(request: Request, call_next):
    """Reject peers that are not on loopback even if Uvicorn was bound broadly."""
    if not settings.relax_loopback_check and not client_is_loopback(request):
        return JSONResponse(
            status_code=403,
            content={"detail": "Recall accepts loopback clients only"},
        )
    return await call_next(request)


app.include_router(meta.router)
app.include_router(topics.router)
app.include_router(problems.router)
app.include_router(reviews.router)
app.include_router(capture.router)
app.include_router(analytics.router)
app.include_router(export_import.router)

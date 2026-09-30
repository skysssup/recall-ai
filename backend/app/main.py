from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import analytics, capture, export_import, meta, problems, reviews, topics

APP_VERSION = "1.1.0"


def _is_loopback(host: str) -> bool:
    h = (host or "").strip().lower()
    return h in {"127.0.0.1", "localhost", "::1"} or h.startswith("127.")


@asynccontextmanager
async def lifespan(_app: FastAPI):
    default_token = "dev-token-change-me"
    if settings.api_token == default_token and not _is_loopback(settings.host):
        raise RuntimeError(
            "Refusing to start: RECALL_API_TOKEN is still the default and "
            f"RECALL_HOST={settings.host!r} is not loopback. "
            "Bind 127.0.0.1 or set a real token."
        )
    init_db()
    yield


app = FastAPI(
    title="Recall",
    description="Spaced repetition for coding problems",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Allow configured origins plus localhost / extension origins.
_origins = list(settings.cors_origins)
app.add_middleware(
    CORSMiddleware,
    allow_origins=_origins,
    allow_origin_regex=r"^(https?://(localhost|127\.0\.0\.1)(:\d+)?|chrome-extension://.*)$",
    allow_credentials=False,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(meta.router)
app.include_router(topics.router)
app.include_router(problems.router)
app.include_router(reviews.router)
app.include_router(capture.router)
app.include_router(analytics.router)
app.include_router(export_import.router)

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import analytics, capture, export_import, meta, problems, reviews, topics

APP_VERSION = "1.1.0"


@asynccontextmanager
async def lifespan(_app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Recall",
    description="Spaced repetition for algorithmic problem solving",
    version=APP_VERSION,
    lifespan=lifespan,
)

# Local-first API: allow configured origins plus any localhost / extension origin.
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

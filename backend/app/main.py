from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .config import settings
from .db import init_db
from .routers import analytics, capture, export_import, meta, problems, reviews, topics

app = FastAPI(
    title="Recall",
    description="Spaced repetition for algorithmic problem solving",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins + ["*"],
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


@app.on_event("startup")
def on_startup():
    init_db()

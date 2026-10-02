from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_api_token
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Problem, Review
from ..schemas import ProblemOut
from ..services import (
    build_forecast,
    due_problems,
    interval_previews_for,
    list_leeches,
    problem_to_out,
    undo_last_review,
)

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/queue", response_model=list[ProblemOut])
def review_queue(limit: int = Query(20, le=100), db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    return [problem_to_out(p) for p in due_problems(db, limit)]


@router.get("/history")
def review_history(limit: int = Query(50, le=200), db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    rows = (
        db.query(Review)
        .options(joinedload(Review.problem))
        .order_by(Review.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "problem_id": r.problem_id,
            "problem_title": r.problem.title if r.problem else None,
            "rating": r.rating,
            "duration_sec": r.duration_sec,
            "note": r.note,
            "created_at": r.created_at.isoformat() + "Z",
        }
        for r in rows
    ]


@router.get("/stats")
def review_stats(db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    since = now - timedelta(days=30)
    rows = db.query(Review).filter(Review.created_at >= since).all()
    by_day: dict[str, int] = {}
    by_rating = {1: 0, 2: 0, 3: 0, 4: 0}
    for r in rows:
        key = r.created_at.date().isoformat()
        by_day[key] = by_day.get(key, 0) + 1
        by_rating[r.rating] = by_rating.get(r.rating, 0) + 1
    return {"last_30_days": by_day, "by_rating": by_rating, "total": len(rows)}


@router.get("/forecast")
def review_forecast(days: int = Query(14, ge=1, le=90), db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    """Projected due counts for the next N days (no new reviews assumed)."""
    series = build_forecast(db, days=days)
    return {
        "days": days,
        "series": series,
        "total_projected": sum(d["due_count"] for d in series),
    }


@router.get("/leeches", response_model=list[ProblemOut])
def review_leeches(
    threshold: int | None = Query(None, ge=1, le=50),
    db: Session = Depends(get_db), _token: str = Depends(require_api_token),
):
    return [problem_to_out(p) for p in list_leeches(db, threshold)]


@router.get("/preview/{problem_id}")
def review_preview(problem_id: str, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    return {
        "problem_id": p.id,
        "intervals_days": interval_previews_for(p),
    }


@router.post("/undo")
def review_undo(problem_id: str | None = Query(None), db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    """Undo the most recent review (optionally scoped to a problem) and rebuild card state."""
    result = undo_last_review(db, problem_id=problem_id)
    if result is None:
        raise HTTPException(404, "No review to undo")
    db.commit()
    return {"ok": True, **result}

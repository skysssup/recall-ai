from datetime import datetime, timedelta, timezone

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Review
from ..schemas import ProblemOut
from ..services import due_problems, problem_to_out

router = APIRouter(prefix="/api/reviews", tags=["reviews"])


@router.get("/queue", response_model=list[ProblemOut])
def review_queue(limit: int = Query(20, le=100), db: Session = Depends(get_db)):
    return [problem_to_out(p) for p in due_problems(db, limit)]


@router.get("/history")
def review_history(limit: int = Query(50, le=200), db: Session = Depends(get_db)):
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
def review_stats(db: Session = Depends(get_db)):
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

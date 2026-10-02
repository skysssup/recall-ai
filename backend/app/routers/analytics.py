from datetime import datetime, timezone

from fastapi import APIRouter, Depends

from ..auth import require_api_token
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Problem, Solve, Topic
from ..scheduler import retrievability
from ..services import compute_streak, health_score, problem_to_out, solve_to_out
from ..schemas import DashboardOut

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/dashboard", response_model=DashboardOut)
def dashboard(db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    problems = db.query(Problem).options(joinedload(Problem.topic)).all()
    topics = db.query(Topic).all()
    due = [
        p
        for p in problems
        if p.due_at is None or p.due_at <= now or retrievability(p.stability, p.last_reviewed_at, now) < 0.9
    ]
    due_sorted = sorted(
        due,
        key=lambda p: -problem_to_out(p, now).priority,
    )
    weak = sorted(
        [
            {
                "name": t.name,
                "retrievability": round(retrievability(t.stability, t.last_reviewed_at, now), 4),
                "difficulty": t.difficulty,
            }
            for t in topics
        ],
        key=lambda x: x["retrievability"],
    )[:6]

    from ..models import Review

    today = now.date()
    reviews_today = (
        db.query(Review).filter(Review.created_at >= datetime(today.year, today.month, today.day)).count()
    )
    recent = (
        db.query(Solve).order_by(Solve.created_at.desc()).limit(8).all()
    )
    return DashboardOut(
        due_count=len(due),
        learned_count=sum(1 for p in problems if p.review_count > 0),
        problem_count=len(problems),
        topic_count=len(topics),
        health_score=health_score(db),
        streak_days=compute_streak(db),
        reviews_today=reviews_today,
        weak_topics=weak,
        upcoming=[problem_to_out(p, now) for p in due_sorted[:8]],
        recent_solves=[solve_to_out(s) for s in recent],
    )


@router.get("/analytics/overview")
def analytics_overview(db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    topics = db.query(Topic).order_by(Topic.name).all()
    problems = db.query(Problem).all()
    return {
        "health_score": health_score(db),
        "streak_days": compute_streak(db),
        "topics": [
            {
                "name": t.name,
                "retrievability": round(retrievability(t.stability, t.last_reviewed_at, now), 4),
                "stability": t.stability,
                "difficulty": t.difficulty,
                "practice_count": t.practice_count,
            }
            for t in topics
        ],
        "difficulty_breakdown": {
            d: sum(1 for p in problems if p.difficulty == d) for d in ("Easy", "Medium", "Hard")
        },
        "platform_breakdown": {
            plat: sum(1 for p in problems if p.platform == plat)
            for plat in sorted({p.platform for p in problems})
        },
        "leech_count": sum(1 for p in problems if p.lapses >= 8),
    }

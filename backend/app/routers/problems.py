from fastapi import APIRouter, Depends, HTTPException, Query

from ..auth import require_api_token
from sqlalchemy.orm import Session, joinedload

from ..db import get_db
from ..models import Problem
from ..schemas import ProblemCreate, ProblemOut, ProblemUpdate, ReviewIn, ReviewOut
from ..services import (
    _tags_str,
    find_topic,
    problem_to_out,
    record_review,
    slugify,
    _utcnow,
)

router = APIRouter(prefix="/api/problems", tags=["problems"])


@router.get("", response_model=list[ProblemOut])
def list_problems(
    q: str | None = None,
    topic: str | None = None,
    difficulty: str | None = None,
    due_only: bool = False,
    limit: int = Query(200, le=500),
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    query = db.query(Problem).options(joinedload(Problem.topic))
    if topic:
        query = query.join(Problem.topic).filter(Problem.topic.has(name=topic))
    if difficulty:
        query = query.filter(Problem.difficulty == difficulty)
    rows = query.order_by(Problem.updated_at.desc()).limit(1000).all()
    out = [problem_to_out(p) for p in rows]
    if q:
        ql = q.lower()
        out = [
            p
            for p in out
            if ql in p.title.lower()
            or ql in p.slug.lower()
            or any(ql in t.lower() for t in p.tags)
            or ql in (p.notes or "").lower()
        ]
    if due_only:
        now = _utcnow()
        out = [p for p in out if p.due_at is None or p.due_at <= now or p.retrievability < 0.9]
    out.sort(key=lambda p: -p.priority)
    return out[:limit]


@router.post("", response_model=ProblemOut, status_code=201)
def create_problem(body: ProblemCreate, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    slug = body.slug or slugify(body.title)
    existing = (
        db.query(Problem)
        .filter(Problem.platform == body.platform, Problem.slug == slug)
        .first()
    )
    if existing:
        raise HTTPException(409, "Problem already exists for this platform/slug")
    topic = find_topic(db, body.topic_name)
    p = Problem(
        title=body.title,
        platform=body.platform,
        slug=slug,
        url=body.url,
        difficulty=body.difficulty,
        topic_id=topic.id if topic else None,
        tags=_tags_str(body.tags),
        notes=body.notes or "",
        due_at=_utcnow(),
    )
    db.add(p)
    db.commit()
    db.refresh(p)
    return problem_to_out(p)


@router.get("/{problem_id}", response_model=ProblemOut)
def get_problem(problem_id: str, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    p = db.query(Problem).options(joinedload(Problem.topic)).filter(Problem.id == problem_id).first()
    if not p:
        raise HTTPException(404, "Problem not found")
    return problem_to_out(p)


@router.patch("/{problem_id}", response_model=ProblemOut)
def update_problem(problem_id: str, body: ProblemUpdate, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    if body.title is not None:
        p.title = body.title
    if body.url is not None:
        p.url = body.url
    if body.difficulty is not None:
        p.difficulty = body.difficulty
    if body.notes is not None:
        p.notes = body.notes
    if body.tags is not None:
        p.tags = _tags_str(body.tags)
    if body.topic_name is not None:
        topic = find_topic(db, body.topic_name)
        p.topic_id = topic.id if topic else None
    db.commit()
    db.refresh(p)
    return problem_to_out(p)


@router.delete("/{problem_id}")
def delete_problem(problem_id: str, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    db.delete(p)
    db.commit()
    return {"ok": True}


@router.post("/{problem_id}/reviews", response_model=ReviewOut)
def review_problem(problem_id: str, body: ReviewIn, db: Session = Depends(get_db), _token: str = Depends(require_api_token)):
    p = db.get(Problem, problem_id)
    if not p:
        raise HTTPException(404, "Problem not found")
    review = record_review(db, p, body.rating, body.duration_sec, body.note)
    db.commit()
    db.refresh(p)
    return ReviewOut(
        id=review.id,
        problem_id=review.problem_id,
        rating=review.rating,
        duration_sec=review.duration_sec,
        note=review.note,
        created_at=review.created_at,
        next_due_at=p.due_at,
        stability=p.stability,
        retrievability=p.retrievability,
    )

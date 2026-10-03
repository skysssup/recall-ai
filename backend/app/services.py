from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Optional
from uuid import uuid4

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from . import graph as graph_mod
from .models import Problem, Review, Setting, Solve, Topic
from .config import settings
from .scheduler import (
    apply_review,
    forecast_due_counts,
    priority_score,
    preview_intervals,
    recall_from_solve,
    retrievability,
)
from .schemas import ProblemOut, SolveOut, TopicOut


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


def _tags_list(raw: str) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split(",") if t.strip()]


def _tags_str(tags: list[str]) -> str:
    return ", ".join(sorted({t.strip() for t in tags if t.strip()}))


def slugify(title: str) -> str:
    s = "".join(ch.lower() if ch.isalnum() else "-" for ch in title).strip("-")
    while "--" in s:
        s = s.replace("--", "-")
    return s or uuid4().hex[:8]


def refresh_topic_stats(db: Session, topic: Optional[Topic]) -> None:
    if topic is None:
        return
    problems = db.query(Problem).filter(Problem.topic_id == topic.id).all()
    if not problems:
        topic.retrievability = retrievability(topic.stability, topic.last_reviewed_at)
        return
    now = _utcnow()
    rs = [retrievability(p.stability, p.last_reviewed_at, now) for p in problems]
    topic.retrievability = round(sum(rs) / len(rs), 4)
    topic.practice_count = sum(p.review_count for p in problems)
    lasts = [p.last_reviewed_at for p in problems if p.last_reviewed_at]
    topic.last_reviewed_at = max(lasts) if lasts else topic.last_reviewed_at
    dues = [p.due_at for p in problems if p.due_at]
    topic.next_review_at = min(dues) if dues else None


def problem_to_out(p: Problem, now: Optional[datetime] = None) -> ProblemOut:
    now = now or _utcnow()
    r = retrievability(p.stability, p.last_reviewed_at, now)
    return ProblemOut(
        id=p.id,
        title=p.title,
        platform=p.platform,
        slug=p.slug,
        url=p.url,
        difficulty=p.difficulty,
        topic_id=p.topic_id,
        topic_name=p.topic.name if p.topic else None,
        tags=_tags_list(p.tags),
        notes=p.notes or "",
        stability=p.stability,
        difficulty_score=p.difficulty_score,
        retrievability=round(r, 4),
        due_at=p.due_at,
        last_reviewed_at=p.last_reviewed_at,
        review_count=p.review_count,
        lapses=p.lapses,
        created_at=p.created_at,
        priority=round(priority_score(r, p.difficulty_score, p.due_at, now), 4),
    )


def topic_to_out(db: Session, t: Topic) -> TopicOut:
    nbr = graph_mod.neighbors(db, t.name)
    count = db.query(func.count(Problem.id)).filter(Problem.topic_id == t.id).scalar() or 0
    r = retrievability(t.stability, t.last_reviewed_at)
    return TopicOut(
        id=t.id,
        name=t.name,
        description=t.description,
        stability=t.stability,
        difficulty=t.difficulty,
        retrievability=round(r, 4),
        practice_count=t.practice_count,
        last_reviewed_at=t.last_reviewed_at,
        next_review_at=t.next_review_at,
        problem_count=count,
        prerequisites=nbr["prerequisites"],
        dependents=nbr["dependents"],
    )


def solve_to_out(s: Solve, recall_strength: Optional[float] = None, rating: Optional[int] = None) -> SolveOut:
    return SolveOut(
        id=s.id,
        problem_id=s.problem_id,
        platform=s.platform,
        slug=s.slug,
        title=s.title,
        difficulty=s.difficulty,
        verdict=s.verdict,
        time_to_understand_s=s.time_to_understand_s,
        time_to_write_s=s.time_to_write_s,
        num_submissions=s.num_submissions,
        hints_used=s.hints_used,
        tags=_tags_list(s.tags),
        source=s.source,
        created_at=s.created_at,
        recall_strength=recall_strength,
        applied_rating=rating,
    )


def find_topic(db: Session, name: Optional[str]) -> Optional[Topic]:
    if not name:
        return None
    return db.query(Topic).filter(func.lower(Topic.name) == name.lower()).first()


def get_or_create_problem(
    db: Session,
    *,
    platform: str,
    slug: str,
    title: str,
    url: Optional[str] = None,
    difficulty: str = "Medium",
    topic_name: Optional[str] = None,
    tags: Optional[list[str]] = None,
) -> Problem:
    slug = slug or slugify(title)
    existing = (
        db.query(Problem)
        .filter(Problem.platform == platform, Problem.slug == slug)
        .first()
    )
    if existing:
        if title and existing.title != title:
            existing.title = title
        if url:
            existing.url = url
        if tags:
            merged = set(_tags_list(existing.tags)) | set(tags)
            existing.tags = _tags_str(list(merged))
        return existing

    topic = find_topic(db, topic_name)
    if topic is None and tags:
        # Map first known tag to a topic name.
        for tag in tags:
            topic = find_topic(db, tag)
            if topic:
                break

    p = Problem(
        title=title or slug,
        platform=platform,
        slug=slug,
        url=url,
        difficulty=difficulty or "Medium",
        topic_id=topic.id if topic else None,
        tags=_tags_str(tags or []),
        due_at=_utcnow(),
    )
    db.add(p)
    db.flush()
    return p


def record_review(
    db: Session,
    problem: Problem,
    rating: int,
    duration_sec: int = 0,
    note: str = "",
) -> Review:
    state = apply_review(
        stability=problem.stability,
        difficulty=problem.difficulty_score,
        rating=rating,
        review_count=problem.review_count,
        lapses=problem.lapses,
        last_review=problem.last_reviewed_at,
    )
    problem.stability = state.stability
    problem.difficulty_score = state.difficulty
    problem.retrievability = state.retrievability
    problem.due_at = state.due_at
    problem.last_reviewed_at = state.last_reviewed_at
    problem.review_count = state.review_count
    problem.lapses = state.lapses

    review = Review(
        problem_id=problem.id,
        rating=rating,
        duration_sec=duration_sec,
        note=note or "",
    )
    db.add(review)

    if problem.topic:
        # Nudge topic stability in the same direction (lighter weight).
        tstate = apply_review(
            stability=problem.topic.stability,
            difficulty=problem.topic.difficulty,
            rating=rating,
            review_count=problem.topic.practice_count,
            last_review=problem.topic.last_reviewed_at,
        )
        problem.topic.stability = tstate.stability
        problem.topic.difficulty = tstate.difficulty
        problem.topic.last_reviewed_at = tstate.last_reviewed_at
        refresh_topic_stats(db, problem.topic)

    db.flush()
    return review


def ingest_solve(db: Session, payload, source: str = "extension") -> tuple[Solve, float, int]:
    if payload.client_event_id:
        existing = db.query(Solve).filter(Solve.client_event_id == payload.client_event_id).first()
        if existing:
            strength, rating = recall_from_solve(
                existing.time_to_understand_s,
                existing.time_to_write_s,
                existing.num_submissions,
                existing.hints_used,
                existing.verdict,
                existing.difficulty,
            )
            return existing, strength, rating

    problem = get_or_create_problem(
        db,
        platform=payload.platform,
        slug=payload.slug,
        title=payload.title or payload.slug,
        url=payload.url,
        difficulty=payload.difficulty,
        topic_name=payload.topic_name,
        tags=payload.tags,
    )
    strength, rating = recall_from_solve(
        payload.time_to_understand_s,
        payload.time_to_write_s,
        payload.num_submissions,
        payload.hints_used,
        payload.verdict,
        payload.difficulty,
    )
    solve = Solve(
        problem_id=problem.id,
        client_event_id=payload.client_event_id,
        platform=payload.platform,
        slug=payload.slug,
        title=payload.title or payload.slug,
        difficulty=payload.difficulty,
        verdict=payload.verdict,
        time_to_understand_s=payload.time_to_understand_s,
        time_to_write_s=payload.time_to_write_s,
        num_submissions=payload.num_submissions,
        hints_used=payload.hints_used,
        tags=_tags_str(payload.tags),
        source=source,
    )
    db.add(solve)
    if getattr(payload, "auto_review", True):
        record_review(db, problem, rating)
    db.commit()
    db.refresh(solve)
    return solve, strength, rating


def due_problems(db: Session, limit: int = 50) -> list[Problem]:
    now = _utcnow()
    rows = db.query(Problem).all()
    scored = []
    for p in rows:
        r = retrievability(p.stability, p.last_reviewed_at, now)
        p.retrievability = r
        due = p.due_at is None or p.due_at <= now or r < 0.9
        if due:
            scored.append((priority_score(r, p.difficulty_score, p.due_at, now), p))
    scored.sort(key=lambda x: -x[0])
    return [p for _, p in scored[:limit]]


def compute_streak(db: Session) -> int:
    days = {
        r.created_at.date()
        for r in db.query(Review.created_at).all()
        if r.created_at
    }
    if not days:
        return 0
    streak = 0
    day = _utcnow().date()
    # Allow yesterday to count if nothing today yet
    if day not in days and (day - timedelta(days=1)) in days:
        day = day - timedelta(days=1)
    while day in days:
        streak += 1
        day = day - timedelta(days=1)
    return streak


def health_score(db: Session) -> float:
    topics = db.query(Topic).all()
    if not topics:
        return 1.0
    now = _utcnow()
    vals = [retrievability(t.stability, t.last_reviewed_at, now) for t in topics]
    return round(sum(vals) / len(vals), 4)


def search_all(db: Session, q: str, limit: int = 30) -> list[dict]:
    q = (q or "").strip()
    if not q:
        return []
    like = f"%{q}%"
    hits: list[dict] = []
    for t in db.query(Topic).filter(or_(Topic.name.ilike(like), Topic.description.ilike(like))).limit(limit):
        hits.append({"kind": "topic", "id": t.id, "title": t.name, "subtitle": t.description or "", "score": 1.0})
    for p in (
        db.query(Problem)
        .filter(
            or_(
                Problem.title.ilike(like),
                Problem.slug.ilike(like),
                Problem.tags.ilike(like),
                Problem.notes.ilike(like),
            )
        )
        .limit(limit)
    ):
        hits.append(
            {
                "kind": "problem",
                "id": p.id,
                "title": p.title,
                "subtitle": f"{p.platform} · {p.difficulty}",
                "score": 0.9,
            }
        )
    return hits[:limit]


def get_setting(db: Session, key: str, default: str = "") -> str:
    row = db.get(Setting, key)
    return row.value if row else default


def set_setting(db: Session, key: str, value: str) -> None:
    row = db.get(Setting, key)
    if row:
        row.value = value
    else:
        db.add(Setting(key=key, value=value))



def rebuild_topic_from_history(db: Session, topic: Optional[Topic]) -> None:
    """
    Recompute topic stability, difficulty, and timestamps from remaining
    review history across all problems in the topic (cold-start + replay).
    """
    if topic is None:
        return
    db.flush()
    problems = db.query(Problem).filter(Problem.topic_id == topic.id).all()
    problem_ids = [p.id for p in problems]
    topic.stability = 1.0
    topic.difficulty = 5.0
    topic.practice_count = 0
    topic.last_reviewed_at = None
    topic.next_review_at = None
    topic.retrievability = 1.0
    if not problem_ids:
        return
    reviews = (
        db.query(Review)
        .filter(Review.problem_id.in_(problem_ids))
        .order_by(Review.created_at.asc())
        .all()
    )
    for rev in reviews:
        tstate = apply_review(
            stability=topic.stability,
            difficulty=topic.difficulty,
            rating=rev.rating,
            review_count=topic.practice_count,
            last_review=topic.last_reviewed_at,
            current=rev.created_at,
        )
        topic.stability = tstate.stability
        topic.difficulty = tstate.difficulty
        topic.last_reviewed_at = tstate.last_reviewed_at
        topic.practice_count = tstate.review_count
    refresh_topic_stats(db, topic)


def undo_last_review(db: Session, problem_id: Optional[str] = None) -> Optional[dict]:
    """
    Remove the most recent review and rebuild card state from remaining history.
    When problem_id is set, undo only that problem's latest review.
    Returns a summary dict, or None if nothing to undo.
    """
    q = db.query(Review).order_by(Review.created_at.desc())
    if problem_id:
        q = q.filter(Review.problem_id == problem_id)
    latest = q.first()
    if latest is None:
        return None

    problem = db.get(Problem, latest.problem_id)
    if problem is None:
        db.delete(latest)
        db.flush()
        return {"undone_review_id": latest.id, "problem_id": latest.problem_id}

    topic = problem.topic
    summary = {
        "undone_review_id": latest.id,
        "problem_id": problem.id,
        "rating": latest.rating,
        "problem_title": problem.title,
    }
    db.delete(latest)
    db.flush()

    remaining = (
        db.query(Review)
        .filter(Review.problem_id == problem.id)
        .order_by(Review.created_at.asc())
        .all()
    )
    # Rebuild from cold-start defaults.
    problem.stability = 1.0
    problem.difficulty_score = 5.0
    problem.retrievability = 1.0
    problem.review_count = 0
    problem.lapses = 0
    problem.last_reviewed_at = None
    problem.due_at = _utcnow()

    for rev in remaining:
        state = apply_review(
            stability=problem.stability,
            difficulty=problem.difficulty_score,
            rating=rev.rating,
            review_count=problem.review_count,
            lapses=problem.lapses,
            last_review=problem.last_reviewed_at,
            current=rev.created_at,
        )
        problem.stability = state.stability
        problem.difficulty_score = state.difficulty
        problem.retrievability = state.retrievability
        problem.due_at = state.due_at
        problem.last_reviewed_at = state.last_reviewed_at
        problem.review_count = state.review_count
        problem.lapses = state.lapses

    if topic:
        rebuild_topic_from_history(db, topic)
    db.flush()
    return summary


def build_forecast(db: Session, days: int = 14) -> list[dict]:
    now = _utcnow()
    cards = [
        (p.stability, p.last_reviewed_at, p.due_at)
        for p in db.query(Problem).all()
    ]
    return forecast_due_counts(cards, days=days, current=now)


def list_leeches(db: Session, threshold: Optional[int] = None) -> list[Problem]:
    thresh = threshold if threshold is not None else settings.leech_threshold
    rows = db.query(Problem).filter(Problem.lapses >= thresh).order_by(Problem.lapses.desc()).all()
    return rows


def interval_previews_for(problem: Problem) -> dict[str, float]:
    raw = preview_intervals(
        stability=problem.stability,
        difficulty=problem.difficulty_score,
        review_count=problem.review_count,
        lapses=problem.lapses,
        last_review=problem.last_reviewed_at,
    )
    return {str(k): v for k, v in raw.items()}

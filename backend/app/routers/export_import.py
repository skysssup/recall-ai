import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel, ValidationError
from sqlalchemy.orm import Session

from ..auth import require_api_token
from ..backup import Backup
from ..db import get_db
from ..graph import ensure_edge
from ..models import Problem, Review, Setting, Solve, Topic, TopicEdge
from ..services import _tags_list, _tags_str, set_setting

router = APIRouter(prefix="/api", tags=["export"])


def _csv_cell(value):
    if isinstance(value, str) and value.lstrip().startswith(("=", "+", "-", "@")):
        return "'" + value
    return value


def _parse_ts(raw) -> datetime | None:
    if not raw:
        return None
    try:
        value = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
        if value.tzinfo is not None:
            value = value.astimezone(timezone.utc)
        return value.replace(tzinfo=None)
    except ValueError:
        return None


@router.get("/export")
def export_data(
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    topics = db.query(Topic).all()
    edges = db.query(TopicEdge).all()
    id_to_name = {t.id: t.name for t in topics}
    problems = db.query(Problem).all()
    reviews = db.query(Review).all()
    solves = db.query(Solve).all()
    # Never export the live API token — only non-secret preference keys.
    settings = {
        s.key: s.value
        for s in db.query(Setting).all()
        if s.key not in {"api_token", "api_key"}
    }
    problems_by_id = {p.id: p for p in problems}
    bundle = {
        "version": 1,
        "exported_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "topics": [
            {
                "name": t.name,
                "description": t.description,
                "stability": t.stability,
                "difficulty": t.difficulty,
                "practice_count": t.practice_count,
                "last_reviewed_at": t.last_reviewed_at.isoformat() + "Z" if t.last_reviewed_at else None,
                "next_review_at": t.next_review_at.isoformat() + "Z" if t.next_review_at else None,
            }
            for t in topics
        ],
        "edges": [
            {"from": id_to_name.get(e.from_topic_id), "to": id_to_name.get(e.to_topic_id)}
            for e in edges
            if e.from_topic_id in id_to_name and e.to_topic_id in id_to_name
        ],
        "problems": [
            {
                "title": p.title,
                "platform": p.platform,
                "slug": p.slug,
                "url": p.url,
                "difficulty": p.difficulty,
                "topic": p.topic.name if p.topic else None,
                "tags": _tags_list(p.tags),
                "notes": p.notes,
                "stability": p.stability,
                "difficulty_score": p.difficulty_score,
                "review_count": p.review_count,
                "lapses": p.lapses,
                "created_at": p.created_at.isoformat() + "Z",
                "due_at": p.due_at.isoformat() + "Z" if p.due_at else None,
                "last_reviewed_at": p.last_reviewed_at.isoformat() + "Z" if p.last_reviewed_at else None,
            }
            for p in problems
        ],
        "reviews": [
            {
                "problem_platform": problems_by_id[r.problem_id].platform,
                "problem_slug": problems_by_id[r.problem_id].slug,
                "rating": r.rating,
                "duration_sec": r.duration_sec,
                "note": r.note,
                "created_at": r.created_at.isoformat() + "Z",
            }
            for r in reviews if r.problem_id in problems_by_id
        ],
        "solves": [
            {
                "platform": s.platform,
                "slug": s.slug,
                "title": s.title,
                "difficulty": s.difficulty,
                "verdict": s.verdict,
                "time_to_understand_s": s.time_to_understand_s,
                "time_to_write_s": s.time_to_write_s,
                "num_submissions": s.num_submissions,
                "hints_used": s.hints_used,
                "tags": _tags_list(s.tags),
                "source": s.source,
                "client_event_id": s.client_event_id,
                "created_at": s.created_at.isoformat() + "Z",
            }
            for s in solves
        ],
        "settings": settings,
    }
    return bundle


@router.get("/export/download")
def export_download(
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    bundle = export_data(db, _token)
    body = json.dumps(bundle, indent=2)
    return PlainTextResponse(
        body,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=recall-export.json"},
    )


@router.get("/export/csv")
def export_problems_csv(
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    """Flat CSV of the problem library — handy for spreadsheets."""
    import csv
    import io

    problems = db.query(Problem).order_by(Problem.title).all()
    buf = io.StringIO()
    writer = csv.writer(buf)
    writer.writerow(
        [
            "title",
            "platform",
            "slug",
            "difficulty",
            "topic",
            "tags",
            "stability",
            "difficulty_score",
            "retrievability",
            "review_count",
            "lapses",
            "due_at",
            "last_reviewed_at",
            "url",
            "notes",
        ]
    )
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    from ..scheduler import retrievability

    for p in problems:
        r = retrievability(p.stability, p.last_reviewed_at, now)
        writer.writerow(
            [_csv_cell(value) for value in [
                p.title,
                p.platform,
                p.slug,
                p.difficulty,
                p.topic.name if p.topic else "",
                p.tags or "",
                f"{p.stability:.4f}",
                f"{p.difficulty_score:.4f}",
                f"{r:.4f}",
                p.review_count,
                p.lapses,
                p.due_at.isoformat() + "Z" if p.due_at else "",
                p.last_reviewed_at.isoformat() + "Z" if p.last_reviewed_at else "",
                p.url or "",
                (p.notes or "").replace("\n", " ").strip(),
            ]]
        )
    return PlainTextResponse(
        buf.getvalue(),
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=recall-problems.csv"},
    )


class ImportBody(BaseModel):
    data: dict
    merge: bool = True


@router.post("/import")
def import_data(
    body: ImportBody,
    db: Session = Depends(get_db),
    _token: str = Depends(require_api_token),
):
    """
    Merge (default) or replace-into semantics for a Recall export bundle.

    Merge keeps existing rows and upserts by platform/slug (problems) or
    (platform, slug, created_at, rating/verdict) for history. Settings keys
    in the bundle overwrite local preference values; API tokens are ignored.
    """
    try:
        backup = Backup.model_validate(body.data)
    except ValidationError:
        raise HTTPException(400, "Invalid export bundle: check record types, ranges, timestamps and duplicates")
    # Replacement requires all sections, so a partial bundle cannot erase history.
    if not body.merge and not all(key in body.data for key in
                                  ("topics", "edges", "problems", "reviews", "solves", "settings")):
        raise HTTPException(400, "Replacement requires a complete export bundle")
    data = backup.model_dump(mode="json", exclude_unset=True)
    if not body.merge:
        for model in (Review, Solve, Problem, TopicEdge, Topic, Setting):
            db.query(model).delete(synchronize_session=False)
        db.flush()

    # Topics
    topics_by_name = {t.name.lower(): t for t in db.query(Topic).all()}
    for t in data.get("topics", []):
        existing = topics_by_name.get(t["name"].lower())
        if not existing:
            existing = Topic(
                name=t["name"],
                description=t.get("description"),
                stability=float(t.get("stability", 1.0)),
                difficulty=float(t.get("difficulty", 5.0)),
                practice_count=int(t.get("practice_count", 0)),
            )
            db.add(existing)
            topics_by_name[t["name"].lower()] = existing
        else:
            for field in ("description", "stability", "difficulty", "practice_count"):
                if field in t:
                    setattr(existing, field, t[field])
        for field in ("last_reviewed_at", "next_review_at"):
            if field in t:
                setattr(existing, field, _parse_ts(t[field]))
    db.flush()

    name_to_topic = {t.name.lower(): t for t in db.query(Topic).all()}
    for e in data.get("edges", []):
        a, b = name_to_topic.get(e["from"].lower()), name_to_topic.get(e["to"].lower())
        if a and b:
            ensure_edge(db, a, b)
            db.flush()

    # Persist problems BEFORE querying them for review/solve linking.
    # SessionLocal uses autoflush=False, so pending inserts are invisible
    # to subsequent queries until an explicit flush.
    for raw in data.get("problems", []):
        platform = raw.get("platform", "manual")
        slug = raw.get("slug")
        if not slug:
            continue
        existing = (
            db.query(Problem).filter(Problem.platform == platform, Problem.slug == slug).first()
        )
        topic = name_to_topic.get(raw["topic"].lower()) if raw.get("topic") else None
        due_at = _parse_ts(raw.get("due_at"))
        last_reviewed_at = _parse_ts(raw.get("last_reviewed_at"))
        if existing and body.merge:
            existing.title = raw.get("title", existing.title)
            existing.notes = raw.get("notes", existing.notes)
            existing.tags = _tags_str(raw["tags"]) if "tags" in raw else existing.tags
            if "topic" in raw:
                existing.topic_id = topic.id if topic else None
            if "stability" in raw:
                existing.stability = float(raw.get("stability", existing.stability))
            if "difficulty_score" in raw:
                existing.difficulty_score = float(
                    raw.get("difficulty_score", existing.difficulty_score)
                )
            if "review_count" in raw:
                existing.review_count = int(raw.get("review_count", existing.review_count))
            if "lapses" in raw:
                existing.lapses = int(raw.get("lapses", existing.lapses))
            if "due_at" in raw:
                existing.due_at = due_at
            if "last_reviewed_at" in raw:
                existing.last_reviewed_at = last_reviewed_at
            for field in ("url", "difficulty"):
                if field in raw:
                    setattr(existing, field, raw[field])
            if "created_at" in raw and raw["created_at"] is not None:
                existing.created_at = _parse_ts(raw["created_at"])
        elif not existing:
            db.add(
                Problem(
                    title=raw.get("title") or slug,
                    platform=platform,
                    slug=slug,
                    url=raw.get("url"),
                    difficulty=raw.get("difficulty", "Medium"),
                    topic_id=topic.id if topic else None,
                    tags=_tags_str(raw.get("tags") or []),
                    notes=raw.get("notes") or "",
                    stability=float(raw.get("stability", 1.0)),
                    difficulty_score=float(raw.get("difficulty_score", 5.0)),
                    review_count=int(raw.get("review_count", 0)),
                    lapses=int(raw.get("lapses", 0)),
                    due_at=due_at,
                    last_reviewed_at=last_reviewed_at,
                    created_at=_parse_ts(raw.get("created_at")) or datetime.now(timezone.utc).replace(tzinfo=None),
                )
            )
    db.flush()

    problems_by_key = {
        (p.platform, p.slug): p for p in db.query(Problem).all() if p.slug
    }
    existing_reviews = {
        (r.problem_id, r.rating, r.created_at.isoformat() if r.created_at else None, r.note or "")
        for r in db.query(Review).all()
    }
    for raw in data.get("reviews") or []:
        platform = raw.get("problem_platform")
        slug = raw.get("problem_slug")
        prob = problems_by_key.get((platform, slug)) if platform and slug else None
        if not prob:
            continue
        created = _parse_ts(raw.get("created_at"))
        key = (
            prob.id,
            int(raw.get("rating", 0)),
            created.isoformat() if created else None,
            raw.get("note") or "",
        )
        if key in existing_reviews:
            continue
        rev = Review(
            problem_id=prob.id,
            rating=int(raw.get("rating", 0)),
            duration_sec=raw.get("duration_sec", 0),
            note=raw.get("note") or "",
        )
        if created is not None:
            rev.created_at = created
        db.add(rev)
        existing_reviews.add(key)

    event_ids = {s.client_event_id for s in db.query(Solve).all() if s.client_event_id}
    existing_solves = {
        (s.platform, s.slug, s.created_at.isoformat() if s.created_at else None, s.verdict or "")
        for s in db.query(Solve).all()
    }
    for raw in data.get("solves") or []:
        platform = raw.get("platform") or "manual"
        slug = raw.get("slug")
        if not slug:
            continue
        created = _parse_ts(raw.get("created_at"))
        key = (platform, slug, created.isoformat() if created else None, raw.get("verdict") or "")
        event_id = raw.get("client_event_id")
        if key in existing_solves or (event_id and event_id in event_ids):
            continue
        prob = problems_by_key.get((platform, slug))
        sol = Solve(
            problem_id=prob.id if prob else None,
            platform=platform,
            slug=slug,
            title=raw.get("title") or slug,
            difficulty=raw.get("difficulty") or "Medium",
            verdict=raw.get("verdict") or "",
            time_to_understand_s=raw.get("time_to_understand_s"),
            time_to_write_s=raw.get("time_to_write_s"),
            num_submissions=raw.get("num_submissions", 1),
            hints_used=raw.get("hints_used", 0),
            tags=_tags_str(raw.get("tags") or []),
            source=raw.get("source") or "import",
            client_event_id=event_id,
        )
        if created is not None:
            sol.created_at = created
        db.add(sol)
        existing_solves.add(key)
        if event_id:
            event_ids.add(event_id)

    for k, v in (data.get("settings") or {}).items():
        if k in {"api_token", "api_key"}:
            continue
        set_setting(db, k, str(v))
    db.commit()
    return {"ok": True}

import json
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from ..db import get_db
from ..graph import ensure_edge
from ..models import Problem, Review, Setting, Solve, Topic, TopicEdge
from ..services import _tags_list, _tags_str, find_topic, set_setting

router = APIRouter(prefix="/api", tags=["export"])


@router.get("/export")
def export_data(db: Session = Depends(get_db)):
    topics = db.query(Topic).all()
    edges = db.query(TopicEdge).all()
    id_to_name = {t.id: t.name for t in topics}
    problems = db.query(Problem).all()
    reviews = db.query(Review).all()
    solves = db.query(Solve).all()
    settings = {s.key: s.value for s in db.query(Setting).all()}
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
                "due_at": p.due_at.isoformat() + "Z" if p.due_at else None,
                "last_reviewed_at": p.last_reviewed_at.isoformat() + "Z" if p.last_reviewed_at else None,
            }
            for p in problems
        ],
        "reviews": [
            {
                "problem_platform": next((p.platform for p in problems if p.id == r.problem_id), None),
                "problem_slug": next((p.slug for p in problems if p.id == r.problem_id), None),
                "rating": r.rating,
                "duration_sec": r.duration_sec,
                "note": r.note,
                "created_at": r.created_at.isoformat() + "Z",
            }
            for r in reviews
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
                "created_at": s.created_at.isoformat() + "Z",
            }
            for s in solves
        ],
        "settings": settings,
    }
    return bundle


@router.get("/export/download")
def export_download(db: Session = Depends(get_db)):
    bundle = export_data(db)
    body = json.dumps(bundle, indent=2)
    return PlainTextResponse(
        body,
        media_type="application/json",
        headers={"Content-Disposition": "attachment; filename=recall-export.json"},
    )




@router.get("/export/csv")
def export_problems_csv(db: Session = Depends(get_db)):
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
            [
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
            ]
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
def import_data(body: ImportBody, db: Session = Depends(get_db)):
    data = body.data
    if not isinstance(data, dict) or "problems" not in data:
        raise HTTPException(400, "Invalid export bundle")

    # Topics
    for t in data.get("topics", []):
        existing = find_topic(db, t.get("name"))
        if not existing:
            db.add(
                Topic(
                    name=t["name"],
                    description=t.get("description"),
                    stability=float(t.get("stability", 1.0)),
                    difficulty=float(t.get("difficulty", 5.0)),
                    practice_count=int(t.get("practice_count", 0)),
                )
            )
    db.flush()

    name_to_topic = {t.name: t for t in db.query(Topic).all()}
    for e in data.get("edges", []):
        a, b = name_to_topic.get(e.get("from")), name_to_topic.get(e.get("to"))
        if a and b:
            ensure_edge(db, a, b)

    for raw in data.get("problems", []):
        platform = raw.get("platform", "manual")
        slug = raw.get("slug")
        if not slug:
            continue
        existing = (
            db.query(Problem).filter(Problem.platform == platform, Problem.slug == slug).first()
        )
        topic = name_to_topic.get(raw.get("topic")) if raw.get("topic") else None
        if existing and body.merge:
            existing.title = raw.get("title", existing.title)
            existing.notes = raw.get("notes", existing.notes) or existing.notes
            existing.tags = _tags_str(raw.get("tags") or _tags_list(existing.tags))
            if topic:
                existing.topic_id = topic.id
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
                )
            )
    # Restore review / solve history without duplicating identical rows.
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
        created = None
        if raw.get("created_at"):
            try:
                created = datetime.fromisoformat(str(raw["created_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                created = None
        key = (prob.id, int(raw.get("rating", 0)), created.isoformat() if created else None, raw.get("note") or "")
        if key in existing_reviews:
            continue
        rev = Review(
            problem_id=prob.id,
            rating=int(raw.get("rating", 0)),
            duration_sec=raw.get("duration_sec"),
            note=raw.get("note") or "",
        )
        if created is not None:
            rev.created_at = created
        db.add(rev)
        existing_reviews.add(key)

    existing_solves = {
        (s.platform, s.slug, s.created_at.isoformat() if s.created_at else None, s.verdict or "")
        for s in db.query(Solve).all()
    }
    for raw in data.get("solves") or []:
        platform = raw.get("platform") or "manual"
        slug = raw.get("slug")
        if not slug:
            continue
        created = None
        if raw.get("created_at"):
            try:
                created = datetime.fromisoformat(str(raw["created_at"]).replace("Z", "+00:00")).replace(tzinfo=None)
            except ValueError:
                created = None
        key = (platform, slug, created.isoformat() if created else None, raw.get("verdict") or "")
        if key in existing_solves:
            continue
        sol = Solve(
            platform=platform,
            slug=slug,
            title=raw.get("title") or slug,
            difficulty=raw.get("difficulty") or "Medium",
            verdict=raw.get("verdict") or "",
            time_to_understand_s=raw.get("time_to_understand_s"),
            time_to_write_s=raw.get("time_to_write_s"),
            num_submissions=raw.get("num_submissions"),
            hints_used=raw.get("hints_used"),
            tags=_tags_str(raw.get("tags") or []),
            source=raw.get("source") or "import",
        )
        if created is not None:
            sol.created_at = created
        db.add(sol)
        existing_solves.add(key)

    for k, v in (data.get("settings") or {}).items():
        set_setting(db, k, str(v))
    db.commit()
    return {"ok": True}

"""Import/undo fidelity on temp SQLite."""

from datetime import UTC, datetime, timedelta

from app.models import Problem, Review, Solve, Topic
from app.services import record_review, rebuild_topic_from_history, undo_last_review


def test_fresh_import_restores_reviews_due_and_solves(client, db):
    # Build a card with history, export, wipe via re-import into cleared state
    # by posting a bundle to an empty-ish DB (autouse resets between tests;
    # here we import into the current DB after constructing a synthetic bundle).
    created = client.post(
        "/api/problems",
        json={
            "title": "Two Sum",
            "platform": "leetcode",
            "slug": "two-sum-rt",
            "difficulty": "Easy",
            "topic_name": "Arrays",
        },
    )
    assert created.status_code == 201, created.text
    pid = created.json()["id"]
    rev = client.post(f"/api/problems/{pid}/reviews", json={"rating": 3, "duration_sec": 30})
    assert rev.status_code == 200
    due_before = client.get(f"/api/problems/{pid}").json()["due_at"]
    last_before = client.get(f"/api/problems/{pid}").json()["last_reviewed_at"]
    assert due_before
    assert last_before

    # Manual solve row
    solve = client.post(
        "/api/capture/manual",
        json={
            "platform": "leetcode",
            "slug": "two-sum-rt",
            "title": "Two Sum",
            "verdict": "Accepted",
            "auto_review": False,
        },
    )
    assert solve.status_code == 200

    bundle = client.get("/api/export").json()
    assert any(r.get("problem_slug") == "two-sum-rt" for r in bundle["reviews"])
    assert any(s.get("slug") == "two-sum-rt" for s in bundle["solves"])
    problem_row = next(p for p in bundle["problems"] if p["slug"] == "two-sum-rt")
    assert problem_row["due_at"]
    assert problem_row["last_reviewed_at"]

    # Simulate fresh DB import: drop problem/reviews/solves then import bundle
    for row in db.query(Review).all():
        db.delete(row)
    for row in db.query(Solve).all():
        db.delete(row)
    for row in db.query(Problem).all():
        db.delete(row)
    db.commit()

    # Direct import into empty problem table (autoflush=False regression target)
    imp = client.post("/api/import", json={"data": bundle, "merge": True})
    assert imp.status_code == 200, imp.text

    restored = (
        db.query(Problem)
        .filter(Problem.platform == "leetcode", Problem.slug == "two-sum-rt")
        .first()
    )
    assert restored is not None
    assert restored.due_at is not None
    assert restored.last_reviewed_at is not None
    reviews = db.query(Review).filter(Review.problem_id == restored.id).all()
    assert len(reviews) >= 1
    solves = db.query(Solve).filter(Solve.slug == "two-sum-rt").all()
    assert len(solves) >= 1
    assert all(s.problem_id == restored.id for s in solves)


def test_undo_rebuilds_topic_stability_difficulty(db):
    topic = db.query(Topic).filter(Topic.name == "Arrays").first()
    assert topic is not None
    problem = Problem(
        title="Undo Card",
        platform="manual",
        slug="undo-card",
        topic_id=topic.id,
        due_at=datetime.now(UTC).replace(tzinfo=None),
    )
    db.add(problem)
    db.flush()

    record_review(db, problem, rating=4)
    db.commit()
    db.refresh(topic)
    stability_after = topic.stability
    difficulty_after = topic.difficulty
    assert stability_after != 1.0 or difficulty_after != 5.0 or topic.practice_count > 0

    summary = undo_last_review(db, problem_id=problem.id)
    assert summary is not None
    db.commit()
    db.refresh(topic)
    db.refresh(problem)

    assert problem.review_count == 0
    assert problem.last_reviewed_at is None
    # Topic rebuilt from remaining history (none) → cold-start defaults
    assert topic.stability == 1.0
    assert topic.difficulty == 5.0
    assert topic.practice_count == 0

from datetime import datetime, timedelta

import pytest

from app import graph, scheduler
from app.models import Problem, Review, Topic
from app.routers.problems import update_problem
from app.schemas import ProblemUpdate
from app.services import record_review


def test_graph_matches_current_topic_retrievability(client, db, monkeypatch):
    now = datetime(2026, 10, 3, 14)

    class Clock(datetime):
        @classmethod
        def now(cls, tz=None):
            return now.replace(tzinfo=tz)

    monkeypatch.setattr(graph, "datetime", Clock)
    monkeypatch.setattr(scheduler, "datetime", Clock)
    topic = db.query(Topic).filter_by(name="Arrays").one()
    topic.stability = 1
    topic.last_reviewed_at = now - timedelta(days=365)
    topic.retrievability = 1
    db.commit()
    row = next(t for t in client.get("/api/topics").json() if t["id"] == topic.id)
    node = next(t for t in client.get("/api/topics/graph").json()["nodes"] if t["id"] == topic.id)
    expected = round(scheduler.retrievability(1, topic.last_reviewed_at, now), 4)
    assert node["retrievability"] == row["retrievability"] == expected
    assert expected < 0.2


@pytest.mark.parametrize("action", ["delete", "reassign", "detach"])
def test_removing_only_reviewed_problem_resets_old_topic(client, db, action):
    response = client.post("/api/problems", json={"title": "Reviewed", "topic_name": "Arrays"})
    assert response.status_code == 201
    problem = response.json()
    assert client.post(f"/api/problems/{problem['id']}/reviews", json={"rating": 4}).status_code == 200
    old_topic = client.get(f"/api/topics/{problem['topic_id']}").json()
    assert old_topic["practice_count"] == 1
    if action == "delete":
        response = client.delete(f"/api/problems/{problem['id']}")
    else:
        response = client.patch(f"/api/problems/{problem['id']}",
                                json={"topic_name": "Graphs" if action == "reassign" else ""})
    assert response.status_code == 200, response.text
    after = client.get(f"/api/topics/{problem['topic_id']}").json()
    assert after["problem_count"] == after["practice_count"] == 0
    assert after["stability"] == after["retrievability"] == 1
    assert after["difficulty"] == 5
    assert after["last_reviewed_at"] is None
    assert after["next_review_at"] is None
    if action == "reassign":
        new_topic = client.get(f"/api/topics/{response.json()['topic_id']}").json()
        assert new_topic["problem_count"] == new_topic["practice_count"] == 1
        for field in ("stability", "difficulty", "last_reviewed_at", "next_review_at"):
            assert new_topic[field] == old_topic[field]
    assert db.query(Review).count() == (0 if action == "delete" else 1)


@pytest.mark.parametrize("action", ["delete", "reassign"])
def test_topic_rebuild_replays_only_remaining_and_moved_history(client, db, action):
    old_topic = db.query(Topic).filter_by(name="Arrays").one()
    new_topic = db.query(Topic).filter_by(name="Graphs").one()
    cards = []
    for slug, topic, rating in (("keep", old_topic, 2), ("move", old_topic, 4), ("destination", new_topic, 3)):
        problem = Problem(title=slug, slug=slug, topic=topic)
        db.add(problem)
        db.flush()
        record_review(db, problem, rating)
        cards.append(problem)
    db.commit()
    keep, move, destination = cards
    move_id = move.id
    if action == "delete":
        response = client.delete(f"/api/problems/{move_id}")
    else:
        response = client.patch(f"/api/problems/{move_id}", json={"topic_name": "Graphs"})
    assert response.status_code == 200, response.text
    db.expire_all()
    assert old_topic.practice_count == old_topic.problems[0].review_count == 1
    assert old_topic.stability == keep.stability
    assert old_topic.difficulty == keep.difficulty_score
    assert old_topic.last_reviewed_at == keep.last_reviewed_at
    assert old_topic.next_review_at == keep.due_at
    expected = scheduler.apply_review(1, 5, 4 if action == "reassign" else 3,
                                      current=move.last_reviewed_at if action == "reassign" else destination.last_reviewed_at)
    if action == "reassign":
        expected = scheduler.apply_review(expected.stability, expected.difficulty, 3,
                                          review_count=1, last_review=expected.last_reviewed_at,
                                          current=destination.last_reviewed_at)
    assert new_topic.practice_count == (2 if action == "reassign" else 1)
    assert new_topic.stability == expected.stability
    assert new_topic.difficulty == expected.difficulty
    assert new_topic.last_reviewed_at == destination.last_reviewed_at
    assert new_topic.next_review_at == min(p.due_at for p in new_topic.problems)


def test_reassignment_updates_cached_relationship_before_followup_review(db):
    old_topic = db.query(Topic).filter_by(name="Arrays").one()
    new_topic = db.query(Topic).filter_by(name="Graphs").one()
    problem = Problem(title="Cached", slug="cached", topic=old_topic)
    db.add(problem)
    db.flush()
    record_review(db, problem, 4)
    assert problem.topic is old_topic
    assert problem in old_topic.problems
    assert problem not in new_topic.problems
    assert db.autoflush is False
    db.expire_on_commit = False
    updated = update_problem(problem.id, ProblemUpdate(topic_name="Graphs"), db, "test-token")
    assert updated.topic_id == new_topic.id
    assert updated.topic_name == new_topic.name
    assert problem.topic is new_topic
    assert problem not in old_topic.problems
    assert problem in new_topic.problems
    record_review(db, problem, 3)
    assert old_topic.practice_count == 0
    assert old_topic.last_reviewed_at is None
    assert new_topic.practice_count == 2


def test_assigning_reviewed_unassigned_problem_rebuilds_destination(client):
    problem = client.post("/api/problems", json={"title": "Unassigned"}).json()
    assert client.post(f"/api/problems/{problem['id']}/reviews", json={"rating": 4}).status_code == 200
    response = client.patch(f"/api/problems/{problem['id']}", json={"topic_name": "Arrays"})
    assert response.status_code == 200
    topic = client.get(f"/api/topics/{response.json()['topic_id']}").json()
    assert topic["practice_count"] == 1
    assert topic["stability"] == 3
    assert topic["last_reviewed_at"] is not None

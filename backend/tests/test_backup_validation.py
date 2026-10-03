import csv
import io
from datetime import datetime

import pytest
from fastapi.testclient import TestClient
from starlette.requests import Request

from app.auth import client_is_loopback
from app.backup import Backup
from app.config import settings
from app.main import app
from app.models import Problem, Review, Solve, Topic


@pytest.mark.parametrize("host", ["testclient", "localhost", "192.168.1.2", "", "127.evil"])
def test_peer_names_and_headers_do_not_bypass_loopback(host):
    request = Request({"type": "http", "client": (host, 123),
                       "headers": [(b"user-agent", b"testclient")]})
    assert not client_is_loopback(request)


def test_remote_peer_rejected_with_valid_token():
    with TestClient(app, client=("192.168.1.2", 123)) as client:
        assert client.get("/api/health", headers={"X-API-Key": settings.api_token}).status_code == 403


@pytest.mark.parametrize("replacement", [False, True])
def test_invalid_backup_is_atomic(client, replacement):
    client.post("/api/problems", json={"title": "Keep me", "slug": "keep"})
    before = client.get("/api/export").json()
    invalid = {**before, "problems": [{"slug": "valid"}, {"slug": "bad", "stability": -1}]}
    assert client.post("/api/import", json={"data": invalid, "merge": not replacement}).status_code == 400
    after = client.get("/api/export").json()
    assert before["problems"] == after["problems"]
    assert before["topics"] == after["topics"]


@pytest.mark.parametrize("changes", [{"problems": "wrong"}, {"version": 2},
    {"settings": {"daily_goal": "not-a-number"}}, {"reviews": [{"rating": 5}]},
    {"problems": [{"slug": "a"}, {"slug": "a"}]}])
def test_invalid_shapes_return_client_error(client, changes):
    bundle = {**client.get("/api/export").json(), **changes}
    assert client.post("/api/import", json={"data": bundle}).status_code == 400


def test_replacement_restores_dates_event_ids_and_cleared_fields(client, db):
    client.post("/api/capture/manual", json={"slug": "restore", "client_event_id": "event-123"})
    bundle = client.get("/api/export").json()
    record = bundle["problems"][0]
    record.update(notes="", tags=[], topic=None, due_at=None,
                  created_at="2025-01-01T10:00:00+05:45")
    client.post("/api/problems", json={"title": "Remove me", "slug": "remove"})
    assert client.post("/api/import", json={"data": bundle, "merge": False}).status_code == 200
    problems = client.get("/api/problems").json()
    assert [p["slug"] for p in problems] == ["restore"]
    assert problems[0]["created_at"] == "2025-01-01T04:15:00"
    assert problems[0]["due_at"] is None
    assert db.query(Solve).one().client_event_id == "event-123"
    assert client.post("/api/capture/manual", json={"slug": "restore", "client_event_id": "event-123"}).status_code == 200
    assert db.query(Solve).count() == 1
    assert client.post("/api/import", json={"data": bundle}).status_code == 200
    assert db.query(Solve).count() == 1


def test_merge_clears_notes_tags_and_null_dates(client):
    client.post("/api/problems", json={"title": "Merge", "slug": "merge", "notes": "old", "tags": ["old"]})
    bundle = client.get("/api/export").json()
    bundle["problems"][0].update(notes="", tags=[], due_at=None, topic=None)
    assert client.post("/api/import", json={"data": bundle}).status_code == 200
    p = client.get("/api/problems").json()[0]
    assert p["notes"] == "" and p["tags"] == [] and p["due_at"] is None


def test_csv_does_not_execute_formula_cells(client):
    client.post("/api/problems", json={"title": "=SUM(1,2)", "slug": "formula", "notes": "@command"})
    rows = list(csv.reader(io.StringIO(client.get("/api/export/csv").text)))
    assert rows[1][0] == "'=SUM(1,2)"
    assert rows[1][-1] == "'@command"


@pytest.mark.parametrize("route", ["/api/problems", "/api/reviews/queue", "/api/reviews/history", "/api/search"])
def test_negative_limits_are_rejected(client, route):
    assert client.get(route, params={"limit": -1}).status_code == 422


def test_negative_solve_and_review_durations_are_rejected(client):
    assert client.post("/api/capture/manual", json={"slug": "x", "hints_used": -1}).status_code == 422
    p = client.post("/api/problems", json={"title": "x"}).json()
    assert client.post(f"/api/problems/{p['id']}/reviews", json={"rating": 3, "duration_sec": -1}).status_code == 422


def test_replacement_rolls_back_on_write_failure(client, monkeypatch):
    from app.routers import export_import
    client.post("/api/problems", json={"title": "Original", "slug": "original"})
    before = client.get("/api/export").json()
    replacement = {**before, "problems": [{"slug": "replacement"}]}
    def fail(*args):
        raise RuntimeError("simulated storage failure")
    monkeypatch.setattr(export_import, "set_setting", fail)
    with pytest.raises(RuntimeError, match="simulated storage failure"):
        client.post("/api/import", json={"data": replacement, "merge": False})
    assert client.get("/api/export").json()["problems"] == before["problems"]


def test_partial_replacement_cannot_erase_history(client):
    assert client.post("/api/import", json={"data": {"problems": []}, "merge": False}).status_code == 400


def test_startup_rejects_shared_default_token(monkeypatch):
    monkeypatch.setattr(settings, "api_token", "dev-token-change-me")
    with pytest.raises(RuntimeError, match="RECALL_API_TOKEN"):
        with TestClient(app, client=("127.0.0.1", 123)):
            pass


@pytest.mark.parametrize("field,value", [
    ("title", ""), ("title", "t" * 241),
    ("platform", ""), ("platform", "p" * 41),
    ("slug", ""), ("slug", "s" * 241),
])
def test_problem_write_text_validation(client, field, value):
    response = client.post("/api/problems", json={"title": "Title", field: value})
    assert response.status_code == 422
    assert client.get("/api/problems").json() == []


@pytest.mark.parametrize("title", ["", "t" * 241])
def test_problem_update_title_validation(client, title):
    problem = client.post("/api/problems", json={"title": "Original"}).json()
    response = client.patch(f"/api/problems/{problem['id']}", json={"title": title})
    assert response.status_code == 422
    assert client.get(f"/api/problems/{problem['id']}").json()["title"] == "Original"


@pytest.mark.parametrize("route", ["manual", "solve"])
@pytest.mark.parametrize("field,value", [
    ("title", "t" * 241),
    ("platform", ""), ("platform", "p" * 41),
    ("slug", ""), ("slug", "s" * 241),
    ("client_event_id", ""), ("client_event_id", "e" * 65),
])
def test_capture_write_text_validation(client, route, field, value):
    response = client.post(f"/api/capture/{route}", json={"slug": "solve", field: value})
    assert response.status_code == 422
    bundle = client.get("/api/export").json()
    assert bundle["problems"] == bundle["reviews"] == bundle["solves"] == []


@pytest.mark.parametrize("merge", [False, True])
def test_write_boundaries_round_trip_without_text_loss(client, merge):
    fields = {"platform": "p" * 40, "slug": "s" * 240, "title": "t" * 240,
              "url": "https://example.com/" + "u" * 500, "difficulty": "d" * 21,
              "notes": "n\n" * 500, "tags": ["tag" * 200], "topic_name": "Arrays"}
    response = client.post("/api/problems", json=fields)
    assert response.status_code == 201, response.text
    problem_id = response.json()["id"]
    assert client.patch(f"/api/problems/{problem_id}", json={"title": "u" * 240}).status_code == 200
    assert client.post(f"/api/problems/{problem_id}/reviews",
                       json={"rating": 3, "note": "r\n" * 500}).status_code == 200
    for route in ("manual", "solve"):
        response = client.post(f"/api/capture/{route}", json={
            **fields, "slug": route + "s" * (240 - len(route)),
            "client_event_id": route + "e" * (64 - len(route)), "verdict": "v" * 41,
        })
        assert response.status_code == 200, response.text
    response = client.post("/api/capture/manual", json={"slug": "fallback", "title": "",
                                                        "client_event_id": None})
    assert response.status_code == 200
    assert response.json()["title"] == "fallback"
    response = client.post("/api/problems", json={"title": "Generated slug", "slug": None})
    assert response.status_code == 201
    assert response.json()["slug"] == "generated-slug"
    before = client.get("/api/export").json()
    response = client.post("/api/import", json={"data": before, "merge": merge})
    assert response.status_code == 200, response.text
    after = client.get("/api/export").json()
    for section in ("topics", "edges", "problems", "reviews", "solves", "settings"):
        assert after[section] == before[section]


@pytest.mark.parametrize("merge", [False, True])
def test_legacy_text_round_trip_without_truncation(client, db, merge):
    topic = Topic(name="n" * 121)
    db.add(topic)
    db.flush()
    for text in ("", "x" * 1000):
        problem = Problem(title=text, platform=text, slug=text, topic=topic,
                          url=text, difficulty=text, notes=text)
        db.add(problem)
        db.flush()
        db.add(Review(problem_id=problem.id, rating=3, note=text))
        db.add(Solve(problem_id=problem.id, platform=text, slug=text, title=text,
                     difficulty=text, verdict=text, source=text, client_event_id=text))
    db.commit()
    before = client.get("/api/export").json()
    response = client.post("/api/import", json={"data": before, "merge": merge})
    assert response.status_code == 200, response.text
    after = client.get("/api/export").json()
    for section in ("topics", "edges", "problems", "reviews", "solves", "settings"):
        assert after[section] == before[section]
    assert client.post("/api/import", json={"data": before}).status_code == 200
    assert len(client.get("/api/export").json()["solves"]) == 2


@pytest.mark.parametrize("section,count", [
    ("topics", 10001), ("edges", 50001), ("problems", 50001),
    ("reviews", 200001), ("solves", 200001),
])
def test_backup_accepts_collections_beyond_former_restore_only_limits(section, count):
    records = {
        "topics": lambda i: {"name": str(i)},
        "edges": lambda i: {"from": str(i), "to": str(i + 1)},
        "problems": lambda i: {"slug": str(i)},
        "reviews": lambda i: {"problem_platform": "manual", "problem_slug": "card",
                              "rating": 3, "created_at": datetime(2026, 1, 1)},
        "solves": lambda i: {"slug": "card", "created_at": datetime(2026, 1, 1)},
    }
    backup = Backup.model_validate({"problems": [], section: [records[section](i) for i in range(count)]})
    assert len(getattr(backup, section)) == count


@pytest.mark.parametrize("merge", [False, True])
@pytest.mark.parametrize("reference", [
    {"problem_slug": "missing"}, {"problem_platform": "another-platform"},
])
def test_dangling_reviews_are_rejected_before_mutation(client, monkeypatch, merge, reference):
    from sqlalchemy.orm import Query

    assert client.post("/api/capture/manual", json={"slug": "keep"}).status_code == 200
    before = client.get("/api/export").json()
    invalid = {**before, "reviews": [{**before["reviews"][0], **reference}]}

    def fail_delete(*args, **kwargs):
        pytest.fail("A dangling review must be rejected before deleting records")

    monkeypatch.setattr(Query, "delete", fail_delete)
    response = client.post("/api/import", json={"data": invalid, "merge": merge})
    assert response.status_code == 400
    assert "Review references missing problem" in response.json()["detail"]
    after = client.get("/api/export").json()
    for section in ("topics", "edges", "problems", "reviews", "solves", "settings"):
        assert after[section] == before[section]


@pytest.mark.parametrize("merge", [False, True])
def test_only_merge_can_link_reviews_to_existing_problems(client, merge):
    assert client.post("/api/capture/manual", json={"slug": "existing"}).status_code == 200
    bundle = client.get("/api/export").json()
    bundle["problems"] = []
    response = client.post("/api/import", json={"data": bundle, "merge": merge})
    assert response.status_code == (200 if merge else 400)
    after = client.get("/api/export").json()
    assert len(after["problems"]) == len(after["reviews"]) == len(after["solves"]) == 1


def test_import_preserves_intentionally_unlinked_solves(client, db):
    bundle = client.get("/api/export").json()
    bundle["solves"] = [{"slug": "orphan", "created_at": "2026-01-01T00:00:00Z"}]
    response = client.post("/api/import", json={"data": bundle, "merge": False})
    assert response.status_code == 200, response.text
    assert db.query(Solve).one().problem_id is None
